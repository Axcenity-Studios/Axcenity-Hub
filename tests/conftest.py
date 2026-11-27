"""Shared fixtures for the whole test suite (see docs/TESTING.md).

Two fixtures run for every test:
- the cache is cleared before and after, so nothing cached leaks between tests
- the network guard makes any outbound connection fail the test

The guard has exactly one opening: a test marked `browser` that asks for the
`browser_server` fixture may reach the live server at its own loopback IP and
port, and nothing else (no hostnames, no other ports, no other tests).

Before collection, the run brings the credits lists up to date (below).
"""

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.core.cache import cache

from config.theme import COOKIE_NAME

# ---------- Credits, brought up to date before anything is collected ----------
# The credits tests compare marketing/legal/ with the engine's last commit and the Hub's
# uv.lock. Rather than fail whenever either moves on, the run refreshes the lists first
# (`credits.bring_up_to_date`: only when stale, nothing written in the engine) and says so
# in its header; the refreshed files are then left to commit. docs/frontend/credits.md.
_CREDITS_REPORT: list[str] = []


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    from marketing import credits

    line = credits.bring_up_to_date(Path(settings.AXCENITY_ENGINE_DIR))
    if line:
        _CREDITS_REPORT.append(line)


def pytest_report_header(config):
    return _CREDITS_REPORT


_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex


class NetworkBlockedError(RuntimeError):
    """Raised when a test tries to reach the network.

    It is deliberately not an OSError or a requests exception, so no client
    code can turn it into a friendly error: it always escapes and fails the test.
    """


def _blocked(target: object) -> None:
    raise NetworkBlockedError(
        f"A test tried to reach the network ({target!r}). Mock external HTTP instead; "
        "only a browser test's own live server is reachable (browser_server)."
    )


class NetworkGuard:
    """Blocks every outbound connection except exact (loopback IP, port) pairs allowed by a test."""

    def __init__(self) -> None:
        self._allowed: set[tuple[str, int]] = set()

    def allow(self, host: str, port: int) -> None:
        """Open one loopback IP literal and port. Hostnames, other IPs and bad ports raise ValueError."""
        ip = ipaddress.ip_address(host)  # a hostname such as "localhost" raises ValueError
        if not ip.is_loopback:
            raise ValueError(f"{host} is not a loopback address")
        if not isinstance(port, int) or not 0 < port < 65536:
            raise ValueError(f"{port!r} is not a port")
        self._allowed.add((str(ip), port))

    def is_allowed(self, host: object, port: object) -> bool:
        try:
            key = (str(ipaddress.ip_address(host)), int(port))
        except (TypeError, ValueError):
            return False
        return key in self._allowed

    def _check(self, address: object) -> None:
        if isinstance(address, tuple) and len(address) >= 2 and self.is_allowed(*address[:2]):
            return
        _blocked(address)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        guard = self

        def getaddrinfo(host, port, *args, **kwargs):
            guard._check((host, port))
            return _REAL_GETADDRINFO(host, port, *args, **kwargs)

        def connect(sock, address):
            guard._check(address)
            return _REAL_CONNECT(sock, address)

        def connect_ex(sock, address):
            guard._check(address)
            return _REAL_CONNECT_EX(sock, address)

        def resolve(host, *args, **kwargs):
            _blocked(host)

        # DNS lookup and socket connect are where every HTTP client (requests,
        # urllib, http.client) first touches the network.
        monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
        monkeypatch.setattr(socket, "gethostbyname", resolve)
        monkeypatch.setattr(socket, "gethostbyname_ex", resolve)
        monkeypatch.setattr(socket.socket, "connect", connect)
        monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def network_guard(monkeypatch) -> NetworkGuard:
    """The guard for this test. Nothing is allowed unless browser_server opens its address."""
    guard = NetworkGuard()
    guard.install(monkeypatch)
    return guard


