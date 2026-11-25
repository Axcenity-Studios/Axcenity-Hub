"""Forums: members' posts.

- Anyone may read a post; only its author may edit or delete it. Everyone else (another
  member, a staff member or superuser who isn't the author, or a signed-out visitor) is shown
  a 404, never a 403: `ForumPost.objects.authored_by(user)` is the only way the edit and
  delete views find a post. Admins act on others' posts through moderation (a later phase).
- Posting and editing need a verified email (forums.services, accounts.access).
"""

from django.conf import settings
from django.db import models
from django.urls import reverse


class ForumPostQuerySet(models.QuerySet):
    def authored_by(self, user) -> "ForumPostQuerySet":
        """The posts `user` wrote, the only ones they may change (none for a visitor)."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(author=user)


class ForumPost(models.Model):
    """A member's post in the forums: a title and a plain-text body."""

    TITLE_MAX = 120
    BODY_MAX = 10_000

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_posts"
    )
    title = models.CharField(max_length=TITLE_MAX)
    body = models.TextField(max_length=BODY_MAX)
    created = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = ForumPostQuerySet.as_manager()

    class Meta:
        ordering = ["-created", "-pk"]
        verbose_name = "forum post"

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("forums:detail", args=[self.pk])

    def is_author(self, user) -> bool:
        """Whether `user` wrote this post (False for a signed-out visitor)."""
        return getattr(user, "is_authenticated", False) and user.pk == self.author_id
