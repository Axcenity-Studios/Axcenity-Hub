"""Reports: a member telling the Hub's moderators about something.

A Report is feedback or an abuse report, generic over its target (a forum post or comment
now; more kinds later, see reports.targets). A member reports a given target once: the
database refuses a second abuse report by the same member on the same target, so two
requests at once can't both get in. Reports are deleted with their target, and kept (with
no reporter) when the reporter's account is deleted, so moderation can still act on them.
Phase 14 adds statuses and report management; Phase 15 acts on them.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxLengthValidator
from django.db import models

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
