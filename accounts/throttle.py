"""The database backstop for sign-in rate limits.

Two layers limit failed sign-ins, sign-ups, reset requests and failed two-factor codes,
each per IP address and per account:

1. allauth's rate limits (settings.ACCOUNT_RATE_LIMITS), kept in the cache. They're
   tight and trip first. Production shares the cache between processes.
2. These database counts (AuthAttempt rows), looser and over longer windows. They hold
   even when the cache is cleared, restarted or not shared, so emptying the cache never
   resets an attacker's budget.

The same refusal is given whether or not the account exists, so a limit never reveals
which emails have accounts. IPs and accounts are stored as keyed hashes only.
"""

import hashlib
import hmac
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import AuthAttempt

Kind = AuthAttempt.Kind
Scope = AuthAttempt.Scope

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)

# kind -> scope -> (how many, within what window). A request at the limit is refused.
LIMITS: dict[str, dict[str, tuple[int, timedelta]]] = {
    Kind.LOGIN_FAILED: {Scope.IP: (50, HOUR), Scope.ACCOUNT: (20, HOUR)},
    Kind.SIGNUP: {Scope.IP: (20, DAY), Scope.ACCOUNT: (5, DAY)},
    Kind.PASSWORD_RESET: {Scope.IP: (30, HOUR), Scope.ACCOUNT: (10, HOUR)},
    Kind.MFA_FAILED: {Scope.IP: (50, HOUR), Scope.ACCOUNT: (20, HOUR)},
}
# Rows older than the longest window are never counted again; they're deleted as we go.
RETENTION = DAY


def hashed(value: str) -> str:
    """A keyed hash of an IP or account, so the table never holds the value itself."""
    key = hashlib.sha256(f"accounts.throttle:{settings.SECRET_KEY}".encode()).digest()
    return hmac.new(key, value.strip().lower().encode(), hashlib.sha256).hexdigest()


def _keys(ip: str, account: str) -> dict[str, str]:
    keys = {Scope.IP: hashed(ip)} if ip else {}
    if account:
        keys[Scope.ACCOUNT] = hashed(account)
    return keys


def is_blocked(kind: str, *, ip: str, account: str = "", now: datetime | None = None) -> bool:
    """True when `ip` or `account` has used up its database budget for `kind`."""
    now = now or timezone.now()
    for scope, key in _keys(ip, account).items():
        limit, window = LIMITS[kind][scope]
        recent = AuthAttempt.objects.filter(
            kind=kind, scope=scope, key=key, created__gt=now - window
        )
        if recent.count() >= limit:
            return True
    return False


def record(kind: str, *, ip: str, account: str = "", now: datetime | None = None) -> None:
    """Count one `kind` event against `ip` and `account`, and drop expired rows."""
    now = now or timezone.now()
    AuthAttempt.objects.filter(created__lte=now - RETENTION).delete()
    AuthAttempt.objects.bulk_create(
        AuthAttempt(kind=kind, scope=scope, key=key, created=now)
        for scope, key in _keys(ip, account).items()
    )
