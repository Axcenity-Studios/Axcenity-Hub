"""Admin: projects and their repository links, read-only where GitHub is the source.

A link's webhook secret is derived, never stored, so the admin can't show it. Deliveries
are an append-only record of what was accepted. Teams are read-only here: memberships change
only through projects.teams, which keeps every project's last Owner.
"""

from django.contrib import admin

from .models import (
    Project,
    ProjectInvitation,
    ProjectMembership,
    RepositoryLink,
    WebhookDelivery,
)


class RepositoryLinkInline(admin.StackedInline):
    model = RepositoryLink
    fk_name = "project"
    extra = 0
    can_delete = True
    readonly_fields = [
        "github_id", "full_name", "html_url", "description", "default_branch", "private",
        "archived", "pushed_at", "deleted_on_github", "linked_by", "fetched_at", "webhook_at",
    ]  # fmt: skip
    exclude = ["etag"]

    def has_add_permission(self, request, obj=None) -> bool:
        return False  # linking needs the owner's GitHub permission (projects.services)


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class MembershipInline(ReadOnlyInline):
    model = ProjectMembership
    fields = readonly_fields = ["user", "role", "created"]


class InvitationInline(ReadOnlyInline):
    model = ProjectInvitation
    fields = readonly_fields = ["invitee", "role", "invited_by", "created"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owners", "created"]
    search_fields = ["name", "memberships__user__username"]
    readonly_fields = ["slug", "created", "updated"]
    inlines = [MembershipInline, InvitationInline, RepositoryLinkInline]

    @admin.display(description="Owners")
    def owners(self, project: Project) -> str:
        return ", ".join(
            project.memberships.filter(role="owner").values_list("user__username", flat=True)
        )


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ["event", "delivery_id", "link", "received_at"]
    readonly_fields = ["link", "delivery_id", "body_sha256", "event", "received_at"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
