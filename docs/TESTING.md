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
| `test_theme.py` | The palette, the accent, light mode, and the contrast of every real colour pair (ported from the Toolbox) |
| `test_shell.py` | The marketing shell: nav, phone menu, footer, links (internal ones resolve, fragments exist), branding, fonts, hover gate, motion, versioned static |
| `test_home.py` | The Home: section order, copy as data (visible prose only), the rotating headline, reveal and reduced-motion fallbacks, pillars, the media manifest, the Luau sample, drawings, honesty |
| `test_theme_switch.py` | The theme cookie (validation, attributes), pre-paint script, switch markup, `ThemeView` and CSRF |
| `test_network_guard.py` | The network guard and its single browser-test opening |
| `test_browser_server.py` | `browser`: the live server is reachable at its own address and nowhere else |

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

Phase 3 adds pytest-playwright and the reel smoke tests on top of it.

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
