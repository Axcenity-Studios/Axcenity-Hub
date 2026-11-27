"""The shared list pattern: search, filters, sorting and pages, with their state in the
query string.

A list declares what it offers once, in code (a `Listing`: the fields search looks in, its
`Sort`s, its `Filter`s and their `Choice`s). `Listing.read(request.GET)` turns the query
string into a `Selection`; `Selection.apply` narrows and orders a queryset, `paginate` cuts
its page, and `query` writes the state back as a query string, so every list has the same
shareable URLs: `?q=…&sort=…&<filter>=…&page=…`.

Everything a visitor sends only ever *selects* among what the list declared: a sort or a
filter's value is looked up in the declared ones, never passed to the ORM as a field name,
a lookup or an ordering.

`ListingMixin` is the view's side: the page for a plain request, the list's part for an HTMX
one (docs/architecture/lists.md, docs/frontend/lists.md).
"""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from urllib.parse import urlencode

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import QueryDict
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django_htmx.http import push_url

# The parameters every list shares. A filter may not take one of these names.
SEARCH, SORT, PAGE = "q", "sort", "page"
# The longest search kept, and the most words of it searched for.
MAX_QUERY = 100
MAX_WORDS = 8
PER_PAGE = 20
# What a page number too long to be one is read as: past the end of any list.
PAST_THE_END = 10**9


def _once(params: QueryDict, name: str) -> str:
    """The parameter's value if the query string gives it exactly once, "" otherwise."""
    values = params.getlist(name)
    return values[0] if len(values) == 1 else ""


def clean_search(raw: str) -> str:
    """A search as it's run and shown back: control characters (a NUL, a line break) read
    as spaces, runs of space as one, and at most `MAX_WORDS` words and `MAX_QUERY`
    characters, so the box never claims a word that wasn't searched for."""
    text = "".join(" " if unicodedata.category(char) == "Cc" else char for char in raw)
    return " ".join(text.split()[:MAX_WORDS])[:MAX_QUERY].strip()


def clean_page(raw: str) -> int:
    """A page number from the query string: 1 unless it's written in the digits 0-9 alone
    (not "-1", "1.5", " 2" or "٢", which int() would take). 0 is the first page; a number
    too long to be a page is `PAST_THE_END`."""
    if not re.fullmatch(r"[0-9]+", raw):
        return 1
    digits = raw.lstrip("0")
    if len(digits) > 9:
        return PAST_THE_END
    return int(digits or 1)


@dataclass(frozen=True)
class Sort:
    """One order a list can be shown in. `ordering` is what `order_by` gets, written in
    code; it must end in `pk` or `-pk`, so that rows that tie on everything before it (the
    same average, the same count, no ratings at all) still have one fixed order and never
    move between pages."""

    value: str
    label: str
    ordering: tuple

    def __post_init__(self):
        if not self.ordering or self.ordering[-1] not in ("pk", "-pk"):
            raise ValueError(f"The sort {self.value!r} must end in pk or -pk: ties need an order.")


@dataclass(frozen=True)
class Choice:
    """One value of a filter. `narrow(queryset, now)` returns the rows it keeps."""

    value: str
    label: str
    narrow: Callable[[QuerySet, datetime], QuerySet]


@dataclass(frozen=True)
class Filter:
    """A filter: a parameter (`name`) with a fixed set of choices. Without it, or with
    anything that isn't one of its choices, the list isn't narrowed (`any_label`)."""

    name: str
    label: str
    any_label: str
    choices: tuple[Choice, ...]

    def choice(self, value: str) -> Choice | None:
        """The choice with exactly this value, or None."""
        return next((choice for choice in self.choices if choice.value == value), None)

    def offer(self) -> tuple[Choice, ...]:
        """The choices this request may pick from: always the same ones."""
        return self.choices


def _narrow_open(narrow, value, queryset, now):
    return narrow(queryset, value)


@dataclass(frozen=True)
class OpenFilter:
    """A filter over an open set of values the database holds (a showcase's tags), where a
    `Filter`'s choices are written in code. `options()` gives the (value, label) pairs it
    offers now, read once per request (`Listing.read`); `narrow(queryset, value)` returns
    the rows an offered value keeps. A value that isn't offered doesn't narrow the list, as
    for a `Filter`, so a visitor's value is still only ever compared with what's offered."""

    name: str
    label: str
    any_label: str
    options: Callable[[], Iterable[tuple[str, str]]]
    narrow: Callable[[QuerySet, str], QuerySet]

    def offer(self) -> tuple[Choice, ...]:
        """The choices this request may pick from, as the database holds them now."""
        return tuple(
            Choice(value, label, partial(_narrow_open, self.narrow, value))
            for value, label in self.options()
            if value
        )


