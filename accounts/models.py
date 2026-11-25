"""Accounts: each member's Profile, their linked GitHub account's tokens (GitHubLink), and the
sign-in backstop's records.

Users are Django's own `auth.User`. Usernames and emails are unique whatever their
case: the forms check it (allauth's adapter) and the database enforces it with
unique indexes on LOWER(...) (migration 0002), so no route around the forms (the
admin, the shell, a race between two signups) can create a duplicate.
"""

from datetime import datetime

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.db import models

from . import avatars, crypto


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
    # Always a square WebP the Hub made itself (accounts.avatars.process), never the upload.
    avatar = models.ImageField(upload_to=avatars.upload_to, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile of {self.user}"

    @property
    def name(self) -> str:
        """The display name, or the username when there isn't one."""
        return self.display_name or self.user.get_username()

    @property
    def initial(self) -> str:
        """The letter shown in place of a photo."""
        return (self.name[:1] or "?").upper()


class GitHubLinkManager(models.Manager):
    def store(
        self,
        account: SocialAccount,
        *,
        access_token: str,
        refresh_token: str = "",
        expires_at: datetime | None = None,
    ) -> "GitHubLink":
        """Save fresh tokens for a linked GitHub account (a new link or a reconnect).

        The link is marked working again and will be checked on its next use.
        """
        link = self.filter(account=account).first() or self.model(account=account)
        link.set_tokens(access_token, refresh_token, expires_at)
        link.needs_reconnect = False
        link.checked_at = None
        link.save()
        return link


class GitHubLink(models.Model):
    """The Hub's side of a member's linked GitHub account (allauth's SocialAccount).

    Holds the OAuth tokens, encrypted with the environment's key (accounts.crypto), so
    the database never holds a usable token. Deleting the SocialAccount (unlinking)
    deletes this row and its tokens with it.
    """

    account = models.OneToOneField(
        SocialAccount, on_delete=models.CASCADE, related_name="github_link"
    )
    access_token_encrypted = models.TextField(editable=False)
    refresh_token_encrypted = models.TextField(blank=True, editable=False)
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="When the access token expires (GitHub App tokens)."
    )
    needs_reconnect = models.BooleanField(
        default=False, help_text="GitHub refused the token: the member must reconnect."
    )
    checked_at = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

    objects = GitHubLinkManager()

    def __str__(self) -> str:
        return f"GitHub link of {self.account.user}"

    def __repr__(self) -> str:
        return f"<GitHubLink {self.pk} of user {self.account.user_id}>"

    def set_tokens(
        self, access_token: str, refresh_token: str = "", expires_at: datetime | None = None
    ) -> None:
        """Replace the tokens (not saved). An empty refresh token stores nothing."""
        if not access_token:
            raise ValueError("a GitHub link needs an access token")
        self.access_token_encrypted = crypto.encrypt(access_token)
        self.refresh_token_encrypted = crypto.encrypt(refresh_token) if refresh_token else ""
        self.expires_at = expires_at

    @property
    def access_token(self) -> str:
        """The plain access token, for one request to GitHub. Never log or show it.

        Raises crypto.KeyMissing or crypto.Unreadable when the key can't read it.
        """
        return crypto.decrypt(self.access_token_encrypted)

    @property
    def refresh_token(self) -> str:
        """The plain refresh token, or "" when GitHub gave none (OAuth Apps)."""
        if not self.refresh_token_encrypted:
            return ""
        return crypto.decrypt(self.refresh_token_encrypted)

    @property
    def login(self) -> str:
        """The GitHub username, as GitHub last reported it."""
        return str(self.account.extra_data.get("login", ""))


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
