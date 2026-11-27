"""Bug reports and feedback: the rules every way in goes through.

- **Submitting** needs a verified member (accounts.access). A report is about the Axcenity
  Engine (no project: any verified member) or a project the member belongs to, in any role.
  A member sends at most `REPORT_LIMIT` reports within `REPORT_WINDOW`, counted under their
  creation lock (accounts.limits), so simultaneous requests can't slip past it.
- **Seeing** a report is for its submitter, its project's Owners and Maintainers
  (`Action.MANAGE_REPORTS`) and admins (staff); an engine report is the submitter's and
  admins' only. Everyone else gets a 404 (`BugReport.objects.visible_to`).
- **Handling** it (changing its status, assigning it) is for the Owners, Maintainers and
  admins (`BugReport.objects.managed_by`); the submitter can't. Statuses change only along
  `models.TRANSITIONS`. Only someone who handles reports can be assigned one: a project's
  Owners and Maintainers for a project report, admins for an engine report.
- **Commenting** is for anyone who can see the report, verified.

Every change writes a BugActivity entry in the same transaction, which re-reads the report
under its lock, so two people acting at once can't both move it from the same status.
Refusals: `EmailNotVerified`, `LimitReached`, `ValidationError`, `TransitionRefused` and
`AssigneeRefused` (their messages are for the page), and `PermissionDenied` for someone who
can't act at all (the views 404 before that).
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from accounts.access import ensure_can_contribute
from accounts.limits import LimitReached, lock_member, next_allowed, wait_words
from projects.models import PERMISSIONS, Action, Project

from . import strings
from .models import BugActivity, BugReport, BugStatus, allows_transition

# The reporting limit: a database count within a rolling window (accounts.limits).
REPORT_LIMIT, REPORT_WINDOW = 5, timedelta(days=1)


class TransitionRefused(Exception):
    """A status change the permitted-transition table doesn't allow; `str()` is for the page."""


class AssigneeRefused(Exception):
    """An assignee who doesn't handle the report's project; `str()` is for the page."""


def is_admin(user) -> bool:
    """Whether `user` is a Hub admin, who sees and handles every report: staff."""
    return bool(getattr(user, "is_authenticated", False) and user.is_staff)


def can_manage(user, report: BugReport) -> bool:
    """Whether `user` may change `report`'s status and assignee."""
    return BugReport.objects.managed_by(user).filter(pk=report.pk).exists()


def limit_message(user, *, now: datetime | None = None) -> str:
    """The limit's message when `user` can't send a report now, "" otherwise (for the form's
    notice; `submit` decides)."""
    now = now or timezone.now()
    until = next_allowed(
        BugReport.objects.filter(submitter=user), limit=REPORT_LIMIT, window=REPORT_WINDOW, now=now
    )
    if until is None:
        return ""
    return strings.BUG_LIMIT_REACHED.format(limit=REPORT_LIMIT, wait=wait_words(until, now))


def reportable_projects(user) -> QuerySet:
    """The projects `user` may send a report about: those they're a member of."""
    return Project.objects.visible_to(user).order_by("name")


def submit(
    submitter,
    *,
    project: Project | None,
    kind: str,
    title: str,
    description: str,
    steps: str = "",
    expected: str = "",
    engine_version: str = "",
    platform: str = "",
    now: datetime | None = None,
) -> BugReport:
    """Send a bug report or feedback about `project` (None: the Axcenity Engine).

    Raises EmailNotVerified for an unverified member, PermissionDenied for a project they
    aren't a member of, ValidationError for a missing or invalid field, and LimitReached when
    they've sent REPORT_LIMIT reports within REPORT_WINDOW. `now` is for tests.
    """
    ensure_can_contribute(submitter)
    if project is not None and project.role_of(submitter) is None:
        raise PermissionDenied("Only a project's members may report about it.")
    report = BugReport(
        project=project,
        submitter=submitter,
        kind=kind,
        title=title,
        description=description,
        steps=steps,
        expected=expected,
        engine_version=engine_version,
        platform=platform,
    )
    report.full_clean()
    now = now or timezone.now()
    with transaction.atomic():
        lock_member(submitter)
        until = next_allowed(
            BugReport.objects.filter(submitter=submitter),
            limit=REPORT_LIMIT,
            window=REPORT_WINDOW,
            now=now,
        )
        if until is not None:
            raise LimitReached(
                strings.BUG_LIMIT_REACHED.format(limit=REPORT_LIMIT, wait=wait_words(until, now))
            )
        report.save()
    return report


