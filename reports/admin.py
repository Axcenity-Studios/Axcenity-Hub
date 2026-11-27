"""Admin: reports and bug reports, for looking up. Acting on reported content is moderation's
(Phase 15); bug reports are handled on the Hub's own pages (reports.bugs), so that every
change follows the transition table and writes the timeline. The admin is read-only."""

from django.contrib import admin

from .models import BugActivity, BugReport, Report


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Report)
class ReportAdmin(ReadOnlyAdmin):
    list_display = ["__str__", "kind", "reason", "content_type", "object_id", "reporter", "created"]
    list_filter = ["kind", "reason", "content_type"]
    readonly_fields = [
        "reporter", "kind", "reason", "details", "content_type", "object_id", "created",
    ]  # fmt: skip


class BugActivityInline(admin.TabularInline):
    model = BugActivity
    extra = 0
    can_delete = False
    readonly_fields = ["actor", "kind", "body", "old_status", "new_status", "assignee", "created"]

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(BugReport)
class BugReportAdmin(ReadOnlyAdmin):
    list_display = ["__str__", "kind", "status", "project", "submitter", "assignee", "created"]
    list_filter = ["kind", "status", "platform"]
    search_fields = ["title", "description"]
    readonly_fields = [
        "project", "submitter", "kind", "title", "description", "steps", "expected",
        "engine_version", "platform", "status", "assignee", "created", "updated",
    ]  # fmt: skip
    inlines = [BugActivityInline]
