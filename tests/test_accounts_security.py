"""Accounts security: sessions and cookies, CSRF everywhere, password reset tokens, rate
limits (cache, the production cache, and the database backstop), enumeration and timing,
anonymous access to every members-only URL, the honeypots and Turnstile
(see docs/architecture/accounts.md)."""

import re
import time
from datetime import timedelta

import pytest
import requests
import responses
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import MD5PasswordHasher
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.urls import URLResolver, get_resolver, reverse

from accounts import forms as account_forms
from accounts import throttle, turnstile
from accounts.middleware import LAST_SEEN_AT, SIGNED_IN_AT

User = get_user_model()
PASSWORD = "a-Long-pass-7731"
LOGIN = "/accounts/login/"


def make_member(username="ada", email="ada@example.com", *, verified=True) -> User:
    user = User.objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


def sign_in(client, email="ada@example.com", password=PASSWORD):
    return client.post(reverse("account_login"), {"login": email, "password": password})


def _page(response) -> str:
    html = response.content.decode()
    return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', 'name="csrfmiddlewaretoken"', html)


# ---------- Sessions and cookies ----------


@pytest.mark.django_db
def test_the_session_cookie_is_httponly_and_lax(client):
    make_member()
    response = sign_in(client)
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"] is True and cookie["samesite"] == "Lax"
    # In development it isn't Secure (no HTTPS); production's settings make it so (below).
    assert not cookie["secure"]


@pytest.mark.django_db
def test_the_session_key_changes_at_sign_in(client):
    make_member()
    session = client.session
    session["before"] = True
    session.save()
    before = session.session_key
    sign_in(client)
    assert client.session.session_key != before
    assert not Session.objects.filter(session_key=before).exists()


@pytest.mark.django_db
def test_the_session_key_changes_on_a_password_change_and_the_member_stays_in(client):
    make_member()
    sign_in(client)
    before = client.session.session_key
    response = client.post(
        reverse("account_change_password"),
        {
            "oldpassword": PASSWORD,
            "password1": "an-Other-pass-8842",
            "password2": "an-Other-pass-8842",
        },
    )
    assert response.status_code == 302
    assert client.session.session_key != before
    assert client.get(reverse("accounts:profile")).status_code == 200


@pytest.mark.django_db
def test_sign_out_deletes_the_session_on_the_server(client):
    make_member()
    sign_in(client)
    stolen = client.cookies["sessionid"].value
    assert client.post(reverse("account_logout")).status_code == 302
    assert not Session.objects.filter(session_key=stolen).exists()
    replay = Client()
    replay.cookies["sessionid"] = stolen
    response = replay.get(reverse("accounts:profile"))
    assert response.status_code == 302 and response["Location"].startswith(LOGIN)


@pytest.mark.django_db
def test_signing_out_needs_a_post(client):
    make_member()
    sign_in(client)
    client.get(reverse("account_logout"))  # shows the confirmation, doesn't sign out
    assert client.get(reverse("accounts:profile")).status_code == 200


def _age_session(client, **seconds_ago) -> str:
    session = client.session
    now = time.time()
    if "idle" in seconds_ago:
        session[LAST_SEEN_AT] = now - seconds_ago["idle"]
    if "since_sign_in" in seconds_ago:
        session[SIGNED_IN_AT] = now - seconds_ago["since_sign_in"]
    session.save()
    return session.session_key


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("ages", "signed_out"),
    [
        ({"idle": 23 * 3600}, False),
        ({"idle": 25 * 3600}, True),
        ({"idle": 60, "since_sign_in": 13 * 86400}, False),
        ({"idle": 60, "since_sign_in": 15 * 86400}, True),
    ],
)
def test_sessions_end_after_a_day_idle_or_two_weeks_in_all(client, settings, ages, signed_out):
    assert settings.SESSION_IDLE_TIMEOUT == timedelta(hours=24)
    assert settings.SESSION_ABSOLUTE_TIMEOUT == timedelta(days=14)
    make_member()
    sign_in(client)
    key = _age_session(client, **ages)
    response = client.get(reverse("accounts:profile"))
    assert (response.status_code == 302) is signed_out
    assert Session.objects.filter(session_key=key).exists() is not signed_out


