"""Projects: a member's Hub project, the GitHub repository linked to it, and the webhook
deliveries received for that repository.

- A member owns at most `Project.LIMIT_PER_OWNER` projects (projects.services.create_project).
- Project names are unique across the Hub whatever their case, and so are their slugs (the
  slug is the name, slugified, and follows renames). Both are database constraints.
- A GitHub repository can be linked to one Hub project only: `RepositoryLink.github_id` (the
  repository's numeric id, which survives renames and transfers) is unique.
- A webhook delivery is accepted once per link: its delivery id and its body's SHA-256 are
  each unique per link (projects.webhooks).
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.text import slugify

from . import strings


class ProjectQuerySet(models.QuerySet):
    def owned_by(self, user) -> "ProjectQuerySet":
        """The projects `user` owns (none for an anonymous visitor)."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(owner=user)


class Project(models.Model):
    """A member's project in the Hub, optionally linked to one GitHub repository."""

    NAME_MAX = 60
    DESCRIPTION_MAX = 500
    LIMIT_PER_OWNER = 5
    # Slugs that would shadow the app's own URLs (/projects/new/, /projects/hooks/).
    RESERVED_SLUGS = frozenset({"new", "hooks"})

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(
        max_length=NAME_MAX,
        help_text="Unique across the Hub (letter case doesn't count). It sets the address.",
    )
    slug = models.SlugField(max_length=NAME_MAX, unique=True, editable=False)
    description = models.TextField(
        max_length=DESCRIPTION_MAX, blank=True, help_text="What it is, in plain text."
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="projects_project_name_ci_unique",
                violation_error_message=strings.NAME_TAKEN,
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("projects:detail", kwargs={"slug": self.slug})

    def clean(self) -> None:
        """The name's rules: not blank, gives a usable address, and not taken (any case)."""
        self.name = " ".join((self.name or "").split())
        self.slug = slugify(self.name)
        if not self.name:
            raise ValidationError({"name": ValidationError(strings.NAME_REQUIRED, "required")})
        if not self.slug or self.slug in self.RESERVED_SLUGS:
            raise ValidationError({"name": strings.NAME_UNUSABLE})
        others = Project.objects.exclude(pk=self.pk)
        if others.filter(models.Q(name__iexact=self.name) | models.Q(slug=self.slug)).exists():
            raise ValidationError({"name": strings.NAME_TAKEN})

    def validate_constraints(self, exclude=None) -> None:
        # The LOWER(name) constraint has no field of its own: its error belongs to the name.
        try:
            super().validate_constraints(exclude=exclude)
        except ValidationError as error:
            if strings.NAME_TAKEN in error.messages:
                raise ValidationError({"name": strings.NAME_TAKEN}) from None
            raise

    def validate_unique(self, exclude=None) -> None:
        # clean() reports a taken address as the name's error; the slug's unique index stays
        # the database's backstop.
        super().validate_unique(exclude={*(exclude or ()), "slug"})


class RepositoryLink(models.Model):
    """The GitHub repository linked to a project, as GitHub last described it.

    The details are kept current by the repository's webhook (projects.webhooks) and by
    conditional requests with `etag` (projects.github). `hook_id` is the random part of the
    webhook's URL; the webhook's secret is derived from it (projects.webhooks.secret_for).
    """

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="repository")
    github_id = models.BigIntegerField(
        unique=True, help_text="GitHub's id for the repository: one Hub project per repository."
    )
    full_name = models.CharField(max_length=140, help_text="owner/name on GitHub.")
    html_url = models.URLField(max_length=300)
    description = models.TextField(blank=True)
    default_branch = models.CharField(max_length=255, blank=True)
    private = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    pushed_at = models.DateTimeField(null=True, blank=True)
    deleted_on_github = models.BooleanField(default=False)
    hook_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    etag = models.CharField(max_length=200, blank=True, editable=False)
    fetched_at = models.DateTimeField(null=True, blank=True)
    webhook_shown_at = models.DateTimeField(
        null=True, blank=True, help_text="When the owner last opened the webhook's settings."
    )
    webhook_at = models.DateTimeField(
        null=True, blank=True, help_text="When GitHub's last webhook delivery arrived."
    )
    first_webhook_at = models.DateTimeField(
        null=True, blank=True, help_text="When GitHub's first webhook delivery arrived."
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.full_name} → {self.project}"


class WebhookDelivery(models.Model):
    """One webhook delivery accepted for a repository link, kept to refuse replays.

    GitHub signs the body but not the `X-GitHub-Delivery` header, so a captured body could
    be replayed under a new delivery id: the body's SHA-256 is unique per link too.
    Identical bodies sent for different links don't interfere.
    """

    link = models.ForeignKey(RepositoryLink, on_delete=models.CASCADE, related_name="deliveries")
    delivery_id = models.CharField(max_length=64)
    body_sha256 = models.CharField(max_length=64)
    event = models.CharField(max_length=64)
    received_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["link", "delivery_id"], name="projects_delivery_once_per_link"
            ),
            models.UniqueConstraint(
                fields=["link", "body_sha256"], name="projects_body_once_per_link"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event} {self.delivery_id}"
