# Frontend

Read this before changing templates, styles, the theme or motion. **This
page is an index:** the rules below apply to every template; open a topic
file only for the area you're changing. The visual reference is
`prototypes/home-direction.html`, variant A (throwaway: take its look, not
its code).

## Topic files

| Open… | Before you touch… |
|---|---|
| [frontend/theme.md](frontend/theme.md) | colours, the accent, light and dark, contrast, fonts, the logo, buttons, focus, the hover gate, motion primitives, reduced motion |
| [frontend/home.md](frontend/home.md) | the Home's sections, copy as data, the media manifest and drawn media, the rotating headline, reveals, the pillars' sticky stage |
| [frontend/media.md](frontend/media.md) | the media manifest, captures and `make_media`'s derivatives, `<picture>`, the hero's film (its cut, encodes and playback), where each animated loop sits, their playback, fallbacks and the screenshot test |
| [frontend/download.md](frontend/download.md) | the download page (`/download/`): the release from GitHub, the build kinds and their copy, system detection, the cache and fallbacks, the `.dl-*` classes |
| [frontend/credits.md](frontend/credits.md) | the credits page (`/credits/`): the engine's NOTICE, every crate and Python package, `refresh_credits` and the lists it generates, NOTICE dividers, the `.cr-*` classes |
| [frontend/toolbox.md](frontend/toolbox.md) | the Toolbox page (`/toolbox/`): its sections, the `.tb-*` panel classes, the commands and demo credentials, its screenshots and their capture record |
| [frontend/documentation.md](frontend/documentation.md) | the docs at `/docs/`: re-syncing the snapshot, rendering and its link rules, heading ids, Luau highlighting, the three-column layout, the sidebar, `docs.js`, the API reference's layouts and type links, search |
| [frontend/projects.md](frontend/projects.md) | the project pages: the setup checklist and its states, showing the webhook's values, copy buttons (`projects.js`), the cards, each step's help, the `.pj-*` classes |
| [frontend/forums.md](frontend/forums.md) | the forum pages (posts, ratings, comments) and the report page, **HTMX** (loading, partials, targets, fallbacks, CSRF, errors), focus after a swap and the live region, `forums.js`, the `.fm-*` classes |
| [frontend/lists.md](frontend/lists.md) | a list's controls (search, filters, sort) and pager, shared by every list: the two partials, the swapped part, the address bar and Back, focus and the live region, the `.ls-*` classes |
| [frontend/app-shell.md](frontend/app-shell.md) | the app shell for signed-in pages, Account settings and its tabs, profile photos, the sign-in entrance, allauth's layouts and elements, `form_fields.html`, the honeypot and Turnstile markup, the `.app-*` classes |
| [frontend/canvas.md](frontend/canvas.md) | the loops' canvas kit (`static/reel/`): the loop contract, its context, the determinism and seamless-wrap rules, the drawing modules, fidelity to the editor |

Later phases add topic files for each area they build.

## Error pages

`templates/errors/page.html` is every error page (copy in `config/errors.py`): the
entrance's bar and grid backdrop, one panel with a Toolbox title bar ("Error 404", the
status's name), the code in Home's outlined numerals, a motif, the headline, what happened,
and three ways on (home, docs, projects). It renders without the request's context
processors, so it uses no `user`, `request` or `{% csrf_token %}`, and no theme switch (the
validated theme cookie is passed in). The CSRF page adds Django's reason and the
`HUB_PUBLIC_URL` hint under `DEBUG` only. Under `DEBUG` Django shows its technical 404 and 500
pages instead, so preview these at `/errors/<kind>/`. Classes: `.err`, `.err-panel`,
`.err-bar`, `.err-body`, `.err-head`, `.err-code`, `.err-icon`, `.err-title`, `.err-lede`,
`.err-debug`, `.err-detail`. Tests: `test_errors.py`, `test_errors_browser.py`.

## Tailwind + DaisyUI (no Node)

