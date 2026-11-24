"""The browser tests' live server is reachable at its own address and nowhere else.

The Playwright tests (the hero's film, the loops) run on top of `browser_server`.
"""

import socket
import urllib.request
from urllib.parse import urlsplit

import pytest

from tests.conftest import NetworkBlockedError

pytestmark = pytest.mark.browser


def test_the_live_server_serves_home_at_its_own_address(browser_server):
    with urllib.request.urlopen(browser_server.url + "/", timeout=5) as response:
        assert response.status == 200
        assert 'id="site-nav"' in response.read().decode()


def test_nothing_else_opens_for_a_browser_test(browser_server):
    port = urlsplit(browser_server.url).port
    with pytest.raises(NetworkBlockedError):
        urllib.request.urlopen(f"http://localhost:{port}/", timeout=1)
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("127.0.0.1", port + 1), timeout=1)
    with pytest.raises(NetworkBlockedError):
        urllib.request.urlopen("https://example.com", timeout=1)


def test_the_live_server_uses_the_test_database_never_the_development_one(browser_server, settings):
    from django.db import connection

    assert str(connection.settings_dict["NAME"]) != str(settings.BASE_DIR / "db.sqlite3")
    # The per-process test file (config/settings.py: DATABASES["default"]["TEST"]).
    assert str(connection.settings_dict["NAME"]) == connection.settings_dict["TEST"]["NAME"]
    assert "axcenity-hub-test-" in str(connection.settings_dict["NAME"])
