"""A project's team: invitations, roles and leaving.

Every change runs in one transaction that first locks the project's row (SELECT … FOR UPDATE
on PostgreSQL; SQLite's IMMEDIATE transactions serialize instead), then re-reads the acting
member's role and the membership or invitation it changes. So two Owners acting at the same
moment can't both act on what the other has just changed. Locks are always taken in the same
order, the project and then a member (accounts.limits.lock_member, for the ownership limit),
so concurrent changes queue rather than deadlock.

- Owners invite members by username (case-insensitive), as Owner, Maintainer or Viewer, up to
  INVITE_BATCH_MAX at once (invite_many: each invitation its own transaction, so one refusal
  doesn't stop the others). One invitation per member and project; never to a member
  already in the team.
- Only the invitee accepts or declines; Owners can cancel. Anyone else gets a 404.
- Becoming an Owner (accepting an Owner invitation, or being made one) counts against
  Project.LIMIT_PER_OWNER. At the limit it's refused, and nothing changes: the invitation
  stays pending, and the member keeps their role.

A project always keeps at least one Owner: stepping down, removing or leaving as its last
Owner is refused (TeamError), counted under the project's lock so two Owners stepping down
together can't both go. (Deleting the account of a project's last Owner is refused too:
models.protect_last_owner.)

Refusals: TeamError (the Hub's rules; its message is for the page), LimitReached, and the
model's DoesNotExist for anything the member can't see (the views' 404).
"""

import re
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Lower

from accounts.access import ensure_can_contribute
from accounts.limits import LimitReached, lock_member

from . import strings
from .models import Action, Project, ProjectInvitation, ProjectMembership, Role, allows
from .services import owned_count


class TeamError(Exception):
    """A team change refused by the Hub's rules; `str()` is the message for the page."""


def _role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError:
        raise TeamError(strings.ROLE_INVALID) from None


def _lock(project_pk: int) -> Project:
    """The project's row, locked until the transaction ends (Project.DoesNotExist if gone)."""
    return Project.objects.select_for_update().get(pk=project_pk)


def _acting(user, project: Project, action: Action) -> ProjectMembership:
    """`user`'s membership, if their role (read now, under the lock) allows `action`."""
    membership = ProjectMembership.objects.filter(project=project, user=user).first()
    if membership is None or not allows(membership.role, action):
        raise Project.DoesNotExist
    return membership


def _ensure_room_to_own(user, message: str) -> None:
    """Refuse if `user` already owns the most projects one member can (under their lock)."""
    lock_member(user)
    if owned_count(user) >= Project.LIMIT_PER_OWNER:
        raise LimitReached(message)


# Finding someone to invite: at least SEARCH_MIN characters, at most SEARCH_LIMIT people.
SEARCH_MIN = 2
SEARCH_MAX = 150  # a username's longest
SEARCH_LIMIT = 6


@dataclass(frozen=True)
class Candidate:
    """A member an Owner might invite, and whether they can: "available", "member" (already
    in the team), "invited" (has a pending invitation) or "you"."""

    user: object
    state: str

    @property
    def available(self) -> bool:
        return self.state == "available"


