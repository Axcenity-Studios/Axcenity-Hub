"""Showcases: what members built with the engine, an image and a description each, with tags
to browse by and likes.

- Anyone may browse showcases and open one; only its author may edit or delete it. Everyone
  else (another member, a staff member who isn't the author, a signed-out visitor) is shown a
  404, never a 403: `Showcase.objects.authored_by(user)` is the only way the edit and delete
  views find a showcase.
- Publishing, editing and liking need a verified email (showcases.services, accounts.access);
  a member may publish one showcase a day.
- A showcase's address is its slug, made from its title when it's published and kept when the
  title changes, so a shared link keeps working.
- Showcases carry a moderation state (reports.moderation): hidden and removed ones are seen
  by staff only.
"""

import re

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models
from django.db.models.functions import Coalesce, Lower
from django.urls import reverse

from reports.moderation import ModeratedQuerySet, Visibility

from . import images, strings

TAG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"


class Tag(models.Model):
    """A word showcases are browsed by: lower-case letters and digits, words joined by
    hyphens (`ray-tracing`). Members make tags by using them; each is stored once, in lower
    case (a database constraint), so `Terrain` and `terrain` are one tag."""

    NAME_MIN, NAME_MAX = 2, 24

    name = models.SlugField(
        max_length=NAME_MAX,
        unique=True,
        validators=[RegexValidator(rf"\A{TAG_PATTERN}\Z", strings.TAG_INVALID)],
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(name=Lower("name")), name="tag_lower_case")
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        """The list of showcases with this tag."""
        return f"{reverse('showcases:list')}?tag={self.name}"

    @classmethod
    def parse(cls, text: str) -> list[str]:
        """The tag names in `text` (separated by commas or spaces; a leading `#` is dropped),
        in lower case, each once, in the order given. Raises ValidationError for a name that
        isn't a tag, or for more than `Showcase.TAGS_MAX` of them."""
        names = []
        for word in re.split(r"[\s,]+", text.lower()):
            word = word.lstrip("#")
            if word and word not in names:
                names.append(word)
        return cls.check_names(names)

    @classmethod
    def check_names(cls, names: list[str]) -> list[str]:
        """`names` if each is a usable tag name and there are at most `Showcase.TAGS_MAX`;
        ValidationError otherwise."""
        if len(names) > Showcase.TAGS_MAX:
            raise ValidationError(strings.TAGS_TOO_MANY, code="too_many")
        for name in names:
            if not cls.NAME_MIN <= len(name) <= cls.NAME_MAX or not re.fullmatch(TAG_PATTERN, name):
                raise ValidationError(strings.TAG_INVALID_NAMED.format(name=name), code="invalid")
        return names


class ShowcaseQuerySet(ModeratedQuerySet):
    def authored_by(self, user) -> "ShowcaseQuerySet":
        """The showcases `user` published, the only ones they may change (none for a visitor)."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(author=user)

    def with_likes(self) -> "ShowcaseQuerySet":
        """Each showcase with `like_count`."""
        likes = (
            Like.objects.filter(showcase=models.OuterRef("pk"))
            .order_by()
            .values("showcase")
            .annotate(n=models.Count("pk"))
            .values("n")
        )
        return self.annotate(like_count=Coalesce(models.Subquery(likes), 0))


class Showcase(models.Model):
    """A member's showcase: a title, a plain-text description, one image and its tags."""

    TITLE_MAX = 100
    DESCRIPTION_MAX = 5_000
    ALT_MAX = 200
    TAGS_MAX = 5
    SLUG_MAX = 60
    RESERVED_SLUGS = frozenset({"new"})

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="showcases"
    )
    title = models.CharField(max_length=TITLE_MAX)
    slug = models.SlugField(max_length=SLUG_MAX, unique=True, editable=False)
    # A TextField's max_length binds only forms; the validator binds full_clean (the services).
    description = models.TextField(
        max_length=DESCRIPTION_MAX, validators=[MaxLengthValidator(DESCRIPTION_MAX)]
    )
    # Always the Hub's own WebP (showcases.images.process), never the upload.
    image = models.ImageField(
        upload_to=images.upload_to, width_field="image_width", height_field="image_height"
    )
    image_width = models.PositiveIntegerField(default=0, editable=False)
    image_height = models.PositiveIntegerField(default=0, editable=False)
    card = models.ImageField(
        upload_to=images.card_upload_to, width_field="card_width", height_field="card_height"
    )
    card_width = models.PositiveIntegerField(default=0, editable=False)
    card_height = models.PositiveIntegerField(default=0, editable=False)
    image_alt = models.CharField(max_length=ALT_MAX, blank=True)
    tags = models.ManyToManyField(Tag, related_name="showcases", blank=True)
    created = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Set by moderation only (reports.moderation).
    state = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.VISIBLE, editable=False
    )
    # A showcase's reports go with it.
    reports = GenericRelation("reports.Report", related_query_name="showcase")

    objects = ShowcaseQuerySet.as_manager()

    class Meta:
        ordering = ["-created", "-pk"]
        indexes = [models.Index(fields=["author", "created"], name="showcase_author_created")]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("showcases:detail", kwargs={"slug": self.slug})

    def is_author(self, user) -> bool:
        """Whether `user` published this showcase (False for a signed-out visitor)."""
        return getattr(user, "is_authenticated", False) and user.pk == self.author_id

    @property
    def alt_text(self) -> str:
        """What the image shows, for people who can't see it: the author's description of
        it, or the title."""
        return self.image_alt or self.title


class Like(models.Model):
    """One member liking a showcase: once per member per showcase (a database constraint);
    liking again changes nothing, and it can be taken back."""

    showcase = models.ForeignKey(Showcase, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="showcase_likes"
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["showcase", "user"], name="one_like_per_member_per_showcase"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} likes “{self.showcase}”"
