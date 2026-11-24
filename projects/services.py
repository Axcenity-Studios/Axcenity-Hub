"""Project workflows that span models: creating a project under the per-member limit, and
linking, refreshing and unlinking its GitHub repository.

Every repository-dependent action (linking, refreshing, showing the webhook's secret) first
resolves the member's current permission with GitHub (projects.github.require_permission)
and raises RepositoryError when it isn't established. Unlinking and deleting are the Hub's
own business and never ask GitHub, so an owner who has lost access can still clean up.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from accounts.access import ensure_can_contribute
from accounts.limits import LimitReached, lock_member

from . import github, strings, webhooks
from .github import Permission, Reason
from .models import Project, RepositoryLink


class RepositoryError(Exception):
    """A repository action was refused; `str()` is the message for the page.

    `reason` is the projects.github.Reason when GitHub's answer refused it (None for the
    Hub's own rules), and `retry_at` when to try again after a rate limit.
    """

    def __init__(self, message: str, reason: Reason | None = None, retry_at=None):
        super().__init__(message)
        self.reason = reason
        self.retry_at = retry_at


@dataclass(frozen=True)
class WebhookSettings:
    """What the owner enters in the repository's webhook settings on GitHub."""

    path: str
    secret: str


def create_project(owner, *, name: str, description: str = "") -> Project:
    """Create a project owned by `owner`.

    Raises accounts.access.EmailNotVerified for an unverified member,
    accounts.limits.LimitReached when they already own Project.LIMIT_PER_OWNER projects
    (counted under their creation lock, so concurrent requests can't exceed it), and
    django.core.exceptions.ValidationError for a name that's unusable or taken.
    """
    ensure_can_contribute(owner)
    try:
        with transaction.atomic():
            # Serialize this member's creations, so concurrent requests can't all count four.
            lock_member(owner)
            if Project.objects.filter(owner=owner).count() >= Project.LIMIT_PER_OWNER:
                raise LimitReached(strings.LIMIT_REACHED)
            project = Project(owner=owner, name=name, description=description)
            project.full_clean()
            project.save()
    except IntegrityError:  # another member took the name a moment ago
        raise ValidationError({"name": strings.NAME_TAKEN}) from None
    return project


def _ensure_owner(user, project: Project) -> None:
    if project.owner_id != getattr(user, "pk", None):
        raise Project.DoesNotExist  # the views' 404: never say whose it is


def _require(user, full_name: str, needed: Permission, now, *, fresh: bool = False):
    access = github.require_permission(user, full_name, needed, now=now, fresh=fresh)
    if not access.allowed:
        raise RepositoryError(strings.REFUSED[access.reason], access.reason, access.retry_at)
    return access.repository


def _apply(link: RepositoryLink, repository: github.Repository) -> None:
    link.full_name = repository.full_name
    link.html_url = repository.html_url
    link.description = repository.description
    link.default_branch = repository.default_branch
    link.private = repository.private
    link.archived = repository.archived
    link.pushed_at = repository.pushed_at


def link_repository(user, project: Project, text: str, *, now: datetime | None = None):
    """Link the GitHub repository `text` (owner/name or its URL) to `user`'s project.

    Needs admin permission on the repository, as GitHub reports it now. A repository is
    linked to one Hub project at most, and a project to one repository.
    """
    now = now or datetime.now(UTC)
    ensure_can_contribute(user)
    _ensure_owner(user, project)
    if RepositoryLink.objects.filter(project=project).exists():
        raise RepositoryError(strings.PROJECT_HAS_REPOSITORY)
    full_name = github.normalize_full_name(text)
    if not full_name:
        raise RepositoryError(strings.REPOSITORY_NAME_INVALID)
    repository = _require(user, full_name, Permission.ADMIN, now, fresh=True)
    if RepositoryLink.objects.filter(github_id=repository.github_id).exists():
        raise RepositoryError(strings.REPOSITORY_TAKEN)
    link = RepositoryLink(
        project=project, github_id=repository.github_id, linked_by=user, fetched_at=now
    )
    _apply(link, repository)
    try:
        with transaction.atomic():
            link.save()
    except IntegrityError:  # linked by someone else a moment ago
        raise RepositoryError(strings.REPOSITORY_TAKEN) from None
    return link


def refresh_repository(user, project: Project, *, now: datetime | None = None):
    """Fetch the linked repository's details from GitHub again (needs read permission)."""
    now = now or datetime.now(UTC)
    _ensure_owner(user, project)
    link = RepositoryLink.objects.filter(project=project).first()
    if link is None:
        raise RepositoryError(strings.NO_REPOSITORY)
    repository = _require(user, link.full_name, Permission.PULL, now, fresh=True)
    if repository.github_id != link.github_id:
        # The name now belongs to another repository (deleted and recreated, or renamed).
        raise RepositoryError(strings.REPOSITORY_REPLACED)
    _apply(link, repository)
    link.fetched_at = now
    link.save()
    return link


def webhook_settings(user, project: Project, *, now: datetime | None = None) -> WebhookSettings:
    """The linked repository's webhook URL and secret, for an admin of it on GitHub."""
    now = now or datetime.now(UTC)
    _ensure_owner(user, project)
    link = RepositoryLink.objects.filter(project=project).first()
    if link is None:
        raise RepositoryError(strings.NO_REPOSITORY)
    if not webhooks.webhooks_on():
        raise RepositoryError(strings.WEBHOOKS_OFF)
    _require(user, link.full_name, Permission.ADMIN, now)
    # The setup checklist's third step: the owner has the values to add on GitHub.
    RepositoryLink.objects.filter(pk=link.pk).update(webhook_shown_at=now)
    return WebhookSettings(webhooks.payload_path(link.hook_id), webhooks.secret_for(link.hook_id))


def unlink_repository(user, project: Project) -> None:
    """Unlink the project's repository (the Hub's own record; GitHub isn't asked)."""
    _ensure_owner(user, project)
    RepositoryLink.objects.filter(project=project).delete()