- django-tailwind-cli downloads the standalone Tailwind CLI and DaisyUI's
  plugin bundles (`daisyui.mjs`, `daisyui-theme.mjs`) into
  `.django_tailwind_cli/` (git-ignored). `source.css` loads them by
  relative path and excludes them from class scanning (`@source not`).
- The source is `styles/source.css`, outside `STATICFILES_DIRS`. The build
  writes `static/css/tailwind.css` (git-ignored). `tailwind runserver` runs
  Django and the watcher; `tailwind build` makes a one-off build.
- Tailwind finds classes by scanning files. **Write class names out in
  full**; a class built from pieces at runtime won't be found.
- Any JavaScript library is a vendored static file. `static/js/shell.js`
  runs on every page (including the motifs: any `class="motif"` icon
  draws in as it comes into view); `static/js/home.js` only on Home (its `head`
  block); the animated loops' ES modules (`static/reel/loops/main.js`)
  once, at the end of Home; `static/js/docs.js` on the docs pages;
  `static/js/download.js` on `/download/` (the license dialog);
  `static/js/projects.js` on a project's page (the copy buttons);
  `static/js/forums.js` on the forum's list and a post's page (error answers load in full). htmx 2 comes
  from django-htmx (a static file in the package, through uv) on every app-shell page
  ([forums.md](frontend/forums.md#htmx)). The one
  script from another site is Cloudflare Turnstile's `api.js`, which
  Cloudflare doesn't allow to be vendored, on signup and reset only when
  Turnstile is configured ([app-shell.md](frontend/app-shell.md)).

## Shells

- `templates/base.html`: the document every shell shares: `<html
  data-theme="axcenity">` with the validated scheme choice, the pre-paint
  scheme script, font preloads, the versioned stylesheet and `shell.js`.
- `templates/marketing/shell.html`: a skip link, the fixed
  nav (`partials/site_nav.html`), `<main id="content">` and the four-column
  footer (`partials/site_footer.html`).
- `templates/app/shell.html` (signed-in pages) and `templates/app/entrance.html`
  (sign in, sign up, reset): see [app-shell.md](frontend/app-shell.md). All three
  share `partials/theme_switch.html`.
- **Nav:** wordmark (home), Engine, Features (`/#features`), Toolbox,
  Docs, Community; then the
  theme switch, Sign in, and Download (the only primary button). It's
  transparent over the hero and solid once the page scrolls past 40 px
  (`html[data-scrolled]`) or the phone menu is open. Below `md` the links
  fold into a `<details class="nav-menu">`, which works without
  JavaScript. A page's first section clears the nav with `.under-nav`.
- **Footer:** the brand column (wordmark, tagline, signature), then
  Engine, Learn and Community, from `content.FOOTER_COLUMNS`.
- **Links to pages that don't exist yet** are `soon` in `content.py`:
  `partials/nav_link.html` renders them as a label with a "Soon" tag,
  never as an `<a>`. Sign in links to `account_login`; signed in, the nav shows
  Account (`accounts:profile`) in its place.

## Rules for every template

- Colour comes only from the axcenity tokens; the chrome is monochrome and
  the accent has fixed uses ([theme.md](frontend/theme.md)).
- Text uses `fg`, `fg-strong`, `fg-secondary` or `fg-weak` only. `fg-muted`
  is under 4.5:1 and is never text (tested).
- Copy and links live in `marketing/content.py` (the docs' frame in
  `documentation/strings.py`), not in templates
  (screen-reader-only labels and attributes may be written in place).
- Every image or drawing is in the media manifest (`content.MEDIA`, and
  the docs' diagrams in `documentation/diagrams.py`) and captioned
  "Engine capture", "Toolbox screenshot", "Illustrative" or "Diagram"; a capture is served only as
  `make_media`'s derivatives, through `picture.html` ([media.md](frontend/media.md)).
- Every `:hover` style sits behind the hover gate
  (`html[data-pointer] …`); keyboard focus never waits for it.
- Drawn or stylised visuals are captioned as illustrative, never as
  engine captures. The engine is alpha; scripting is **Luau**.
- Nothing may scroll sideways at 360 px (`body { overflow-x: clip; }`).
