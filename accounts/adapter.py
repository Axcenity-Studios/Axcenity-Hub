"""The Hub's allauth adapters (settings.ACCOUNT_ADAPTER and MFA_ADAPTER)."""

from io import BytesIO

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter

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