@pytest.mark.django_db
def test_activity_moves_the_idle_clock_but_never_the_sign_in_clock(client):
    make_member()
    sign_in(client)
    _age_session(client, idle=3600, since_sign_in=3600)
    signed_in_at = client.session[SIGNED_IN_AT]
    client.get(reverse("accounts:profile"))
    assert time.time() - client.session[LAST_SEEN_AT] < 5
    assert client.session[SIGNED_IN_AT] == signed_in_at


# ---------- CSRF ----------


def _routes():
    """(path, name, callback, arg names) for every URL pattern. Path is None for a pattern
    that takes arguments; arg names lists them."""

    def walk(patterns, prefix="", namespace=None):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                ns = ":".join(x for x in [namespace, pattern.namespace] if x) or None
                yield from walk(pattern.url_patterns, prefix + str(pattern.pattern), ns)
            else:
                route = (prefix + str(pattern.pattern)).replace("^", "").replace("$", "")
                name = f"{namespace}:{pattern.name}" if namespace else pattern.name
                args = [a or b for a, b in re.findall(r"\(\?P<(\w+)>|<(?:\w+:)?(\w+)>", route)]
                yield (None if args else "/" + route), name, pattern.callback, args

    return list(walk(get_resolver().url_patterns))


def test_only_the_repository_webhook_is_csrf_exempt(settings):
    # GitHub can't send a CSRF token: the webhook authenticates each delivery by its
    # signature instead (tests/test_projects_webhooks.py). Nothing else is exempt.
    exempt = [name for _, name, callback, _ in _routes() if getattr(callback, "csrf_exempt", False)]
    assert exempt == ["projects:webhook"]
    allowed = settings.BASE_DIR / "projects" / "views.py"
    for folder in ["accounts", "config", "marketing", "documentation", "projects", "forums"]:
        for path in (settings.BASE_DIR / folder).rglob("*.py"):
            if path != allowed:
                assert "csrf_exempt" not in path.read_text(encoding="utf-8"), path
    assert allowed.read_text(encoding="utf-8").count("@method_decorator(csrf_exempt") == 1


@pytest.mark.django_db
@pytest.mark.parametrize("signed_in", [False, True])
def test_every_post_without_a_csrf_token_is_refused_htmx_included(signed_in):
    client = Client(enforce_csrf_checks=True)
    if signed_in:
        client.force_login(make_member())
    paths = sorted({path for path, _, _, _ in _routes() if path})
    assert "/accounts/login/" in paths and "/accounts/2fa/totp/deactivate/" in paths
    for path in paths:
        for headers in [{}, {"HX-Request": "true"}]:
            response = client.post(path, {"x": "1"}, headers=headers)
            assert response.status_code == 403, (path, headers)
    assert User.objects.count() == (1 if signed_in else 0)


# ---------- Password reset ----------


def _reset_link(email="ada@example.com") -> str:
    Client().post(reverse("account_reset_password"), {"email": email})
    message = next(m for m in mail.outbox if "password" in m.subject.lower())
    return re.search(r"http://testserver(/accounts/password/reset/key/[^\s]+/)", message.body)[1]


@pytest.mark.django_db
def test_a_reset_link_works_once_and_hides_its_token_from_referrers(client):
    make_member()
    link = _reset_link()
    # Opening the link moves the token into the session and onto a token-free URL.
    response = client.get(link)
    assert response.status_code == 302
    form_url = response["Location"]
    assert (
        form_url.endswith("-set-password/") and link.rstrip("/").rsplit("-", 1)[1] not in form_url
    )
    page = client.get(form_url)
    assert page.status_code == 200 and page["Referrer-Policy"] == "same-origin"
    assert not re.search(
        r'(?:src|href)="https?://', page.content.decode()
    )  # nothing off-site to leak to
    done = client.post(
        form_url, {"password1": "an-Other-pass-8842", "password2": "an-Other-pass-8842"}
    )
    assert done.status_code == 302
    # The same link again: refused.
    again = Client().get(link, follow=True)
    assert "token" in again.content.decode().lower() and "invalid" in again.content.decode().lower()


@pytest.mark.django_db
def test_reset_tokens_expire_after_an_hour_and_die_with_any_password_change(settings, monkeypatch):
    assert settings.PASSWORD_RESET_TIMEOUT == 3600
    user = make_member()
    generator = PasswordResetTokenGenerator()
    token = generator.make_token(user)
    real_now = generator._now()
    monkeypatch.setattr(
        PasswordResetTokenGenerator, "_now", lambda self: real_now + timedelta(minutes=59)
    )
    assert generator.check_token(user, token)
    monkeypatch.setattr(
        PasswordResetTokenGenerator, "_now", lambda self: real_now + timedelta(minutes=61)
    )
    assert not generator.check_token(user, token)
    monkeypatch.undo()
    user.set_password("an-Other-pass-8842")
    user.save()
    assert not generator.check_token(user, token)


