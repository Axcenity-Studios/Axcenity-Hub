"""Admin: projects and their repository links, read-only where GitHub is the source.

A link's webhook secret is derived, never stored, so the admin can't show it. Deliveries
are an append-only record of what was accepted.
"""

from django.contrib import admin

from .models import Project, RepositoryLink, WebhookDelivery


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


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created"]
    search_fields = ["name", "owner__username"]
    readonly_fields = ["slug", "created", "updated"]
    inlines = [RepositoryLinkInline]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ["event", "delivery_id", "link", "received_at"]
    readonly_fields = ["link", "delivery_id", "body_sha256", "event", "received_at"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
