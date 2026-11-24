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
| [frontend/toolbox.md](frontend/toolbox.md) | the Toolbox page (`/toolbox/`): its sections, the `.tb-*` panel classes, the commands and demo credentials, its screenshots and their capture record |
| [frontend/documentation.md](frontend/documentation.md) | the docs at `/docs/`: re-syncing the snapshot, rendering and its link rules, heading ids, Luau highlighting, the three-column layout, the sidebar, `docs.js` |
| [frontend/canvas.md](frontend/canvas.md) | the loops' canvas kit (`static/reel/`): the loop contract, its context, the determinism and seamless-wrap rules, the drawing modules, fidelity to the editor |

Later phases add topic files for each area they build.

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
  runs on every page; `static/js/home.js` only on Home (its `head`
  block); the animated loops' ES modules (`static/reel/loops/main.js`)
  once, at the end of Home; `static/js/docs.js` on the docs pages.

## Shells

- `templates/base.html`: the document every shell shares: `<html
  data-theme="axcenity">` with the validated scheme choice, the pre-paint
  scheme script, font preloads, the versioned stylesheet and `shell.js`.
- `templates/marketing/shell.html` (this phase): a skip link, the fixed
  nav (`partials/site_nav.html`), `<main id="content">` and the four-column
  footer (`partials/site_footer.html`). An editor-style app shell for
  signed-in pages arrives in Phase 8 and extends `base.html` too.
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
  never as an `<a>`. Sign in stays `soon` until Phase 8.

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
