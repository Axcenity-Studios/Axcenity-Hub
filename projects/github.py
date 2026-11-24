"""A member's repository on GitHub, asked with their own linked token: its details and their
permission on it.

The Hub's GitHub link is an OAuth App with **no scopes**, which GitHub documents as
"read-only access to public information (including ... repository info)". The one call is
`GET /repos/{owner}/{repo}`: it needs no scope, and its reply carries `permissions` (admin,
maintain, push, triage, pull), the member's own role on the repository. When that object is
missing or malformed the permission can't be established, and every action fails closed.

**Permission before every repository-dependent action** (`require_permission`): the
member's permission is resolved from GitHub, or reused from a check younger than
`GITHUB_PERMISSION_TTL` (60 s) for that member and repository, and never older. So a
permission GitHub revokes stops working within 60 s. Anything that stops the Hub from
establishing the permission (no linked account, a refused token, a 404, a rate limit, an
outage, a malformed reply) blocks the action; the Hub never grants more than GitHub does.

**Rate limits:** each reply's `X-RateLimit-Remaining` and `X-RateLimit-Reset`, and
`Retry-After` on a 403 or 429, set a per-member backoff: GitHub isn't asked for that member
until it ends. The Hub also spends at most `GITHUB_CALLS_PER_MEMBER_PER_HOUR` calls per member
per hour. Repeat checks send the last ETag (`If-None-Match`), and a 304 reuses what that reply
said. Nothing here raises for an HTTP or network failure, or logs a token.
"""

import logging
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

from accounts import crypto
from accounts import github as account_github
from accounts.models import GitHubLink
from marketing.github import HEADERS, TIMEOUT

API_URL = "https://api.github.com"
# owner/name: GitHub's owner names (letters, digits, single hyphens) and repository names.
FULL_NAME_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}/(?!\.\.?$)[A-Za-z0-9._-]{1,100}$"
)
# Backoff bounds when GitHub asks the Hub to wait.
DEFAULT_BACKOFF = timedelta(minutes=1)
MAX_BACKOFF = timedelta(hours=1)
# How long a member's last reply (its ETag and details) is kept for conditional requests.
KEEP_REPLY_FOR = timedelta(days=1)
logger = logging.getLogger(__name__)


class Permission(IntEnum):
    """A member's role on a repository, lowest to highest (GitHub's `permissions` keys)."""

    NONE = 0
    PULL = 1
    TRIAGE = 2
    PUSH = 3
    MAINTAIN = 4
    ADMIN = 5


class Reason(StrEnum):
    """Why an action may (OK) or may not go ahead."""

    OK = "ok"
    NO_GITHUB = "no_github"  # the member hasn't linked a GitHub account
    RECONNECT = "reconnect"  # GitHub refused the member's token
    INSUFFICIENT = "insufficient"  # GitHub reports a lower role than the action needs
    NO_ACCESS = "no_access"  # 404 (or a plain 403): gone, private, or access removed
    UNVERIFIABLE = "unverifiable"  # GitHub's reply didn't establish the permission
    RATE_LIMITED = "rate_limited"  # GitHub's limit, or the Hub's per-member budget
    UNAVAILABLE = "unavailable"  # an outage, a timeout, a 5xx


@dataclass(frozen=True)
class Repository:
    """A repository as GitHub described it to the member, checked field by field."""

    github_id: int
    full_name: str
    html_url: str
    description: str
    default_branch: str
    private: bool
    archived: bool
    pushed_at: datetime | None
    permission: Permission


@dataclass(frozen=True)
class Access:
    """The outcome of resolving a member's permission for an action.

    `repository` is GitHub's latest description when the action is allowed. `retry_at` is
    when to try again, for RATE_LIMITED.
    """

    reason: Reason
    repository: Repository | None = None
    retry_at: datetime | None = None

    @property
    def allowed(self) -> bool:
        return self.reason is Reason.OK


@dataclass(frozen=True)
class Reply:
    """One request's outcome: a Reason (OK for a 200 or 304) and what came with it."""

    reason: Reason
    payload: object = None
    etag: str = ""
    not_modified: bool = False
    retry_at: datetime | None = None


def normalize_full_name(text: str) -> str:
    """`owner/name` from what a member typed (also a github.com URL), or "" if it isn't one."""
    text = (text or "").strip()
    text = re.sub(r"^(?:https?://)?(?:www\.)?github\.com/", "", text, flags=re.I)
    text = text.removesuffix("/").removesuffix(".git")
    return text if FULL_NAME_RE.match(text) else ""


def repository_url(full_name: str) -> str:
    return f"{API_URL}/repos/{full_name}"


