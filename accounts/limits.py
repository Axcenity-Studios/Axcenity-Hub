"""Count-based limits on what one member may create, safe under concurrent requests.

Every limit is a database count ("at most 5 projects", later "5 posts a day"). Counting and
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

from django.contrib.auth import get_user_model
from django.db import transaction


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
