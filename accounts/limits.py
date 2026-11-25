"""Count-based limits on what one member may create, safe under concurrent requests.

Every limit is a database count: of what a member has ("at most 5 projects"), or of what they
made within a window ("5 posts a day", "5 comments a minute": `next_allowed`). Counting and
then inserting is a race: two requests can both count four and both insert. So a limited
creation runs inside one transaction that first takes the member's lock:

    with transaction.atomic():
        lock_member(user)
        if Thing.objects.filter(owner=user).count() >= LIMIT:
            raise LimitReached(...)
        Thing.objects.create(owner=user, ...)

The lock is the member's own `auth_user` row (`SELECT ... FOR UPDATE` on PostgreSQL), so
creations by the same member queue behind each other while other members never wait. SQLite
has no row locks; there `transaction_mode = "IMMEDIATE"` (config/settings.py) makes every
transaction take the database's write lock when it begins, which serializes them all.
"""

import math
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.timesince import timeuntil


class LimitReached(Exception):
    """The member has reached a creation limit; the message says which, for the page."""


def lock_member(user) -> None:
    """Take `user`'s creation lock until the surrounding transaction ends.

    Must be called inside `transaction.atomic()`; raises TransactionManagementError otherwise.
    """
    if not transaction.get_connection().in_atomic_block:
        raise transaction.TransactionManagementError("lock_member needs transaction.atomic()")
    # Evaluated, so the lock is taken now rather than whenever the queryset is read.
    list(get_user_model().objects.select_for_update().filter(pk=user.pk).values_list("pk"))


def next_allowed(recent, *, limit: int, window: timedelta, now: datetime) -> datetime | None:
    """When a member may create again under a "`limit` per `window`" limit.

    `recent` is a queryset of that member's rows with a `created` time. Returns None while
    fewer than `limit` of them were created within `window` before `now` (a row exactly
    `window` old no longer counts), and otherwise the moment enough of them have left the
    window. Call it under `lock_member`, inside the transaction that inserts.
    """
    times = list(
        recent.filter(created__gt=now - window)
        .order_by("-created")
        .values_list("created", flat=True)[:limit]
    )
    if len(times) < limit:
        return None
    return times[-1] + window


def wait_words(until: datetime, now: datetime) -> str:
    """How long from `now` until `until`, for a limit's message: "42 seconds", "1 second",
    "3 hours, 12 minutes"."""
    seconds = max(1, math.ceil((until - now).total_seconds()))
    if seconds < 60:
        return f"{seconds} second{'' if seconds == 1 else 's'}"
    # timeuntil joins with non-breaking spaces; a message wraps like the words around it.
    return timeuntil(until, now, depth=2).replace("\xa0", " ")