@pytest.mark.django_db
def test_a_password_change_kills_a_reset_link_sent_before_it(client):
    user = make_member()
    link = _reset_link()
    user.set_password("an-Other-pass-8842")
    user.save()
    response = client.get(link, follow=True)
    assert "invalid" in response.content.decode().lower()


# ---------- Rate limits: the cache layer ----------


@pytest.fixture(params=["local memory", "database (production)"])
def any_cache(request, settings, django_db_blocker):
    """Each rate-limit test runs on development's cache and on production's shared one."""
    if request.param.startswith("database"):
        settings.CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "LOCATION": "axcenity_cache",
            }
        }
        call_command("createcachetable", verbosity=0)
    cache.clear()
    return request.param


@pytest.mark.django_db
def test_failed_sign_ins_are_limited_per_account(any_cache):
    make_member()
    for _ in range(5):
        assert "_auth_user_id" not in (c := Client()).session
        sign_in(c, password="wrong-Pass-1")
    # The right password from a fresh browser is refused too, for now.
    client = Client()
    response = sign_in(client)
    assert response.status_code == 200 and "_auth_user_id" not in client.session
    assert "too many" in response.content.decode().lower()
    if any_cache.startswith("database"):  # the limit really lived in the shared table
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM axcenity_cache")
            assert cursor.fetchone()[0] > 0


@pytest.mark.django_db
def test_failed_sign_ins_are_limited_per_ip(any_cache):
    for n in range(10):
        sign_in(Client(), email=f"nobody{n}@example.com", password="wrong-Pass-1")
    make_member()
    response = sign_in(Client())
    assert "too many" in response.content.decode().lower()


