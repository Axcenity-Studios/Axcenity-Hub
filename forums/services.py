"""Writing forum posts: the rules every way in goes through.

Both functions check the email-verification gate first (accounts.access), so an
unverified member can't post or edit whichever way the request arrives. Ownership is the
views' lookup (ForumPost.objects.authored_by); `edit_post` checks it again.
"""

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from accounts.access import ensure_can_contribute

from .models import ForumPost


def create_post(author, *, title: str, body: str) -> ForumPost:
    """Publish a post by `author`. Raises EmailNotVerified for an unverified member."""
    ensure_can_contribute(author)
    post = ForumPost(author=author, title=title, body=body)
    post.full_clean()
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
