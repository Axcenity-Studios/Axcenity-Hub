"""The app shell's rail, Account settings' tabs and header (templates/app/shell.html,
templates/accounts/base.html)."""

from allauth.mfa.models import Authenticator
from allauth.socialaccount.models import SocialAccount
from django import template
from django.urls import reverse
from django.utils import dateformat, timezone

from accounts import strings
from accounts.access import has_verified_email
from accounts.adapter import GITHUB
from accounts.models import Profile

register = template.Library()

ACCOUNT_PAGES = {key for key, *_ in strings.ACCOUNT_TABS}


def page_key(view_name: str) -> str:
    """Which page a view is: an account tab's key (allauth's two-factor pages are all
    two_factor), a rail item's key for a namespace (projects:* is projects), or ""."""
    if view_name in strings.PAGES:
        return strings.PAGES[view_name]
    namespace = view_name.split(":", 1)[0] if ":" in view_name else ""
    if namespace in strings.RAIL_NAMESPACES:
        return strings.RAIL_NAMESPACES[namespace]
    return "two_factor" if view_name.startswith("mfa_") else ""


def rail_key(view_name: str) -> str:
    """The rail item a view belongs to: every account tab is Account settings."""
    key = page_key(view_name)
    return "account" if key in ACCOUNT_PAGES else key


def current_view(context) -> str:
    match = getattr(context.get("request"), "resolver_match", None)
    return match.view_name if match else ""


def items(entries, current: str) -> list[dict]:
    return [
        {"key": key, "label": label, "href": reverse(name), "icon": icon, "current": key == current}
        for key, label, name, icon in entries
    ]


@register.simple_tag(takes_context=True)
def app_rail(context) -> list[dict]:
    """The rail's sections (Workspace, then Account for a signed-in member): each a heading
    and its items, each item with its URL and whether it's the current page."""
    current = rail_key(current_view(context))
    sections = [(strings.RAIL_HUB_HEADING, strings.RAIL_HUB)]
    if getattr(context.get("user"), "is_authenticated", False):
        sections.append((strings.RAIL_HEADING, strings.RAIL_ACCOUNT))
    return [{"heading": heading, "items": items(entries, current)} for heading, entries in sections]


@register.simple_tag(takes_context=True)
def account_tabs(context) -> list[dict]:
    """Account settings' tabs, the current page's marked."""
    return items(strings.ACCOUNT_TABS, page_key(current_view(context)))


def github_state(user) -> str:
    """ "linked", "attention" (GitHub refused the token, or none is stored) or "" (no link),
    from what the Hub last recorded: the header never asks GitHub."""
    account = (
        SocialAccount.objects.filter(user=user, provider=GITHUB)
        .select_related("github_link")
        .first()
    )
    if account is None:
        return ""
    link = getattr(account, "github_link", None)  # the reverse one-to-one, or None
    return "attention" if link is None or link.needs_reconnect else "linked"


@register.simple_tag(takes_context=True)
def member(context) -> dict | None:
    """The signed-in member as the shell shows them: name, photo or initial, and the state
    of their account (email, two-factor, GitHub). Worked out once per request."""
    request, user = context.get("request"), context.get("user")
    if not getattr(user, "is_authenticated", False):
        return None
    cached = getattr(request, "_hub_member", None)
    if cached is not None:
        return cached
    # Never written here: a member made before profiles existed gets one on the Profile page.
    profile = Profile.objects.filter(user=user).first() or Profile(user=user)
    summary = {
        "name": profile.name,
        "username": user.get_username(),
        "email": user.email,
        "initial": profile.initial,
        "photo": profile.avatar.url if profile.avatar else "",
        "bio": profile.bio,
        "since": strings.MEMBER_SINCE.format(
            date=dateformat.format(timezone.localtime(user.date_joined), "F Y")
        ),
        "verified": has_verified_email(user),
        "two_factor": Authenticator.objects.filter(
            user=user, type=Authenticator.Type.TOTP
        ).exists(),
        "github": github_state(user),
    }
    if request is not None:
        request._hub_member = summary
    return summary


@register.simple_tag
def fill(text: str, **values) -> str:
    """Copy with {placeholders} filled in: {% fill copy.CODES_LEFT unused=3 %}."""
    return text.format(**values)


@register.simple_tag
def account_copy():
    """The account pages' copy (accounts/strings.py), for templates: {% account_copy as copy %}."""
    return strings
