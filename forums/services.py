"""Writing in the forums: the rules every way in goes through.

Posting, editing, commenting and rating check the email-verification gate first
(accounts.access), so an unverified member can't do them whichever way the request arrives;
deleting your own post or comment is never gated. Ownership is the views' lookup
(`authored_by`); the services check it again. Posting and commenting are limited per member
within a rolling window, counted under the member's creation lock (accounts.limits).
"""

from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.access import ensure_can_contribute
from accounts.limits import LimitReached, lock_member, next_allowed, wait_words

from . import strings
from .models import Comment, ForumPost, Rating

# The posting limits: database counts within a rolling window (accounts.limits).
POST_LIMIT, POST_WINDOW = 5, timedelta(days=1)
COMMENT_LIMIT, COMMENT_WINDOW = 5, timedelta(minutes=1)


class RatingRefused(Exception):
    """A rating the Hub's rules refuse; `str()` is the message for the page."""


def _within_limit(recent, *, limit: int, window: timedelta, message: str, now) -> None:
    """Raise LimitReached (with `message` filled in) when `limit` of `recent` (one member's
    rows) were made within `window`. Call under `lock_member`."""
    until = next_allowed(recent, limit=limit, window=window, now=now)
    if until is not None:
        raise LimitReached(message.format(limit=limit, wait=wait_words(until, now)))


def create_post(author, *, title: str, body: str, now: datetime | None = None) -> ForumPost:
    """Publish a post by `author`.

    Raises EmailNotVerified for an unverified member, LimitReached when they've published
    POST_LIMIT posts within POST_WINDOW (hidden and removed ones count; deleted ones don't),
    and ValidationError for an unusable title or body. `now` is for tests.
    """
    ensure_can_contribute(author)
    post = ForumPost(author=author, title=title, body=body)
    post.full_clean()
    now = now or timezone.now()
    with transaction.atomic():
        lock_member(author)
        _within_limit(
            ForumPost.objects.filter(author=author),
            limit=POST_LIMIT,
            window=POST_WINDOW,
            message=strings.POST_LIMIT_REACHED,
            now=now,
        )
        post.save()
    return post


def edit_post(user, post: ForumPost, *, title: str, body: str) -> ForumPost:
    """Change `post`'s title and body, marking when. Only its author may (PermissionDenied
    otherwise: the views never get here for anyone else, they 404 first). Raises
    EmailNotVerified for an unverified author."""
    if not post.is_author(user):
        raise PermissionDenied("Only a post's author may edit it.")
    ensure_can_contribute(user)
    post.title, post.body = title, body
    post.full_clean()
    post.edited_at = timezone.now()
    post.save(update_fields=["title", "body", "edited_at"])
    return post


def delete_post(user, post: ForumPost) -> str:
    """Delete `post`, returning its title. Only its author may (PermissionDenied otherwise;
    the views 404 first). Deleting your own post needs no verified email."""
    if not post.is_author(user):
        raise PermissionDenied("Only a post's author may delete it.")
    title = post.title
    post.delete()
    return title


def add_comment(author, post: ForumPost, *, body: str, now: datetime | None = None) -> Comment:
    """Comment on `post` as `author`.

    Raises EmailNotVerified for an unverified member, LimitReached when they've posted
    COMMENT_LIMIT comments within COMMENT_WINDOW (counted under their creation lock, so
    simultaneous requests can't slip past it), and ValidationError for an unusable body.
    `now` is for tests.
    """
    ensure_can_contribute(author)
    comment = Comment(post=post, author=author, body=body)
    comment.full_clean()
    now = now or timezone.now()
    with transaction.atomic():
        lock_member(author)
        _within_limit(
            Comment.objects.filter(author=author),
            limit=COMMENT_LIMIT,
            window=COMMENT_WINDOW,
            message=strings.COMMENT_LIMIT_REACHED,
            now=now,
        )
        comment.save()
    return comment


def delete_comment(user, comment: Comment) -> None:
    """Delete `comment`. Only its author may (PermissionDenied otherwise; the views 404
    first). Needs no verified email."""
    if not comment.is_author(user):
        raise PermissionDenied("Only a comment's author may delete it.")
    comment.delete()


def rate_post(user, post: ForumPost, score: int) -> Rating:
    """Rate `post` `score` stars (1 to 5) as `user`, replacing their earlier rating: one
    rating per member per post, which the database enforces too.

    Raises EmailNotVerified for an unverified member, RatingRefused for the post's author
    and ValidationError for a score out of range.
    """
    ensure_can_contribute(user)
    if post.is_author(user):
        raise RatingRefused(strings.RATE_OWN_POST)
    if not isinstance(score, int) or not Rating.LOWEST <= score <= Rating.HIGHEST:
        raise ValidationError(strings.RATING_OUT_OF_RANGE)
    # update_or_create locks the row, and on a race to create it reads the winner's back.
    rating, _ = Rating.objects.update_or_create(post=post, user=user, defaults={"score": score})
    return rating


def clear_rating(user, post: ForumPost) -> None:
    """Take back `user`'s rating of `post`, if any. Needs no verified email."""
    Rating.objects.filter(post=post, user=user).delete()
