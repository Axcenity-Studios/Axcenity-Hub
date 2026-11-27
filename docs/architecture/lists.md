# Lists: search, filters, sorting and pages

Read this before adding search, a filter, a sort or pages to any list, or touching
`config/listing.py`. The forum's list is the first to use it (`forums/listing.py`), the
showcases' the second (`showcases/listing.py`), the bug reports' the third
(`reports/listing.py`); projects will reuse it. The templates and HTMX: [../frontend/lists.md](../frontend/lists.md).

A list's state lives in its query string, so every state has a URL to share or reload:

    /forums/?q=decal&sort=top&posted=week&comments=some&rating=4&page=2

| Parameter | Is |
|---|---|
| `q` | The search: every word must be in one of the list's `search_fields` (`icontains`) |
| `sort` | One of the list's declared sorts; the first is the default |
| a filter's `name` | One of that filter's declared choices; absent or empty is "any" |
| `page` | The page, 20 rows each (`PER_PAGE`) |

## The module (`config/listing.py`)

| Name | Does |
|---|---|
| `Sort(value, label, ordering)` | An order. `ordering` is what `order_by` gets, written in code |
| `Choice(value, label, narrow)`, `Filter(name, label, any_label, choices)` | A filter and its fixed choices; `narrow(queryset, now)` returns the rows a choice keeps |
| `OpenFilter(name, label, any_label, options, narrow)` | A filter over values the database holds (a showcase's tags): `options()` gives the (value, label) pairs offered now, read once per request; `narrow(queryset, value)` the rows an offered value keeps |
| `Listing(search_fields, sorts, filters, per_page, words)` | What one list offers. `Words` holds the controls' and pager's words (the same on every list unless overridden) |
| `Listing.read(request.GET)` | The query string as a `Selection` (each filter's choices for this request in its `offered`). Never raises |
| `Selection.apply(queryset, now=)` | The queryset searched, filtered and ordered |
| `Selection.paginate(queryset, now=)` | Its page (Django's `Page`) |
| `Selection.query(page=)` | The state as a query string, defaults left out: one state, one URL |
| `Selection.controls()`, `pager(selection, page, url)` | What the two shared templates draw |
| `ListingMixin` | The view's side: the page, or the list's part for HTMX |

## Untrusted input

Everything in the query string only ever **selects** among what the list declared. A
visitor's value is compared with the declared sorts and choices and is never passed to the
ORM as a field name, a lookup or an ordering. `read` treats each parameter by itself, and
each falls back by itself:

| Sent | Read as |
|---|---|
| An unknown sort (`author__password`, `-created`, `?`, `NEWEST`, `" oldest"`) | The default sort |
| A value that isn't one of a filter's choices (`rating=abc`, `99`, `٤`, `4 OR 1=1`) | Any: the list isn't narrowed |
| A page that isn't written in the digits 0–9 alone (`-1`, `1.5`, `" 2"`, `٢`), or `0` | Page 1 |
| A page past the end, however long the number | The last page |
| A parameter given more than once, even twice the same | Ignored: its default. Never one value picked from several |
| Parameters the list doesn't have (`next`, `sort[]`) | Not read, and never copied into a link |
| A search | Control characters as spaces, runs of space as one, at most 8 words and 100 characters (`clean_search`). The box shows exactly what was searched. `%` and `_` are themselves |

The pager's links and `HX-Push-Url` are built from the `Selection` (`query`), never from the
request, so nothing a visitor sent reaches a link unless it's a valid state.

## Stable pages

Every `Sort` must end in `pk` or `-pk`; one that doesn't is refused when it's declared. Rows
that tie on everything before it (the same moment, count or average, or no ratings at all)
then still have one order, so a row never repeats or goes missing between pages. Nulls are
placed explicitly (`F("rating_average").desc(nulls_last=True)`).

## Queries

- Give `apply` a queryset already limited to what the caller may see (`visible_to(user)`);
  search and filters only narrow it, so they can't reveal or count hidden content.
- Anything a row shows or a filter or sort reads (a count, an average) is an annotation on
  that queryset, and related rows are joined (`select_related`): the forum's page is two
  queries (the count, and the page's rows) however many posts it shows.
- `icontains` is `LIKE`: on SQLite it ignores case for ASCII letters only; PostgreSQL's
  ignores it for all.

## Adding a list

1. Declare a `Listing` beside the app's models (`forums/listing.py`): `search_fields`,
   `sorts` (default first, each ending in the pk), `filters`.
2. The view: `class …(ListingMixin, TemplateView)` with `listing`, `template_name`,
   `partial_template_name`, `list_id`, `get_listing_queryset()` and `get_list_url()`.
3. The templates: see [../frontend/lists.md](../frontend/lists.md).
4. A filter over an open set (a showcase's tag, a report's project) is an `OpenFilter`. Its
   `options()` must offer only what the visitor may see (the showcases' offers only the tags
   of published showcases, so a hidden showcase's tag is never named), and a value it doesn't
   offer doesn't narrow the list, as for a `Filter`.

## The forum's list (`forums/listing.py`)

| | Values |
|---|---|
| Search | `title`, `body` (not the author's name) |
| `sort` | `newest` (default), `oldest`, `top` (highest average; of equal averages the one more members rated; unrated last), `comments` (most comments the viewer may see) |
| `posted` | `day`, `week`, `month`: rolling windows back from now (a post exactly a day old is out) |
| `comments` | `none`, `some`: counted as the viewer sees them (`with_stats(user)`) |
| `rating` | `4`, `3`, `2`: an average of at least that many stars |

`manage.py seed_forum_demo` (development only, idempotent) adds 45 backdated demo posts by
`seed_team_demo`'s members, with comments and ratings on some, so pages and every filter
have something to show: a member can publish only 5 posts a day by hand.

## The showcase list (`showcases/listing.py`)

| | Values |
|---|---|
| Search | `title`, `description` |
| `sort` | `newest` (default), `oldest`, `liked` (most likes; ties newest first) |
| `tag` | Any tag of a published showcase (`OpenFilter`; a subquery, so a showcase with several tags is listed once); anything else, a different case included, is any tag |
| `posted` | `day`, `week`, `month` |
| `page` | 24 a page (a grid of 2, 3 or 4 across fills its rows) |

A visitor's page is four queries however many showcases: the tags offered, the count, the
page's rows, and their tags (`prefetch_related`). `manage.py seed_showcase_demo` adds 30 demo
showcases (two pages) by the team demo's members; only alice's newest is within a day.

## The reports list (`reports/listing.py`)

It depends on who's looking, so `for_member(user, visible)` builds its `Listing` per request.

| | Values |
|---|---|
| Search | `title`, `description` |
| `sort` | `newest` (default), `oldest`, `updated` (recently updated: a status change, assignment or comment) |
| `status` | `open` (new, confirmed or in progress), or one status |
| `kind` | `bug`, `feedback` |
| `about` | `engine`, or a project's slug: an `OpenFilter` offering only the engine and projects of reports the member may see |
| `assigned` | `me`, `nobody` |

A page is a fixed number of queries however many reports (`select_related` for the project,
sender and assignee).

## Tests

`tests/test_forums_list.py` (the fallbacks, test-first; search, each filter and sort, ties,
page boundaries, hidden content, query counts, the HTMX answers, the seed) and
`tests/test_forums_list_browser.py` (`browser`); `tests/test_showcases_list.py` (the tag
filter, `OpenFilter`, the showcase list). See [../TESTING.md](../TESTING.md). `tests/test_reports_bugs_list.py` (the reports list).
