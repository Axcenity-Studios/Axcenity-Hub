# Testing

```sh
uv run pytest -m "not browser"   # the fast suite; green before every commit
uv run pytest -m browser         # browser tests against the live server
uv run pytest                    # everything
```

All tests live in `tests/` and share one `tests/conftest.py`. pytest-django
reads `DJANGO_SETTINGS_MODULE` from `pyproject.toml`; `--strict-markers`
is on, so an unregistered marker fails.

## Test files

| File | Covers |
|---|---|
| `test_theme.py` | The palette, the accent, light mode, the contrast of every real colour pair (ported from the Toolbox), and the content colours (Luau, node headers, pins) derived from the engine's values |
| `test_shell.py` | The marketing shell: nav, phone menu, footer, links (internal ones resolve, fragments exist), branding, fonts, hover gate, motion, versioned static |
| `test_home.py` | The Home: section order, copy as data (visible prose only), the rotating headline, reveal and reduced-motion fallbacks, pillars, the media manifest (files, derivatives at their real sizes, no upscaling on 2× screens, `<picture>` markup), the Luau sample and its token kinds, drawings, honesty |
| `test_theme_switch.py` | The theme cookie (validation, attributes), pre-paint script, switch markup, `ThemeView` and CSRF |
| `test_network_guard.py` | The network guard and its single browser-test opening |
| `test_browser_server.py` | `browser`: the live server is reachable at its own address and nowhere else |
| `test_hero.py` | The hero's film without a browser: its files and size budget, the video markup (sources in order with their codecs, poster, never autoplay), caption, pause button and `home.js`'s playing rules, and `BackdropVideo`'s refusals |
| `test_canvas.py` | The canvas kit as written: only the loops and their helpers remain, the determinism rules (loops and drawing helpers), tokens only, the accent only on the scan line, preloaded fonts, fidelity to the editor's default dock, Properties, Console, Toolbox and Animation words and Dark theme |
| `test_media.py` | The media pipeline (`media.build` against a fake source in `tmp_path`: widths, formats, sizes, idempotence, size mismatch), the loops as written (registration, contract, playback rules), their markup and fallbacks, and their fidelity to the engine's words |
| `test_home_browser.py` | `browser`: the workflow and stat motifs play in view, reset once fully off screen and play again on return; rest drawn under reduced motion; sit beside their numerals and titles with no overflow from 360 to 1280 px |
| `test_media_browser.py` | `browser`: the Toolbox page's screenshots at the same widths, schemes and ratios (the scheme's own twin, 16:10, drawn whole, sharp, the other twin never fetched, no sideways scroll) and a live switch to light; every pillar's and section's media at 360, 768, 1280, 1440 and 2560 px, dark and light, 1× and 2× (16:10, a file or canvas sharp for the pixel ratio, no sideways scroll), saved to `screenshots/media/` for review by eye; loops play only on screen and pause with their button; reduced motion shows the still; each loop is a pure function of time and wraps seamlessly; the wipe's capture is never upscaled |
| `test_toolbox.py` | The Toolbox page: its URL, sections and links (nav, footer, the Home banner, the GitHub repo), copy as data, the commands (uv only; equal to the Toolbox README when its checkout is on this machine, skipped otherwise), the demo credentials' labels, the screenshots (Toolbox captions, derivatives, a `<picture>` per scheme, light twins that match their capture) and their capture record (SHA-256 of each committed file, the source commit, the demo accounts' lack of privileges) |
| `test_download.py` | The download page: choosing the release (drafts, prereleases marked alpha, stable), GitHub's failures falling back to the cache then the plain link, the 304 and ETag, freshness and backoff, the request's headers, untrusted fields (digests, download URLs, names, sizes, malformed lists), builds by system for every real release, system detection, the page (the highlighted build, every file reachable, sizes and SHA-256s, commands, stale and unavailable states, `Vary`, escaping, copy as data), the icons (every system and kind drawn and animated, decorative motifs on the button, panels, cards and tips), the tip cards filling a panel's last row, the from-source steps against the docs snapshot, a newly published release replacing the old one, and the license agreement (every link gated, the dialog, agreeing, refusals, files outside the release, CSRF, the terms against the engine's README and LICENSE when checked out, the full LICENSE and NOTICE shown word for word with the link to Credits, and `legal.reflow`'s headings, sections, sub-items and dividers) |
| `test_credits.py` | Credits: licence spellings, authors without emails, the crate list from Cargo metadata against Cargo.lock (vendored, unbuilt, refusals), the Hub's packages by group with classifier and PyPI fills, `refresh` and the command against a fake engine repository (HEAD only, nothing written in it, idempotent, refusing uncommitted changes), every package in uv.lock and every crate in the engine's Cargo.lock credited, and the page (every crate, package and font, licence groups, the NOTICE word for word with its dividers, the footer link, no subprocess) |
| `test_credits_browser.py` | `browser`: `/credits/` at 360 and 1280 px, dark and light, with no sideways scroll, a licence group opening, and the NOTICE's dividers drawn; screenshots in `screenshots/credits/` |
| `test_documentation.py` | The docs: link rewriting and its refusals, SUMMARY.md's tree, `sync` against a fake engine repository in `tmp_path` (atomicity, refusals, idempotence, determinism) and `tree_hash` against git on sha1 and sha256 repos, Luau highlighting on the editor's own test cases, rendering as a security boundary, heading ids, front matter, the committed snapshot (build check, tree hash, its commit in the engine when checked out, diagrams), every page's title and description, a walk of every link, anchor and image, the layout's markup, badges, provenance, routing, the site's docs links and the command |
| `test_documentation_api.py` | The API reference: parsing each page shape and its refusals, type names and linked signatures, every API page's member table and anchors, type links on every page, the class layout (lead, tables, inherited group, rail), the API home without JavaScript, search ranking and query handling, the fixed queries' first results, pagination, messages, escaping, the form, the index |
| `test_documentation_browser.py` | `browser`: the longest class page at 375 px has no sideways scroll (its summary tables and inherited group included), its sidebar is a closed disclosure, and the copy button copies a block's exact text; the API home's filter narrows its lists |
| `test_hero_browser.py` | `browser` (Playwright): the film plays its AV1 source with no console errors; the button pauses and plays it; reduced motion shows the poster, followed live; off-screen and hidden-tab pausing; it covers the hero at 360 to 2560 px with its caption above its button |
| `test_accounts.py` | Accounts: the contribution gate (TDD), case-insensitive uniqueness (TDD) and the index migration's duplicate check, the verification policy end to end through allauth's real signup, confirm and login views (`tests/gate_urls.py` adds a stand-in contribution view), registration rules, the admin's forms, the profile, the email and verify pages, the app shell, Account settings' rail item, tabs and header states, and entrance markup |
| `test_accounts_photos.py` | Profile photos: stored as the Hub's own 256 px WebP and shown, the initial without one, no metadata kept, refused for size, type, format and dimensions, a truncated image a form error, old files deleted on replace, remove and member deletion, `/media/` served under `DEBUG` only |
| `test_accounts_security.py` | Sessions and cookies (rotation, idle and absolute limits, server-side sign-out), CSRF on every URL (HTMX header too) and no `csrf_exempt`, password-reset tokens, rate limits on the dev and production caches and the database backstop, enumeration and hash counts, every members-only URL refusing an anonymous visitor, the honeypots, Turnstile (mocked siteverify, fail closed, never the only check) |
| `test_accounts_mfa.py` | Two-factor: enrolling (real TOTP codes from the secret), recovery codes once each, the code step that can't be skipped, rate limits on codes (cache and database), re-authentication before turning it off, session rotation |
| `test_accounts_github.py` | GitHub linking: tokens encrypted at rest and deleted on unlink (TDD), a 401 marking the link for reconnection (TDD), `check_link`'s other replies, refresh and rotation, key rotation, OAuth state (missing, unknown, another session's, reused), one account each way, linking only, the page's states, unlinking after re-authentication, no token in logs, sessions or the admin |
| `test_settings_production.py` | Production settings in a subprocess: `check --deploy --fail-level WARNING`, every security value, proxy and Redis options, refusal to start without a real secret key and hosts, or with a GitHub app but no (or a malformed) token key; `.env.example` lists every variable settings reads, with no values, and `.env` is git-ignored; development's security headers |
| `test_projects.py` | Projects: the five-project limit (TDD; one at a time and eight concurrent creations), the lock, names unique in any case (form, model and database), addresses, owners only (404 for others on every URL), the verification gate, CSRF on every project POST, the app shell, escaping |
| `test_projects_github.py` | Repositories: permission resolved before every action with its 60 s window (TDD), linking needs admin, owner/name parsing, one project per repository, no GitHub or a needs-reconnect link, every GitHub failure (401, 403, 404, 5xx, timeouts, malformed replies), expiring tokens, rate limits and backoff per member, the hourly budget, ETags and 304s, refreshing and a replaced repository, unlinking without GitHub, the pages and their notices, the webhook page, no token in logs |
| `test_errors.py` | The error pages: every status's words and handlers, the 404 for unknown addresses and others' projects (nothing echoed), the CSRF page (Django's reason under DEBUG only), a host the Hub doesn't serve (400), an empty 405 keeping `Allow`, the 500 and 429 with no database queries and the theme cookie, allauth's 429, the 403, the DEBUG-only preview, tokens only |
| `test_errors_browser.py` | `browser`: the 404, CSRF and 500 pages at 360 and 1280 px, dark and light, with no sideways scroll; screenshots in `screenshots/errors/` |
| `test_projects_setup.py` | The setup checklist: each step's state from the records (one current at a time, attention, off without webhooks and never complete then, the operator's hint in development only), the payload URL on `HUB_PUBLIC_URL`, the page at each stage, a real ping completing it, the webhook values with copy buttons and the local warning, the cards' progress, each step's help (every step and every webhook response, open by itself only on a first repository), the guide's URL gone and "guide" a usable name |
| `test_projects_browser.py` | `browser`: the empty list, each setup stage, the webhook values (the copy button copies), connected (the help open where it should be, the responses table fitting), the cards, the team pages (an Owner inviting, the invitations panel and accepting, a Viewer's page), at 360 and 1280 px, dark and light: no sideways scroll, nothing spilling past its panel; screenshots in `screenshots/projects/` |
| `test_projects_teams.py` | Teams: the role matrix through the pages (TDD), a project always keeping an Owner (TDD; stepping down, removing, leaving, deleting the account, two Owners at once), invitations (invitee only, cancelling, refusals), the ownership limit on accepting and promotion (concurrent acceptances), re-checks inside the transaction, database constraints, the pages per role, the admin, CSRF, the migration both ways |
| `test_projects_webhooks.py` | Webhooks: only the link's valid signature, replays refused per link (TDD), GitHub's published test vector, per-link secrets never stored, 404s, 405, events (ping, rename, push, deleted, other repositories and kinds), malformed and oversized deliveries, escaping |
| `test_accounts_browser.py` | `browser`: a member signs in through the form; the app shell's rail, account menu and every Account settings tab at 360 and 1280 px, dark and light, centred, with no sideways scroll; a photo uploaded through the form and shown; sign-out returns Home; Connected accounts with a link needing reconnection fits the same widths |

Add a row when you create a file.

## Fixtures every test gets (autouse)

- **`_clear_cache`:** clears Django's cache before and after each test.
- **`network_guard`:** replaces `socket.getaddrinfo`, `gethostbyname`,
  `gethostbyname_ex`, `socket.socket.connect` and `connect_ex`. Any
  outbound connection raises `NetworkBlockedError`, a `RuntimeError` (not
  an `OSError`), so no client code can swallow it, and the test fails.
  There's no opt-out marker, and none may be added.
- **`_fast_password_hashing`:** MD5 hashing in tests, for speed only.

## The test database

A SQLite **file** per test process (`DATABASES["default"]["TEST"]["NAME"]`, in the system
temp folder, removed after the run), not SQLite's shared in-memory database: that one fails
a waiting writer at once ("database table is locked") instead of queueing it, so it can't
show `accounts.limits.lock_member` working. A concurrency test uses
`django_db(transaction=True)`, one thread per attempt released together by a
`threading.Barrier`, and closes each thread's connection (`create_at_once` in
`test_projects.py`).

