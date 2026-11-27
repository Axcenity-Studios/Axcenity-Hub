# List controls and pages

Read this before changing `templates/partials/list_controls.html` or `list_pager.html`, the
`.ls-*` classes, or giving another list search, filters, sorting or pages. The rules behind
them (the query string, fallbacks, ordering): [../architecture/lists.md](../architecture/lists.md).
HTMX in general: [forums.md](forums.md#htmx).

| Template | Part |
|---|---|
| `partials/list_controls.html` | The form `#<list_id>-controls`: the search field (`#<list_id>-q`), a select per filter (`#<list_id>-<name>`), the sort (`#<list_id>-sort`) and Apply. Needs `controls`, `list_url`, `list_id` |
| `partials/list_pager.html` | Previous (`#<list_id>-previous`), "Page 2 of 5", Next (`#<list_id>-next`); nothing when there's one page. Needs `pager`, `list_id` |
| `forums/list.html` | `/forums/`: the head, the controls, the live region `#post-list-status`, and the list's part |
| `forums/partials/post_list.html` | `#post-list`: the rows and their count, the pager; or "No posts yet" (`data-empty`); or "No posts match" with Clear (`data-no-match`) |
| `showcases/list.html`, `showcases/partials/showcase_list.html` | `/showcases/` and `#showcase-list`, the same shape as the forum's ([showcases.md](showcases.md)) |

`ListingMixin` gives every template `selection`, `page`, `count`, `controls`, `pager`,
`list_url`, `list_id`, `swapped` and `focus_list`.

## A page shaped for a list

- The page includes the controls, a live region, and the list's part: one element with the
  id `list_id`, holding the rows and the pager. Only that part is swapped.
- **Without JavaScript** the controls are a plain `method="get"` form with an Apply button,
  and the pager's links are plain links: the same URLs, loaded as pages.
- **With htmx** the search field asks after a 300 ms pause in typing, each select on change,
  and the form on submit; all target `#<list_id>`, `outerHTML`. `hx-sync="this:replace"` on
  the form drops an answer that a newer request has overtaken. The field and the selects
  carry `hx-include="closest form"`, so every request holds the whole state.
- **The address bar:** the view answers with `HX-Push-Url`, the state's own URL (defaults
  and empty fields left out), not the request's. A copied address opens the same list.
- **Back and forward:** the form has `hx-history="false"`, so htmx asks the server for that
  URL instead of restoring its saved copy (whose fields would hold what was typed later).
  That request carries `HX-History-Restore-Request`, and the view answers it with the whole
  page; responses vary on that header and `HX-Request`.
- **A new search starts at page 1:** the form has no `page` field.
- **Clear** is a plain link to the list: the page loads whole, so the form resets with it.
- **An empty list** has no controls (there's nothing to search); a list with no matches
  keeps them.

## Focus and announcements

- While typing or choosing, focus stays where it is: the controls sit outside the swapped
  part, and the form's answers carry no `autofocus`.
- After the pager, the link that was pressed is gone, so the list's heading
  (`h2#posts-title`, `tabindex="-1"`) takes focus and the part scrolls to the top
  (`show:top`). The view knows the pager by `HX-Trigger` (`<list_id>-previous` or `-next`)
  and sets `focus_list`.
- Each in-place answer fills the live region out of band with the count ("3 posts") or "No
  posts match" (`hx-swap-oob="innerHTML:#post-list-status"`). The region is `sr-only`.
- `forums.js` loads on the list too: an error answer loads that URL in full, so the Hub's
  error page shows.

## The `.ls-*` classes

Monochrome tokens only; every `:hover` behind the hover gate.

- `.ls-controls` (a wrapping row), `.ls-field` (label over control, at least 9rem),
  `.ls-search` (twice as wide), `.ls-apply`.
- `.ls-list` (the swapped part; its focused heading shows the ink ring for keyboard focus).
- `.ls-pager`, `.ls-page-link`, `.ls-page-label`.

At 360 px the search takes a row and the selects sit two to a row.

## Tests

`tests/test_forums_list.py` (the form's markup, the partial, `HX-Push-Url`, `Vary`, the
focus rule, history restores). `tests/test_forums_list_browser.py` (`browser`): typing,
choosing, the pager by keyboard, Back, Clear, a copied address, and all of it with JavaScript
off, at 360 and 1280 px, dark and light; screenshots in `screenshots/forums/list-*.png`. In a
browser test wait for `htmx:load` after each swap (its `swap` helper), not for the rows: a
key pressed on a link htmx hasn't set up yet follows it as a plain link.