@dataclass(frozen=True)
class Words:
    """The words of a list's controls and pager, the same on every list unless it says
    otherwise."""

    controls: str = "Search, filter and sort"
    search: str = "Search"
    placeholder: str = ""
    sort: str = "Sort by"
    apply: str = "Apply"
    clear: str = "Clear search and filters"
    pages: str = "Pages"
    previous: str = "Previous"
    next: str = "Next"
    page: str = "Page {number} of {total}"


@dataclass(frozen=True)
class Listing:
    """What one list offers: the text fields search looks in, its sorts (the first is the
    default) and its filters."""

    search_fields: tuple[str, ...]
    sorts: tuple[Sort, ...]
    filters: tuple[Filter | OpenFilter, ...] = ()
    per_page: int = PER_PAGE
    words: Words = field(default_factory=Words)

    def __post_init__(self):
        names = [f.name for f in self.filters]
        if not self.sorts:
            raise ValueError("A list needs at least one sort: pages need an order.")
        if len(set(names)) != len(names) or {SEARCH, SORT, PAGE} & set(names):
            raise ValueError("Filter names must differ from each other and from q, sort and page.")
        for values in (
            [s.value for s in self.sorts],
            *([c.value for c in f.choices] for f in self.filters if isinstance(f, Filter)),
        ):
            if "" in values or len(set(values)) != len(values):
                raise ValueError("Sort and choice values must be distinct and not empty.")

    @property
    def default_sort(self) -> Sort:
        return self.sorts[0]

    def sort(self, value: str) -> Sort | None:
        """The sort with exactly this value, or None."""
        return next((sort for sort in self.sorts if sort.value == value), None)

    def read(self, params: QueryDict) -> "Selection":
        """The state a query string asks for. Each parameter is read by itself and falls
        back by itself: a parameter given more than once is ignored (never one value picked
        from several), an unknown sort is the default one, a value that isn't one of a
        filter's choices doesn't narrow the list, and anything else in the query string
        isn't read at all. Never raises."""
        chosen, offered = {}, {}
        for each in self.filters:
            offered[each.name] = each.offer()
            value = _once(params, each.name)
            chosen[each.name] = value if _pick(offered[each.name], value) else ""
        return Selection(
            listing=self,
            q=clean_search(_once(params, SEARCH)),
            sort=self.sort(_once(params, SORT)) or self.default_sort,
            chosen=chosen,
            page=clean_page(_once(params, PAGE)),
            offered=offered,
        )


def _pick(choices: tuple[Choice, ...], value: str) -> Choice | None:
    """The choice with exactly this value, or None."""
    return next((choice for choice in choices if choice.value == value), None)


