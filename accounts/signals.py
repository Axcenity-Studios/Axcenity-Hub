"""Signal receivers for accounts."""

from allauth.mfa import signals as mfa_signals
from allauth.socialaccount import signals as social_signals
from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created: bool, **kwargs) -> None:
    """Every user gets a Profile when they're created, however they're created."""
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_delete, sender=Profile)
def delete_photo(sender, instance: Profile, **kwargs) -> None:
    """A deleted profile (or user) takes its photo's file with it."""
    if instance.avatar:
        instance.avatar.storage.delete(instance.avatar.name)


@receiver(mfa_signals.authenticator_added)
@receiver(mfa_signals.authenticator_removed)
@receiver(mfa_signals.authenticator_reset)
def rotate_session_on_security_change(sender, request, user, **kwargs) -> None:
    """Turning two-factor on or off, or new recovery codes, is a privilege change: the
    session gets a new key (as Django gives it at sign-in and on a password change), so a
    session id captured before the change no longer works."""
    if request is not None and hasattr(request, "session"):
        request.session.cycle_key()


@receiver(social_signals.social_account_added)
def store_github_tokens(sender, request, sociallogin, **kwargs) -> None:
    """A new GitHub link: store its tokens, encrypted, once allauth has saved the account.

    (A reconnect's tokens are stored by SocialAccountAdapter.pre_social_login, after it has
    checked the account belongs to the member: allauth's `social_account_updated` fires
    before that check, so it isn't used.)
    """
    from .adapter import GITHUB, store_tokens

    if sociallogin.account.provider == GITHUB and sociallogin.token is not None:
        store_tokens(sociallogin.account, sociallogin.token)


# The session clocks start at sign-in (the receiver lives beside the middleware that reads them).
from . import middleware  # noqa: E402, F401
