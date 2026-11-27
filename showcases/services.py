"""Publishing showcases: the rules every way in goes through.

Publishing, editing and liking check the email-verification gate first (accounts.access);
deleting your own showcase or taking back a like is never gated. Ownership is the views'
lookup (`authored_by`); the services check it again. A member may publish one showcase within
any 24 hours, counted under their creation lock (accounts.limits), so simultaneous requests
can't slip a second past it.

Images arrive already checked and remade (showcases.images); the services write them to
storage only once everything else has passed, and delete files nothing refers to any more.
"""

import uuid
from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.access import ensure_can_contribute
from accounts.limits import LimitReached, lock_member, next_allowed, wait_words

from . import strings
from .images import Processed
from .models import Like, Showcase, Tag

# The publishing limit: a database count within a rolling window (accounts.limits).
SHOWCASE_LIMIT, SHOWCASE_WINDOW = 1, timedelta(days=1)
# How many numbered slugs (`title-2`, `title-3`, …) to try before a random suffix.
SLUG_ATTEMPTS = 20


class LikeRefused(Exception):
    """A like the Hub's rules refuse; `str()` is the message for the page."""


def slug_candidates(title: str):
    """The addresses a showcase called `title` may take, in order: the title slugified (or
    `showcase` when nothing of it is left), then numbered ones, then random ones."""
    base = slugify(title)[: Showcase.SLUG_MAX - 9].strip("-") or "showcase"
    if base not in Showcase.RESERVED_SLUGS:
        yield base
    for n in range(2, SLUG_ATTEMPTS + 2):
        yield f"{base}-{n}"
    while True:
        yield f"{base}-{uuid.uuid4().hex[:8]}"


def _set_tags(showcase: Showcase, names: list[str]) -> None:
    tags = []
    for name in names:
        tag, _ = Tag.objects.get_or_create(name=name)
        tags.append(tag)
    showcase.tags.set(tags)


def _save_files(showcase: Showcase, processed: Processed) -> list[str]:
    """Write `processed` to storage as `showcase`'s images, returning the names written."""
    showcase.image.save(processed.display.name, processed.display, save=False)
    showcase.card.save(processed.card.name, processed.card, save=False)
    return [showcase.image.name, showcase.card.name]


def delete_files(names) -> None:
    """Delete these stored files, if they exist."""
    for name in names:
        if name:
            default_storage.delete(name)


def limit_message(author, *, now: datetime | None = None) -> str:
    """The publishing limit's message if `author` can't publish now, "" if they can. For the
    page only: `create_showcase` decides, under the lock."""
    now = now or timezone.now()
    until = next_allowed(
        Showcase.objects.filter(author=author),
        limit=SHOWCASE_LIMIT,
        window=SHOWCASE_WINDOW,
        now=now,
    )
    if until is None:
        return ""
    return strings.SHOWCASE_LIMIT_REACHED.format(limit=SHOWCASE_LIMIT, wait=wait_words(until, now))


def create_showcase(
    author,
    *,
    title: str,
    description: str,
    image: Processed,
    tags: list[str] = (),
    image_alt: str = "",
    now: datetime | None = None,
) -> Showcase:
    """Publish a showcase by `author`.

    Raises EmailNotVerified for an unverified member, LimitReached when they've published
    SHOWCASE_LIMIT showcases within SHOWCASE_WINDOW (hidden and removed ones count; deleted
    ones don't), and ValidationError for an unusable title, description or tag. `image` comes
    from `images.process`. `now` is for tests.
    """
    ensure_can_contribute(author)
    names = Tag.check_names(list(tags))
    showcase = Showcase(author=author, title=title, description=description, image_alt=image_alt)
    showcase.full_clean(exclude=["slug", "image", "card"])
    now = now or timezone.now()
    written: list[str] = []
    try:
        with transaction.atomic():
            lock_member(author)
            if message := limit_message(author, now=now):
                raise LimitReached(message)
            written = _save_files(showcase, image)
            # The slug's unique index decides between two showcases of the same title.
            for slug in slug_candidates(title):
                showcase.slug = slug
                try:
                    with transaction.atomic():
                        showcase.save()
                    break
                except IntegrityError:
                    continue
            _set_tags(showcase, names)
    except BaseException:
        delete_files(written)
        raise
    return showcase


def edit_showcase(
    user,
    showcase: Showcase,
    *,
    title: str,
    description: str,
    tags: list[str] = (),
    image_alt: str = "",
    image: Processed | None = None,
) -> Showcase:
    """Change `showcase`'s words and tags, and its image when `image` is given (the old
    image's files are deleted), marking when. Its address stays the same. Only its author may
    (PermissionDenied otherwise: the views 404 first). Raises EmailNotVerified for an
    unverified author and ValidationError for unusable words or tags."""
    if not showcase.is_author(user):
        raise PermissionDenied("Only a showcase's author may edit it.")
    ensure_can_contribute(user)
    names = Tag.check_names(list(tags))
    showcase.title, showcase.description, showcase.image_alt = title, description, image_alt
    showcase.full_clean(exclude=["slug", "image", "card"])
    old = [showcase.image.name, showcase.card.name] if image else []
    written: list[str] = []
    try:
        with transaction.atomic():
            if image:
                written = _save_files(showcase, image)
            showcase.edited_at = timezone.now()
            showcase.save()
            _set_tags(showcase, names)
    except BaseException:
        delete_files(written)
        raise
    delete_files(old)
    return showcase


def delete_showcase(user, showcase: Showcase) -> str:
    """Delete `showcase` and its images, returning its title. Only its author may
    (PermissionDenied otherwise; the views 404 first). Needs no verified email."""
    if not showcase.is_author(user):
        raise PermissionDenied("Only a showcase's author may delete it.")
    title = showcase.title
    showcase.delete()  # its files go with it (showcases.signals)
    return title


def like(user, showcase: Showcase) -> Like:
    """Like `showcase` as `user`; liking it again changes nothing (one like per member per
    showcase, which the database enforces). Raises EmailNotVerified for an unverified member
    and LikeRefused for its author."""
    ensure_can_contribute(user)
    if showcase.is_author(user):
        raise LikeRefused(strings.LIKE_OWN)
    try:
        with transaction.atomic():
            return Like.objects.get_or_create(showcase=showcase, user=user)[0]
    except IntegrityError:  # a simultaneous like won the race
        return Like.objects.get(showcase=showcase, user=user)


def unlike(user, showcase: Showcase) -> None:
    """Take back `user`'s like of `showcase`, if any. Needs no verified email."""
    Like.objects.filter(showcase=showcase, user=user).delete()


def has_liked(user, showcase: Showcase) -> bool:
    """Whether `user` likes `showcase` (False for a visitor)."""
    if not getattr(user, "is_authenticated", False):
        return False
    return Like.objects.filter(showcase=showcase, user=user).exists()
