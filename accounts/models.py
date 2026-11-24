"""Accounts: each member's Profile.

Users are Django's own `auth.User`. Usernames and emails are unique whatever their
case: the forms check it (allauth's adapter) and the database enforces it with
unique indexes on LOWER(...) (migration 0002), so no route around the forms (the
admin, the shell, a race between two signups) can create a duplicate.
"""

from django.conf import settings
from django.db import models


class Profile(models.Model):
    """What other members see about a user, beyond the username."""

    DISPLAY_NAME_MAX = 50
    BIO_MAX = 500

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField(
        max_length=DISPLAY_NAME_MAX,
        blank=True,
        help_text="Shown beside your username. Leave blank to show only the username.",
    )
    bio = models.TextField(
        max_length=BIO_MAX, blank=True, help_text="A few words about you, in plain text."
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile of {self.user}"

    @property
    def name(self) -> str:
        """The display name, or the username when there isn't one."""
        return self.display_name or self.user.get_username()


class AuthAttempt(models.Model):
    """One sign-in event that counts towards a database rate limit (accounts.throttle).

    allauth's rate limits live in the cache; these rows are the backstop that still
    holds if the cache is cleared, restarted or not shared. The IP address and the
    account (an email or a user id) are stored only as keyed hashes, never as typed.
    """

    class Kind(models.TextChoices):
        LOGIN_FAILED = "login_failed", "Failed sign-in"
        SIGNUP = "signup", "Sign-up"
        PASSWORD_RESET = "password_reset", "Password reset request"
        MFA_FAILED = "mfa_failed", "Failed two-factor code"

    class Scope(models.TextChoices):
        IP = "ip", "IP address"
        ACCOUNT = "account", "Account"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    scope = models.CharField(max_length=10, choices=Scope.choices)
    key = models.CharField(max_length=64, help_text="HMAC-SHA256 of the IP or account")
    created = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [models.Index(fields=["kind", "scope", "key", "created"])]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.get_scope_display()}) at {self.created}"
