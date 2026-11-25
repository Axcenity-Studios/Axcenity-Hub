"""Admin: forum posts and comments, for looking up. Changing others' content, and its
moderation state, is moderation's (Phase 15, which records every action), so the admin is
read-only here."""

from django.contrib import admin

from .models import Comment, ForumPost


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "state", "created", "edited_at"]
    list_filter = ["state"]
    search_fields = ["title", "author__username"]
    readonly_fields = ["author", "title", "body", "state", "created", "edited_at"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["__str__", "author", "state", "created"]
    list_filter = ["state"]
    search_fields = ["body", "author__username"]
    readonly_fields = ["post", "author", "body", "state", "created"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
