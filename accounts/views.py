"""Signed-in account pages, in the app shell (templates/app/shell.html)."""

from allauth.account.internal.flows.email_verification import send_verification_email_for_user
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView, UpdateView

from . import strings
from .access import has_verified_email
from .forms import ProfileForm
from .models import Profile


class ProfileView(LoginRequiredMixin, UpdateView):
    """The signed-in member's own profile: what others see, and its edit form."""

    form_class = ProfileForm
    template_name = "accounts/profile.html"

    def get_object(self, queryset=None):
        # Users made before the accounts app existed get their profile on first visit.
        return Profile.objects.get_or_create(user=self.request.user)[0]

    def get_success_url(self) -> str:
        return reverse("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, strings.PROFILE_SAVED)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            verified=has_verified_email(user),
            two_factor=Authenticator.objects.filter(
                user=user, type=Authenticator.Type.TOTP
            ).exists(),
        )
        return context


class EmailView(LoginRequiredMixin, TemplateView):
    """The member's email address, whether it's verified, and a button to resend the link.

    Adding or changing an address isn't offered yet: allauth's add-email form would let an
    address another account holds be added unverified, and the Hub keeps every email on one
    account only (see docs/architecture/accounts.md). This view replaces allauth's
    account_email page.
    """

    template_name = "accounts/email.html"
    lede = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            addresses=EmailAddress.objects.filter(user=self.request.user).order_by(
                "-primary", "email"
            ),
            verified=has_verified_email(self.request.user),
            lede=self.lede,
            next_url=self._next_url(),
        )
        return context

    def _next_url(self) -> str:
        url = self.request.GET.get("next", "") or self.request.POST.get("next", "")
        if url and url_has_allowed_host_and_scheme(
            url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        ):
            return url
        return ""

    def post(self, request, *args, **kwargs):
        if not has_verified_email(request.user):
            # allauth's cooldown (ACCOUNT_RATE_LIMITS["confirm_email"]) keeps this from flooding.
            if send_verification_email_for_user(request, request.user):
                messages.info(request, strings.VERIFICATION_SENT)
            else:
                messages.info(request, strings.VERIFICATION_WAIT)
        target = request.path
        if next_url := self._next_url():
            target = f"{target}?next={next_url}"
        return HttpResponseRedirect(target)


class VerifyEmailView(EmailView):
    """Where the contribution gate sends an unverified member (accounts.access)."""

    template_name = "accounts/verify_email.html"
    lede = strings.VERIFY_TO_CONTRIBUTE
