"""What the showcase list offers (config.listing): search in titles and descriptions, a tag
filter, a filter by when it was published, and three orders.

The tag filter is open (`OpenFilter`): its choices are the tags of published showcases, read
from the database once per request, so a tag that only hidden showcases carry is never
offered (or named) to anyone. "Most liked" reads `like_count`, so the list's queryset comes
from `Showcase.objects.visible_to(user).with_likes()`.
"""

from datetime import timedelta

from config.listing import Choice, Filter, Listing, OpenFilter, Sort, Words

from . import strings
from .models import Showcase, Tag

# Every order ends in the pk: showcases that tie keep one order across pages.
SORTS = (
    Sort("newest", strings.SORT_NEWEST, ("-created", "-pk")),
    Sort("oldest", strings.SORT_OLDEST, ("created", "pk")),
    Sort("liked", strings.SORT_LIKED, ("-like_count", "-created", "-pk")),
)


def tag_options() -> list[tuple[str, str]]:
    """The tags to offer: those of published showcases, by name."""
    published = Showcase.objects.published()
    return [
        (name, name)
        for name in Tag.objects.filter(showcases__in=published)
        .distinct()
        .order_by("name")
        .values_list("name", flat=True)
    ]


def with_tag(showcases, name: str):
    """The showcases carrying the tag `name` (a subquery, so no row repeats)."""
    return showcases.filter(pk__in=Showcase.objects.filter(tags__name=name).values("pk"))


def _since(window: timedelta):
    return lambda showcases, now: showcases.filter(created__gt=now - window)


FILTERS = (
    OpenFilter("tag", strings.FILTER_TAG, strings.TAG_ANY, tag_options, with_tag),
    Filter(
        "posted",
        strings.FILTER_POSTED,
        strings.POSTED_ANY,
        (
            Choice("day", strings.POSTED_DAY, _since(timedelta(days=1))),
            Choice("week", strings.POSTED_WEEK, _since(timedelta(days=7))),
            Choice("month", strings.POSTED_MONTH, _since(timedelta(days=30))),
        ),
    ),
)

SHOWCASES = Listing(
    search_fields=("title", "description"),
    sorts=SORTS,
    filters=FILTERS,
    per_page=24,  # a grid of 2, 3 or 4 across fills every row
    words=Words(
        controls=strings.CONTROLS_LABEL,
        search=strings.SEARCH_LABEL,
        placeholder=strings.SEARCH_PLACEHOLDER,
        pages=strings.PAGES_LABEL,
    ),
)