## Browser tests: the one opening

Browser tests (marked `browser`) use the **`browser_server`** fixture
instead of `live_server`:

- It fails any test not marked `browser`.
- It opens the guard for **exactly** the live server's `127.0.0.1:<port>`.
  `pyproject.toml`'s addopts bind the live server to that IP literal
  (`--liveserver=127.0.0.1`).
- Everything else stays blocked: `localhost` by name, other ports, and the
  internet. `NetworkGuard.allow()` refuses hostnames, non-loopback IPs and
  invalid ports.
- Every `browser` test is marked `django_db(transaction=True)` at
  collection (`pytest_collection_modifyitems`), so pytest-django sets up
  the **test** database for it. (Asked for lazily from inside the fixture,
  it came too late: a browser test run alone reached `db.sqlite3`.)
  `browser_server` also fails the test if the connection is ever the
  development database, and `test_browser_server.py` pins that.

### Playwright

- Install Chromium once: `uv run playwright install chromium`.
- Build the stylesheet first (`uv run python manage.py tailwind build`);
  the browser tests fail with that instruction if it's missing or older
  than `styles/source.css`.
- `open_home` (in `conftest.py`) opens Home (or `path=`, such as
  `"/toolbox/"`) in a fresh context whose
  requests to anything but the live server are **aborted**, and collects
  console errors. Its init script counts `requestAnimationFrame` calls
  (`window.__frames`); `scheme="light"` or `"dark"` sets the theme cookie
  first. `CONTROL_VISIBILITY` lets a test hide and show the tab.
