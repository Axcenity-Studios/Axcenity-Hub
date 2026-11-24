"""The sign-in entrance and the app shell in headless Chromium: a member signs in through
the real form, and nothing scrolls sideways from a phone to a desktop, in dark and light.

Each page may reach only the live server (browser_server); every other request is
aborted. They need the built stylesheet: `uv run python manage.py tailwind build`.
`open_home` is in tests/conftest.py.
"""

import os
from urllib.parse import urlsplit

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

# Playwright's sync API runs an event loop in this thread; the database teardown
# that the live server needs is synchronous and harmless here.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PASSWORD = "a-Long-pass-7731"


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_a_member_signs_in_and_the_app_shell_fits_the_screen(open_home, width, scheme):
    user = get_user_model().objects.create_user("ada_lovelace", "ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email="ada@example.com", primary=True, verified=True)

    page, errors = open_home(path="/accounts/login/", width=width, height=800, scheme=scheme)
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    page.fill("input[name=login]", "ada@example.com")
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit].btn-primary")
    page.wait_for_url("**/accounts/profile/")

    # The rail: a closed disclosure on a phone, an open column on a desktop.
    phone = width < 1024
    assert page.evaluate("document.getElementById('app-rail').open") is (not phone)
    assert (
        page.locator(".app-rail-link[aria-current=page]").inner_text().strip() == "Profile" or phone
    )
    if phone:
        page.click(".app-rail-toggle")
        assert page.locator(".app-rail-link[aria-current=page]").inner_text().strip() == "Profile"
    # The account menu opens and holds the sign-out button; nothing pushes the page sideways.
    page.click(".app-user-button")
    assert page.locator(".app-menu-item").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.evaluate(
        "[...document.querySelectorAll('.app-user-menu, .app-panel')]"
        ".every(box => box.getBoundingClientRect().right <= innerWidth + 0.5)"
    )
    page.screenshot(path=f"screenshots/accounts/profile-{width}-{scheme}.png", full_page=True)

    # Signing out returns to Home, signed out: the nav offers Sign in again.
    page.click(".app-menu-item")
    page.wait_for_url(lambda url: urlsplit(url).path == "/")
    assert page.locator("#site-nav a.nav-sign-in").inner_text() == "Sign in" or width < 768
    assert errors == []
