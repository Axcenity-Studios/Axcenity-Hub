"""The hooks moderation uses: content states, and who may see content that isn't visible.

Members' content (forum posts and comments now; showcases later) carries a `state`:
visible, hidden or removed. Phase 15's moderation actions set it; nothing else does. Content
that isn't visible is shown only to those `can_see_moderated` allows, and is missing for
everyone else (its author included) from every list, count and page, its URL a 404.

Every query that shows members' content goes through `ModeratedQuerySet.visible_to(user)`,
and every write that interacts with content (commenting, rating, reporting) through
`ModeratedQuerySet.published()`, so the rule lives here and nowhere else.
"""

from django.db import models


class Visibility(models.TextChoices):
    VISIBLE = "visible", "Visible"
    HIDDEN = "hidden", "Hidden"
    REMOVED = "removed", "Removed"


def can_see_moderated(user) -> bool:
    """Whether `user` may see hidden and removed content: staff only."""
    return bool(getattr(user, "is_authenticated", False) and user.is_staff)


class ModeratedQuerySet(models.QuerySet):
    """A queryset of content with a `state` (Visibility). Content that hangs off other
    moderated content (a comment on a post) names it in `parent`, so that hiding the parent
    hides it too."""

    parent: str = ""

    def _shown(self) -> models.Q:
        condition = models.Q(state=Visibility.VISIBLE)
        if self.parent:
            condition &= models.Q(**{f"{self.parent}__state": Visibility.VISIBLE})
        return condition

    def visible_to(self, user) -> "ModeratedQuerySet":
        """What `user` may see: everything for staff (`can_see_moderated`), and otherwise
        only visible content under a visible parent."""
        if can_see_moderated(user):
            return self
        return self.filter(self._shown())

    def published(self) -> "ModeratedQuerySet":
        """Content anyone may interact with (comment on, rate, report): visible content
        under a visible parent, for staff too."""
        return self.filter(self._shown())


def is_published(obj) -> bool:
    """Whether `obj` (a post or comment) may be interacted with, by the same rule as
    `ModeratedQuerySet.published()`."""
    return type(obj).objects.filter(pk=obj.pk).published().exists()
