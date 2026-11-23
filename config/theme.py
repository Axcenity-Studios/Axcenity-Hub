"""The site's colour scheme: System, Light or Dark.

The choice lives in the `ax-theme` cookie, for every visitor, so each page
renders in it from the first paint. Only the three known values are ever
used: anything else in the cookie or a request is treated as missing
("system") and never echoed into a page.

The cookie is a harmless display preference that the page's own script
writes (static/js/shell.js), so it is not HttpOnly. It is SameSite=Lax,
Secure whenever `settings.THEME_COOKIE_SECURE` is on (production), and lasts
a year, after which the visitor simply sees System again.
"""

from django.conf import settings
from django.http import HttpRequest, HttpResponse

COOKIE_NAME = "ax-theme"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # one year, in seconds
COOKIE_SAMESITE = "Lax"
DEFAULT_THEME = "system"
# The choices, in the order the nav's switch steps through them.
THEME_CHOICES = [("system", "System"), ("light", "Light"), ("dark", "Dark")]
THEME_LABELS = dict(THEME_CHOICES)


def is_valid_theme(value: object) -> bool:
    """True only for "system", "light" or "dark" (exact, case-sensitive strings)."""
    return isinstance(value, str) and value in THEME_LABELS


def theme_choice(request: HttpRequest) -> str:
    """The visitor's chosen scheme from their cookie, or "system" for anything unknown."""
    value = request.COOKIES.get(COOKIE_NAME, "")
    return value if is_valid_theme(value) else DEFAULT_THEME


def next_theme(choice: str) -> str:
    """The choice after `choice`, as the nav's switch steps through them."""
    keys = [key for key, _ in THEME_CHOICES]
    return keys[(keys.index(choice) + 1) % len(keys)] if choice in keys else keys[0]


def set_theme_cookie(response: HttpResponse, choice: str) -> None:
    """Store a validated `choice` on `response`. Raises ValueError for anything else."""
    if not is_valid_theme(choice):
        raise ValueError(f"Unknown theme {choice!r}")
    response.set_cookie(
        COOKIE_NAME,
        choice,
        max_age=COOKIE_MAX_AGE,
        samesite=COOKIE_SAMESITE,
        secure=settings.THEME_COOKIE_SECURE,
        httponly=False,
    )