@dataclass(frozen=True)
class Selection:
    """A list's state: the search, the sort, each filter's chosen value ("" for any) and
    the page asked for."""

    listing: Listing
    q: str
    sort: Sort
    chosen: dict[str, str]
    page: int = 1
    # Each filter's choices for this request (`Listing.read`): an open filter's come from
    # the database once, then every use reads them here.
    offered: dict[str, tuple[Choice, ...]] = field(default_factory=dict)

    def choices(self, each: "Filter | OpenFilter") -> tuple[Choice, ...]:
        """The choices `each` offers in this selection."""
        if each.name in self.offered:
            return self.offered[each.name]
        return each.offer()

    @property
    def words(self) -> list[str]:
        """The words searched for: a row must hold every one of them."""
        return self.q.split()[:MAX_WORDS]

    @property
    def narrowed(self) -> bool:
        """Whether a search or a filter is on (so an empty list means "nothing matches")."""
        return bool(self.q) or any(self.chosen.values())

    def apply(self, queryset: QuerySet, *, now: datetime | None = None) -> QuerySet:
        """`queryset` searched, filtered and ordered. Start from what the caller may see
        (`visible_to`): this only ever narrows it. `now` is for the filters that count back
        from the present."""
        now = now or timezone.now()
        for word in self.words:
            match = Q()
            for name in self.listing.search_fields:
                match |= Q(**{f"{name}__icontains": word})
            queryset = queryset.filter(match)
        for each in self.listing.filters:
            choice = _pick(self.choices(each), self.chosen.get(each.name, ""))
            if choice:
                queryset = choice.narrow(queryset, now)
        return queryset.order_by(*self.sort.ordering)

    def paginate(self, queryset: QuerySet, *, now: datetime | None = None) -> Page:
        """The asked-for page of `queryset` (after `apply`); the last page when the list
        ends before it."""
        return Paginator(self.apply(queryset, now=now), self.listing.per_page).get_page(self.page)

    def query(self, *, page: int = 1) -> str:
        """The state as a query string ("" or "?…") for `page`, defaults left out, so one
        state has one URL."""
        pairs = []
        if self.q:
            pairs.append((SEARCH, self.q))
        if self.sort != self.listing.default_sort:
            pairs.append((SORT, self.sort.value))
        pairs += [
            (f.name, self.chosen[f.name]) for f in self.listing.filters if self.chosen.get(f.name)
        ]
        if page > 1:
            pairs.append((PAGE, page))
        return f"?{urlencode(pairs)}" if pairs else ""

    def controls(self) -> dict:
        """What `partials/list_controls.html` draws: the search field and one select per
        filter, then the sort, each with its current value."""
        selects = [
            {
                "name": each.name,
                "label": each.label,
                "options": [
                    {
                        "value": "",
                        "label": each.any_label,
                        "selected": not self.chosen.get(each.name),
                    },
                    *(
                        {
                            "value": c.value,
                            "label": c.label,
                            "selected": self.chosen.get(each.name) == c.value,
                        }
                        for c in self.choices(each)
                    ),
                ],
            }
            for each in self.listing.filters
        ]
        selects.append(
            {
                "name": SORT,
                "label": self.listing.words.sort,
                "options": [
                    {"value": s.value, "label": s.label, "selected": s == self.sort}
                    for s in self.listing.sorts
                ],
            }
        )
        return {
            "q": self.q,
            "max_query": MAX_QUERY,
            "selects": selects,
            "words": self.listing.words,
        }


def pager(selection: Selection, page: Page, url: str) -> dict:
    """What `partials/list_pager.html` draws: the page's place and its neighbours' URLs
    ("" at either end)."""
    return {
        "number": page.number,
        "total": page.paginator.num_pages,
        "label": selection.listing.words.page.format(
            number=page.number, total=page.paginator.num_pages
        ),
        "previous": url + selection.query(page=page.number - 1) if page.has_previous() else "",
        "next": url + selection.query(page=page.number + 1) if page.has_next() else "",
        "words": selection.listing.words,
    }


class ListingMixin:
    """A list page whose state is in its query string. A view names its `listing`, its
    `template_name` (the page), `partial_template_name` (the part of it that holds the rows
    and the pager) and `list_id` (that part's id), and gives `get_listing_queryset()` (what
    the caller may see) and `get_list_url()`.

    A plain request gets the page. An HTMX request gets the part, and the address bar gets
    the state's own URL (`HX-Push-Url`), so what's on screen can always be shared or
    reloaded. Going back or forward through those URLs asks for the page again
    (`HX-History-Restore-Request`), and gets all of it.
    """

    listing: Listing
    partial_template_name: str
    list_id: str

    def get_listing_queryset(self) -> QuerySet:
        raise NotImplementedError

    def get_list_url(self) -> str:
        raise NotImplementedError

    def is_partial(self) -> bool:
        htmx = self.request.htmx
        return bool(htmx) and not htmx.history_restore_request

    def get_template_names(self) -> list[str]:
        return [self.partial_template_name if self.is_partial() else self.template_name]

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        selection = self.listing.read(self.request.GET)
        page = selection.paginate(self.get_listing_queryset())
        url = self.get_list_url()
        self.current_url = url + selection.query(page=page.number)
        context.update(
            selection=selection,
            page=page,
            count=page.paginator.count,
            list_url=url,
            list_id=self.list_id,
            controls=selection.controls(),
            pager=pager(selection, page, url),
            swapped=self.is_partial(),
            # The pager's links ask for the heading to be focused: the link pressed is gone
            # after the swap. The form doesn't: the visitor is still typing in it.
            focus_list=self.is_partial()
            and self.request.htmx.trigger
            in (
                f"{self.list_id}-previous",
                f"{self.list_id}-next",
            ),
        )
        return context

    def render_to_response(self, context, **kwargs):
        response = super().render_to_response(context, **kwargs)
        if self.is_partial():
            push_url(response, self.current_url)
        patch_vary_headers(response, ["HX-Request", "HX-History-Restore-Request"])
        return response