def find_members(owner, project: Project, query: str) -> list[Candidate]:
    """Active members whose username or display name starts with `query` (any case), for an
    Owner of `project` choosing whom to invite; an exact username first, then by username.

    Raises Project.DoesNotExist unless `owner` may manage the team. A query shorter than
    SEARCH_MIN or longer than SEARCH_MAX finds no one. Emails are never matched or returned.
    """
    _acting(owner, project, Action.MANAGE_MEMBERS)
    query = (query or "").strip()
    if not SEARCH_MIN <= len(query) <= SEARCH_MAX:
        return []
    people = (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(username__istartswith=query) | Q(profile__display_name__istartswith=query))
        .select_related("profile")
        .annotate(
            exact=Case(
                When(username__iexact=query, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("exact", Lower("username"))[:SEARCH_LIMIT]
    )
    members = set(ProjectMembership.objects.filter(project=project).values_list("user", flat=True))
    invited = set(
        ProjectInvitation.objects.filter(project=project).values_list("invitee", flat=True)
    )
    candidates = []
    for person in people:
        if person.pk == owner.pk:
            state = "you"
        elif person.pk in members:
            state = "member"
        elif person.pk in invited:
            state = "invited"
        else:
            state = "available"
        candidates.append(Candidate(person, state))
    return candidates


def invite(owner, project: Project, username: str, role: str) -> ProjectInvitation:
    """Invite the member called `username` to `project` as `role` (an Owner's action)."""
    ensure_can_contribute(owner)
    role = _role(role)
    username = (username or "").strip()
    with transaction.atomic():
        project = _lock(project.pk)
        _acting(owner, project, Action.MANAGE_MEMBERS)
        invitee = get_user_model().objects.filter(username__iexact=username, is_active=True)
        invitee = invitee.first() if username else None
        if invitee is None:
            raise TeamError(strings.NO_SUCH_MEMBER.format(username=username))
        if invitee.pk == owner.pk:
            raise TeamError(strings.INVITE_YOURSELF)
        if ProjectMembership.objects.filter(project=project, user=invitee).exists():
            raise TeamError(strings.ALREADY_MEMBER.format(username=invitee.username))
        if ProjectInvitation.objects.filter(project=project, invitee=invitee).exists():
            raise TeamError(strings.ALREADY_INVITED.format(username=invitee.username))
        try:
            with transaction.atomic():
                return ProjectInvitation.objects.create(
                    project=project, invitee=invitee, role=role, invited_by=owner
                )
        except IntegrityError:  # the unique index: invited a moment ago
            raise TeamError(strings.ALREADY_INVITED.format(username=invitee.username)) from None


INVITE_BATCH_MAX = 10


def parse_usernames(values: list[str]) -> list[str]:
    """The usernames in what the invite form sent: each value may hold several, separated by
    commas or spaces (usernames have neither). Blanks dropped, repeats (in any case) once,
    in the order given."""
    seen, names = set(), []
    for value in values:
        for name in re.split(r"[\s,]+", value or ""):
            if name and name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
    return names


@dataclass
class InviteResult:
    """What invite_many did: the usernames invited, and each refused one with its reason."""

    invited: list[str] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)


def invite_many(owner, project: Project, usernames: list[str], role: str) -> InviteResult:
    """Invite each member in `usernames` to `project` as `role` (an Owner's action).

    Each invitation is its own transaction (invite), so a refusal (no such member, already
    in the team or invited) is reported and the others still go. Raises TeamError, inviting
    no one, for no usernames, more than INVITE_BATCH_MAX, or an invalid role; and
    EmailNotVerified or Project.DoesNotExist like invite.
    """
    ensure_can_contribute(owner)
    role = _role(role)
    if not usernames:
        raise TeamError(strings.INVITE_INVALID)
    if len(usernames) > INVITE_BATCH_MAX:
        raise TeamError(strings.INVITE_TOO_MANY.format(limit=INVITE_BATCH_MAX))
    result = InviteResult()
    for username in usernames:
        try:
            invitation = invite(owner, project, username, role)
        except TeamError as error:
            result.refused.append((username, str(error)))
        else:
            result.invited.append(invitation.invitee.username)
    return result


def _pending(user, invitation_pk: int) -> ProjectInvitation:
    """`user`'s own invitation, or ProjectInvitation.DoesNotExist (it's someone else's, or
    already answered or cancelled)."""
    return ProjectInvitation.objects.select_for_update().get(pk=invitation_pk, invitee=user)


def accept(user, invitation_pk: int) -> ProjectMembership:
    """Join the project `user` was invited to, in the invitation's role (the invitee only)."""
    with transaction.atomic():
        # Read without a lock to find the project, so the locks come in the usual order.
        project_pk = ProjectInvitation.objects.get(pk=invitation_pk, invitee=user).project_id
        _lock(project_pk)
        invitation = _pending(user, invitation_pk)  # still there, now that the project is held
        already = ProjectMembership.objects.filter(project_id=project_pk, user=user).exists()
        if already:
            # Joined another way since: the invitation has nothing left to do.
            invitation.delete()
        else:
            if invitation.role == Role.OWNER:
                _ensure_room_to_own(user, strings.LIMIT_REACHED)
            membership = ProjectMembership.objects.create(
                project_id=project_pk, user=user, role=invitation.role
            )
            invitation.delete()
    if already:  # raised after the transaction, so the invitation's deletion stands
        raise TeamError(strings.INVITATION_GONE)
    return membership


def decline(user, invitation_pk: int) -> None:
    """Turn down an invitation (the invitee only)."""
    with transaction.atomic():
        project_pk = ProjectInvitation.objects.get(pk=invitation_pk, invitee=user).project_id
        _lock(project_pk)
        _pending(user, invitation_pk).delete()


def cancel(owner, project: Project, invitation_pk: int) -> None:
    """Withdraw a pending invitation to `project` (an Owner's action)."""
    with transaction.atomic():
        project = _lock(project.pk)
        _acting(owner, project, Action.MANAGE_MEMBERS)
        ProjectInvitation.objects.get(pk=invitation_pk, project=project).delete()


def _member(project: Project, membership_pk: int) -> ProjectMembership:
    return ProjectMembership.objects.select_related("user").get(pk=membership_pk, project=project)


def _keep_an_owner(member: ProjectMembership) -> None:
    """Refuse a change that takes away the project's last Owner (counted under its lock)."""
    if member.role != Role.OWNER:
        return
    others = ProjectMembership.objects.filter(project_id=member.project_id, role=Role.OWNER)
    if not others.exclude(pk=member.pk).exists():
        raise TeamError(strings.LAST_OWNER)


def change_role(owner, project: Project, membership_pk: int, role: str) -> ProjectMembership:
    """Give a member of `project` another role (an Owner's action, their own role included).

    Making someone an Owner is refused when they already own Project.LIMIT_PER_OWNER
    projects; they keep the role they had.
    """
    role = _role(role)
    with transaction.atomic():
        project = _lock(project.pk)
        _acting(owner, project, Action.MANAGE_MEMBERS)
        member = _member(project, membership_pk)
        if member.role == role:
            return member
        if role == Role.OWNER:
            _ensure_room_to_own(
                member.user, strings.MEMBER_AT_LIMIT.format(username=member.user.username)
            )
        else:
            _keep_an_owner(member)
        member.role = role
        member.save(update_fields=["role"])
    return member


def remove(owner, project: Project, membership_pk: int) -> None:
    """Take a member out of `project` (an Owner's action)."""
    with transaction.atomic():
        project = _lock(project.pk)
        _acting(owner, project, Action.MANAGE_MEMBERS)
        member = _member(project, membership_pk)
        _keep_an_owner(member)
        member.delete()


def leave(user, project: Project) -> None:
    """Leave `project` (any member)."""
    with transaction.atomic():
        project = _lock(project.pk)
        member = _acting(user, project, Action.VIEW)
        _keep_an_owner(member)
        member.delete()
