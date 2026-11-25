# The forum pages and HTMX

Read this before changing `templates/forums/`, `static/js/forums.js`, the `.fm-*` classes,
or adding HTMX anywhere: the forum is the Hub's first HTMX, and its pattern is the one to
follow. The rules behind the pages: [../architecture/forums.md](../architecture/forums.md).
They sit in the app shell ([app-shell.md](app-shell.md)), under the rail's **Forums** item;
the marketing nav's Community and the footer's Forums link here.

| Template | Page or part |
|---|---|
| `forums/list.html` | `/forums/`: every post as a row (title link stretched over the row, author, date, "Edited", the body's start), New post (signed in) or Sign in to post, or the empty state |
| `forums/detail.html` | `/forums/<pk>/`: All posts, the live region `#post-status`, and the post |
| `forums/partials/post.html` | `#post`: title (`h1#post-title`, `tabindex=-1`), author, dates, body, and for its author "Your post", Edit and Delete |
| `forums/partials/post_form.html` | `#post` as its edit form (`data-editing`) |
| `forums/partials/confirm_delete.html` | `#post` as the question (`data-confirming`) |
| `forums/partials/deleted.html` | Where `#post` was (`data-deleted`) |
| `forums/form.html`, `forums/confirm_delete.html` | Full pages: a new post; editing and deleting without JavaScript |

Copy lives in `forums/strings.py`; the pages get it as `text`.

## HTMX

- **Loading:** `{% htmx_script %}` (django-htmx's static htmx 2) in `app/shell.html`'s `head`,
  so every app-shell page has it; pages add scripts in its `app_head` block.
  `HtmxMiddleware` sets `request.htmx`.
- **One target:** every swap replaces `#post` (`hx-target="#post" hx-swap="outerHTML"`), and
  every part above has `id="post"` at its root.
- **Progressive enhancement:** each control is a real link or form first. Edit and Delete are
  `<a href>` to the full edit and delete pages, with `hx-get` to the same URL; Save and
  Delete post are `<form method="post" action>` with `hx-post`. With JavaScript off,
  everything works as full pages with redirects and messages.
- **Fragment or page:** a view answers an HTMX request with the partial, any other with the
  page; `HtmxAwareMixin` adds `Vary: HX-Request`, and turns a redirect an HTMX request would
  get (to sign in, to verify) into `HX-Redirect`, so that page loads in full instead of being
  swapped into the post.
- **CSRF:** every HTMX write is a form carrying `{% csrf_token %}`, so htmx sends the token
  with the fields. Nothing is exempt.
- **Errors:** an invalid edit answers 200 with the form and its errors (htmx 2 doesn't swap
  4xx/5xx). Any error answer (a post deleted in another tab, a stale token) makes
  `forums.js` load the page in full, so the Hub's error page shows instead of a dead click.
- **Double submits:** htmx drops a second request from an element while one is in flight.
  (Not `hx-disabled-elt` with `find`: once the form is swapped out it logs an error.)

## Focus and announcements

- A swapped part carries `autofocus` where focus belongs, and htmx focuses it after the swap:
  the title field when editing (or the first invalid field, with `aria-invalid="true"`, its
  error a `role="alert"`), the post's heading after Save or Cancel, the question when
  deleting, the "Post deleted" heading after. Headings take focus with `tabindex="-1"`.
  `autofocus` is only on HTMX answers (the `swapped` flag), never on a full page.
- Save fills the page's polite live region (`#post-status`, `role="status"`) out of band
  (`hx-swap-oob="innerHTML:#post-status"`): updating the region that's already there is what
  screen readers announce. `.fm-status:empty` hides it until then.
- A focused heading shows the ink ring only for keyboard focus (`:focus-visible`).

## The `.fm-*` classes

Inside the projects' panels (`.pj-panel`, `.pj-bar`, `.tb-chip`, `.pj-tag`); monochrome
tokens only, every `:hover` behind the hover gate.

- `.fm-rows`, `.fm-row` (the title's link stretches over it; the ink ring on its focus),
  `.fm-row-title`, `.fm-row-text` (two lines), `.fm-meta`, `.fm-author`.
- `.fm-back`, `.fm-status`, `.fm-post`, `.fm-post-body`, `.fm-post-head`, `.fm-title`,
  `.fm-text` (46rem measure), `.fm-confirm-title`.

## Tests

`tests/test_forums.py` (the partials' markup, focus attributes, `Vary`, `HX-Redirect`, CSRF
with and without `HX-Request`). `tests/test_forums_browser.py` (`browser`): the author edits,
fixes an error, saves, cancels, keeps and deletes by keyboard with focus following each swap
and no reload; the same with JavaScript off; every page at 360 and 1280 px, dark and light;
screenshots in `screenshots/forums/`. Tests wait on `htmx:load`, not focus alone: a field
keeps focus across a swap, and a key pressed before htmx sets up the new part acts as a plain
link.
