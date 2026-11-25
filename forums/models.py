"""Forums: members' posts, their comments and ratings.

- Anyone may read a post; only its author may edit or delete it. Everyone else (another
  member, a staff member or superuser who isn't the author, or a signed-out visitor) is shown
  a 404, never a 403: `ForumPost.objects.authored_by(user)` is the only way the edit and
  delete views find a post. Admins act on others' posts through moderation (a later phase).
- Posting, editing, commenting and rating need a verified email (forums.services,
  accounts.access).
- Posts and comments carry a moderation state (reports.moderation): hidden and removed
  content is seen by staff only.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models.functions import Coalesce
from django.urls import reverse

from reports.moderation import ModeratedQuerySet, Visibility


class ForumPostQuerySet(ModeratedQuerySet):
    def authored_by(self, user) -> "ForumPostQuerySet":
        """The posts `user` wrote, the only ones they may change (none for a visitor)."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(author=user)

    def with_stats(self, user) -> "ForumPostQuerySet":
        """Each post with `comment_count` (the comments `user` may see), `rating_count` and
        `rating_average` (None without ratings). Use on posts already `visible_to(user)`: a
        post's ratings are shown only with the post."""
        comments = (
            Comment.objects.visible_to(user)
            .filter(post=models.OuterRef("pk"))
            .order_by()
            .values("post")
            .annotate(n=models.Count("pk"))
            .values("n")
        )
        ratings = Rating.objects.filter(post=models.OuterRef("pk")).order_by().values("post")
        return self.annotate(
            comment_count=Coalesce(models.Subquery(comments), 0),
            rating_count=Coalesce(
                models.Subquery(ratings.annotate(n=models.Count("pk")).values("n")), 0
            ),
            rating_average=models.Subquery(
                ratings.annotate(a=models.Avg("score")).values("a"),
                output_field=models.FloatField(),
            ),
        )


class ForumPost(models.Model):
    """A member's post in the forums: a title and a plain-text body."""

    TITLE_MAX = 120
    BODY_MAX = 10_000

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_posts"
    )
    title = models.CharField(max_length=TITLE_MAX)
    # A TextField's max_length binds only forms; the validator binds full_clean (the services).
    body = models.TextField(max_length=BODY_MAX, validators=[MaxLengthValidator(BODY_MAX)])
    created = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Set by moderation only (reports.moderation).
    state = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.VISIBLE, editable=False
    )
    # A post's reports go with it.
    reports = GenericRelation("reports.Report", related_query_name="forum_post")

    objects = ForumPostQuerySet.as_manager()

    class Meta:
        ordering = ["-created", "-pk"]
        verbose_name = "forum post"
        indexes = [models.Index(fields=["author", "created"], name="forumpost_author_created")]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("forums:detail", args=[self.pk])

    def is_author(self, user) -> bool:
        """Whether `user` wrote this post (False for a signed-out visitor)."""
        return getattr(user, "is_authenticated", False) and user.pk == self.author_id


class CommentQuerySet(ModeratedQuerySet):
    parent = "post"  # a hidden post hides its comments

    def authored_by(self, user) -> "CommentQuerySet":
        """The comments `user` wrote, the only ones they may delete (none for a visitor)."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(author=user)


class Comment(models.Model):
    """A member's plain-text comment on a post."""

    BODY_MAX = 2_000

    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_comments"
    )
    body = models.TextField(max_length=BODY_MAX, validators=[MaxLengthValidator(BODY_MAX)])
    created = models.DateTimeField(auto_now_add=True)
    # Set by moderation only (reports.moderation).
    state = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.VISIBLE, editable=False
    )
    reports = GenericRelation("reports.Report", related_query_name="forum_comment")

    objects = CommentQuerySet.as_manager()

    class Meta:
        ordering = ["created", "pk"]
        indexes = [models.Index(fields=["author", "created"], name="comment_author_created")]

    def __str__(self) -> str:
        return f"Comment by {self.author} on “{self.post}”"

    def get_absolute_url(self) -> str:
        return f"{self.post.get_absolute_url()}#comment-{self.pk}"

    def is_author(self, user) -> bool:
        """Whether `user` wrote this comment (False for a signed-out visitor)."""
        return getattr(user, "is_authenticated", False) and user.pk == self.author_id


class Rating(models.Model):
    """One member's rating of a post, 1 to 5 stars. One per member per post: rating again
    changes it."""

    LOWEST, HIGHEST = 1, 5

    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="ratings")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_ratings"
    )
    score = models.PositiveSmallIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="one_rating_per_member_per_post"),
            models.CheckConstraint(
                condition=models.Q(score__gte=1, score__lte=5), name="rating_score_1_to_5"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} rated “{self.post}” {self.score}"
