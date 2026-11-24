"""The Hub's error pages: one design for every status Django or allauth answers with.

Django's handlers (`handler400`, `handler403`, `handler404`, `handler500` in config/urls.py),
allauth's rate limit (`handler429`), the CSRF failure view (`CSRF_FAILURE_VIEW`) and an empty
405 (`ErrorPageMiddleware`) all render `templates/errors/page.html`.

Every page renders **without the request's context processors**: no session, no user, no
database. A 500 may come from the database itself, and a 400 from a request whose host can't be
trusted, so the page reads only the theme cookie (already validated) and the copy below. It
never echoes the requested path or anything else the visitor sent.

With DEBUG on, Django shows its technical pages for 404 and 500 instead: open
`/errors/<kind>/` (development only) to see these.
"""

from dataclasses import dataclass

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.template import loader

from config.theme import theme_choice


@dataclass(frozen=True)
class ErrorPage:
    """One error's words: the status, its name, a headline, what happened and what to do."""

    status: int
    name: str
    title: str
    lede: str
    icon: str


PAGES = {
    "400": ErrorPage(
        400,
        "Bad request",
        "That request didn't make sense.",
        "The Hub couldn't read what your browser sent. Go back to the page you came from and "
        "try again.",
        "file",
    ),
    "403": ErrorPage(
        403,
        "Forbidden",
        "You can't do that here.",
        "This needs a permission your account doesn't have. If you think it should work, sign "
        "in with the account that owns it.",
        "lock",
    ),
    "csrf": ErrorPage(
        403,
        "Form expired",
        "That form has expired.",
        "For your security, a form only works from the page that showed it, with cookies on. "
        "Go back, reload the page, and send it again.",
        "shield",
    ),
    "404": ErrorPage(
        404,
        "Not found",
        "This page doesn't exist.",
        "It may have moved, or the address has a typo. A project shows only to the member it "
        "belongs to, so someone else's looks like this too.",
        "files",
    ),
    "405": ErrorPage(
        405,
        "Method not allowed",
        "That page doesn't work that way.",
        "The page exists, but not for this kind of request. Open it from a link or a button on "
        "the site instead.",
        "close",
    ),
    "429": ErrorPage(
        429,
        "Too many requests",
        "Slow down a moment.",
        "That was tried too many times in a short while. Wait a few minutes, then try again.",
        "history",
    ),
    "500": ErrorPage(
        500,
        "Server error",
        "Something broke on our side.",
        "The Hub hit an error it couldn't recover from. It wasn't anything you did. Try again "
        "in a moment.",
        "build",
    ),
}

# Where to go from any error page: (label, URL name). Nothing here needs the visitor's session.
ACTIONS = [
    ("Go to the home page", "marketing:home"),
    ("Read the docs", "documentation:index"),
    ("Your projects", "projects:list"),
]
COPY = {
    "eyebrow": "Error",
    "home": "Axcenity home",
    "debug_heading": "Development only",
    "csrf_debug_hint": (
        "Signing in through a tunnel or proxy? The browser posts from its https:// address "
        "while the Hub sees http. Set HUB_PUBLIC_URL to that address and restart."
    ),
}


def render_error(request: HttpRequest | None, kind: str, *, detail: str = "") -> HttpResponse:
    """The error page for `kind` (a key of PAGES) with its status code.

    `detail` is shown only on a development server (DEBUG); it's for the developer, never the
    visitor. Rendering touches no session or database.
    """
    page = PAGES[kind]
    try:
        choice = theme_choice(request) if request is not None else "system"
    except Exception:  # noqa: BLE001 (an error page must render whatever went wrong)
        choice = "system"
    context = {
        "page": page,
        "kind": kind,
        "actions": ACTIONS,
        "copy": COPY,
        "theme_choice": choice,
        "detail": detail if settings.DEBUG else "",
        "debug_hint": COPY["csrf_debug_hint"] if settings.DEBUG and kind == "csrf" else "",
    }
    html = loader.render_to_string("errors/page.html", context)
    response = HttpResponse(html, status=page.status)
    response["Cache-Control"] = "no-store"
    return response


def bad_request(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """handler400: a malformed request, or a host the Hub doesn't serve."""
    return render_error(request, "400")


def permission_denied(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """handler403. (The Hub answers 404 for what a member doesn't own; this is rarer.)"""
    return render_error(request, "403")


def page_not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """handler404."""
    return render_error(request, "404")


def server_error(request: HttpRequest) -> HttpResponse:
    """handler500: no context processors, no database."""
    return render_error(request, "500")


def too_many_requests(request: HttpRequest) -> HttpResponse:
    """handler429: allauth's rate limits (sign-in, sign-up, resets, codes)."""
    return render_error(request, "429")


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """CSRF_FAILURE_VIEW: a form posted without a valid token (or from an untrusted origin)."""
    return render_error(request, "csrf", detail=reason)


def preview(request: HttpRequest, kind: str) -> HttpResponse:
    """`/errors/<kind>/`: a development server's preview of each page (a 404 otherwise)."""
    if not settings.DEBUG or kind not in PAGES:
        raise Http404
    detail = "Origin checking failed - https://hub.example.com does not match any trusted origins."
    return render_error(request, kind, detail=detail if kind == "csrf" else "")


class ErrorPageMiddleware:
    """Gives an empty 405 (Django's `http_method_not_allowed`) the Hub's page, keeping `Allow`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code == 405 and not getattr(response, "content", b"x"):
            page = render_error(request, "405")
            if "Allow" in response:
                page["Allow"] = response["Allow"]
            return page
        return response
