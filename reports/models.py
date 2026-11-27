"""Reports: a member telling the Hub's moderators about something.

A Report is feedback or an abuse report, generic over its target (a forum post or comment
now; more kinds later, see reports.targets). A member reports a given target once: the
database refuses a second abuse report by the same member on the same target, so two
requests at once can't both get in. Reports are deleted with their target, and kept (with
no reporter) when the reporter's account is deleted, so moderation can still act on them.
Phase 15's moderation acts on them.

A BugReport is a bug report or feedback about a member's project or the Axcenity Engine,
with a status that changes only along `TRANSITIONS`, an assignee, and a timeline of
BugActivity (comments, status changes, assignments). Who may see and handle one is
reports.bugs's.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models
from django.urls import reverse

from . import strings


class Report(models.Model):
    DETAILS_MAX = 1_000

    class Kind(models.TextChoices):
        ABUSE = "abuse", "Abuse"
        FEEDBACK = "feedback", "Feedback"

    class Reason(models.TextChoices):
        SPAM = "spam", strings.REASON_SPAM
        ABUSE = "abuse", strings.REASON_ABUSE
        OFF_TOPIC = "off_topic", strings.REASON_OFF_TOPIC
        OTHER = "other", strings.REASON_OTHER

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reports_made",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.ABUSE)
    reason = models.CharField(max_length=10, choices=Reason.choices)
    details = models.TextField(
        max_length=DETAILS_MAX, blank=True, validators=[MaxLengthValidator(DETAILS_MAX)]
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created", "-pk"]
        indexes = [models.Index(fields=["content_type", "object_id"], name="report_target")]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "content_type", "object_id"],
                condition=models.Q(kind="abuse"),
                name="one_abuse_report_per_member_per_target",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} report: {self.get_reason_display()}"


# ---------- Bug reports and feedback ----------


class BugStatus(models.TextChoices):
    """Where a bug report is in its workflow. Changes follow `TRANSITIONS` only."""

    NEW = "new", "New"
    CONFIRMED = "confirmed", "Confirmed"
    IN_PROGRESS = "in_progress", "In progress"
    RESOLVED = "resolved", "Resolved"
    WONT_FIX = "wont_fix", "Won't fix"
    CLOSED = "closed", "Closed"


# The permitted-transition table: each status and the statuses it may change to. Anything
# else (the status it already has included) is refused. Closed is final.
TRANSITIONS: dict[BugStatus, frozenset[BugStatus]] = {
    BugStatus.NEW: frozenset({BugStatus.CONFIRMED, BugStatus.WONT_FIX}),
    BugStatus.CONFIRMED: frozenset({BugStatus.IN_PROGRESS, BugStatus.WONT_FIX}),
    BugStatus.IN_PROGRESS: frozenset({BugStatus.RESOLVED, BugStatus.CONFIRMED}),
    BugStatus.RESOLVED: frozenset({BugStatus.CLOSED, BugStatus.IN_PROGRESS}),
    BugStatus.WONT_FIX: frozenset({BugStatus.CLOSED, BugStatus.NEW}),
    BugStatus.CLOSED: frozenset(),
}

# Statuses still waiting on someone: the list's "Open" filter.
OPEN_STATUSES = frozenset({BugStatus.NEW, BugStatus.CONFIRMED, BugStatus.IN_PROGRESS})


def allows_transition(current: str, new: str) -> bool:
    """Whether a report in status `current` may move to `new` (`TRANSITIONS`)."""
    try:
        return BugStatus(new) in TRANSITIONS[BugStatus(current)]
    except ValueError:
        return False


# An engine version as its releases name it: 0.4, 0.4.0, 0.4.0-alpha.2, v0.4.0.
ENGINE_VERSION = RegexValidator(
    r"\Av?\d{1,4}\.\d{1,4}(\.\d{1,4})?(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?\Z",
    strings.BUG_VERSION_INVALID,
    code="invalid_version",
)


class BugReportQuerySet(models.QuerySet):
    """Who may see and handle bug reports (docs/architecture/reports.md#bug-reports)."""

    def _handled_by(self, user) -> models.Q:
        """The reports of projects where `user`'s role allows Action.MANAGE_REPORTS."""
        from projects.models import Action, Project

        return models.Q(
            project__in=Project.objects.allowing(user, Action.MANAGE_REPORTS).values("pk")
        )

    def visible_to(self, user) -> "BugReportQuerySet":
        """The reports `user` may open, find and comment on: every report for admins (staff);
        otherwise the ones they sent and the ones their projects' roles let them handle.
        Engine reports (no project) are their submitter's and admins' only. None for a
        signed-out visitor."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        if user.is_staff:
            return self.all()
        return self.filter(models.Q(submitter=user) | self._handled_by(user))

    def managed_by(self, user) -> "BugReportQuerySet":
        """The reports `user` may change the status of and assign: every report for admins
        (staff), and a project's reports for its Owners and Maintainers. Sending a report
        never makes it yours to handle. None for a signed-out visitor."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        if user.is_staff:
            return self.all()
        return self.filter(self._handled_by(user))


class BugReport(models.Model):
    """A bug report or feedback, about a member's project or the Axcenity Engine itself
    (`project` empty).

    Who may see it and handle it is reports.bugs's: the submitter, the project's Owners and
    Maintainers (Action.MANAGE_REPORTS), and admins (staff); an engine report is the
    submitter's and admins' only. Its status changes only along `TRANSITIONS`.
    """

    TITLE_MAX = 120
    TEXT_MAX = 5_000
    EXPECTED_MAX = 2_000
    VERSION_MAX = 40

    class Kind(models.TextChoices):
        BUG = "bug", strings.KIND_BUG
        FEEDBACK = "feedback", strings.KIND_FEEDBACK

    class Platform(models.TextChoices):
        WINDOWS = "windows", "Windows"
        MACOS = "macos", "macOS"
        LINUX = "linux", "Linux"
        OTHER = "other", strings.PLATFORM_OTHER

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bug_reports",
        help_text="Empty: a report about the Axcenity Engine itself, for admins.",
    )
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="bug_reports_submitted",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.BUG)
    title = models.CharField(max_length=TITLE_MAX)
    description = models.TextField(max_length=TEXT_MAX, validators=[MaxLengthValidator(TEXT_MAX)])
    steps = models.TextField(
        max_length=TEXT_MAX, blank=True, validators=[MaxLengthValidator(TEXT_MAX)]
    )
    expected = models.TextField(
        max_length=EXPECTED_MAX, blank=True, validators=[MaxLengthValidator(EXPECTED_MAX)]
    )
    engine_version = models.CharField(
        max_length=VERSION_MAX, blank=True, validators=[ENGINE_VERSION]
    )
    platform = models.CharField(max_length=10, choices=Platform.choices, blank=True)
    status = models.CharField(max_length=20, choices=BugStatus.choices, default=BugStatus.NEW)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bug_reports_assigned",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = BugReportQuerySet.as_manager()

    class Meta:
        ordering = ["-created", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=BugStatus.values), name="reports_bug_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["bug", "feedback"]), name="reports_bug_kind_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.title}"

    def get_absolute_url(self) -> str:
        return reverse("reports:bug_detail", kwargs={"pk": self.pk})

    @property
    def about_label(self) -> str:
        """What it's about, as the pages name it: its project, or the Axcenity Engine."""
        return self.project.name if self.project_id else strings.ENGINE

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def next_statuses(self) -> list[BugStatus]:
        """The statuses this report may change to, in the workflow's order."""
        allowed = TRANSITIONS[BugStatus(self.status)]
        return [status for status in BugStatus if status in allowed]

    def clean(self) -> None:
        """Every report needs a title and a description; a bug also needs the steps to
        reproduce it, the engine version and the platform. Text is trimmed first, so
        whitespace alone counts as empty. The errors' code is "missing", not "required": a
        form would swap a "required" error for its field's generic message."""
        for name in ("title", "description", "steps", "expected", "engine_version"):
            setattr(self, name, (getattr(self, name) or "").strip())
        self.title = " ".join(self.title.split())
        errors = {}
        if not self.title:
            errors["title"] = ValidationError(strings.BUG_TITLE_REQUIRED, "missing")
        if not self.description:
            errors["description"] = ValidationError(strings.BUG_DESCRIPTION_REQUIRED, "missing")
        if self.kind == self.Kind.BUG:
            if not self.steps:
                errors["steps"] = ValidationError(strings.BUG_STEPS_REQUIRED, "missing")
            if not self.engine_version:
                errors["engine_version"] = ValidationError(strings.BUG_VERSION_REQUIRED, "missing")
            if not self.platform:
                errors["platform"] = ValidationError(strings.BUG_PLATFORM_REQUIRED, "missing")
        if errors:
            raise ValidationError(errors)


class BugActivity(models.Model):
    """One entry in a bug report's timeline: a comment, a status change or an assignment.
    Written only by reports.bugs; never edited."""

    class Kind(models.TextChoices):
        COMMENT = "comment", "Comment"
        STATUS = "status", "Status"
        ASSIGNED = "assigned", "Assigned"

    COMMENT_MAX = 2_000

    report = models.ForeignKey(BugReport, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    body = models.TextField(
        max_length=COMMENT_MAX, blank=True, validators=[MaxLengthValidator(COMMENT_MAX)]
    )
    old_status = models.CharField(max_length=20, choices=BugStatus.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=BugStatus.choices, blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="For an assignment: who it went to (empty: unassigned).",
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created", "pk"]
        verbose_name_plural = "bug activity"

    def __str__(self) -> str:
        return f"{self.get_kind_display()} on {self.report}"
