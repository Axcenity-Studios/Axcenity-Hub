"""Admin: reports, for looking up. Acting on them is moderation's (Phase 15), so the admin
is read-only here."""

from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["__str__", "kind", "reason", "content_type", "object_id", "reporter", "created"]
    list_filter = ["kind", "reason", "content_type"]
    readonly_fields = [
        "reporter", "kind", "reason", "details", "content_type", "object_id", "created",
    ]  # fmt: skip

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
