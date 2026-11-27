"""What the reports list offers (config.listing): search in titles and descriptions, filters
by status, kind, what it's about and who it's assigned to, and three orders.

The list depends on who's looking: "About" offers only the projects (and the engine) of the
reports they may see, and "Assigned to me" means them. So the Listing is made per request
(`for_member`); it's a small frozen value, cheap to build.
"""

from config.listing import Choice, Filter, Listing, OpenFilter, Sort, Words

from . import strings
from .forms import ENGINE
from .models import OPEN_STATUSES, BugReport, BugStatus

# Every order ends in the pk: reports that tie keep one order across pages.
SORTS = (
    Sort("newest", strings.SORT_NEWEST, ("-created", "-pk")),
    Sort("oldest", strings.SORT_OLDEST, ("created", "pk")),
    Sort("updated", strings.SORT_UPDATED, ("-updated", "-pk")),
)


def _status(value: str):
    return lambda reports, now: reports.filter(status=value)


STATUS = Filter(
    "status",
    strings.FILTER_STATUS,
    strings.STATUS_ANY,
    (
        Choice(
            "open",
            strings.STATUS_OPEN,
            lambda reports, now: reports.filter(status__in=OPEN_STATUSES),
        ),
        *(Choice(status.value, status.label, _status(status.value)) for status in BugStatus),
    ),
)

KIND = Filter(
    "kind",
    strings.FILTER_KIND,
    strings.KIND_ANY,
    tuple(
        Choice(
            kind.value, kind.label, lambda reports, now, kind=kind.value: reports.filter(kind=kind)
        )
        for kind in BugReport.Kind
    ),
)


def about_options(visible) -> list[tuple[str, str]]:
    """What "About" offers: the engine if any of `visible` (the reports the member may see)
    is about it, then their projects by name."""
    options = []
    if visible.filter(project__isnull=True).exists():
        options.append((ENGINE, strings.ENGINE))
    projects = (
        visible.filter(project__isnull=False)
        .order_by("project__name")
        .values_list("project__slug", "project__name")
        .distinct()
    )
    return options + list(projects)


def about(reports, value: str):
    """The reports about the engine (`ENGINE`) or the project with slug `value`."""
    if value == ENGINE:
        return reports.filter(project__isnull=True)
    return reports.filter(project__slug=value)


def for_member(user, visible) -> Listing:
    """The reports list as `user` sees it; `visible` is `BugReport.objects.visible_to(user)`."""
    assigned = Filter(
        "assigned",
        strings.FILTER_ASSIGNED,
        strings.ASSIGNED_ANY,
        (
            Choice("me", strings.ASSIGNED_ME, lambda reports, now: reports.filter(assignee=user)),
            Choice(
                "nobody",
                strings.ASSIGNED_NOBODY,
                lambda reports, now: reports.filter(assignee__isnull=True),
            ),
        ),
    )
    return Listing(
        search_fields=("title", "description"),
        sorts=SORTS,
        filters=(
            STATUS,
            KIND,
            OpenFilter(
                "about",
                strings.FILTER_PROJECT,
                strings.PROJECT_ANY,
                lambda: about_options(visible),
                about,
            ),
            assigned,
        ),
        words=Words(
            controls=strings.BUGS_CONTROLS_LABEL,
            search=strings.BUGS_SEARCH_LABEL,
            placeholder=strings.BUGS_SEARCH_PLACEHOLDER,
            pages=strings.BUGS_PAGES_LABEL,
        ),
    )
