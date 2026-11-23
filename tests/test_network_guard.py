"""No test reaches the network; a browser test reaches only its own live server."""

import socket
import urllib.request

import pytest

from tests.conftest import NetworkBlockedError


@pytest.fixture
def listener():
    """A real socket listening on 127.0.0.1, so a connection would succeed if allowed."""
    servers = []

    def make() -> int:
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        servers.append(server)
        return server.getsockname()[1]

    yield make
    for server in servers:
        server.close()


def test_http_to_the_internet_fails_the_test():
    with pytest.raises(NetworkBlockedError):
        urllib.request.urlopen("https://example.com", timeout=1)


def test_dns_lookups_are_blocked():
    for lookup in (socket.gethostbyname, socket.gethostbyname_ex):
        with pytest.raises(NetworkBlockedError):
            lookup("example.com")
    with pytest.raises(NetworkBlockedError):
        socket.getaddrinfo("example.com", 443)


def test_loopback_is_blocked_by_default(listener):
    port = listener()
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("127.0.0.1", port), timeout=1)
    with socket.socket() as sock, pytest.raises(NetworkBlockedError):
        sock.connect_ex(("127.0.0.1", port))


def test_an_allowed_address_opens_only_that_ip_and_port(network_guard, listener):
    allowed, other = listener(), listener()
    network_guard.allow("127.0.0.1", allowed)
    socket.create_connection(("127.0.0.1", allowed), timeout=1).close()
    # Another port on the same IP, and the same port by name, stay blocked.
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("127.0.0.1", other), timeout=1)
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("localhost", allowed), timeout=1)


@pytest.mark.parametrize(
    ("host", "port"),
    [("localhost", 8000), ("example.com", 443), ("10.0.0.1", 80), ("127.0.0.1", 0)],
)
def test_only_loopback_ip_literals_with_a_real_port_can_be_allowed(network_guard, host, port):
    with pytest.raises(ValueError):
        network_guard.allow(host, port)


def test_browser_server_refuses_tests_not_marked_browser(request):
    with pytest.raises(pytest.fail.Exception, match="only for tests marked"):
        request.getfixturevalue("browser_server")