def _bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _timestamp(value: object) -> datetime | None:
    """GitHub's times: ISO 8601 strings, or Unix seconds in push events."""
    if isinstance(value, str):
        try:
            parsed = parse_datetime(value)
        except ValueError:
            return None
        return parsed if parsed and parsed.tzinfo else None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        try:
            return datetime.fromtimestamp(value, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def parse_details(payload: object) -> dict | None:
    """A repository object's details the Hub keeps, checked field by field, or None if any
    required one (id, owner/name, its github.com address, private, archived) is malformed."""
    if not isinstance(payload, dict):
        return None
    github_id, full_name, html_url = (
        payload.get("id"), payload.get("full_name"), payload.get("html_url")
    )  # fmt: skip
    if isinstance(github_id, bool) or not isinstance(github_id, int) or github_id <= 0:
        return None
    if not isinstance(full_name, str) or not FULL_NAME_RE.match(full_name):
        return None
    if not isinstance(html_url, str) or html_url != f"https://github.com/{full_name}":
        return None
    private, archived = _bool(payload.get("private")), _bool(payload.get("archived"))
    if private is None or archived is None:
        return None
    description = payload.get("description")
    branch = payload.get("default_branch")
    return {
        "github_id": github_id,
        "full_name": full_name,
        "html_url": html_url,
        "description": description[:2000] if isinstance(description, str) else "",
        "default_branch": branch[:255] if isinstance(branch, str) else "",
        "private": private,
        "archived": archived,
        "pushed_at": _timestamp(payload.get("pushed_at")),
    }


def parse_repository(payload: object) -> Repository | None:
    """GitHub's repository reply as a Repository, or None if any field the Hub uses is
    missing or malformed, `permissions` included (then the permission is unverifiable)."""
    details = parse_details(payload)
    if details is None:
        return None
    permissions = payload.get("permissions")
    if not isinstance(permissions, dict):
        return None
    flags = {name: _bool(permissions.get(name)) for name in ("admin", "push", "pull")}
    if None in flags.values():  # GitHub's schema requires these three
        return None
    flags |= {name: permissions.get(name) is True for name in ("maintain", "triage")}
    permission = max(
        (level for level in Permission if level and flags[level.name.lower()]),
        default=Permission.NONE,
    )
    return Repository(**details, permission=permission)


# ---------- Budget and backoff (per member, in the shared cache) ----------


def _backoff_key(user) -> str:
    return f"projects:github:retry-at:{user.pk}"


def _budget_key(user, now: datetime) -> str:
    return f"projects:github:budget:{user.pk}:{int(now.timestamp() // 3600)}"


def _back_off(user, until: datetime, now: datetime) -> datetime:
    until = min(max(until, now + timedelta(seconds=1)), now + MAX_BACKOFF)
    cache.set(_backoff_key(user), until.timestamp(), int((until - now).total_seconds()) + 1)
    return until


def backoff_until(user, now: datetime) -> datetime | None:
    """When GitHub may next be asked for `user`, if the Hub is backing off now."""
    stamp = cache.get(_backoff_key(user))
    if stamp is None or stamp <= now.timestamp():
        return None
    return datetime.fromtimestamp(stamp, UTC)


def _spend_budget(user, now: datetime) -> datetime | None:
    """Count one call against the member's hour; when it's spent, the hour's end."""
    key = _budget_key(user, now)
    cache.add(key, 0, 3600)
    try:
        used = cache.incr(key)
    except ValueError:  # evicted between add and incr
        cache.set(key, 1, 3600)
        used = 1
    if used > settings.GITHUB_CALLS_PER_MEMBER_PER_HOUR:
        return datetime.fromtimestamp((int(now.timestamp() // 3600) + 1) * 3600, UTC)
    return None


def _rate_limit_wait(response: requests.Response, now: datetime) -> datetime | None:
    """When GitHub said to come back: Retry-After, or the reset once none remain."""
    headers = response.headers
    retry_after = headers.get("Retry-After", "")
    if retry_after.isdigit():
        return now + timedelta(seconds=int(retry_after))
    reset = headers.get("X-RateLimit-Reset", "")
    if headers.get("X-RateLimit-Remaining") == "0" and reset.isdigit():
        return datetime.fromtimestamp(int(reset), UTC)
    return None


def _is_rate_limited(response: requests.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    if response.headers.get("X-RateLimit-Remaining") == "0" or "Retry-After" in response.headers:
        return True
    try:  # a secondary rate limit may come with neither header
        message = response.json().get("message", "")
    except (ValueError, AttributeError):
        return False
    return isinstance(message, str) and "rate limit" in message.lower()


# ---------- One request ----------


def member_link(user) -> GitHubLink | None:
    """The member's stored GitHub link, if they've linked an account."""
    return GitHubLink.objects.filter(account__user=user, account__provider="github").first()


def fetch_repository(user, full_name: str, *, etag: str = "", now: datetime | None = None) -> Reply:
    """GET the repository with `user`'s token, conditionally when `etag` is given.

    Spends one call of the member's budget, honours and records GitHub's rate limits, and
    marks the member's link for reconnection on a 401. Never raises for an HTTP failure.
    """
    now = now or datetime.now(UTC)
    link = member_link(user)
    if link is None:
        return Reply(Reason.NO_GITHUB)
    if link.needs_reconnect:
        return Reply(Reason.RECONNECT)
    if retry_at := backoff_until(user, now):
        return Reply(Reason.RATE_LIMITED, retry_at=retry_at)
    if retry_at := _spend_budget(user, now):
        return Reply(Reason.RATE_LIMITED, retry_at=retry_at)
    try:
        if link.expires_at and link.expires_at - account_github.EXPIRY_MARGIN <= now:
            state = account_github.refresh_tokens(link, now=now)
            if state is not account_github.LinkState.OK:
                return Reply(
                    Reason.RECONNECT
                    if state is account_github.LinkState.NEEDS_RECONNECT
                    else Reason.UNAVAILABLE
                )
        headers = {**HEADERS, "Authorization": f"Bearer {link.access_token}"}
    except crypto.Unreadable:
        account_github.mark_needs_reconnect(link)
        return Reply(Reason.RECONNECT)
    except crypto.KeyMissing:
        return Reply(Reason.UNAVAILABLE)
    if etag:
        headers["If-None-Match"] = etag
    try:
        response = requests.get(repository_url(full_name), headers=headers, timeout=TIMEOUT)
    except requests.RequestException:
        logger.warning("GitHub repository request for user %s didn't complete", user.pk)
        return Reply(Reason.UNAVAILABLE)
    wait = _rate_limit_wait(response, now)
    if response.status_code == 401:
        account_github.mark_needs_reconnect(link)
        return Reply(Reason.RECONNECT)
    if _is_rate_limited(response):
        until = _back_off(user, wait or now + DEFAULT_BACKOFF, now)
        return Reply(Reason.RATE_LIMITED, retry_at=until)
    if wait is not None:  # a reply that spent the last of the member's GitHub limit
        _back_off(user, wait, now)
    if response.status_code in (403, 404):
        return Reply(Reason.NO_ACCESS)
    if response.status_code == 304:
        return Reply(Reason.OK, etag=response.headers.get("ETag", etag), not_modified=True)
    if response.status_code != 200:
        logger.warning("GitHub repository request for user %s: %s", user.pk, response.status_code)
        return Reply(Reason.UNAVAILABLE)
    try:
        payload = response.json()
    except ValueError:
        return Reply(Reason.UNVERIFIABLE)
    return Reply(Reason.OK, payload=payload, etag=response.headers.get("ETag", "")[:200])


# ---------- Permission ----------


def _permission_key(user, full_name: str) -> str:
    return f"projects:github:permission:{user.pk}:{full_name.lower()}"


def _store(user, full_name: str, repository: Repository, etag: str, now: datetime) -> None:
    entry = {"checked_at": now.timestamp(), "etag": etag, "repository": asdict(repository)}
    cache.set(_permission_key(user, full_name), entry, int(KEEP_REPLY_FOR.total_seconds()))


def _cached(user, full_name: str) -> dict | None:
    entry = cache.get(_permission_key(user, full_name))
    return entry if isinstance(entry, dict) else None


def _repository(entry: dict) -> Repository:
    data = dict(entry["repository"])
    data["permission"] = Permission(data["permission"])
    return Repository(**data)


def forget_permission(user, full_name: str) -> None:
    """Drop the member's stored check for a repository (its next action asks GitHub)."""
    cache.delete(_permission_key(user, full_name))


def require_permission(
    user, full_name: str, needed: Permission, *, now: datetime | None = None, fresh: bool = False
) -> Access:
    """Resolve `user`'s permission on `full_name` for an action that needs `needed`.

    Call it before every repository-dependent action. A check younger than
    GITHUB_PERMISSION_TTL is reused unless `fresh` (then GitHub is asked, conditionally);
    an older one never is. Allowed only when GitHub's reply establishes a role at least
    `needed`; every failure to establish it blocks the action.
    """
    now = now or datetime.now(UTC)
    entry = _cached(user, full_name)
    age = now.timestamp() - entry["checked_at"] if entry else None
    ttl = settings.GITHUB_PERMISSION_TTL.total_seconds()
    if entry and not fresh and age is not None and 0 <= age < ttl:
        repository = _repository(entry)
    else:
        repository = _ask(user, full_name, entry, now)
        if isinstance(repository, Access):  # GitHub didn't establish it: nothing is reused
            forget_permission(user, full_name)
            return repository
    if repository.permission < needed:
        return Access(Reason.INSUFFICIENT, repository=None)
    return Access(Reason.OK, repository=repository)


def _ask(user, full_name: str, entry: dict | None, now: datetime) -> "Repository | Access":
    """Ask GitHub (conditionally, with the last reply's ETag) and record a check it answers."""
    etag = entry["etag"] if entry else ""
    reply = fetch_repository(user, full_name, etag=etag, now=now)
    if reply.reason is not Reason.OK:
        return Access(reply.reason, retry_at=reply.retry_at)
    if reply.not_modified:
        # Unchanged since that reply, the member's `permissions` included.
        if entry is None:
            return Access(Reason.UNVERIFIABLE)
        repository = _repository(entry)
        etag = reply.etag or etag
    else:
        repository = parse_repository(reply.payload)
        if repository is None:
            return Access(Reason.UNVERIFIABLE)
        etag = reply.etag
    _store(user, full_name, repository, etag, now)
    return repository