def pytest_collection_modifyitems(items):
    """Every browser test gets the transactional test database, declared up front.

    pytest-django sets the test database up for tests that declare it (a django_db mark or
    a database fixture in their signature). Asked for lazily, from inside browser_server,
    it came too late: a browser test run on its own reached the development database,
    which a transactional test flushes at teardown. Declaring it here closes that.
    """
    for item in items:
        if item.get_closest_marker("browser") and not item.get_closest_marker("django_db"):
            item.add_marker(pytest.mark.django_db(transaction=True))


def assert_test_database() -> None:
    """Fail loudly unless the default connection is the test database."""
    from django.db import connection

    name = str(connection.settings_dict["NAME"])
    if name == str(settings.BASE_DIR / "db.sqlite3"):
        pytest.fail("A test reached the development database (db.sqlite3); see conftest.py")


@pytest.fixture
def browser_server(request, network_guard):
    """The live server, reachable from a `browser` test at its own 127.0.0.1:<port> only.

    pytest's addopts bind the live server to the IP literal 127.0.0.1, so the
    guard never trusts a hostname. Any test not marked `browser` fails here.
    """
    if request.node.get_closest_marker("browser") is None:
        pytest.fail("browser_server is only for tests marked @pytest.mark.browser")
    # The transactional test database is declared for every browser test at collection
    # (pytest_collection_modifyitems); the guard makes sure it really is the test one.
    request.getfixturevalue("transactional_db")
    assert_test_database()
    live_server = request.getfixturevalue("live_server")
    url = urlsplit(live_server.url)
    network_guard.allow(url.hostname, url.port)
    return live_server


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# ---------- Browser tests (Playwright) ----------

# Counts requestAnimationFrame calls, so a test can see that a paused loop does no work.
COUNT_FRAMES = """
window.__frames = 0;
const request = window.requestAnimationFrame.bind(window);
window.requestAnimationFrame = (callback) => { window.__frames += 1; return request(callback); };
"""

# Lets a test hide and show the tab (Playwright pages are always "visible").
CONTROL_VISIBILITY = """
window.__visibility = window.__startHidden ? "hidden" : "visible";
Object.defineProperty(document, "visibilityState", { get: () => window.__visibility });
Object.defineProperty(document, "hidden", { get: () => window.__visibility === "hidden" });
window.__setVisibility = (value) => {
  window.__visibility = value;
  document.dispatchEvent(new Event("visibilitychange"));
};
"""


@pytest.fixture(scope="session")
def built_stylesheet():
    """Browser tests need the stylesheet built from the current source."""
    stylesheet = settings.BASE_DIR / "static" / "css" / "tailwind.css"
    source = settings.BASE_DIR / "styles" / "source.css"
    if not stylesheet.exists() or stylesheet.stat().st_mtime < source.stat().st_mtime:
        pytest.fail("Build the stylesheet first: uv run python manage.py tailwind build")


@pytest.fixture
def open_home(browser, browser_server, built_stylesheet):
    """Opens Home (or the page at `path`) in a fresh context; returns (page, errors). Only the
    live server is reachable. `scheme` ("light" or "dark") sets the theme cookie first;
    `wait_ready` waits for Home's scripts and loops (Home only)."""
    contexts = []

    def open_(
        *,
        path="/",
        width=1280,
        height=800,
        scale=1,
        init="",
        wait_ready=True,
        scheme=None,
        **options,
    ):
        context = browser.new_context(
            viewport={"width": width, "height": height}, device_scale_factor=scale, **options
        )
        contexts.append(context)
        if scheme:
            context.add_cookies([{"name": COOKIE_NAME, "value": scheme, "url": browser_server.url}])
        context.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(browser_server.url)
                else route.abort()
            ),
        )
        page = context.new_page()
        errors = []
        page.on("console", lambda message: message.type == "error" and errors.append(message.text))
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script(COUNT_FRAMES + init)
        page.goto(browser_server.url + path)
        if wait_ready and path == "/":
            page.wait_for_selector("[data-film][data-state]")  # home.js has run
            page.wait_for_function(  # and every loop has mounted
                "[...document.querySelectorAll('[data-loop]')].every(f => 'live' in f.dataset)"
            )
        return page, errors

    yield open_
    for context in contexts:
        context.close()