- Show a loop's moment with its `loop-seek` event (see
  [frontend/media.md](frontend/media.md)), and compare canvases inside
  the page (`test_media_browser.py`'s `snapshot` and `changed_share`)
  rather than shipping pixels to Python.
- The module sets `DJANGO_ALLOW_ASYNC_UNSAFE`: Playwright's sync API runs
  an event loop, and the live server's database teardown is synchronous.
- Seek the way the scrubber does (set the range, fire `input` then
  `change`). Wait on the figure's `data-state`, `data-motion`, `data-size`
  and `data-ready` rather than sleeping. Two `emulate_media` switches
  within one frame cancel out: wait for each to land.

## Git in tests

`test_documentation.py` builds throwaway engine repositories in
`tmp_path` with `git` itself, isolated from the machine's config
(`GIT_CONFIG_GLOBAL=/dev/null`, no system config, a fixed identity and
date, no signing). That's local only, so the network guard is unaffected.

## Mocking

External HTTP is mocked with `responses` (`@responses.activate`). Never
call a live API: the guard fails the test, and its error is a
`RuntimeError`, so the clients' failure handling (which catches
`requests` exceptions) can't swallow it
(`test_an_unmocked_request_fails_the_test_instead_of_being_swallowed`).

- GitHub replies are built from real payloads trimmed to the fields the
  Hub reads, in `tests/fixtures/github/` (`releases.json`: the engine's
  release list, with the ETag GitHub sent noted in `test_download.py`;
  `user.json`: `/user` for GitHub's public example account; `repository.json`: GitHub's
  documented example repository, which `repo_reply(role)` gives `permissions` for).
