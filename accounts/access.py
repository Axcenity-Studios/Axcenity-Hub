"""Who may do what: the email-verification gate.

The Hub's policy: an unverified account can sign in, but can't post, create or report
until its email is verified. Views that contribute mix in VerifiedEmailRequiredMixin;
services call ensure_can_contribute() before they write, so the rule holds whichever
way a contribution arrives.
"""

from allauth.account.internal.flows.email_verification import send_verification_email_for_user
from allauth.account.models import EmailAddress
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import urlencode


class EmailNotVerified(Exception):
    """The user must verify their email address before contributing."""


def has_verified_email(user) -> bool:
    """True when `user` is signed in and has at least one verified email address."""
    if not getattr(user, "is_authenticated", False):
        return False
    return EmailAddress.objects.filter(user=user, verified=True).exists()


def ensure_can_contribute(user) -> None:
    """Raise EmailNotVerified unless `user` may post, create or report."""
    if not has_verified_email(user):
        raise EmailNotVerified("Verify your email address before you post, create or report.")


def verify_email_url(next_path: str = "") -> str:
    """The page that asks a member to verify, returning to `next_path` afterwards."""
    url = reverse("accounts:verify_email")
    return f"{url}?{urlencode({'next': next_path})}" if next_path else url


class VerifiedEmailRequiredMixin(LoginRequiredMixin):
    """Members only, and verified.

    Anonymous visitors go to sign in (LoginRequiredMixin). A signed-in member without a
    verified address is sent to verify instead, and the verification email is sent again
    (allauth's cooldown stops repeats from flooding their inbox). The view itself never
    runs for them, so a refused POST changes nothing.
    """

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if request.user.is_authenticated and not has_verified_email(request.user):
            send_verification_email_for_user(request, request.user)
            # A GET comes back to the same page once verified; a refused POST can't be
            # replayed, so it returns to nowhere in particular.
            next_path = request.get_full_path() if request.method == "GET" else ""
            return HttpResponseRedirect(verify_email_url(next_path))
        return super().dispatch(request, *args, **kwargs)
