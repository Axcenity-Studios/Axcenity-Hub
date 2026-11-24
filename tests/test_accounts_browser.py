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


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_connected_accounts_shows_a_link_needing_reconnection_and_fits_the_screen(
    open_home, settings, width, scheme
):
    from allauth.socialaccount.models import SocialAccount

    from accounts.models import GitHubLink

    settings.GITHUB_TOKEN_KEYS = ["eE5nY3VhTnJ0d1lCV0lQZ3VHWHZmS2F6c0p6Q0JxS0Q="]
    settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET = "Ov23liTestClientId", "secret"
    settings.SOCIALACCOUNT_PROVIDERS = {
        "github": {"SCOPE": [], "APPS": [{"client_id": "Ov23liTestClientId", "secret": "secret"}]}
    }
    user = get_user_model().objects.create_user("ada_lovelace", "ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email="ada@example.com", primary=True, verified=True)
    account = SocialAccount.objects.create(
        user=user, provider="github", uid="583231", extra_data={"login": "octocat"}
    )
    link = GitHubLink.objects.store(account, access_token="gho_not_a_real_token")
    link.needs_reconnect = True  # so the page never asks GitHub
    link.save()

    page, errors = open_home(path="/accounts/login/", width=width, height=800, scheme=scheme)
    page.fill("input[name=login]", "ada@example.com")
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit].btn-primary")
    page.wait_for_url("**/accounts/profile/")
    page.goto(page.url.replace("/accounts/profile/", "/accounts/3rdparty/"))

    panel = page.locator("[data-github-state=needs_reconnect]")
    assert "octocat" in panel.inner_text()
    assert page.get_by_role("button", name="Reconnect GitHub").is_visible()
    assert page.get_by_role("button", name="Unlink GitHub").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.evaluate(
        "[...document.querySelectorAll('.app-panel, .app-actions .btn')]"
        ".every(box => box.getBoundingClientRect().right <= innerWidth + 0.5)"
    )
    page.screenshot(path=f"screenshots/accounts/connections-{width}-{scheme}.png", full_page=True)
    assert errors == []
