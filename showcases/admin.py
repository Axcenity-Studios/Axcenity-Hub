"""Admin: showcases and tags, for looking up. Changing others' content, and its moderation
state, is moderation's (Phase 15, which records every action), so the admin is read-only."""

from django.contrib import admin

from .models import Showcase, Tag


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Showcase)
class ShowcaseAdmin(ReadOnlyAdmin):
    list_display = ["title", "author", "state", "created", "edited_at"]
    list_filter = ["state", "tags"]
    search_fields = ["title", "slug", "author__username"]
    readonly_fields = [
        "author", "title", "slug", "description", "image", "card", "image_alt", "tags",
        "state", "created", "edited_at",
    ]  # fmt: skip


@admin.register(Tag)
class TagAdmin(ReadOnlyAdmin):
    list_display = ["name", "created"]
    search_fields = ["name"]
