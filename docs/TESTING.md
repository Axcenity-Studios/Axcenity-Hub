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
| `test_download.py` | The download page: choosing the release (drafts, prereleases marked alpha, stable), GitHub's failures falling back to the cache then the plain link, the 304 and ETag, freshness and backoff, the request's headers, untrusted fields (digests, download URLs, names, sizes, malformed lists), builds by system for every real release, system detection, and the page (the highlighted build, every file reachable, sizes and SHA-256s, commands, stale and unavailable states, `Vary`, escaping, copy as data) |
| `test_documentation.py` | The docs: link rewriting and its refusals, SUMMARY.md's tree, `sync` against a fake engine repository in `tmp_path` (atomicity, refusals, idempotence, determinism) and `tree_hash` against git on sha1 and sha256 repos, Luau highlighting on the editor's own test cases, rendering as a security boundary, heading ids, front matter, the committed snapshot (build check, tree hash, its commit in the engine when checked out, diagrams), every page's title and description, a walk of every link, anchor and image, the layout's markup, badges, provenance, routing, the site's docs links and the command |
| `test_documentation_api.py` | The API reference: parsing each page shape and its refusals, type names and linked signatures, every API page's member table and anchors, type links on every page, the class layout (lead, tables, inherited group, rail), the API home without JavaScript, search ranking and query handling, the fixed queries' first results, pagination, messages, escaping, the form, the index |
| `test_documentation_browser.py` | `browser`: the longest class page at 375 px has no sideways scroll (its summary tables and inherited group included), its sidebar is a closed disclosure, and the copy button copies a block's exact text; the API home's filter narrows its lists |
| `test_hero_browser.py` | `browser` (Playwright): the film plays its AV1 source with no console errors; the button pauses and plays it; reduced motion shows the poster, followed live; off-screen and hidden-tab pausing; it covers the hero at 360 to 2560 px with its caption above its button |

Add a row when you create a file.

## Fixtures every test gets (autouse)

- **`_clear_cache`:** clears Django's cache before and after each test.
- **`network_guard`:** replaces `socket.getaddrinfo`, `gethostbyname`,
  `gethostbyname_ex`, `socket.socket.connect` and `connect_ex`. Any
  outbound connection raises `NetworkBlockedError`, a `RuntimeError` (not
  an `OSError`), so no client code can swallow it, and the test fails.
  There's no opt-out marker, and none may be added.
- **`_fast_password_hashing`:** MD5 hashing in tests, for speed only.

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
- It loads `transactional_db` before the live server, since pytest-django
  only does that itself when `live_server` is a declared fixture.

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
  release list, with the ETag GitHub sent noted in `test_download.py`).
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
- Members-only and object-access tests (redirect to login; 404, never 403)
  start in Phase 8.

## Before finishing a phase

`uv run pytest` is green, and `uv run ruff check .` and
`uv run ruff format --check .` are clean. Ruff skips Markdown files.
