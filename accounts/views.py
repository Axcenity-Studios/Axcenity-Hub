"""Signed-in account pages, in the app shell (templates/app/shell.html)."""

from allauth.account.decorators import reauthentication_required
from allauth.account.internal.flows.email_verification import send_verification_email_for_user
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.internal.flows import connect as connect_flows
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.base import AuthProcess
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import TemplateView, UpdateView

from . import crypto, github, strings
from .access import has_verified_email
from .adapter import GITHUB
from .forms import ProfileForm
from .models import GitHubLink, Profile


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


def github_account(user) -> SocialAccount | None:
    """The member's linked GitHub account, if any (one at most: SocialAccountAdapter)."""
    return SocialAccount.objects.filter(user=user, provider=GITHUB).first()


def github_linking_on() -> bool:
    """Whether this server can link GitHub: an app's id and secret, and a token key."""
    return bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET) and (
        crypto.is_configured()
    )


class ConnectionsView(LoginRequiredMixin, TemplateView):
    """The member's linked GitHub account: its state, and link, reconnect and unlink.

    Replaces allauth's socialaccount_connections page (same URL and name). Viewing it checks
    the link with GitHub (at most every GITHUB_LINK_CHECK_INTERVAL): a revoked token shows
    the reconnect prompt, and GitHub being down shows the last known state.
    """

    template_name = "accounts/connections.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = github_account(self.request.user)
        link = GitHubLink.objects.filter(account=account).first() if account else None
        state, login = None, ""
        if link is not None:
            state, login = github.check_link(link), link.login  # the check may update it
        elif account is not None:
            # A link with no stored token (made before this page, or by hand) can't be used.
            state = github.LinkState.NEEDS_RECONNECT
            login = str(account.extra_data.get("login", ""))
        context.update(
            account=account,
            login=login,
            state=state,  # a LinkState, a str: the template compares its value
            linking_on=github_linking_on(),
        )
        return context

    @method_decorator(reauthentication_required)
    def post(self, request, *args, **kwargs):
        """Unlink: after a fresh re-authentication (allauth replays this POST after it).

        allauth's own disconnect checks that a social account isn't the member's last way
        to sign in; GitHub never is one here, so it's left out.
        """
        account = github_account(request.user)
        if account is None:
            raise Http404
        connect_flows.disconnect(request, account)
        return HttpResponseRedirect(reverse("socialaccount_connections"))


class GitHubConnectView(LoginRequiredMixin, View):
    """Start linking (or reconnecting) GitHub: POST only, always allauth's connect process.

    Replaces allauth's github_login view (same URL and name), so no URL starts a GitHub
    sign-in. allauth's callback finishes the link through SocialAccountAdapter.
    """

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse("socialaccount_connections"))

    def post(self, request, *args, **kwargs):
        provider = get_social_adapter(request).get_provider(request, GITHUB)  # 404 when off
        return provider.redirect(
            request, process=AuthProcess.CONNECT, next_url=reverse("socialaccount_connections")
        )


class VerifyEmailView(EmailView):
    """Where the contribution gate sends an unverified member (accounts.access)."""

    template_name = "accounts/verify_email.html"
    lede = strings.VERIFY_TO_CONTRIBUTE
