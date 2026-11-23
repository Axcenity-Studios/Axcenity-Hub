"""Shared fixtures for the whole test suite (see docs/TESTING.md).

Two fixtures run for every test:
- the cache is cleared before and after, so nothing cached leaks between tests
- the network guard makes any outbound connection fail the test

The guard has exactly one opening: a test marked `browser` that asks for the
`browser_server` fixture may reach the live server at its own loopback IP and
port, and nothing else (no hostnames, no other ports, no other tests).
"""

import ipaddress
import socket
from urllib.parse import urlsplit

import pytest
from django.core.cache import cache

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


@pytest.fixture
def browser_server(request, network_guard):
    """The live server, reachable from a `browser` test at its own 127.0.0.1:<port> only.

    pytest's addopts bind the live server to the IP literal 127.0.0.1, so the
    guard never trusts a hostname. Any test not marked `browser` fails here.
    """
    if request.node.get_closest_marker("browser") is None:
        pytest.fail("browser_server is only for tests marked @pytest.mark.browser")
    # Loaded lazily, after the check; pytest-django gives a live server test the
    # transactional database itself only when live_server is a declared fixture.
    request.getfixturevalue("transactional_db")
    live_server = request.getfixturevalue("live_server")
    url = urlsplit(live_server.url)
    network_guard.allow(url.hostname, url.port)
    return live_server


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