@pytest.mark.django_db
def test_signups_are_limited_per_ip(any_cache):
    for n in range(10):
        Client().post(
            reverse("account_signup"),
            {
                "email": f"m{n}@example.com",
                "username": f"member{n}",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
    response = Client().post(
        reverse("account_signup"),
        {
            "email": "late@example.com",
            "username": "late",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert response.status_code == 429
    assert not User.objects.filter(username="late").exists()


@pytest.mark.django_db
def test_reset_requests_are_limited_per_address(any_cache):
    make_member()
    for _ in range(3):
        Client().post(reverse("account_reset_password"), {"email": "ada@example.com"})
    sent = len(mail.outbox)
    response = Client().post(reverse("account_reset_password"), {"email": "ada@example.com"})
    assert response.status_code in (200, 429) and len(mail.outbox) == sent
    assert sent == 3


# ---------- Rate limits: the database backstop ----------


@pytest.fixture
def tight_limits(monkeypatch):
    """Database limits of three, so a test can reach them; the cache is emptied before
    every attempt, so only the database can be what refuses."""
    tight = {
        kind: {scope: (3, limit[1]) for scope, limit in scopes.items()}
        for kind, scopes in throttle.LIMITS.items()
    }
    monkeypatch.setattr(throttle, "LIMITS", tight)


@pytest.mark.django_db
def test_the_database_limits_hold_when_the_cache_is_cleared(tight_limits):
    make_member()
    for _ in range(3):
        cache.clear()
        sign_in(Client(), password="wrong-Pass-1")
    cache.clear()
    client = Client()
    response = sign_in(client)  # the right password
    assert "_auth_user_id" not in client.session
    assert account_forms.TOO_MANY_ATTEMPTS in response.content.decode().replace("&#x27;", "'")


@pytest.mark.django_db
def test_the_database_limits_cover_signups_and_resets(tight_limits):
    for n in range(3):
        cache.clear()
        Client().post(
            reverse("account_signup"),
            {
                "email": "same@example.com",
                "username": f"same{n}",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
    cache.clear()
    refused = Client().post(
        reverse("account_signup"),
        {
            "email": "same@example.com",
            "username": "fourth",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert refused.status_code == 200 and account_forms.TOO_MANY_ATTEMPTS in _page(refused).replace(
        "&#x27;", "'"
    )

    make_member()
    mail.outbox.clear()
    for _ in range(3):
        cache.clear()
        Client().post(reverse("account_reset_password"), {"email": "ada@example.com"})
    cache.clear()
    refused = Client().post(reverse("account_reset_password"), {"email": "ada@example.com"})
    assert account_forms.TOO_MANY_ATTEMPTS in _page(refused).replace("&#x27;", "'")
    assert len(mail.outbox) == 3


@pytest.mark.django_db
def test_the_backstop_stores_hashes_never_addresses_or_ips(tight_limits):
    sign_in(Client(), email="secret@example.com", password="wrong-Pass-1")
    from accounts.models import AuthAttempt

    stored = list(AuthAttempt.objects.values_list("key", flat=True))
    assert len(stored) == 2 and all(re.fullmatch(r"[0-9a-f]{64}", key) for key in stored)
    assert "secret" not in str(stored) and "127.0.0.1" not in str(stored)


@pytest.mark.django_db
def test_old_backstop_rows_are_dropped_and_stop_counting():
    from django.utils import timezone

    then = timezone.now() - timedelta(days=2)
    for _ in range(30):
        throttle.record(
            throttle.Kind.LOGIN_FAILED, ip="10.0.0.1", account="a@example.com", now=then
        )
    assert throttle.is_blocked(
        throttle.Kind.LOGIN_FAILED, ip="10.0.0.1", account="a@example.com", now=then
    )
    assert not throttle.is_blocked(
        throttle.Kind.LOGIN_FAILED, ip="10.0.0.1", account="a@example.com"
    )
    throttle.record(throttle.Kind.SIGNUP, ip="10.0.0.2")
    from accounts.models import AuthAttempt

    assert AuthAttempt.objects.count() == 1


# ---------- Enumeration and timing ----------


class CountingHasher(MD5PasswordHasher):
    """Counts password hashes, to show an unknown email costs the same work as a wrong password."""

    algorithm = "counting_md5"
    calls = 0

    def encode(self, password, salt):
        CountingHasher.calls += 1
        return super().encode(password, salt)


@pytest.mark.django_db
def test_sign_in_hashes_once_whether_or_not_the_account_exists(settings):
    settings.PASSWORD_HASHERS = ["tests.test_accounts_security.CountingHasher"]
    make_member()
    results = {}
    for label, email in [("unknown", "nobody@example.com"), ("wrong password", "ada@example.com")]:
        CountingHasher.calls = 0
        response = sign_in(Client(), email=email, password="wrong-Pass-1")
        results[label] = (CountingHasher.calls, response.status_code)
    assert results == {"unknown": (1, 200), "wrong password": (1, 200)}


@pytest.mark.django_db
def test_a_reset_request_reads_the_same_whether_or_not_the_account_exists():
    make_member()
    pages = []
    for email in ["ada@example.com", "nobody@example.com"]:
        client = Client()
        response = client.post(reverse("account_reset_password"), {"email": email})
        assert response.status_code == 302
        pages.append((response["Location"], _page(client.get(response["Location"]))))
    assert pages[0] == pages[1]
    # Each address gets exactly one email: a link for the member, a note for the stranger.
    assert sorted(m.to[0] for m in mail.outbox) == ["ada@example.com", "nobody@example.com"]


# ---------- Unauthenticated access ----------

# Pages anyone may open: the marketing site, the docs, and the way in.
PUBLIC = {
    "marketing:home", "marketing:toolbox", "marketing:download", "marketing:download_agree",
    "marketing:theme", "marketing:credits", "documentation:index", "documentation:search", "documentation:page",
    "account_login", "account_logout", "account_signup", "account_inactive",
    "account_email_verification_sent", "account_confirm_email", "account_confirm_login_code",
    "account_reset_password", "account_reset_password_done", "account_reset_password_from_key",
    "account_reset_password_from_key_done", "mfa_authenticate",
    # GitHub's return to the Hub, and allauth's pages for a cancelled or failed one: they
    # show an error to anyone and link nothing (accounts.adapter.SocialAccountAdapter).
    "github_callback", "socialaccount_login_cancelled", "socialaccount_login_error",
    # GitHub's repository webhooks: authenticated by each delivery's signature, not a session.
    "projects:webhook",
    # The forums are read by anyone (writing them is members-only).
    "forums:list", "forums:detail",
}  # fmt: skip
SAMPLE_KWARGS = {"key": "not-a-key", "uidb36": "1", "path": "not-a-page"}


@pytest.mark.django_db
def test_every_members_only_url_sends_an_anonymous_visitor_to_sign_in(client):
    members_only = []
    for path, name, _, args in _routes():
        if name in PUBLIC or (name or "").startswith("admin:"):
            continue
        if path is None:
            path = reverse(name, kwargs={arg: SAMPLE_KWARGS.get(arg, "1") for arg in args})
        members_only.append(name)
        response = client.get(path)
        if name is None and path.startswith("/accounts/social/"):
            # allauth's deprecated, unnamed /social/ URLs: permanent redirects to their
            # /3rdparty/ pages, which this walk checks under their own names.
            assert response.status_code == 301, path
            assert response["Location"].startswith("/accounts/3rdparty/"), path
            continue
        assert response.status_code in (302, 404), (name, response.status_code)
        if response.status_code == 302:
            assert response["Location"].startswith(LOGIN), (name, response["Location"])
    # The walk found the account pages (so it isn't passing by finding nothing).
    assert {
        "accounts:profile",
        "account_email",
        "account_change_password",
        "mfa_index",
        "mfa_activate_totp",
        "mfa_deactivate_totp",
        "mfa_view_recovery_codes",
        "socialaccount_connections",
        "socialaccount_signup",
        "github_login",
        "projects:list",
        "projects:create",
        "projects:detail",
        "projects:edit",
        "projects:delete",
        "projects:link_repository",
        "projects:unlink_repository",
        "projects:refresh_repository",
        "forums:create",
        "forums:edit",
        "forums:delete",
    } <= set(members_only)


@pytest.mark.django_db
def test_the_admin_sends_an_anonymous_visitor_to_its_own_sign_in(client):
    for path, name, _, _ in _routes():
        if (
            path
            and (name or "").startswith("admin:")
            and name != "admin:login"
            and name != "admin:logout"
        ):
            response = client.get(path)
            assert response.status_code == 302 and "/admin/login/" in response["Location"], name


# ---------- Honeypots ----------


@pytest.mark.django_db
def test_a_signup_bot_that_fills_the_honeypot_sees_success_and_gets_nothing(client):
    human = Client().post(
        reverse("account_signup"),
        {
            "email": "h@example.com",
            "username": "human",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    mail.outbox.clear()
    bot = client.post(
        reverse("account_signup"),
        {
            "email": "b@example.com",
            "username": "robot",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "website": "http://spam.example",
        },
    )
    assert (bot.status_code, bot["Location"]) == (human.status_code, human["Location"])
    assert not User.objects.filter(username="robot").exists() and mail.outbox == []


@pytest.mark.django_db
def test_a_reset_bot_that_fills_the_honeypot_sees_success_and_nothing_is_sent():
    make_member()
    human = Client().post(reverse("account_reset_password"), {"email": "ada@example.com"})
    mail.outbox.clear()
    cache.clear()
    bot = Client().post(
        reverse("account_reset_password"), {"email": "ada@example.com", "website": "x"}
    )
    assert (bot.status_code, bot["Location"]) == (human.status_code, human["Location"])
    assert mail.outbox == []


def test_the_honeypots_are_hidden_from_people(client):
    for name in ["account_signup", "account_reset_password"]:
        html = client.get(reverse(name)).content.decode()
        trap = re.search(r'<div class="app-honeypot" aria-hidden="true">(.*?)</div>', html, re.S)
        assert trap and 'name="website"' in trap[1] and 'tabindex="-1"' in trap[1], name


# ---------- Turnstile ----------

PASS_SITE, PASS_SECRET = "1x00000000000000000000AA", "1x0000000000000000000000000000000AA"


@pytest.fixture
def turnstile_on(settings):
    """Cloudflare's published test keys; siteverify itself is always mocked."""
    settings.TURNSTILE_SITE_KEY, settings.TURNSTILE_SECRET_KEY = PASS_SITE, PASS_SECRET


def _siteverify(**reply):
    responses.add(responses.POST, turnstile.SITEVERIFY_URL, **reply)


@responses.activate
def test_verify_asks_cloudflare_and_accepts_only_a_clear_yes(turnstile_on):
    _siteverify(json={"success": True})
    assert turnstile.verify("XXXX.DUMMY.TOKEN.XXXX", "203.0.113.9")
    body = responses.calls[0].request.body
    assert f"secret={PASS_SECRET}" in body and "remoteip=203.0.113.9" in body


@responses.activate
@pytest.mark.parametrize(
    "reply",
    [
        {"json": {"success": False, "error-codes": ["invalid-input-response"]}},
        {"json": {"success": "true"}},
        {"json": ["success"]},
        {"body": "not json"},
        {"status": 500, "json": {"success": True}},
        {"body": requests.Timeout("slow")},
        {"body": requests.ConnectionError("down")},
    ],
)
def test_verify_fails_closed(turnstile_on, reply):
    _siteverify(**reply)
    assert turnstile.verify("XXXX.DUMMY.TOKEN.XXXX") is False


@responses.activate
@pytest.mark.parametrize("token", ["", "x" * 2049])
def test_verify_refuses_missing_and_oversized_tokens_without_asking(turnstile_on, token):
    assert turnstile.verify(token) is False
    assert len(responses.calls) == 0


def test_turnstile_is_off_until_both_keys_are_set(client, settings):
    assert not turnstile.is_enabled()
    assert "cf-turnstile" not in client.get(reverse("account_signup")).content.decode()
    settings.TURNSTILE_SITE_KEY = PASS_SITE
    assert not turnstile.is_enabled()


def test_the_widget_is_on_signup_and_reset_when_configured(client, turnstile_on):
    for name in ["account_signup", "account_reset_password"]:
        html = client.get(reverse(name)).content.decode()
        assert f'class="cf-turnstile app-turnstile" data-sitekey="{PASS_SITE}"' in html, name
        assert f'<script src="{turnstile.SCRIPT_URL}" async defer></script>' in html, name
    assert "cf-turnstile" not in client.get(reverse("account_login")).content.decode()


def _signup_post(client, username="ada", **extra):
    return client.post(
        reverse("account_signup"),
        {
            "email": f"{username}@example.com",
            "username": username,
            "password1": PASSWORD,
            "password2": PASSWORD,
            **extra,
        },
    )


@pytest.mark.django_db
@responses.activate
def test_signup_needs_turnstiles_yes_when_its_on(turnstile_on):
    refused = _signup_post(Client())  # no token at all
    assert refused.status_code == 200 and account_forms.NOT_A_PERSON in _page(refused).replace(
        "&#x27;", "'"
    )
    _siteverify(json={"success": False})
    assert (
        _signup_post(Client(), **{turnstile.RESPONSE_FIELD: "XXXX.DUMMY.TOKEN.XXXX"}).status_code
        == 200
    )
    _siteverify(body=requests.ConnectionError("Cloudflare is down"))
    assert (
        _signup_post(Client(), **{turnstile.RESPONSE_FIELD: "XXXX.DUMMY.TOKEN.XXXX"}).status_code
        == 200
    )
    assert not User.objects.exists()
    responses.replace(responses.POST, turnstile.SITEVERIFY_URL, json={"success": True})
    assert (
        _signup_post(Client(), **{turnstile.RESPONSE_FIELD: "XXXX.DUMMY.TOKEN.XXXX"}).status_code
        == 302
    )
    assert User.objects.filter(username="ada").exists()


@pytest.mark.django_db
@responses.activate
def test_turnstiles_yes_is_never_the_only_check(turnstile_on, tight_limits):
    _siteverify(json={"success": True})
    token = {turnstile.RESPONSE_FIELD: "XXXX.DUMMY.TOKEN.XXXX"}
    # The honeypot still catches a bot that solved the challenge...
    _signup_post(Client(), username="robot", website="spam", **token)
    assert not User.objects.filter(username="robot").exists()
    # ...and the rate limits still stop a flood of solved challenges.
    for n in range(2):
        cache.clear()
        _signup_post(Client(), username=f"member{n}", **token)
    cache.clear()
    refused = _signup_post(Client(), username="flood", **token)
    assert account_forms.TOO_MANY_ATTEMPTS in _page(refused).replace("&#x27;", "'")
    assert not User.objects.filter(username="flood").exists()


@pytest.mark.django_db
@responses.activate
def test_a_reset_request_needs_turnstiles_yes_when_its_on(turnstile_on):
    make_member()
    refused = Client().post(reverse("account_reset_password"), {"email": "ada@example.com"})
    assert account_forms.NOT_A_PERSON in _page(refused).replace("&#x27;", "'") and mail.outbox == []
    _siteverify(json={"success": True})
    Client().post(
        reverse("account_reset_password"),
        {"email": "ada@example.com", turnstile.RESPONSE_FIELD: "t"},
    )
    assert len(mail.outbox) == 1
