# Architecture

Read this before adding models, URLs, views or services. **This page is an
index:** the rules below apply everywhere; topic files under
`docs/architecture/` get written as areas grow:

| Open… | Before you touch… |
|---|---|
| [architecture/github-releases.md](architecture/github-releases.md) | the GitHub release list behind `/download/`: choosing and validating the release, the cache, ETag, fallbacks and backoff |
| [architecture/accounts.md](architecture/accounts.md) | accounts and sign-in: the email-verification policy and gate, case-insensitive uniqueness, sessions, password reset, rate limits, enumeration, two-factor, Turnstile, production settings |
| [architecture/github-linking.md](architecture/github-linking.md) | linking a GitHub account: linking only (never sign-in), the OAuth App and its secrets, OAuth state, encrypted tokens and key rotation, revoked and expiring tokens, unlinking |
| [architecture/projects.md](architecture/projects.md) | projects and their repositories: names, the concurrency-safe limit (`accounts/limits.py`), the no-scope permission check and its 60 s window, rate limits and budget, duplicate links, the webhook (per-link secrets, replays) |

## Layout

| Path | Holds |
|---|---|
| `config/` | Settings, root URLs, WSGI/ASGI, site-wide context processors, `theme.py` (the colour-scheme cookie), `errors.py` (every error page) |
| `marketing/` | Public signed-out pages: Home, Toolbox and Download. `content.py` holds their copy, links and media manifest as data; `drawings.py` computes the drawn media; `media.py` cuts captures into derivatives (`manage.py make_media`); `github.py` is the one GitHub request (the engine's release list) and `releases.py` chooses the release, groups its builds and caches it; `legal.py` reflows the engine's LICENSE and NOTICE into prose for the download agreement ([frontend/download.md](frontend/download.md)) |
| `documentation/` | The engine docs at `/docs/`: `sync.py` (`sync_engine_docs`), `navigation.py`, `links.py`, `rendering.py`, `highlight.py`, `library.py` (the snapshot as served, and its build check), `api.py` (API pages as structure), `search.py` (the index and ranking), `diagrams.py`, `strings.py`. See [frontend/documentation.md](frontend/documentation.md) |
| `documentation/content/` | The committed snapshot of the engine's `documentation/` folder, with `SOURCE.json` (commit and tree). Only `sync_engine_docs` writes it |
| `accounts/` | Profiles and the sign-in policy around django-allauth: the verification gate (`access.py`), the signup-only verification stage, case-insensitive unique indexes, the rate-limit backstop, Turnstile, session lifetimes ([architecture/accounts.md](architecture/accounts.md)); GitHub linking: `GitHubLink`, `crypto.py`, `github.py` ([architecture/github-linking.md](architecture/github-linking.md)); `limits.py`, the lock behind every count-based limit |
| `projects/` | Projects and their GitHub repositories: `services.py` (the limit, linking, refreshing), `github.py` (the member's repository calls and permission), `webhooks.py` ([architecture/projects.md](architecture/projects.md)) |
| `marketing/legal/` | The engine's `LICENSE` and `NOTICE`, copied in unchanged (`content.LEGAL_COMMIT`), shown in full in the download agreement |
| `marketing/media_sources/` | Captures as copied in (never served, never edited): the sources `make_media` reads, and `toolbox-capture.json`, the Toolbox screenshots' capture record |
| `templates/` | `base.html` (shared by every shell), `marketing/` (the marketing shell and its pages), `documentation/` (the docs layout and pages), `app/` (the app shell and the entrance), `allauth/` (allauth's layouts and elements), `accounts/`, `projects/`, `partials/` |
| `styles/source.css` | The Tailwind source; built into `static/css/tailwind.css` (git-ignored) |
| `static/` | `js/`, `reel/` (the canvas kit and `reel/loops/`, the Home's animated recreations), `fonts/`, `brand/`, `marketing/media/` (the captures' derivatives, written by `make_media`, and the hero's film in `homestead/`) |
| `tests/` | Every test (see [TESTING.md](TESTING.md)) |

Later phases add `forums`, `showcases`, `reports`,
`moderation` and `api` (see the plan's architectural decisions).

## Rules

- **Thin class-based views.** Logic goes in models and managers;
  cross-model workflows get a service module. Every public function in a
  deep module gets a docstring and type hints.
- **Every URL is named and app-namespaced** (`marketing:home`). The one exception is
  allauth's pages (`account_login`, `mfa_index`, ...): allauth reverses its own
  un-namespaced names. The Hub's account pages are `accounts:*`.
- **Access:** members-only views use `LoginRequiredMixin`; anything the
  caller can't see is a 404, never a 403. Every write is CSRF protected.
  Nothing is `csrf_exempt` except the repository webhook (`projects:webhook`), which
  authenticates each delivery by its signature instead.
  Views that post, create or report use `accounts.access.VerifiedEmailRequiredMixin`,
  and their services call `ensure_can_contribute(user)`.
- **Count-based limits** (5 projects; later posts, comments, showcases, reports) run in one
  transaction: `accounts.limits.lock_member(user)`, count, raise `LimitReached`, insert
  ([architecture/projects.md](architecture/projects.md#the-five-project-limit-concurrency-safe)).
- **New URLs are members-only by default:** `test_accounts_security.py` walks every
  URL, and anything not on its `PUBLIC` list must send an anonymous visitor to sign in.
- **Error pages** are the Hub's own for every status: `handler400`/`403`/`404`/`500` and
  `handler429` (allauth's rate limits) in `config/urls.py`, `CSRF_FAILURE_VIEW`, and
  `errors.ErrorPageMiddleware` for an empty 405. They render without context processors (no
  session or database, so a 500 renders even when the database failed), never echo what the
  visitor sent, and show Django's reason only under `DEBUG` ([FRONTEND.md](FRONTEND.md#error-pages)).
- **Secrets** come from environment variables only, never the database.
- **Untrusted input is validated against a fixed set** before use (the
  theme cookie is the first example: only `system`, `light`, `dark`).

## URLs

| URL | Name | View |
|---|---|---|
| `/` | `marketing:home` | `HomeView` |
| `/toolbox/` | `marketing:toolbox` | `ToolboxView`: the Toolbox overview ([frontend/toolbox.md](frontend/toolbox.md)) |
| `/download/agree/` | `marketing:download_agree` | `DownloadAgreeView`: the license agreement for `?file=<name>` (GET: terms and form; POST with CSRF and `agree=yes`: 303 to that file on GitHub). A file not in the current release is a 404 |
| `/download/` | `marketing:download` | `DownloadView`: the engine's newest release from GitHub, its builds by system ([frontend/download.md](frontend/download.md)); varies on `User-Agent` and `Sec-CH-UA-Platform` |
| `/docs/` | `documentation:index` | `DocsIndexView`: the docs' README and a panel per section |
| `/docs/search/` | `documentation:search` | `DocsSearchView`: `?q=` search over the snapshot's index, `&page=` (20 a page) |
| `/docs/<path>/` | `documentation:page` | `DocsPageView`: a snapshot page by its lower-cased path without `.md` (`/docs/api/classes/part/`); a README is its folder; API pages get their own templates; unknown paths 404 |
| `/accounts/profile/` | `accounts:profile` | `ProfileView`: the member's own profile, its photo and its form (members only); the first tab of Account settings |
| `/accounts/verify-email/` | `accounts:verify_email` | `VerifyEmailView`: where the contribution gate sends an unverified member (`?next=`, same-site only) |
| `/accounts/email/` | `account_email` | `EmailView`: the address, its status and a resend button (replaces allauth's page) |
| `/accounts/3rdparty/` | `socialaccount_connections` | `ConnectionsView`: Connected accounts, the linked GitHub account's state (checked with GitHub), link, reconnect, and unlink (POST, after re-authentication); replaces allauth's page |
| `/accounts/github/login/` | `github_login` | `GitHubConnectView`: POST starts linking GitHub (never a sign-in); replaces allauth's view |
| `/accounts/github/login/callback/` | `github_callback` | allauth: GitHub's return; links only for the signed-in member (`SocialAccountAdapter`) |
| `/accounts/…` | `account_*`, `mfa_*`, `socialaccount_*` | allauth: sign in, sign up, sign out, confirm email, password change and reset, re-authenticate, two-factor (`/accounts/2fa/…`), a cancelled or failed link (`/accounts/3rdparty/login/…`) |
| `/projects/` | `projects:list` | `ProjectListView`: the member's own projects and the count against the limit |
| `/projects/new/` | `projects:create` | `ProjectCreateView`: verified members, at most 5 projects each |
| `/projects/<slug>/` | `projects:detail` | `ProjectDetailView`: the setup checklist and the repository (refetched when over an hour old); `?webhook=show` shows the webhook's URL and secret after an admin check, never cached; owner only, others 404 |
| `/projects/<slug>/edit/`, `/delete/` | `projects:edit`, `projects:delete` | Rename (the slug follows) or describe; delete after confirming |
| `/projects/<slug>/repository/link/`, `/unlink/`, `/refresh/` | `projects:link_repository`, `projects:unlink_repository`, `projects:refresh_repository` | POST: link (needs admin on GitHub), unlink (GitHub not asked), refresh (needs read) |
| `/projects/hooks/github/<hook_id>/` | `projects:webhook` | `GitHubWebhookView`: POST only, CSRF-exempt, signed deliveries ([architecture/projects.md](architecture/projects.md#webhooks)) |
| `/errors/<kind>/` | `errors:preview` | A development server's preview of an error page (`400`, `403`, `csrf`, `404`, `405`, `429`, `500`); a 404 when `DEBUG` is off |
| `/media/<path>` | `media` | `config.media.development_media`: members' uploads from `MEDIA_ROOT` on a development server; a 404 when `DEBUG` is off (production's web server serves the folder) |
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
- Download links go to `/download/` (`marketing:download`). Engine links
  point at `github.com/Axcenity-Studios/Axcenity-Engine` (`github.ENGINE_REPO_URL`);
  the releases list is `/releases` (never `/releases/latest`: every release
  is a prerelease, so it 404s). Docs links go to `/docs/` (`documentation:index`,
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

## External APIs

- **GitHub** (Phase 7): `marketing/github.py` requests the engine's release
  list, unauthenticated, with a fixed `User-Agent`, a pinned API version, a
  timeout and `If-None-Match`. It never raises for an HTTP or network
  failure. `marketing/releases.py` caches the result in Django's cache
  (fresh for an hour, kept seven days as the fallback) and backs off after
  a failure. GitHub's data is untrusted input: every field is checked
  before use
  ([architecture/github-releases.md](architecture/github-releases.md)).
- **GitHub, as the member** (Phase 9): `accounts/github.py` checks a linked
  account's token (`GET /user`) and refreshes expiring ones, reusing
  `marketing/github.py`'s headers and timeout
  ([architecture/github-linking.md](architecture/github-linking.md)).
- **GitHub, as the member, for repositories** (Phase 10): `projects/github.py` reads
  `GET /repos/{owner}/{repo}` with the member's no-scope token: details and their permission
  (`permissions`), resolved before every repository-dependent action, with per-member
  backoff, an hourly budget and ETags ([architecture/projects.md](architecture/projects.md)).
- The cache is local memory in development. Production shares one (the
  database cache, or Redis): one list, one backoff and one set of rate limits
  for every process ([architecture/accounts.md](architecture/accounts.md)).

## Settings

`config/settings.py`: development defaults, and production when `DJANGO_DEBUG`
is off ([architecture/accounts.md](architecture/accounts.md#production-settings)).
`.env.example` lists every variable below (a test keeps it complete and value-free);
locally, copy it to `.env` (git-ignored) and run `uv run --env-file .env …`.

| Variable | Default | Effect |
|---|---|---|
| `DJANGO_DEBUG` | `true` | `DEBUG`; off is production: Secure cookies, SSL redirect, HSTS, shared cache, SMTP |
| `DJANGO_SECRET_KEY` | a development key | Required in production (50+ characters), or settings refuse to load |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated; required in production |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | none | Comma-separated `https://` origins whose form posts pass the CSRF check (`HUB_PUBLIC_URL` is added to them) |
| `DJANGO_BEHIND_PROXY`, `DJANGO_TRUSTED_PROXY_COUNT` | off, `1` | Production behind a TLS proxy: trust `X-Forwarded-Proto` and that many `X-Forwarded-For` hops |
| `DJANGO_REDIS_URL` | none | Production: Redis as the shared cache (otherwise the database cache) |
| `DJANGO_EMAIL_BACKEND` | console (dev), SMTP (production) | The default mailer's backend |
| `DJANGO_EMAIL_HOST`, `_PORT`, `_HOST_USER`, `_HOST_PASSWORD`, `_USE_TLS` | `localhost`, `587`, none, none, on | Production SMTP |
| `DJANGO_DEFAULT_FROM_EMAIL` | `Axcenity Hub <noreply@localhost>` | The sender |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | none | The GitHub OAuth App for account linking; off unless both and a token key are set |
| `GITHUB_WEBHOOK_SECRET` | none | The root secret for repository webhooks (each link's secret derives from it); webhooks are off (404) unless set |
| `HUB_PUBLIC_URL` | none | The Hub's address on the internet (scheme and host only): webhook payload URLs are built on it, its host is allowed, and it's a trusted CSRF origin (behind a tunnel or TLS proxy Django sees http while the browser posts from https); in development, a tunnel's address |
| `GITHUB_TOKEN_KEYS` | none | Comma-separated Fernet keys for GitHub tokens at rest (first encrypts); required in production when the app is set |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | none | Cloudflare Turnstile on signup and reset; off unless both are set |
| `DJANGO_MEDIA_ROOT` | `media/` in the repo (git-ignored) | Where members' uploads (profile photos) are stored; production's web server serves it at `/media/` |
| `AXCENITY_ENGINE_DIR` | `~/Documents/VSCode Projects/Axcenity-Engine` | The engine checkout `sync_engine_docs` reads (never at request time) |

`DOCS_SNAPSHOT_DIR` is `documentation/content/`; its `images/` are served
at `/static/docs/images/` (a `STATICFILES_DIRS` prefix).

Every cookie is `SameSite=Lax`. Tailwind and DaisyUI build through
django-tailwind-cli with DaisyUI's official plugin bundle
(`TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"`); see [FRONTEND.md](FRONTEND.md).
