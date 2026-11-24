"""Admin: users with their profile, the sign-in backstop's records (read-only), and no GitHub
secrets."""

from allauth.socialaccount.models import SocialApp, SocialToken
from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import AuthAttempt, Profile

User = get_user_model()

EMAIL_TAKEN = "Another account already uses this email address (in any letter case)."
USERNAME_TAKEN = "Another account already uses this username (in any letter case)."


class CaseInsensitiveUniqueMixin:
    """The admin's half of case-insensitive uniqueness: a clear form error, where the
    database's unique indexes (migration 0002) would otherwise raise an IntegrityError."""

    def _taken(self, field: str, value: str) -> bool:
        others = User.objects.filter(**{f"{field}__iexact": value})
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        return others.exists()

    def clean_username(self):
        username = self.cleaned_data["username"]
        if self._taken("username", username):
            raise forms.ValidationError(USERNAME_TAKEN)
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "")
        if email and self._taken("email", email):
            raise forms.ValidationError(EMAIL_TAKEN)
        return email


class HubUserCreationForm(CaseInsensitiveUniqueMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")


class HubUserChangeForm(CaseInsensitiveUniqueMixin, UserChangeForm):
    pass


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fields = ["display_name", "bio"]


admin.site.unregister(User)
# GitHub secrets never reach the admin: the app's id and secret come from the environment
# (SocialApp rows are ignored by accounts.adapter.SocialAccountAdapter), and tokens live
# encrypted in GitHubLink, which has no admin page (allauth's SocialToken table stays empty).
# allauth's SocialAccount page stays: it shows which GitHub account a member linked.
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = HubUserChangeForm
    add_form = HubUserCreationForm
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2")}),
    )
    inlines = [ProfileInline]


@admin.register(AuthAttempt)
class AuthAttemptAdmin(admin.ModelAdmin):
    """The backstop's counts, for spotting abuse. Keys are hashes; nothing here is editable."""

    list_display = ["kind", "scope", "created"]
    list_filter = ["kind", "scope"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
