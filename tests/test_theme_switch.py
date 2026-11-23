"""The System / Light / Dark switch: validated values, a safe cookie, and no flash."""

import re

import pytest
from django.conf import settings
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

from config import theme

pytestmark = pytest.mark.django_db

SHELL_JS = (settings.BASE_DIR / "static" / "js" / "shell.js").read_text(encoding="utf-8")
HOSTILE = ["", "System", "LIGHT", "blue", '"><script>alert(1)</script>', "light; dark", "dark\n"]
# The same, as they could arrive in a raw Cookie header (a ";" would start a new cookie).
RAW_HOSTILE = [
    "",
    "System",
    "LIGHT",
    "blue",
    '"><script>alert(1)</script>',
    "dark%0A",
    "light,dark",
]


# ---------- Reading the choice ----------


@pytest.mark.parametrize("value", ["system", "light", "dark"])
def test_a_known_cookie_value_is_used(value):
    request = RequestFactory().get("/", HTTP_COOKIE=f"{theme.COOKIE_NAME}={value}")
    assert theme.theme_choice(request) == value


@pytest.mark.parametrize("value", HOSTILE)
def test_anything_else_in_the_cookie_is_system(value):
    request = RequestFactory().get("/")
    request.COOKIES[theme.COOKIE_NAME] = value
    assert theme.theme_choice(request) == "system"


def test_is_valid_theme_accepts_only_the_three_exact_strings():
    assert all(theme.is_valid_theme(value) for value in ("system", "light", "dark"))
    for value in [*HOSTILE, None, 1, ["light"]]:
        assert not theme.is_valid_theme(value), value


# ---------- Rendering: before first paint, never echoing bad input ----------


@pytest.mark.parametrize("value", ["light", "dark"])
def test_light_or_dark_is_set_on_html_by_the_server(client, value):
    client.cookies[theme.COOKIE_NAME] = value
    html = client.get(reverse("marketing:home")).content.decode()
    assert re.search(rf'<html [^>]*data-scheme-choice="{value}" data-scheme="{value}"', html)


@pytest.mark.parametrize("value", RAW_HOSTILE)
def test_a_hostile_cookie_renders_as_system_and_is_never_echoed(client, value):
    html = client.get(
        reverse("marketing:home"), HTTP_COOKIE=f"{theme.COOKIE_NAME}={value}"
    ).content.decode()
    tag = re.search(r"<html [^>]*>", html).group(0)
    assert 'data-scheme-choice="system"' in tag and "data-scheme=" not in tag
    assert "<script>alert(1)</script>" not in html and "alert(1)" not in html


def test_system_is_resolved_before_first_paint(client):
    head = client.get(reverse("marketing:home")).content.decode().split("</head>", 1)[0]
    script = re.search(r"<script>(.*?)</script>", head, re.S).group(1)
    assert 'matchMedia("(prefers-color-scheme: light)")' in script
    assert 'query.addEventListener("change", apply)' in script  # follows the OS live
    # The inline script also refuses anything but the three values.
    assert 'if (!CHOICES[choice]) choice = root.dataset.schemeChoice = "system";' in script
    # It runs before the stylesheet loads, so the page never paints in the wrong scheme.
    assert head.index("<script>") < head.index('rel="stylesheet"')


# ---------- The switch ----------


@pytest.mark.parametrize(
    ("current", "label", "next_value", "next_label"),
    [
        ("system", "System", "light", "Light"),
        ("light", "Light", "dark", "Dark"),
        ("dark", "Dark", "system", "System"),
    ],
)
def test_the_switch_offers_the_next_choice(client, current, label, next_value, next_label):
    client.cookies[theme.COOKIE_NAME] = current
    html = client.get(reverse("marketing:home")).content.decode()
    button = re.search(r'<button type="submit" id="theme-toggle"[^>]*>', html).group(0)
    assert f'value="{next_value}"' in button
    assert f'aria-label="Theme: {label}. Switch to {next_label}"' in button


def test_the_switch_is_a_csrf_protected_post_form(client):
    html = client.get(reverse("marketing:home")).content.decode()
    form = re.search(
        rf'<form method="post" action="{reverse("marketing:theme")}"[^>]*>(.*?)</form>', html, re.S
    )
    assert form
    assert 'name="csrfmiddlewaretoken"' in form.group(1)
    assert '<input type="hidden" name="next" value="/">' in form.group(1)


def test_the_script_writes_only_known_values_with_safe_cookie_attributes():
    assert 'var SCHEMES = ["system", "light", "dark"];' in SHELL_JS
    assert "if (SCHEMES.indexOf(choice) === -1) return;" in SHELL_JS
    assert '"; path=/; max-age=" + COOKIE_MAX_AGE + "; SameSite=Lax"' in SHELL_JS
    assert 'if (location.protocol === "https:") cookie += "; Secure";' in SHELL_JS
    assert "var COOKIE_MAX_AGE = 365 * 24 * 60 * 60;" in SHELL_JS
    assert theme.COOKIE_MAX_AGE == 365 * 24 * 60 * 60


# ---------- The no-JavaScript fallback view ----------


def _post(client, **data):
    return client.post(reverse("marketing:theme"), data)


@pytest.mark.parametrize("choice", ["system", "light", "dark"])
def test_posting_a_choice_sets_a_lax_year_long_cookie(client, choice):
    response = _post(client, choice=choice, next="/")
    assert response.status_code == 302 and response.url == "/"
    cookie = response.cookies[theme.COOKIE_NAME]
    assert cookie.value == choice
    assert cookie["samesite"] == "Lax"
    assert cookie["max-age"] == 365 * 24 * 60 * 60
    assert cookie["path"] == "/"
    assert not cookie["secure"]  # development; see the next test for production


def test_the_cookie_is_secure_in_production(client, settings):
    settings.THEME_COOKIE_SECURE = True
    cookie = _post(client, choice="dark").cookies[theme.COOKIE_NAME]
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Lax"


def test_production_settings_turn_secure_on():
    """THEME_COOKIE_SECURE follows DEBUG, like the session and CSRF cookies."""
    source = (settings.BASE_DIR / "config" / "settings.py").read_text(encoding="utf-8")
    assert "THEME_COOKIE_SECURE = not DEBUG" in source
    assert 'SESSION_COOKIE_SAMESITE = "Lax"' in source and 'CSRF_COOKIE_SAMESITE = "Lax"' in source


@pytest.mark.parametrize("value", [*HOSTILE, None])
def test_an_unknown_choice_is_refused_and_sets_nothing(client, value):
    response = _post(client, **({} if value is None else {"choice": value}))
    assert response.status_code == 400
    assert theme.COOKIE_NAME not in response.cookies


def test_set_theme_cookie_refuses_unknown_values():
    with pytest.raises(ValueError):
        theme.set_theme_cookie(HttpResponse(), "blue")


@pytest.mark.parametrize(
    "next_url", ["https://evil.example/", "//evil.example/", "javascript:alert(1)"]
)
def test_off_site_next_goes_home(client, next_url):
    response = _post(client, choice="light", next=next_url)
    assert response.status_code == 302 and response.url == reverse("marketing:home")


def test_the_switch_requires_a_csrf_token():
    response = Client(enforce_csrf_checks=True).post(
        reverse("marketing:theme"), {"choice": "light"}
    )
    assert response.status_code == 403
    assert theme.COOKIE_NAME not in response.cookies


def test_the_switch_only_accepts_post(client):
    assert client.get(reverse("marketing:theme")).status_code == 405
