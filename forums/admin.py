"""Admin: forum posts, for looking up. Changing others' posts is moderation's (a later
phase), so the admin is read-only here."""

from django.contrib import admin

from .models import ForumPost


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "created", "edited_at"]
    search_fields = ["title", "author__username"]
    readonly_fields = ["author", "title", "body", "created", "edited_at"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
