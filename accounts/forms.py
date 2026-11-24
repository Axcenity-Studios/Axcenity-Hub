"""The Hub's versions of allauth's forms (settings.ACCOUNT_FORMS and MFA_FORMS).

Each one keeps allauth's behaviour and adds the server-side protections:
- the database rate-limit backstop (accounts.throttle) on sign-in, sign-up, password
  reset requests and two-factor codes, per IP and per account;
- a honeypot on the reset request (sign-up has allauth's own, "website");
- Cloudflare Turnstile on sign-up and the reset request, when configured
  (accounts.turnstile). It's an extra check: the others run whatever it says.

Every refusal reads the same whether or not the account exists.
"""

from allauth.account import forms as allauth_forms
from allauth.account.adapter import get_adapter
from allauth.core import context
from allauth.mfa.base import forms as mfa_forms
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from . import throttle, turnstile
from .models import Profile

Kind = throttle.Kind

TOO_MANY_ATTEMPTS = "Too many attempts. Wait a while, then try again."
NOT_A_PERSON = "We couldn't confirm you're a person. Please try again."
HONEYPOT_FIELD = "website"


def client_ip() -> str:
    """The current request's client IP, as allauth determines it (proxy-aware)."""
    return get_adapter().get_client_ip(context.request)


class TurnstileMixin:
    """Adds Cloudflare Turnstile to a form when it's configured (accounts.turnstile)."""

    def turnstile_site_key(self) -> str:
        return settings.TURNSTILE_SITE_KEY if turnstile.is_enabled() else ""

    def check_turnstile(self) -> None:
        if turnstile.is_enabled():
            token = self.data.get(turnstile.RESPONSE_FIELD, "")
            if not turnstile.verify(token, client_ip()):
                raise ValidationError(NOT_A_PERSON, code="turnstile")


def honeypot_field() -> forms.CharField:
    """A field people never see or fill in; a bot that fills it is quietly ignored."""
    return forms.CharField(
        required=False,
        label="Leave this empty",
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )


class LoginForm(allauth_forms.LoginForm):
    """Sign in by email and password, with the database backstop on failures."""

    def clean(self):
        ip, account = client_ip(), str(self.data.get("login", ""))
        if throttle.is_blocked(Kind.LOGIN_FAILED, ip=ip, account=account):
            raise ValidationError(TOO_MANY_ATTEMPTS, code="too_many_login_attempts")
        try:
            return super().clean()
        except ValidationError:
            throttle.record(Kind.LOGIN_FAILED, ip=ip, account=account)
            raise


class SignupForm(TurnstileMixin, allauth_forms.SignupForm):
    """allauth's sign-up (with its honeypot), plus Turnstile and the database backstop."""

    def clean(self):
        cleaned_data = super().clean()
        self.check_turnstile()
        ip, account = client_ip(), str(cleaned_data.get("email") or "")
        if throttle.is_blocked(Kind.SIGNUP, ip=ip, account=account):
            raise ValidationError(TOO_MANY_ATTEMPTS, code="too_many_signups")
        throttle.record(Kind.SIGNUP, ip=ip, account=account)
        return cleaned_data


class ResetPasswordForm(TurnstileMixin, allauth_forms.ResetPasswordForm):
    """Request a reset link: a honeypot, Turnstile and the database backstop."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[HONEYPOT_FIELD] = honeypot_field()

    def clean(self):
        cleaned_data = super().clean()
        self.check_turnstile()
        ip, account = client_ip(), str(cleaned_data.get("email") or "")
        if throttle.is_blocked(Kind.PASSWORD_RESET, ip=ip, account=account):
            raise ValidationError(TOO_MANY_ATTEMPTS, code="too_many_resets")
        throttle.record(Kind.PASSWORD_RESET, ip=ip, account=account)
        return cleaned_data

    def save(self, request, **kwargs) -> str:
        if self.cleaned_data.get(HONEYPOT_FIELD):
            # A bot: answer exactly as for a real request, but send nothing.
            return self.cleaned_data["email"]
        return super().save(request, **kwargs)


class MFABackstopMixin:
    """The database backstop on two-factor codes, per IP and per user."""

    def clean_code(self) -> str:
        ip, account = client_ip(), f"user:{self.user.pk}"
        if throttle.is_blocked(Kind.MFA_FAILED, ip=ip, account=account):
            raise ValidationError(TOO_MANY_ATTEMPTS, code="too_many_mfa_attempts")
        try:
            return super().clean_code()
        except ValidationError:
            throttle.record(Kind.MFA_FAILED, ip=ip, account=account)
            raise


class MFAAuthenticateForm(MFABackstopMixin, mfa_forms.AuthenticateForm):
    """The two-factor step of sign-in."""


class MFAReauthenticateForm(MFABackstopMixin, mfa_forms.ReauthenticateForm):
    """Confirming it's you with a code before a sensitive change."""


class ProfileForm(forms.ModelForm):
    """The parts of a profile its owner can change."""

    class Meta:
        model = Profile
        fields = ["display_name", "bio"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 5})}

    def clean_display_name(self) -> str:
        return " ".join(self.cleaned_data["display_name"].split())
