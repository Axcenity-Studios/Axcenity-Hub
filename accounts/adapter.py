"""The Hub's allauth adapters (settings.ACCOUNT_ADAPTER and MFA_ADAPTER)."""

from io import BytesIO

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.base import AuthProcess
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse

from . import crypto, strings

GITHUB = "github"

ALLAUTH_VERIFICATION_STAGE = "allauth.account.stages.EmailVerificationStage"
HUB_VERIFICATION_STAGE = "accounts.stages.SignupVerificationStage"
# allauth's "Confirmation email sent to <address>." message.
EMAIL_SENT_MESSAGE = "account/messages/email_confirmation_sent.txt"


class AccountAdapter(DefaultAccountAdapter):
    """allauth's defaults, with the Hub's verification policy (see accounts.stages)."""

    def get_login_stages(self) -> list[str]:
        stages = super().get_login_stages()
        if ALLAUTH_VERIFICATION_STAGE not in stages:  # an allauth upgrade moved it: fail loudly
            raise RuntimeError(f"{ALLAUTH_VERIFICATION_STAGE} is no longer a login stage")
        return [HUB_VERIFICATION_STAGE if s == ALLAUTH_VERIFICATION_STAGE else s for s in stages]

    def add_message(
        self,
        request,
        level: int,
        message_template: str | None = None,
        message_context: dict | None = None,
        extra_tags: str = "",
        message: str | None = None,
    ) -> None:
        """allauth's messages, less the one that could reveal an account at signup.

        allauth's verification-email cooldown is per address, so a signup with an address
        that was emailed minutes ago sends nothing, and the "Confirmation email sent"
        message would be missing only for addresses that belong to someone. The page after
        signup already says an email was sent, so at signup that message is dropped and
        every signup ends on exactly the same page.
        """
        if message_template == EMAIL_SENT_MESSAGE and (message_context or {}).get("signup"):
            return
        super().add_message(request, level, message_template, message_context, extra_tags, message)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """GitHub as an account a member links, never as a way to sign in or sign up.

    - Apps come from settings (the environment) only, never SocialApp rows, and only while
      a token key is set; otherwise every GitHub URL is a 404 rather than an error.
    - No provider is listed on the sign-in or sign-up pages.
    - A finished GitHub authorisation is accepted only to connect, by a signed-in member,
      for a GitHub account no other member has linked, and when the member has no other
      GitHub account linked. Its tokens are stored encrypted (GitHubLink); the new link's
      are stored by signals.store_github_tokens once allauth has saved the account.
    """

    def list_apps(self, request, provider=None, client_id=None) -> list:
        if not crypto.is_configured():
            return []
        # Apps built from settings are never saved (no pk); SocialApp rows are ignored.
        apps = super().list_apps(request, provider=provider, client_id=client_id)
        return [app for app in apps if app.pk is None]

    def get_app(self, request, provider, client_id=None):
        from allauth.socialaccount.models import SocialApp

        try:
            return super().get_app(request, provider, client_id)
        except SocialApp.DoesNotExist:
            raise Http404("GitHub linking isn't configured") from None

    def list_providers(self, request) -> list:
        return []

    def is_open_for_signup(self, request, sociallogin) -> bool:
        return False

    def pre_social_login(self, request, sociallogin) -> None:
        user = request.user
        if not user.is_authenticated:
            raise ImmediateHttpResponse(HttpResponseRedirect(reverse("account_login")))
        if sociallogin.state.get("process") != AuthProcess.CONNECT:
            self._refuse(request, strings.GITHUB_NOT_SIGN_IN)
        if sociallogin.is_existing and sociallogin.user != user:
            self._refuse(request, strings.GITHUB_LINKED_ELSEWHERE)
        others = SocialAccount.objects.filter(user=user, provider=GITHUB).exclude(
            uid=sociallogin.account.uid
        )
        if others.exists():
            self._refuse(request, strings.GITHUB_ONE_ACCOUNT)
        if sociallogin.is_existing and sociallogin.token is not None:
            # A reconnect: the same member, the same GitHub account, fresh tokens.
            store_tokens(sociallogin.account, sociallogin.token)

    def _refuse(self, request, message: str) -> None:
        messages.error(request, message)
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse("socialaccount_connections")))


def store_tokens(account, token) -> None:
    """Store allauth's in-memory SocialToken for `account`, encrypted (never allauth's table)."""
    from .models import GitHubLink

    GitHubLink.objects.store(
        account,
        access_token=token.token,
        refresh_token=token.token_secret or "",
        expires_at=token.expires_at,
    )


class MFAAdapter(DefaultMFAAdapter):
    """allauth's two-factor defaults, with a QR code that carries its own white paper.

    Authenticator apps read dark modules on a light ground most reliably, in either colour
    scheme, so the white is part of the image (qrcode's fill variant) rather than chrome.
    """

    def build_totp_svg(self, url: str) -> str:
        import qrcode
        from qrcode.image.svg import SvgPathFillImage

        image = qrcode.make(url, image_factory=SvgPathFillImage)
        buffer = BytesIO()
        image.save(buffer)
        return buffer.getvalue().decode("utf8")
