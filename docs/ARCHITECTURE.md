# Architecture

Read this before adding models, URLs, views or services. **This page is an
index:** the rules below apply everywhere; topic files under
`docs/architecture/` get written as areas grow (none exist yet).

## Layout

| Path | Holds |
|---|---|
| `config/` | Settings, root URLs, WSGI/ASGI, site-wide context processors, `theme.py` (the colour-scheme cookie) |
| `marketing/` | Public signed-out pages: Home now, Toolbox (Phase 6), Download (Phase 7). `content.py` holds their copy and links as data |
| `templates/` | `base.html` (shared by every shell), `marketing/` (the marketing shell and its pages), `partials/` |
| `styles/source.css` | The Tailwind source; built into `static/css/tailwind.css` (git-ignored) |
| `static/` | `js/`, `fonts/`, `brand/` (copied from the engine and Toolbox; never edited there) |
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
| `/theme/` | `marketing:theme` | `ThemeView`: POST only, the no-JavaScript fallback for the theme switch |
| `/admin/` | `admin:*` | Django admin |

## Marketing pages

- Each view mixes in `MarketingPageMixin` (`marketing/views.py`), which
  adds the nav and footer content from `marketing/content.py`, and renders
  a template extending `marketing/shell.html`.
- `content.Link` is internal (`url_name`), external (`external`, an https
  URL) or `soon` (no target; rendered as a "Soon" label, never a link). It
  refuses any other combination. `content.all_links()` lists every link so
  the tests can check them.
- Engine links point at `github.com/Axcenity-Studios/Axcenity-Engine`:
  Download at `/releases` (never `/releases/latest`: every release is a
  prerelease, so it 404s), Docs at the repo's `documentation/` folder.

## Settings

`config/settings.py`, development defaults; Phase 8 adds production
hardening.

| Variable | Default | Effect |
|---|---|---|
| `DJANGO_DEBUG` | `true` | `DEBUG`; when off, the session, CSRF and theme cookies are `Secure` |
| `DJANGO_SECRET_KEY` | a development key | Must be set in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |

Every cookie is `SameSite=Lax`. Tailwind and DaisyUI build through
django-tailwind-cli with DaisyUI's official plugin bundle
(`TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"`); see [FRONTEND.md](FRONTEND.md).