- Repository calls take `now=`, like the releases: step past the 60 s permission window or a
  backoff instead of sleeping. `github.forget_permission` drops a member's stored check.
- Webhook deliveries: sign the exact bytes with `webhooks.signature(webhooks.secret_for(link.hook_id), body)`.
- GitHub linking never drives real OAuth: make `SocialAccount` rows
  directly, or mock the token endpoint and `/user` around allauth's real
  callback ([architecture/github-linking.md](architecture/github-linking.md#tests)).
- Pass `now=` to `releases.current_release` to step through freshness and
  backoff instead of sleeping; the autouse cache clear resets both.
- Simulate failures with `responses`' `status=`, `headers=` (`Retry-After`,
  `X-RateLimit-*`) and `body=requests.Timeout(…)`.

## Access and CSRF tests

- CSRF: use `Client(enforce_csrf_checks=True)` and check that a POST
  without a token gets **403** and changes nothing (see
  `test_the_switch_requires_a_csrf_token`).
- Untrusted input: test the hostile values too (wrong case, unknown
  values, markup), and check that they're refused or ignored and never
  echoed.
- Members-only access: `test_every_members_only_url_sends_an_anonymous_visitor_to_sign_in`
  walks every URL; a new public page must be added to its `PUBLIC` set.
  Object URLs (later phases) must give a 404, never a 403.
- CSRF everywhere: `test_every_post_without_a_csrf_token_is_refused_htmx_included`
  posts to every URL without arguments without a token, signed out and in; URLs with a slug
  get their own walk (`test_every_project_post_without_a_csrf_token_is_refused`). The only
  exempt view is the webhook (`test_only_the_repository_webhook_is_csrf_exempt`).
- Contribution views: test the gate with an unverified member (see
  `tests/gate_urls.py` and `make_member(verified=False)` in `test_accounts.py`).

## Accounts in tests

- Make members with `User.objects.create_user` plus a verified (or not)
  `EmailAddress`; sign in through `reverse("account_login")` with the
  email when the flow matters, `client.force_login` otherwise.
- Email goes to locmem (`django.core.mail.outbox`). allauth's per-address
  verification cooldown lives in the cache: `cache.clear()` stands for
  minutes passing.
- allauth announces new authenticators `on_commit`: a test that needs that
  signal uses `django_db(transaction=True)`.
- Turnstile: set Cloudflare's test keys in `settings`, and mock
  `turnstile.SITEVERIFY_URL` with `responses`.
- Rate limits: the `any_cache` fixture repeats a test on the database
  cache (production's); `tight_limits` shrinks `throttle.LIMITS` so the
  database backstop is reached with the cache cleared before each try.

## Before finishing a phase

`uv run pytest` is green, and `uv run ruff check .` and
`uv run ruff format --check .` are clean. Ruff skips Markdown files.
