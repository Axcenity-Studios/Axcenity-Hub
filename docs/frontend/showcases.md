# The showcase pages

Read this before changing `templates/showcases/` or the `.sc-*` classes. The rules behind the
pages: [../architecture/showcases.md](../architecture/showcases.md). The list's controls and
pager are the shared ones ([lists.md](lists.md)); HTMX follows the forum's pattern
([forums.md](forums.md#htmx)). The pages sit in the app shell under the rail's **Showcases**
item; the footer's Showcases link leads here.

| Template | Page or part |
|---|---|
| `showcases/list.html` | `/showcases/`: New showcase (signed in) or Sign in to publish, the controls (search, Tag, Published, Sort by), the live region `#showcase-list-status`, the list's part |
| `showcases/partials/showcase_list.html` | `#showcase-list`: the heading (`h2#showcases-title`: "Showcases", or "Tagged terrain" while a tag is chosen) and count, the cards, the pager; or "No showcases yet" (`data-empty`); or "No showcases match" with Clear (`data-no-match`) |
| `showcases/detail.html` | `/showcases/<slug>/`: All showcases, `#showcase-status`, the image across the panel (its `alt` is the author's image description or the title), title, author, dates, description, tags, likes; Edit and Delete for its author, Report (or "Reported") for other members, the state tag for staff |
| `showcases/partials/like.html` | `#like`: the count, and one button (`name=action`, `like` or `unlike`, `aria-pressed`); Sign in to like, or "You can't like your own showcase" |
| `showcases/form.html` | Publishing and editing (`multipart/form-data`): title, image (`accept` PNG, JPEG, WebP), image description, description, tags; editing shows the current image and keeps it unless a new one is chosen; at the limit, the limit's message above the form (`data-limit`) |
| `showcases/confirm_delete.html` | Deleting, after the question |

Copy lives in `showcases/strings.py`; the pages get it as `text`.

- **In place:** the list (as every list) and the like. Liking swaps `#like` (`outerHTML`), the
  button focused (`autofocus` on the HTMX answer only), "Liked." or "Like taken back." in the
  live region out of band; a refusal is a `role="alert"` in the part. Without JavaScript the
  like is a form posting to the same URL and back to `#like`.
- **Full pages:** publishing, editing and deleting (they carry a file, or need a question).
- `forums.js` loads on the list and a showcase's page: an error answer loads in full.
- Cards show the `card` image (`loading="lazy"`, `alt=""`: the title beside it names it),
  cropped to 16:10 by CSS; the title's link stretches over the card, and the tags sit above
  it so each is its own link to `/showcases/?tag=<name>`.
- Uploaded images are members' content, not the Hub's claims about the engine. The demo seed's
  placeholders say they're illustrative in their description and image description.

## The `.sc-*` classes

Inside the projects' panels and the forum's meta (`.pj-panel`, `.pj-bar`, `.fm-meta`,
`.fm-post-body`, `.fm-rating`); monochrome tokens only, every `:hover` behind the hover gate,
the accent never used.

- `.sc-grid` (cards 15rem and wider; a line inside each card's right and bottom, the grid 1px
  under the panel's clipped edge), `.sc-card` (the ink ring when its link has keyboard
  focus), `.sc-card-image`, `.sc-card-body`, `.sc-card-title`, `.sc-card-stats`,
  `.sc-card-tags`.
- `.sc-tags`, `.sc-tag` (mono, a 1px line; ink on hover or focus).
- `.sc-image` (the page's image, at most 75vh tall, never cropped), `.sc-like`,
  `.sc-like-button`, `.sc-liked` (the heart filled), `.sc-form-image`.
- Icons: `image`, `heart` and `tag` in `partials/icon.html`.

## Tests

`tests/test_showcases.py` and `tests/test_showcases_list.py` (markup, the like's partial,
`Vary`, CSRF). `tests/test_showcases_browser.py` (`browser`): the grid and a showcase's page
at 360 and 1280 px, dark and light (no sideways scroll, every image drawn), a tag chosen in
place, a card's tag link, liking and taking it back by keyboard with no reload, publishing
with a real file; screenshots in `screenshots/showcases/`.
