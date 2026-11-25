"""Reporting content: the rules every report goes through.

A verified member may report content that isn't theirs, once per item: the database's
unique constraint (`one_abuse_report_per_member_per_target`) decides, so two requests at
once give one report and one AlreadyReported, never two reports or an error page.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Model

from accounts.access import ensure_can_contribute

from .models import Report


class AlreadyReported(Exception):
    """The member has already reported this content."""


def report_content(reporter, target: Model, *, reason: str, details: str = "") -> Report:
    """Report `target` (a post or comment) for abuse as `reporter`.

    Raises EmailNotVerified for an unverified member, PermissionDenied for their own content,
    AlreadyReported for a second report of the same content, and ValidationError for an
    unknown reason or over-long details.
    """
    ensure_can_contribute(reporter)
    if getattr(target, "author_id", None) == reporter.pk:
        raise PermissionDenied("Members can't report their own content.")
    report = Report(
        reporter=reporter, kind=Report.Kind.ABUSE, reason=reason, details=details, target=target
    )
    # The uniqueness rule is the database's, below, so a race can't slip past a check here.
    report.full_clean(validate_constraints=False)
    try:
        with transaction.atomic():
            report.save()
    except IntegrityError:
        raise AlreadyReported from None
    return report


def has_reported(reporter, target: Model) -> bool:
    """Whether `reporter` has already reported `target` for abuse."""
    return reported_ids(reporter, type(target), [target.pk]) == {target.pk}


def reported_ids(reporter, model: type[Model], ids) -> set[int]:
    """Which of `model`'s `ids` `reporter` has reported for abuse (none for a visitor)."""
    if not getattr(reporter, "is_authenticated", False):
        return set()
    return set(
        Report.objects.filter(
            reporter=reporter,
            kind=Report.Kind.ABUSE,
            content_type=ContentType.objects.get_for_model(model),
            object_id__in=list(ids),
        ).values_list("object_id", flat=True)
    )
