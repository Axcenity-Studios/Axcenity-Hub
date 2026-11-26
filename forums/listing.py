"""What the forum's list offers (config.listing): search in titles and posts, three filters
and four orders.

The filters and the orders that use a post's comments or ratings read `comment_count`,
`rating_count` and `rating_average`, so the list's queryset comes from
`ForumPost.objects.visible_to(user).with_stats(user)`.
"""

from datetime import timedelta

from django.db.models import F

from config.listing import Choice, Filter, Listing, Sort, Words

from . import strings

# Every order ends in the pk: posts that tie (the same moment, the same count, the same
# average, or no ratings at all) keep one order, so none repeats or goes missing across pages.
SORTS = (
    Sort("newest", strings.SORT_NEWEST, ("-created", "-pk")),
    Sort("oldest", strings.SORT_OLDEST, ("created", "pk")),
    Sort(
        "top",
        strings.SORT_TOP,
        # Unrated posts last; among equal averages, the one more members rated first.
        (F("rating_average").desc(nulls_last=True), "-rating_count", "-created", "-pk"),
    ),
    Sort("comments", strings.SORT_COMMENTS, ("-comment_count", "-created", "-pk")),
)


def _since(window: timedelta):
    return lambda posts, now: posts.filter(created__gt=now - window)


def _rated(score: int):
    return lambda posts, now: posts.filter(rating_average__gte=score)


FILTERS = (
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
    Filter(
        "comments",
        strings.FILTER_COMMENTS,
        strings.COMMENTS_ANY,
        (
            Choice("none", strings.COMMENTS_NONE, lambda posts, now: posts.filter(comment_count=0)),
            Choice(
                "some", strings.COMMENTS_SOME, lambda posts, now: posts.filter(comment_count__gt=0)
            ),
        ),
    ),
    Filter(
        "rating",
        strings.FILTER_RATING,
        strings.RATING_ANY,
        tuple(
            Choice(str(score), strings.RATING_AT_LEAST.format(score=score), _rated(score))
            for score in (4, 3, 2)
        ),
    ),
)

POSTS = Listing(
    search_fields=("title", "body"),
    sorts=SORTS,
    filters=FILTERS,
    words=Words(
        controls=strings.CONTROLS_LABEL,
        search=strings.SEARCH_LABEL,
        placeholder=strings.SEARCH_PLACEHOLDER,
        pages=strings.PAGES_LABEL,
    ),
)
