"""Projects: a member's Hub project, its team, the GitHub repository linked to it, and the
webhook deliveries received for that repository.

- A project's team is its memberships, each with a Role (Owner, Maintainer, Viewer); what each
  role may do is `PERMISSIONS`. A project always has at least one Owner (projects.teams; and
  `protect_last_owner` refuses to delete the account of a project's last Owner).
- A member owns at most `Project.LIMIT_PER_OWNER` projects: their Owner memberships
  (projects.services.create_project, and projects.teams wherever someone becomes an Owner).
- A member is invited to a project (ProjectInvitation) and joins only by accepting it.
- Project names are unique across the Hub whatever their case, and so are their slugs (the
  slug is the name, slugified, and follows renames). Both are database constraints.
- A GitHub repository can be linked to one Hub project only: `RepositoryLink.github_id` (the
  repository's numeric id, which survives renames and transfers) is unique.
- A webhook delivery is accepted once per link: its delivery id and its body's SHA-256 are
  each unique per link (projects.webhooks).
"""

import uuid
from enum import StrEnum

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.text import slugify

from . import strings


class Role(models.TextChoices):
    """A member's role in one project."""

    OWNER = "owner", "Owner"
    MAINTAINER = "maintainer", "Maintainer"
    VIEWER = "viewer", "Viewer"


class Action(StrEnum):
    """What a member may try to do with a project."""

    VIEW = "view"  # the project, its repository's details and its team
    EDIT = "edit"  # the description
    RENAME = "rename"  # the name, and with it the address
    REFRESH = "refresh"  # fetch the repository's details from GitHub
    MANAGE_REPOSITORY = "manage_repository"  # link, unlink, the setup and the webhook's secret
    MANAGE_MEMBERS = "manage_members"  # invite, cancel invitations, change roles, remove
    MANAGE_REPORTS = "manage_reports"  # see every bug report, change its status, assign it
    DELETE = "delete"


# Each action and the roles allowed it. Anyone else is shown a 404, never a 403.
PERMISSIONS: dict[Action, frozenset[Role]] = {
    Action.VIEW: frozenset({Role.OWNER, Role.MAINTAINER, Role.VIEWER}),
    Action.EDIT: frozenset({Role.OWNER, Role.MAINTAINER}),
    Action.REFRESH: frozenset({Role.OWNER, Role.MAINTAINER}),
    Action.RENAME: frozenset({Role.OWNER}),
    Action.MANAGE_REPOSITORY: frozenset({Role.OWNER}),
    Action.MANAGE_MEMBERS: frozenset({Role.OWNER}),
    Action.MANAGE_REPORTS: frozenset({Role.OWNER, Role.MAINTAINER}),
    Action.DELETE: frozenset({Role.OWNER}),
}


def allows(role: str | None, action: Action) -> bool:
    """Whether a member with `role` (None: not a member) may do `action`."""
    return role is not None and role in PERMISSIONS[action]


class ProjectQuerySet(models.QuerySet):
    def allowing(self, user, action: Action) -> "ProjectQuerySet":
        """The projects in which `user` may do `action` (none for an anonymous visitor)."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(
            pk__in=ProjectMembership.objects.filter(user=user, role__in=PERMISSIONS[action]).values(
                "project"
            )
        )

    def visible_to(self, user) -> "ProjectQuerySet":
        """The projects `user` is a member of, in any role."""
        return self.allowing(user, Action.VIEW)

    def owned_by(self, user) -> "ProjectQuerySet":
        """The projects `user` is an Owner of."""
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(
            pk__in=ProjectMembership.objects.filter(user=user, role=Role.OWNER).values("project")
        )

    def create_with_owner(self, owner, **fields) -> "Project":
        """Create a project and its first Owner membership together.

        No limit or verification check: that's projects.services.create_project, which
        members go through. This is for it, and for fixtures.
        """
        with transaction.atomic():
            project = self.create(**fields)
            ProjectMembership.objects.create(project=project, user=owner, role=Role.OWNER)
        return project


class Project(models.Model):
    """A member's project in the Hub, optionally linked to one GitHub repository."""

    NAME_MAX = 60
    DESCRIPTION_MAX = 500
    LIMIT_PER_OWNER = 5
    # Slugs that would shadow the app's own URLs (/projects/new/, /projects/hooks/).
    RESERVED_SLUGS = frozenset({"new", "hooks"})

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

    def role_of(self, user) -> Role | None:
        """`user`'s role in this project, or None when they aren't a member."""
        if not getattr(user, "is_authenticated", False):
            return None
        role = self.memberships.filter(user=user).values_list("role", flat=True).first()
        return Role(role) if role else None

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


def protect_last_owner(collector, field, sub_objs, using) -> None:
    """`on_delete` for a membership's user: refuse to delete the last Owner of a project.

    Deleting an account deletes its memberships (CASCADE), unless that would leave a project
    with no Owner: then nothing is deleted and ProtectedError names those memberships (the
    admin lists them as the reason it can't delete). Ownership never passes to anyone by
    itself; the Owner makes someone else an Owner first, or deletes the project. Inside a
    transaction (the admin's delete is one) the projects' rows are locked first, as
    projects.teams does, so two Owners can't go at the same moment.
    """
    doomed = [membership.pk for membership in sub_objs]
    owned = {m.project_id for m in sub_objs if m.role == Role.OWNER}
    if owned:
        if transaction.get_connection(using).in_atomic_block:
            list(Project.objects.using(using).select_for_update().filter(pk__in=owned))
        remaining = set(
            ProjectMembership.objects.using(using)
            .filter(project_id__in=owned, role=Role.OWNER)
            .exclude(pk__in=doomed)
            .values_list("project_id", flat=True)
        )
        stranded = [m for m in sub_objs if m.role == Role.OWNER and m.project_id not in remaining]
        if stranded:
            raise models.ProtectedError(strings.LAST_OWNER_ACCOUNT, set(stranded))
    models.CASCADE(collector, field, sub_objs, using)


class ProjectMembership(models.Model):
    """A member of a project's team, in one role. One membership per member and project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=protect_last_owner, related_name="project_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"], name="projects_one_membership_per_member"
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="projects_membership_role_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.get_role_display()}) in {self.project}"


class ProjectInvitation(models.Model):
    """An Owner's invitation for a member to join a project in a role.

    Only the invitee can accept or decline it; Owners can cancel it. It's deleted once
    answered or cancelled. One per member and project.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invitations")
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_invitations"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "invitee"], name="projects_one_invitation_per_member"
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="projects_invitation_role_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invitee} invited to {self.project} as {self.get_role_display()}"


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