def _locked(user, report: BugReport, queryset: QuerySet) -> BugReport:
    """`report` re-read under its row lock, if `queryset` (what `user` may act on) holds it;
    PermissionDenied otherwise."""
    found = queryset.select_for_update().filter(pk=report.pk).first()
    if found is None:
        raise PermissionDenied("This member can't act on this report.")
    return found


def change_status(user, report: BugReport, status: str) -> BugReport:
    """Move `report` to `status` as `user`, who must handle it, recording the change.

    Raises PermissionDenied when `user` can't handle the report, and TransitionRefused for a
    change the permitted-transition table (`models.TRANSITIONS`) doesn't allow: an unknown
    status, the one it has already, or anything from Closed. The table is checked against
    the report as it stands under its lock, so two changes at once can't both apply.
    """
    with transaction.atomic():
        report = _locked(user, report, BugReport.objects.managed_by(user))
        old = report.status
        if not allows_transition(old, status):
            raise TransitionRefused(
                strings.BUG_STATUS_REFUSED.format(old=_label(old), new=_label(status))
                if status in BugStatus.values
                else strings.BUG_STATUS_UNKNOWN
            )
        report.status = status
        report.save(update_fields=["status", "updated"])
        BugActivity.objects.create(
            report=report,
            actor=user,
            kind=BugActivity.Kind.STATUS,
            old_status=old,
            new_status=status,
        )
    return report


def _label(status: str) -> str:
    return BugStatus(status).label.lower()


def assignable(report: BugReport) -> QuerySet:
    """Who may be assigned `report`: its project's Owners and Maintainers, or admins for an
    engine report. Active accounts only, by username."""
    people = get_user_model().objects.filter(is_active=True)
    if report.project_id is None:
        people = people.filter(is_staff=True)
    else:
        people = people.filter(
            project_memberships__project_id=report.project_id,
            project_memberships__role__in=PERMISSIONS[Action.MANAGE_REPORTS],
        )
    return people.order_by("username")


def assign(user, report: BugReport, assignee) -> BugReport:
    """Assign `report` to `assignee` (None: nobody) as `user`, who must handle it.

    Raises PermissionDenied when `user` can't handle the report and AssigneeRefused when
    `assignee` doesn't handle its project. Assigning it to whoever has it already changes
    nothing and records nothing.
    """
    with transaction.atomic():
        report = _locked(user, report, BugReport.objects.managed_by(user))
        if assignee is not None and not assignable(report).filter(pk=assignee.pk).exists():
            raise AssigneeRefused(strings.BUG_ASSIGNEE_REFUSED)
        new_pk = assignee.pk if assignee is not None else None
        if report.assignee_id == new_pk:
            return report
        report.assignee = assignee
        report.save(update_fields=["assignee", "updated"])
        BugActivity.objects.create(
            report=report, actor=user, kind=BugActivity.Kind.ASSIGNED, assignee=assignee
        )
    return report


def comment(user, report: BugReport, body: str) -> BugActivity:
    """Comment on `report` as `user`, who must be able to see it.

    Raises EmailNotVerified for an unverified member, PermissionDenied for someone who can't
    see the report, and ValidationError for an empty or over-long comment.
    """
    ensure_can_contribute(user)
    body = (body or "").strip()
    entry = BugActivity(report=report, actor=user, kind=BugActivity.Kind.COMMENT, body=body)
    if not body:
        raise ValidationError({"body": ValidationError(strings.BUG_COMMENT_REQUIRED, "required")})
    entry.full_clean(exclude=["report", "actor"])
    with transaction.atomic():
        report = _locked(user, report, BugReport.objects.visible_to(user))
        entry.report = report
        entry.save()
        # The report moves up "Recently updated" with its conversation.
        report.save(update_fields=["updated"])
    return entry


def release_assignments(user, project: Project) -> int:
    """Unassign `user` from `project`'s reports, when they stop handling its reports (a
    role that can't, removed, or gone). Returns how many were unassigned. Called by
    projects.teams inside its transaction."""
    return BugReport.objects.filter(project=project, assignee=user).update(
        assignee=None, updated=timezone.now()
    )
