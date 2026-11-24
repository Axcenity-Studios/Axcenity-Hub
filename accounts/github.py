"""A member's linked GitHub account, checked against GitHub with their own token.

`check_link` is the one call so far: it confirms the token still works (`GET /user`), keeps
the GitHub username current, and decides what the member is shown. Phase 10's repository
calls build on the same helpers. Nothing here raises for an HTTP or network failure, logs
a token, or puts one in an exception.

- **401** (revoked, expired or unreadable token): the link is marked `needs_reconnect`, and
  GitHub isn't asked again with that token; reconnecting stores a new one.
- **Expiring tokens** (a GitHub App's user tokens): when the access token has expired and a
  refresh token is held, it's exchanged first. GitHub rotates both; the new pair is stored
  encrypted and the old refresh token is gone. A refused refresh means reconnecting.
- **Anything else** (5xx, 403, timeouts, malformed replies): UNAVAILABLE, link unchanged.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import requests
from django.conf import settings

from marketing.github import HEADERS, TIMEOUT

from . import crypto
from .models import GitHubLink

API_URL = "https://api.github.com"
USER_URL = f"{API_URL}/user"
TOKEN_URL = "https://github.com/login/oauth/access_token"
# GitHub usernames: letters, digits and single hyphens, at most 39 characters.
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
# Logs name the link by its id only: never a token, a username or a reply body.
logger = logging.getLogger(__name__)
# Refresh a little before the recorded expiry, so a request never carries a dying token.
EXPIRY_MARGIN = timedelta(minutes=1)


class LinkState(StrEnum):
    """What a check found: the link works, needs the member to reconnect, or GitHub
    couldn't be asked just now (the link is left as it was)."""

    OK = "ok"
    NEEDS_RECONNECT = "needs_reconnect"
    UNAVAILABLE = "unavailable"


def mark_needs_reconnect(link: GitHubLink) -> LinkState:
    """Record that GitHub refused the link's token; the member is asked to reconnect."""
    logger.info("GitHub link %s needs reconnecting: GitHub refused its token", link.pk)
    link.needs_reconnect = True
    link.save(update_fields=["needs_reconnect", "updated"])
    return LinkState.NEEDS_RECONNECT


def _get(link: GitHubLink, url: str) -> requests.Response | None:
    """GET `url` with the member's token; None when the request didn't complete."""
    headers = {**HEADERS, "Authorization": f"Bearer {link.access_token}"}
    try:
        return requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException:
        return None


def refresh_tokens(link: GitHubLink, *, now: datetime | None = None) -> LinkState:
    """Exchange the link's refresh token for a new access and refresh token (GitHub App).

    GitHub answers a refused refresh with a 200 and an `error` (bad_refresh_token): that
    link needs reconnecting. A failed request leaves everything as it was.
    """
    now = now or datetime.now(UTC)
    if not link.refresh_token:
        return mark_needs_reconnect(link)
    data = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": link.refresh_token,
    }
    try:
        response = requests.post(
            TOKEN_URL, data=data, headers={**HEADERS, "Accept": "application/json"}, timeout=TIMEOUT
        )
        payload = response.json() if response.status_code == 200 else None
    except (requests.RequestException, ValueError):
        payload = None
    if not isinstance(payload, dict):
        logger.warning("GitHub link %s: the token refresh couldn't reach GitHub", link.pk)
        return LinkState.UNAVAILABLE
    access = payload.get("access_token")
    if payload.get("error") or not isinstance(access, str) or not access:
        return mark_needs_reconnect(link)
    refresh = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    expires_at = (
        now + timedelta(seconds=expires_in)
        if isinstance(expires_in, int) and not isinstance(expires_in, bool) and expires_in > 0
        else None
    )
    link.set_tokens(access, refresh if isinstance(refresh, str) else "", expires_at)
    link.save(
        update_fields=[
            "access_token_encrypted", "refresh_token_encrypted", "expires_at", "updated"
        ]
    )  # fmt: skip
    logger.info("GitHub link %s: tokens refreshed and rotated", link.pk)
    return LinkState.OK


def check_link(link: GitHubLink, *, now: datetime | None = None) -> LinkState:
    """Check the link's token with GitHub, at most once per GITHUB_LINK_CHECK_INTERVAL.

    A 200 records the check and the GitHub username GitHub reports now; a 401 marks the
    link as needing reconnection. Any other failure leaves the link as it was and reports
    UNAVAILABLE. A link already marked is never sent to GitHub again.
    """
    now = now or datetime.now(UTC)
    if link.needs_reconnect:
        return LinkState.NEEDS_RECONNECT
    if link.checked_at and now - link.checked_at < settings.GITHUB_LINK_CHECK_INTERVAL:
        return LinkState.OK
    try:
        if link.expires_at and link.expires_at - EXPIRY_MARGIN <= now:
            state = refresh_tokens(link, now=now)
            if state is not LinkState.OK:
                return state
        response = _get(link, USER_URL)
    except crypto.Unreadable:
        # The key that encrypted it is gone: only a new token helps.
        return mark_needs_reconnect(link)
    except crypto.KeyMissing:
        return LinkState.UNAVAILABLE
    if response is not None and response.status_code == 401:
        return mark_needs_reconnect(link)
    if response is None or response.status_code != 200:
        status = "no reply" if response is None else response.status_code
        logger.warning("GitHub link %s: check unavailable (%s)", link.pk, status)
        return LinkState.UNAVAILABLE
    try:
        login = response.json().get("login")
    except (ValueError, AttributeError):
        return LinkState.UNAVAILABLE
    if isinstance(login, str) and LOGIN_RE.match(login) and login != link.login:
        link.account.extra_data = {**link.account.extra_data, "login": login}
        link.account.save(update_fields=["extra_data"])
    link.checked_at = now
    link.save(update_fields=["checked_at", "updated"])
    return LinkState.OK
