"""Two-factor sign-in (allauth MFA): enrolling an authenticator app, one-time recovery
codes, signing in with either, the step that can't be skipped, re-authentication before
turning it off, the rate limits on codes, and a new session key on every change."""

import re
import time

import pytest
from allauth.account.internal.flows.login import AUTHENTICATION_METHODS_SESSION_KEY
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import SECRET_SESSION_KEY, format_hotp_value, hotp_value
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from accounts import forms as account_forms
from accounts import throttle

User = get_user_model()
PASSWORD = "a-Long-pass-7731"


def code_for(secret: str, *, step: int = 0) -> str:
    """The authenticator app's code for `secret`, now (or `step` periods from now)."""
    return format_hotp_value(hotp_value(secret, int(time.time()) // 30 + step))


def make_member(*, verified=True) -> User:
    user = User.objects.create_user("ada", "ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email="ada@example.com", primary=True, verified=verified)
    return user


def password_step(client):
    return client.post(reverse("account_login"), {"login": "ada@example.com", "password": PASSWORD})


def reauthenticate(client) -> None:
    """Confirm the password again, as allauth asks before any two-factor change."""
    response = client.post(reverse("account_reauthenticate"), {"password": PASSWORD})
    assert response.status_code == 302


def enrol(client) -> str:
    """Signs in, confirms the password, and turns on the authenticator app; returns its secret."""
    password_step(client)
    assert client.get(reverse("mfa_activate_totp"))["Location"].startswith(
        reverse("account_reauthenticate")
    )
    reauthenticate(client)
    response = client.get(reverse("mfa_activate_totp"))
    assert response.status_code == 200
    secret = client.session[SECRET_SESSION_KEY]
    response = client.post(reverse("mfa_activate_totp"), {"code": code_for(secret)})
    assert response.status_code == 302
    cache.clear()  # forget the used code, as the next period would
    return secret


def signed_in(client) -> bool:
    return "_auth_user_id" in client.session


@pytest.fixture
def member(db):
    return make_member()


@pytest.mark.django_db(transaction=True)
def test_a_member_enrols_an_app_and_gets_one_time_recovery_codes(client):
    # Real commits (transaction=True), as in production: allauth announces the new
    # authenticator on commit of its own atomic block, inside the request.
    member = make_member()
    password_step(client)
    reauthenticate(client)
    page = client.get(reverse("mfa_activate_totp")).content.decode()
    assert '<img class="app-qr" src="data:image/svg+xml' in page  # the QR, on its own white
    secret = client.session[SECRET_SESSION_KEY]
    before = client.session.session_key
    response = client.post(reverse("mfa_activate_totp"), {"code": code_for(secret)})
    assert response.status_code == 302
    assert client.session.session_key != before  # a privilege change rotates the session
    kinds = set(Authenticator.objects.filter(user=member).values_list("type", flat=True))
    assert kinds == {Authenticator.Type.TOTP, Authenticator.Type.RECOVERY_CODES}
    codes = RecoveryCodes(
        Authenticator.objects.get(user=member, type="recovery_codes")
    ).get_unused_codes()
    assert len(codes) == 10
    shown = client.get(reverse("mfa_view_recovery_codes")).content.decode()
    assert all(code in shown for code in codes)


def test_a_wrong_code_doesnt_enrol(client, member):
    password_step(client)
    reauthenticate(client)
    client.get(reverse("mfa_activate_totp"))
    secret = client.session[SECRET_SESSION_KEY]
    client.post(reverse("mfa_activate_totp"), {"code": code_for(secret, step=10)})
    assert not Authenticator.objects.filter(user=member).exists()


@pytest.mark.django_db
def test_an_unverified_member_cant_enrol_until_verified(client):
    make_member(verified=False)
    password_step(client)
    reauthenticate(client)
    response = client.get(reverse("mfa_activate_totp"))
    assert response.status_code == 302 or "verif" in response.content.decode().lower()
    assert not Authenticator.objects.exists()


def test_sign_in_then_asks_for_the_apps_code(member):
    secret = enrol(Client())
    client = Client()
    response = password_step(client)
    assert response.status_code == 302 and response["Location"] == reverse("mfa_authenticate")
    assert not signed_in(client)
    response = client.post(reverse("mfa_authenticate"), {"code": code_for(secret)})
    assert response.status_code == 302 and signed_in(client)
    assert client.get(reverse("accounts:profile")).status_code == 200


def test_a_recovery_code_signs_in_once(member):
    enrol(Client())
    code = RecoveryCodes(
        Authenticator.objects.get(user=member, type="recovery_codes")
    ).get_unused_codes()[0]
    first = Client()
    password_step(first)
    first.post(reverse("mfa_authenticate"), {"code": code})
    assert signed_in(first)
    again = Client()
    password_step(again)
    again.post(reverse("mfa_authenticate"), {"code": code})
    assert not signed_in(again)


def test_the_code_step_cant_be_skipped_by_going_somewhere_else(member):
    enrol(Client())
    client = Client()
    password_step(client)
    for name in ["accounts:profile", "account_email", "mfa_index", "account_change_password"]:
        response = client.get(reverse(name))
        assert response.status_code == 302 and response["Location"].startswith(
            reverse("account_login")
        ), name
    assert not signed_in(client)
    # And the code page itself, with no password step behind it, sends you back to sign in.
    response = Client().get(reverse("mfa_authenticate"))
    assert response.status_code == 302 and response["Location"].startswith(reverse("account_login"))


def test_wrong_codes_are_rate_limited(member):
    secret = enrol(Client())
    client = Client()
    password_step(client)
    for step in range(10, 15):
        client.post(reverse("mfa_authenticate"), {"code": code_for(secret, step=step)})
    client.post(reverse("mfa_authenticate"), {"code": code_for(secret)})
    assert not signed_in(client)


def test_wrong_codes_meet_the_database_limit_even_when_the_cache_is_cleared(member, monkeypatch):
    secret = enrol(Client())
    tight = {
        kind: {scope: (3, limit[1]) for scope, limit in scopes.items()}
        for kind, scopes in throttle.LIMITS.items()
    }
    monkeypatch.setattr(throttle, "LIMITS", tight)
    client = Client()
    password_step(client)
    for step in range(10, 13):
        cache.clear()
        client.post(reverse("mfa_authenticate"), {"code": code_for(secret, step=step)})
    cache.clear()
    response = client.post(reverse("mfa_authenticate"), {"code": code_for(secret)})
    assert not signed_in(client)
    assert account_forms.TOO_MANY_ATTEMPTS in response.content.decode().replace("&#x27;", "'")


def _forget_recent_authentication(client) -> None:
    """Make the last sign-in older than allauth's re-authentication window (5 minutes)."""
    session = client.session
    session[AUTHENTICATION_METHODS_SESSION_KEY] = [
        {**record, "at": record["at"] - 3600}
        for record in session[AUTHENTICATION_METHODS_SESSION_KEY]
    ]
    session.save()


def test_turning_it_off_needs_re_authentication_first(member):
    secret = enrol(Client())
    client = Client()
    password_step(client)
    client.post(reverse("mfa_authenticate"), {"code": code_for(secret)})
    _forget_recent_authentication(client)

    response = client.post(reverse("mfa_deactivate_totp"))
    assert response.status_code == 302 and "reauthenticate" in response["Location"]
    assert Authenticator.objects.filter(user=member, type="totp").exists()

    reauthenticate(client)
    before = client.session.session_key
    response = client.post(reverse("mfa_deactivate_totp"))
    assert response.status_code == 302
    assert not Authenticator.objects.filter(user=member, type="totp").exists()
    assert client.session.session_key != before


def test_the_two_factor_pages_use_the_app_shell(client, member):
    password_step(client)
    html = client.get(reverse("mfa_index")).content.decode()
    assert 'id="app-rail"' in html
    assert re.search(r'aria-current="page">\s*<svg.*?</svg>\s*Two-factor', html, re.S)
