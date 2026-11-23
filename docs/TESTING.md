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
| `test_reel.py` | The reel without a browser: markup, labels, description, fallbacks, the scene contract and determinism rules as written (scenes, loops and drawing helpers), preloaded fonts, fidelity to the editor's default dock, Properties sections, Console messages and Dark theme |
| `test_media.py` | The media pipeline (`media.build` against a fake source in `tmp_path`: widths, formats, sizes, idempotence, size mismatch), the loops as written (registration, contract, playback rules), their markup and fallbacks, and their fidelity to the engine's words |
| `test_media_browser.py` | `browser`: every pillar's media at 360, 768, 1280, 1440 and 2560 px, dark and light, 1× and 2× (16:10, a file or canvas sharp for the pixel ratio, no sideways scroll), saved to `screenshots/media/` for review by eye; loops play only on screen and pause with their button; reduced motion shows the still; each loop is a pure function of time and wraps seamlessly |
| `test_reel_browser.py` | `browser` (Playwright): the reel mounts sharp with no console errors; play/pause and no frames while paused; Space and the marker jumps, with the range's own arrows left alone; reduced motion (and changing it live); frames as a pure function of time (seek, resize, wrap, the contract at runtime); off-screen and hidden-tab pausing; phone width; the no-canvas fallback |

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
- `open_home` (in `conftest.py`) opens Home in a fresh context whose
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

## Mocking

External HTTP (GitHub, from Phase 7) is mocked with `responses`, added
when the first external call is. Never call a live API: the guard fails
the test.

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
