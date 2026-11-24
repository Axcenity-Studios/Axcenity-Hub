"""GitHub account linking: encrypted tokens, the link's checks against GitHub, OAuth state,
the connect and unlink flows, and where tokens must never appear.

No test drives real OAuth: SocialAccount rows are made directly, and GitHub's token and
user endpoints are mocked with `responses`.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin, SocialToken
from cryptography.fernet import Fernet
from django.contrib.admin import site
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import Client
from django.urls import reverse

from accounts import crypto, github, strings
from accounts.adapter import SocialAccountAdapter
from accounts.models import GitHubLink

User = get_user_model()
PASSWORD = "correct-horse-battery-staple-42"
# Fixed Fernet keys (test-only), so failures are reproducible.
KEY = "eE5nY3VhTnJ0d1lCV0lQZ3VHWHZmS2F6c0p6Q0JxS0Q="
OTHER_KEY = "S3VhcVhPZ0lWS2Z0eUV4Q3NWY3pYbWdaUXVoTEpCWmQ="
# Shaped like GitHub's tokens; never real.
ACCESS = "gho_16C7e42F292c6912E7710c838347Ae178B4a"
# GitHub's /user reply for its public example account, trimmed (tests/fixtures/github/).
USER = json.loads((Path(__file__).parent / "fixtures" / "github" / "user.json").read_text())
REFRESH = "ghr_1B4a2e77838347a7E420ce178F2E7c6912E169246c34E1ccbF66C46812d16D5B1A9Dc86A1498"


@pytest.fixture(autouse=True)
def _token_key(settings):
    settings.GITHUB_TOKEN_KEYS = [KEY]


def make_member(username="ada", email="ada@example.com", *, verified: bool = True):
    user = User.objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


def link_github(user, *, uid="583231", login="octocat") -> SocialAccount:
    return SocialAccount.objects.create(
        user=user, provider="github", uid=uid, extra_data={"id": int(uid), "login": login}
    )


def stored_rows() -> list[tuple]:
    """Every row of the link table exactly as the database holds it."""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {GitHubLink._meta.db_table}")
        return cursor.fetchall()


def test_the_test_keys_are_fernet_keys():
    Fernet(KEY), Fernet(OTHER_KEY)


# ---------- TDD 1: tokens are encrypted at rest ----------


@pytest.mark.django_db
def test_github_tokens_are_encrypted_at_rest_readable_only_with_the_key_and_deleted_on_unlink(
    settings,
):
    account = link_github(make_member())
    GitHubLink.objects.store(account, access_token=ACCESS, refresh_token=REFRESH)

    # The database never holds a token as typed.
    (row,) = stored_rows()
    assert not any(ACCESS in str(value) or REFRESH in str(value) for value in row)

    # It reads back with the environment's key...
    link = GitHubLink.objects.get(account=account)
    assert (link.access_token, link.refresh_token) == (ACCESS, REFRESH)

    # ...and with no other key, nor with none at all.
    settings.GITHUB_TOKEN_KEYS = [OTHER_KEY]
    with pytest.raises(crypto.Unreadable):
        link.access_token  # noqa: B018
    settings.GITHUB_TOKEN_KEYS = []
    with pytest.raises(crypto.KeyMissing):
        link.access_token  # noqa: B018
    settings.GITHUB_TOKEN_KEYS = [KEY]

    # Unlinking (allauth deletes the SocialAccount) deletes the tokens with it.
    account.delete()
    assert stored_rows() == []


# ---------- TDD 2: a 401 means the member must reconnect ----------


def stored_link(**kwargs) -> GitHubLink:
    account = link_github(make_member())
    return GitHubLink.objects.store(account, access_token=ACCESS, **kwargs)


@pytest.mark.django_db
@responses.activate
def test_a_401_from_github_marks_the_link_as_needing_reconnection_and_stops_asking():
    link = stored_link()
    responses.get(github.USER_URL, status=401, json={"message": "Bad credentials"})

    # The check reports it instead of raising...
    assert github.check_link(link) is github.LinkState.NEEDS_RECONNECT
    # ...the link is marked in the database, tokens kept until the member reconnects...
    link = GitHubLink.objects.get(pk=link.pk)
    assert link.needs_reconnect is True
    assert link.access_token == ACCESS
    # ...and GitHub isn't asked again with a token it has refused.
    assert github.check_link(link) is github.LinkState.NEEDS_RECONNECT
    assert len(responses.calls) == 1


# ---------- The link's checks against GitHub ----------

NEW_ACCESS = "ghu_NewAccessToken0000000000000000000000"
NEW_REFRESH = "ghr_NewRefreshToken000000000000000000000000000000000000000000000000000000000"
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


@pytest.mark.django_db
@responses.activate
def test_a_working_link_records_the_check_keeps_the_login_current_and_waits_before_asking_again():
    link = stored_link()
    responses.get(github.USER_URL, json={**USER, "login": "octocat-renamed"})

    assert github.check_link(link, now=NOW) is github.LinkState.OK
    link = GitHubLink.objects.get(pk=link.pk)
    assert link.checked_at == NOW and link.login == "octocat-renamed"
    request = responses.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {ACCESS}"
    assert request.headers["User-Agent"] and request.headers["X-GitHub-Api-Version"]

    # Within the interval GitHub isn't asked; after it, it is.
    assert github.check_link(link, now=NOW + timedelta(minutes=14)) is github.LinkState.OK
    assert len(responses.calls) == 1
    assert github.check_link(link, now=NOW + timedelta(minutes=16)) is github.LinkState.OK
    assert len(responses.calls) == 2


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    "reply",
    [
        {"status": 500},
        {"status": 502, "body": "<html>bad gateway</html>"},
        {"status": 403, "json": {"message": "API rate limit exceeded"}},
        {"status": 404},
        {"body": requests.Timeout("slow")},
        {"body": requests.ConnectionError("down")},
        {"status": 200, "body": "not json"},
        {"status": 200, "json": ["not", "an", "object"]},
    ],
)
def test_github_failing_leaves_the_link_as_it_was(reply):
    link = stored_link()
    responses.get(github.USER_URL, **reply)
    assert github.check_link(link, now=NOW) is github.LinkState.UNAVAILABLE
    link = GitHubLink.objects.get(pk=link.pk)
    assert (link.needs_reconnect, link.checked_at, link.access_token) == (False, None, ACCESS)


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize("login", ["", "<script>", "a" * 40, "-octo", "octo--cat", 42, None])
def test_a_login_github_reports_is_kept_only_when_it_is_a_valid_username(login):
    link = stored_link()
    responses.get(github.USER_URL, json={**USER, "login": login})
    assert github.check_link(link, now=NOW) is github.LinkState.OK
    assert GitHubLink.objects.get(pk=link.pk).login == "octocat"


@pytest.mark.django_db
@responses.activate
def test_an_expired_token_is_refreshed_first_and_both_new_tokens_are_stored_encrypted(settings):
    settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET = "Iv23liTestApp", "app-secret"
    link = stored_link(refresh_token=REFRESH, expires_at=NOW - timedelta(minutes=5))
    responses.post(
        github.TOKEN_URL,
        json={
            "access_token": NEW_ACCESS, "expires_in": 28800, "refresh_token": NEW_REFRESH,
            "refresh_token_expires_in": 15724800, "token_type": "bearer", "scope": "",
        },
    )  # fmt: skip
    responses.get(github.USER_URL, json=USER)

    assert github.check_link(link, now=NOW) is github.LinkState.OK
    refresh_call, user_call = responses.calls
    assert parse_qs(refresh_call.request.body) == {
        "client_id": ["Iv23liTestApp"],
        "client_secret": ["app-secret"],
        "grant_type": ["refresh_token"],
        "refresh_token": [REFRESH],
    }
    assert user_call.request.headers["Authorization"] == f"Bearer {NEW_ACCESS}"
    # Rotated: the new pair is stored (encrypted), and the old refresh token is gone.
    link = GitHubLink.objects.get(pk=link.pk)
    assert (link.access_token, link.refresh_token) == (NEW_ACCESS, NEW_REFRESH)
    assert link.expires_at == NOW + timedelta(seconds=28800)
    (row,) = stored_rows()
    assert not any(t in str(v) for v in row for t in [ACCESS, REFRESH, NEW_ACCESS, NEW_REFRESH])


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    "reply",
    [
        {
            "json": {
                "error": "bad_refresh_token",
                "error_description": "The refresh token passed is incorrect or expired.",
            }
        },
        {"json": {"access_token": ""}},
    ],
)
def test_a_refused_refresh_means_reconnecting_and_github_is_not_asked_with_the_old_token(reply):
    link = stored_link(refresh_token=REFRESH, expires_at=NOW - timedelta(minutes=5))
    responses.post(github.TOKEN_URL, **reply)
    assert github.check_link(link, now=NOW) is github.LinkState.NEEDS_RECONNECT
    assert GitHubLink.objects.get(pk=link.pk).needs_reconnect
    assert [c.request.url for c in responses.calls] == [github.TOKEN_URL]


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize("reply", [{"status": 500}, {"body": requests.Timeout("slow")}])
def test_a_refresh_github_cannot_answer_leaves_the_tokens_as_they_were(reply):
    link = stored_link(refresh_token=REFRESH, expires_at=NOW - timedelta(minutes=5))
    responses.post(github.TOKEN_URL, **reply)
    assert github.check_link(link, now=NOW) is github.LinkState.UNAVAILABLE
    link = GitHubLink.objects.get(pk=link.pk)
    assert (link.access_token, link.refresh_token, link.needs_reconnect) == (ACCESS, REFRESH, False)


@pytest.mark.django_db
@responses.activate
def test_an_expired_token_with_no_refresh_token_means_reconnecting():
    link = stored_link(expires_at=NOW - timedelta(minutes=5))
    assert github.check_link(link, now=NOW) is github.LinkState.NEEDS_RECONNECT
    assert len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
def test_a_token_the_current_key_cannot_read_means_reconnecting(settings):
    link = stored_link()
    settings.GITHUB_TOKEN_KEYS = [OTHER_KEY]
    assert github.check_link(link, now=NOW) is github.LinkState.NEEDS_RECONNECT
    assert len(responses.calls) == 0


@pytest.mark.django_db
def test_rotating_keys_keeps_old_tokens_readable_and_encrypts_new_ones_with_the_new_key(settings):
    link = stored_link()
    settings.GITHUB_TOKEN_KEYS = [OTHER_KEY, KEY]
    assert GitHubLink.objects.get(pk=link.pk).access_token == ACCESS
    GitHubLink.objects.store(link.account, access_token=NEW_ACCESS)
    settings.GITHUB_TOKEN_KEYS = [OTHER_KEY]
    assert GitHubLink.objects.get(pk=link.pk).access_token == NEW_ACCESS


# ---------- Linking through allauth (OAuth state, one account each way) ----------

APP = {"client_id": "Ov23liTestClientId", "secret": "oauth-app-secret", "key": ""}


@pytest.fixture
def github_on(settings):
    settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET = APP["client_id"], APP["secret"]
    settings.SOCIALACCOUNT_PROVIDERS = {"github": {"SCOPE": [], "APPS": [APP]}}


def start_link(client) -> str:
    """Press "Link GitHub"; returns the state allauth sent to GitHub."""
    response = client.post(reverse("github_login"))
    assert response.status_code == 302
    url = urlsplit(response["Location"])
    assert (url.scheme, url.netloc, url.path) == ("https", "github.com", "/login/oauth/authorize")
    query = parse_qs(url.query)
    assert query["client_id"] == [APP["client_id"]]
    assert query.get("scope", [""]) == [""]  # no scopes: public data only
    return query["state"][0]


def mock_github(*, user=None, access=ACCESS):
    responses.post(
        "https://github.com/login/oauth/access_token",
        json={"access_token": access, "token_type": "bearer", "scope": ""},
    )
    responses.get(github.USER_URL, json=user or USER)


def finish_link(client, state: str | None, code: str = "a1b2c3"):
    params = {"code": code} | ({"state": state} if state is not None else {})
    return client.get(reverse("github_callback"), params)


@pytest.mark.django_db
@responses.activate
def test_linking_github_stores_the_account_and_only_an_encrypted_token(client, github_on):
    member = make_member()
    client.force_login(member)
    mock_github()

    response = finish_link(client, start_link(client))

    assert response.status_code == 302 and response["Location"] == reverse(
        "socialaccount_connections"
    )
    assert strings.GITHUB_LINKED in client.get(response["Location"]).content.decode()
    account = SocialAccount.objects.get(user=member, provider="github")
    assert account.uid == str(USER["id"])
    assert GitHubLink.objects.get(account=account).access_token == ACCESS
    # allauth's plain-text token table stays empty; the session never holds the token.
    assert SocialToken.objects.count() == 0
    assert not any(ACCESS in str(s.get_decoded()) for s in Session.objects.all())
    assert ACCESS not in str(account.extra_data)


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize("state", [None, "", "not-a-state-we-issued"])
def test_a_callback_with_a_missing_or_unknown_state_links_nothing(client, github_on, state):
    client.force_login(make_member())
    start_link(client)  # a real state exists in the session, but isn't the one sent back
    mock_github()
    response = finish_link(client, state)
    assert response.status_code == 401  # allauth's authentication error page
    assert strings.GITHUB_LINK_FAILED_TITLE in unescape(response.content.decode())
    assert SocialAccount.objects.count() == 0 and GitHubLink.objects.count() == 0
    assert len(responses.calls) == 0  # refused before the code is ever exchanged


@pytest.mark.django_db
@responses.activate
def test_a_state_issued_to_another_session_links_nothing(github_on):
    ada, eve = Client(), Client()
    ada.force_login(make_member())
    eve.force_login(make_member("eve", "eve@example.com"))
    mock_github()
    response = finish_link(eve, start_link(ada))
    assert response.status_code == 401
    assert SocialAccount.objects.count() == 0 and len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
def test_a_state_works_once(client, github_on):
    member = make_member()
    client.force_login(member)
    mock_github()
    state = start_link(client)
    assert finish_link(client, state).status_code == 302
    SocialAccount.objects.filter(user=member).delete()  # so a replay would show

    calls = len(responses.calls)
    response = finish_link(client, state)
    assert response.status_code == 401
    assert SocialAccount.objects.count() == 0 and len(responses.calls) == calls


@pytest.mark.django_db
@responses.activate
def test_one_github_account_links_to_only_one_hub_account(client, github_on):
    bea = make_member("bea", "bea@example.com")
    GitHubLink.objects.store(link_github(bea), access_token="gho_beas_own_token")
    ada = make_member()
    client.force_login(ada)
    mock_github()  # GitHub says ada authorised as the account bea linked

    response = finish_link(client, start_link(client))

    assert response.status_code == 302
    assert response["Location"] == reverse("socialaccount_connections")
    assert strings.GITHUB_LINKED_ELSEWHERE in unescape(
        client.get(response["Location"]).content.decode()
    )
    account = SocialAccount.objects.get(provider="github")
    assert account.user == bea
    assert account.github_link.access_token == "gho_beas_own_token"
    assert not SocialAccount.objects.filter(user=ada).exists()


@pytest.mark.django_db
@responses.activate
def test_a_member_links_one_github_account_at_most(client, github_on):
    ada = make_member()
    GitHubLink.objects.store(link_github(ada, uid="1", login="first"), access_token=ACCESS)
    client.force_login(ada)
    mock_github(access=NEW_ACCESS)  # a different GitHub account (583231)

    response = finish_link(client, start_link(client))

    assert response["Location"] == reverse("socialaccount_connections")
    assert strings.GITHUB_ONE_ACCOUNT in unescape(client.get(response["Location"]).content.decode())
    assert list(SocialAccount.objects.values_list("uid", flat=True)) == ["1"]
    assert GitHubLink.objects.get().access_token == ACCESS


@pytest.mark.django_db
@responses.activate
def test_reconnecting_stores_the_new_token_and_clears_the_prompt(client, github_on):
    ada = make_member()
    link = GitHubLink.objects.store(link_github(ada), access_token=ACCESS)
    link.needs_reconnect = True
    link.save()
    client.force_login(ada)
    mock_github(access=NEW_ACCESS)

    assert finish_link(client, start_link(client)).status_code == 302

    link = GitHubLink.objects.get()
    assert (link.access_token, link.needs_reconnect) == (NEW_ACCESS, False)
    assert SocialAccount.objects.count() == 1


@pytest.mark.django_db
def test_github_never_signs_anyone_in_or_up(client, github_on, rf):
    # Starting needs a member, and every start is a link.
    response = client.post(reverse("github_login"))
    assert response.status_code == 302 and response["Location"].startswith(reverse("account_login"))
    # The sign-in and sign-up pages offer no GitHub button.
    for name in ["account_login", "account_signup"]:
        assert "github" not in unescape(client.get(reverse(name)).content.decode()).lower()

    # Even a finished authorisation that isn't a link (crafted, or from an old session) is
    # refused: anonymous to sign in, signed in back to Connected accounts.
    adapter = SocialAccountAdapter()
    login = SocialLogin(account=SocialAccount(provider="github", uid="583231"))
    for user, process, target in [
        (AnonymousUser(), "connect", reverse("account_login")),
        (make_member(), "login", reverse("socialaccount_connections")),
        (make_member("bea", "bea@example.com"), "redirect", reverse("socialaccount_connections")),
    ]:
        request = rf.get("/")
        request.user, request.session = user, SessionStore()
        request._messages = FallbackStorage(request)
        login.state = {"process": process}
        with pytest.raises(ImmediateHttpResponse) as refused:
            adapter.pre_social_login(request, login)
        assert refused.value.response["Location"] == target
    assert not adapter.is_open_for_signup(None, login)


@pytest.mark.django_db
def test_github_is_off_without_the_environments_app_and_key(client, settings):
    client.force_login(make_member())
    # A SocialApp row (as the admin used to allow) is ignored: secrets come from the environment.
    SocialApp.objects.create(
        provider="github", name="GitHub", client_id="db-id", secret="db-secret"
    )
    page = unescape(client.get(reverse("socialaccount_connections")).content.decode())
    assert strings.GITHUB_OFF in page and strings.GITHUB_CONNECT not in page
    assert client.post(reverse("github_login")).status_code == 404
    assert client.get(reverse("github_callback"), {"code": "x", "state": "y"}).status_code == 404

    # An app but no token key: still off, since a token would have nowhere safe to go.
    settings.SOCIALACCOUNT_PROVIDERS = {"github": {"SCOPE": [], "APPS": [APP]}}
    settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET = APP["client_id"], APP["secret"]
    settings.GITHUB_TOKEN_KEYS = []
    assert client.post(reverse("github_login")).status_code == 404


# ---------- The Connected accounts page ----------


@pytest.mark.django_db
def test_allauths_cancelled_and_error_pages_speak_of_linking(client):
    for name, title in [
        ("socialaccount_login_cancelled", strings.GITHUB_LINK_CANCELLED_TITLE),
        ("socialaccount_login_error", strings.GITHUB_LINK_FAILED_TITLE),
    ]:
        html = unescape(client.get(reverse(name)).content.decode())
        assert title in html and "entrance-panel" in html
        assert reverse("socialaccount_connections") in html
        assert "login" not in html.lower().split("<main", 1)[1].split("</main>")[0].replace(
            "/accounts/login/", ""
        )


@pytest.mark.django_db
@responses.activate
def test_a_revoked_link_shows_the_reconnect_prompt_instead_of_an_error(client, github_on):
    member = make_member()
    GitHubLink.objects.store(link_github(member), access_token=ACCESS)
    client.force_login(member)
    responses.get(github.USER_URL, status=401, json={"message": "Bad credentials"})

    response = client.get(reverse("socialaccount_connections"))

    assert response.status_code == 200
    html = unescape(response.content.decode())
    assert 'data-github-state="needs_reconnect"' in html
    assert strings.GITHUB_RECONNECT_PROMPT in html and strings.GITHUB_RECONNECT in html
    assert f'action="{reverse("github_login")}"' in html
    assert ACCESS not in html


@pytest.mark.django_db
@responses.activate
def test_the_page_shows_a_working_link_and_survives_github_being_down(client, github_on):
    member = make_member()
    GitHubLink.objects.store(link_github(member), access_token=ACCESS)
    client.force_login(member)

    responses.get(github.USER_URL, status=503)
    html = unescape(client.get(reverse("socialaccount_connections")).content.decode())
    assert 'data-github-state="unavailable"' in html and "octocat" in html
    assert strings.GITHUB_UNAVAILABLE_NOTE in html and strings.GITHUB_RECONNECT not in html

    responses.replace(responses.GET, github.USER_URL, json=USER)
    html = unescape(client.get(reverse("socialaccount_connections")).content.decode())
    assert 'data-github-state="ok"' in html and strings.GITHUB_STATE_OK in html
    assert strings.GITHUB_UNLINK in html and ACCESS not in html


@pytest.mark.django_db
def test_an_unlinked_member_is_offered_the_link_button(client, github_on):
    client.force_login(make_member())
    html = unescape(client.get(reverse("socialaccount_connections")).content.decode())
    assert 'data-github-state="none"' in html and strings.GITHUB_NOT_LINKED in html
    assert strings.GITHUB_CONNECT in html and strings.GITHUB_UNLINK not in html
    assert strings.GITHUB_ACCESS_NOTE in html


@pytest.mark.django_db
def test_a_link_without_a_stored_token_asks_to_reconnect(client, github_on):
    member = make_member()
    link_github(member)  # e.g. made in the admin
    client.force_login(member)
    html = unescape(client.get(reverse("socialaccount_connections")).content.decode())
    assert 'data-github-state="needs_reconnect"' in html and "octocat" in html


@pytest.mark.django_db
def test_unlinking_needs_a_fresh_reauthentication_then_deletes_the_link_and_its_tokens(
    client, github_on
):
    member = make_member()
    GitHubLink.objects.store(link_github(member), access_token=ACCESS, refresh_token=REFRESH)
    client.force_login(member)

    # Signed in isn't enough: allauth asks for the password first, and nothing is deleted.
    response = client.post(reverse("socialaccount_connections"))
    assert response.status_code == 302
    reauth = response["Location"]
    assert reauth.startswith(reverse("account_reauthenticate"))
    assert GitHubLink.objects.count() == 1 and SocialAccount.objects.count() == 1

    # After it, allauth replays the unlink.
    response = client.post(reauth, {"password": PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == reverse("socialaccount_connections")
    assert SocialAccount.objects.count() == 0 and stored_rows() == []
    assert strings.GITHUB_UNLINKED in client.get(response["Location"]).content.decode()

    # Within the re-authentication window, nothing left to unlink is a 404.
    assert client.post(reverse("socialaccount_connections")).status_code == 404


@pytest.mark.django_db
def test_unlinking_only_ever_touches_the_members_own_link(client, github_on):
    bea = make_member("bea", "bea@example.com")
    GitHubLink.objects.store(link_github(bea), access_token=ACCESS)
    ada = make_member()
    client.force_login(ada)
    reauth = client.post(reverse("socialaccount_connections"))["Location"]
    response = client.post(reauth, {"password": PASSWORD, "account": "1"})
    assert response.status_code == 404
    assert SocialAccount.objects.get().user == bea


# ---------- Tokens never appear in logs or the admin ----------


@pytest.mark.django_db
@responses.activate
def test_tokens_are_never_logged(client, github_on, caplog):
    caplog.set_level(logging.DEBUG)
    member = make_member()
    client.force_login(member)
    mock_github()
    finish_link(client, start_link(client))
    link = GitHubLink.objects.get()
    link.set_tokens(ACCESS, REFRESH, NOW - timedelta(minutes=5))
    link.save()
    responses.post(
        github.TOKEN_URL, json={"access_token": NEW_ACCESS, "refresh_token": NEW_REFRESH}
    )
    github.check_link(link, now=NOW)
    client.get(reverse("socialaccount_connections"))

    assert caplog.records  # something was logged, so the check below means something
    for token in [ACCESS, REFRESH, NEW_ACCESS, NEW_REFRESH]:
        assert token not in caplog.text
    assert ACCESS not in repr(link) and ACCESS not in str(link)


@pytest.mark.django_db
def test_the_admin_never_shows_github_tokens_or_secrets(client, github_on):
    member = make_member()
    account = link_github(member)
    GitHubLink.objects.store(account, access_token=ACCESS, refresh_token=REFRESH)
    admin = User.objects.create_superuser("root-admin", "root@example.com", PASSWORD)
    client.force_login(admin)

    assert not site.is_registered(GitHubLink)
    assert not site.is_registered(SocialToken) and not site.is_registered(SocialApp)
    pages = [
        client.get(reverse("admin:index")),
        client.get(reverse("admin:socialaccount_socialaccount_change", args=[account.pk])),
        client.get(reverse("admin:auth_user_change", args=[member.pk])),
    ]
    for page in pages:
        assert page.status_code == 200
        html = page.content.decode()
        assert ACCESS not in html and REFRESH not in html and APP["secret"] not in html
