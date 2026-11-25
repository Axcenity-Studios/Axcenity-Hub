# The forum pages and HTMX

Read this before changing `templates/forums/`, `static/js/forums.js`, the `.fm-*` classes,
or adding HTMX anywhere: the forum is the Hub's first HTMX, and its pattern is the one to
follow. The rules behind the pages: [../architecture/forums.md](../architecture/forums.md).
They sit in the app shell ([app-shell.md](app-shell.md)), under the rail's **Forums** item;
the marketing nav's Community and the footer's Forums link here.

| Template | Page or part |
|---|---|
| `forums/list.html` | `/forums/`: every post as a row (title link stretched over the row, author, date, "Edited", the body's start), New post (signed in) or Sign in to post, or the empty state |
| `forums/detail.html` | `/forums/<pk>/`: All posts, the live region `#post-status`, the post and its comments |
| `forums/partials/post.html` | `#post`: title (`h1#post-title`, `tabindex=-1`), author, dates, body, its rating, and for its author "Your post", Edit and Delete; for other members Report (or "Reported"); for staff its state tag |
| `forums/partials/rating.html` | `#rating` (inside `#post`): the average to one decimal and the count; five star buttons (`name=score`, `aria-pressed` on the member's own), Clear my rating; Sign in to rate, or "You can't rate your own post" |
| `forums/partials/comments.html` | `#comments`: the heading (`h2#comments-title`, `tabindex=-1`) and count, the comments oldest first, and the form (or Sign in to comment); no form under a hidden post |
| `forums/partials/comment.html` | `#comment-<pk>` (`tabindex=-1`): author, time, text, "Your comment" and Delete for its author, Report or "Reported" for other members, the state tag for staff |
| `forums/partials/comment_confirm_delete.html` | `#comment-<pk>` as the question (`data-confirming`) |
| `forums/partials/post_form.html` | `#post` as its edit form (`data-editing`) |
| `forums/partials/confirm_delete.html` | `#post` as the question (`data-confirming`) |
| `forums/partials/deleted.html` | Where `#post` was (`data-deleted`) |
| `forums/form.html`, `forums/confirm_delete.html`, `forums/comment_confirm_delete.html` | Full pages: a new post; editing and deleting a post, and deleting a comment, without JavaScript |
| `reports/form.html` | `/reports/<kind>/<pk>/`: the report form (reasons as radios, details), or "Already reported"; a full page, never HTMX |

Copy lives in `forums/strings.py`; the pages get it as `text`.

## HTMX

- **Loading:** `{% htmx_script %}` (django-htmx's static htmx 2) in `app/shell.html`'s `head`,
  so every app-shell page has it; pages add scripts in its `app_head` block.
  `HtmxMiddleware` sets `request.htmx`.
- **Targets:** each swap replaces one part, `outerHTML`, and each partial has that id at its
  root: `#post` (edit, delete, Cancel), `#rating` (a star, Clear), `#comments` (commenting,
  confirming a comment's deletion: the count changes too), and `#comment-<pk>` (Delete's
  question and Keep it). Deleting a post also removes `#comments`, out of band
  (`<div id="comments" hx-swap-oob="delete">` in `deleted.html`).
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
- **Errors:** an invalid edit or comment, a limit reached, or a refused rating answers 200
  with the part and its errors (`role="alert"`) (htmx 2 doesn't swap
  4xx/5xx). Any error answer (a post deleted in another tab, a stale token) makes
  `forums.js` load the page in full, so the Hub's error page shows instead of a dead click.
- **Double submits:** htmx drops a second request from an element while one is in flight.
  (Not `hx-disabled-elt` with `find`: once the form is swapped out it logs an error.)

## Focus and announcements

- A swapped part carries `autofocus` where focus belongs, and htmx focuses it after the swap:
  the title field when editing (or the first invalid field, with `aria-invalid="true"`, its
  error a `role="alert"`), the post's heading after Save or Cancel, the question when
  deleting, the "Post deleted" heading after; the star just pressed after rating (the first
  after Clear); the new comment after commenting, the comment field after an error, the
  comment's question on Delete, the comment again on Keep it, and the Comments heading after
  deleting one. Headings take focus with `tabindex="-1"`.
  `autofocus` is only on HTMX answers (the `swapped` flag), never on a full page.
- Save, rating, commenting and deleting a comment fill the page's polite live region (`#post-status`, `role="status"`) out of band
  (`hx-swap-oob="innerHTML:#post-status"`): updating the region that's already there is what
  screen readers announce. `.fm-status:empty` hides it until then.
- A focused heading shows the ink ring only for keyboard focus (`:focus-visible`).

## The `.fm-*` classes

Inside the projects' panels (`.pj-panel`, `.pj-bar`, `.tb-chip`, `.pj-tag`); monochrome
tokens only, every `:hover` behind the hover gate.

- `.fm-rows`, `.fm-row` (the title's link stretches over it; the ink ring on its focus),
  `.fm-row-title`, `.fm-row-text` (two lines), `.fm-meta`, `.fm-author`.
- `.fm-back`, `.fm-status`, `.fm-post`, `.fm-post-body`, `.fm-post-head`, `.fm-title`,
  `.fm-text` (46rem measure), `.fm-confirm-title`, `.fm-row-stats` (the list's comment count
  and average).
- The rating: `.fm-rating`, `.fm-rating-title`, `.fm-rating-summary`, `.fm-star-icon`,
  `.fm-rate`, `.fm-stars`, `.fm-star` (2.5rem target), `.fm-star-on` (filled up to the
  member's rating, in `fg-strong`: the accent is never used), `.fm-rating-mine`,
  `.fm-rating-note`.
- The comments: `.fm-comments`, `.fm-comment-list`, `.fm-comment` (its focus ring inset),
  `.fm-comment-text`, `.fm-comments-empty`, `.fm-comment-form`.
- `.fm-reported`, `.fm-state` (staff's Hidden or Removed tag), `.fm-report-target`.
- Icons: `star` and `flag` in `partials/icon.html`.

## Tests

`tests/test_forums.py` and `tests/test_forums_comments.py` (the partials' markup, focus
attributes, `Vary`, `HX-Redirect`, CSRF with and without `HX-Request`). `tests/test_forums_browser.py` (`browser`): the author edits,
fixes an error, saves, cancels, keeps and deletes by keyboard with focus following each swap
and no reload; another member rates, clears, comments, deletes their comment and reports one,
the same way; a deleted post's comments leave with it; all of it with JavaScript off; every page at 360 and 1280 px, dark and light;
screenshots in `screenshots/forums/`. Tests wait on `htmx:load`, not focus alone: a field
keeps focus across a swap, and a key pressed before htmx sets up the new part acts as a plain
link.
