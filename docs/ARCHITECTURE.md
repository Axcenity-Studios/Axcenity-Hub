# Architecture

Read this before adding models, URLs, views or services. **This page is an
index:** the rules below apply everywhere; topic files under
`docs/architecture/` get written as areas grow (none exist yet).

## Layout

| Path | Holds |
|---|---|
| `config/` | Settings, root URLs, WSGI/ASGI, site-wide context processors, `theme.py` (the colour-scheme cookie) |
| `marketing/` | Public signed-out pages: Home, Toolbox, and Download (Phase 7). `content.py` holds their copy, links and media manifest as data; `drawings.py` computes the drawn media; `media.py` cuts captures into derivatives (`manage.py make_media`) |
| `documentation/` | The engine docs at `/docs/`: `sync.py` (`sync_engine_docs`), `navigation.py`, `links.py`, `rendering.py`, `highlight.py`, `library.py` (the snapshot as served, and its build check), `diagrams.py`, `strings.py`. See [frontend/documentation.md](frontend/documentation.md) |
| `documentation/content/` | The committed snapshot of the engine's `documentation/` folder, with `SOURCE.json` (commit and tree). Only `sync_engine_docs` writes it |
| `marketing/media_sources/` | Captures as copied in (never served, never edited): the sources `make_media` reads, and `toolbox-capture.json`, the Toolbox screenshots' capture record |
| `templates/` | `base.html` (shared by every shell), `marketing/` (the marketing shell and its pages), `documentation/` (the docs layout and pages), `partials/` |
| `styles/source.css` | The Tailwind source; built into `static/css/tailwind.css` (git-ignored) |
| `static/` | `js/`, `reel/` (the canvas kit and `reel/loops/`, the Home's animated recreations), `fonts/`, `brand/`, `marketing/media/` (the captures' derivatives, written by `make_media`, and the hero's film in `homestead/`) |
| `tests/` | Every test (see [TESTING.md](TESTING.md)) |

Later phases add `accounts`, `projects`, `forums`, `showcases`, `reports`,
`moderation` and `api` (see the plan's architectural decisions).

## Rules

- **Thin class-based views.** Logic goes in models and managers;
  cross-model workflows get a service module. Every public function in a
  deep module gets a docstring and type hints.
- **Every URL is named and app-namespaced** (`marketing:home`).
- **Access:** members-only views use `LoginRequiredMixin`; anything the
  caller can't see is a 404, never a 403. Every write is CSRF protected.
  Nothing is `csrf_exempt` (Phase 10's webhook will be the one exception).
- **Secrets** come from environment variables only, never the database.
- **Untrusted input is validated against a fixed set** before use (the
  theme cookie is the first example: only `system`, `light`, `dark`).

## URLs

| URL | Name | View |
|---|---|---|
| `/` | `marketing:home` | `HomeView` |
| `/toolbox/` | `marketing:toolbox` | `ToolboxView`: the Toolbox overview ([frontend/toolbox.md](frontend/toolbox.md)) |
| `/docs/` | `documentation:index` | `DocsIndexView`: the docs' README and a panel per section |
| `/docs/<path>/` | `documentation:page` | `DocsPageView`: a snapshot page by its lower-cased path without `.md` (`/docs/api/classes/part/`); a README is its folder; unknown paths 404 |
| `/theme/` | `marketing:theme` | `ThemeView`: POST only, the no-JavaScript fallback for the theme switch |
| `/admin/` | `admin:*` | Django admin |

## Marketing pages

- Each view mixes in `MarketingPageMixin` (`marketing/views.py`), which
  adds the nav and footer content from `marketing/content.py`, and renders
  a template extending `marketing/shell.html`.
- `content.Link` is internal (`url_name`, optionally with a `fragment`
  such as `features`), external (`external`, an https URL) or `soon` (no
  target; rendered as a "Soon" label, never a link). It refuses any other
  combination. `content.all_links()` lists every link so the tests can
  check them. External links go only to the engine's repository or the
  Toolbox's (`TOOLBOX_REPO_URL`).
- `content.Media` is one entry in the media manifest (`content.MEDIA`):
  its kind (`capture` or `illustrative`; a capture's `subject` is the
  engine or the Toolbox), caption, alt text, provenance,
  display sizes per breakpoint, and a source capture with its pixel size
  or a drawing template (optionally animated by a canvas loop). See
  [frontend/media.md](frontend/media.md).
- `marketing/media.py` (`widths_for`, `derivatives`, `build`) is the media
  pipeline; `manage.py make_media [--force]` runs it for every capture.
- Engine links point at `github.com/Axcenity-Studios/Axcenity-Engine`:
  Download at `/releases` (never `/releases/latest`: every release is a
  prerelease, so it 404s). Docs links go to `/docs/` (`documentation:index`,
  and `content.GETTING_STARTED`).
- `content.Link` takes `args` for a URL with arguments, and a `section`
  (a URL namespace) that marks it current anywhere in that section.

## The docs snapshot

- The engine repository's `documentation/` folder is the single source
  of truth. `manage.py sync_engine_docs` copies it from a commit into
  `documentation/content/`. The copy is atomic, checked against the
  commit's git tree, and checked by `Library.check()`.
- Pages render from the snapshot only: no request reads the engine
  repository, GitHub or the network. Text fixes are made in the engine
  and re-synced, never in the snapshot.
- Markdown rendering is a security boundary: raw HTML is off, and every
  link and image passes `links.resolve`'s allow-list. See
  [frontend/documentation.md](frontend/documentation.md).

## Settings

`config/settings.py`, development defaults; Phase 8 adds production
hardening.

| Variable | Default | Effect |
|---|---|---|
| `DJANGO_DEBUG` | `true` | `DEBUG`; when off, the session, CSRF and theme cookies are `Secure` |
| `DJANGO_SECRET_KEY` | a development key | Must be set in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |
| `AXCENITY_ENGINE_DIR` | `~/Documents/VSCode Projects/Axcenity-Engine` | The engine checkout `sync_engine_docs` reads (never at request time) |

`DOCS_SNAPSHOT_DIR` is `documentation/content/`; its `images/` are served
at `/static/docs/images/` (a `STATICFILES_DIRS` prefix).

Every cookie is `SameSite=Lax`. Tailwind and DaisyUI build through
django-tailwind-cli with DaisyUI's official plugin bundle
(`TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"`); see [FRONTEND.md](FRONTEND.md).
