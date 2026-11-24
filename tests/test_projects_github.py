"""Linked repositories: the member's permission resolved before every repository-dependent
action, GitHub's rate limits and failures, ETags, duplicate links, and the details kept current.

No test reaches GitHub: `api.github.com/repos/...` is mocked with `responses`, from GitHub's
documented example repository (tests/fixtures/github/repository.json, trimmed).
"""

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path

import pytest
import requests
import responses
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse

from accounts import github as account_github
from accounts.models import GitHubLink
from projects import github, services, strings, webhooks
from projects.github import Reason
from projects.models import Project, RepositoryLink

User = get_user_model()
PASSWORD = "correct-horse-battery-staple-42"
KEY = "eE5nY3VhTnJ0d1lCV0lQZ3VHWHZmS2F6c0p6Q0JxS0Q="  # test-only Fernet key
ACCESS = "gho_16C7e42F292c6912E7710c838347Ae178B4a"  # shaped like a token; never real
REPOSITORY = json.loads(
    (Path(__file__).parent / "fixtures" / "github" / "repository.json").read_text()
)
FULL_NAME = REPOSITORY["full_name"]
REPO_URL = github.repository_url(FULL_NAME)
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _keys(settings):
    settings.GITHUB_TOKEN_KEYS = [KEY]
    settings.GITHUB_WEBHOOK_SECRET = "root-secret-for-tests-only"


def make_member(username="ada", *, verified: bool = True, github_uid: str | None = "583231"):
    email = f"{username}@example.com"
    user = User.objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    if github_uid:
        account = SocialAccount.objects.create(
            user=user, provider="github", uid=github_uid, extra_data={"login": username}
        )
        GitHubLink.objects.store(account, access_token=ACCESS)
    return user


def repo_reply(role: str = "admin", **fields) -> dict:
    """GitHub's reply for the example repository, as seen by a member with `role`."""
    order = ["pull", "triage", "push", "maintain", "admin"]
    granted = order[: order.index(role) + 1] if role != "none" else []
    permissions = {name: name in granted for name in order}
    return {**REPOSITORY, "permissions": permissions, **fields}


def refused(action, *args, **kwargs) -> Reason | None:
    """Run a repository action; the Reason it was refused for, or None when it went ahead."""
    try:
        action(*args, **kwargs)
    except services.RepositoryError as error:
        return error.reason
    return None


# ---------- TDD 3: permission resolved before every repository-dependent action ----------


@pytest.mark.django_db
@responses.activate
def test_permission_is_resolved_before_each_action_and_a_downgrade_or_removal_blocks_it(
    settings,
):
    ada = make_member()
    project = Project.objects.create(owner=ada, name="Space Game")
    responses.get(REPO_URL, json=repo_reply("admin"), headers={"ETag": '"v1"'})

    # Linked while GitHub reports her an admin.
    services.link_repository(ada, project, FULL_NAME, now=NOW)
    assert len(responses.calls) == 1

    # GitHub downgrades her to write access.
    responses.replace(responses.GET, REPO_URL, json=repo_reply("push"), headers={"ETag": '"v2"'})

    # A check younger than 60 s is reused for an admin-only action (the documented window)...
    assert refused(services.webhook_settings, ada, project, now=NOW + timedelta(seconds=59)) is None
    assert len(responses.calls) == 1
    # ...and at 60 s it has expired: GitHub is asked, and the admin-only action is refused.
    later = NOW + timedelta(seconds=60)
    assert refused(services.webhook_settings, ada, project, now=later) is Reason.INSUFFICIENT
    assert len(responses.calls) == 2
    # A read-only action still goes ahead: the Hub grants exactly what GitHub does.
    assert refused(services.refresh_repository, ada, project, now=later) is None

    # Her access is removed (GitHub answers 404): every repository action is refused...
    responses.replace(responses.GET, REPO_URL, status=404, json={"message": "Not Found"})
    gone = NOW + timedelta(seconds=61)
    assert refused(services.refresh_repository, ada, project, now=gone) is Reason.NO_ACCESS
    assert refused(services.webhook_settings, ada, project, now=gone) is Reason.NO_ACCESS

    # ...and when the permission can't be established at all, it fails closed, even though
    # an admin permission was once known: an outage, or a reply without `permissions`.
    responses.replace(responses.GET, REPO_URL, status=502)
    outage = NOW + timedelta(minutes=5)
    assert refused(services.webhook_settings, ada, project, now=outage) is Reason.UNAVAILABLE
    no_role = {k: v for k, v in repo_reply("admin").items() if k != "permissions"}
    responses.replace(responses.GET, REPO_URL, json=no_role)
    assert refused(services.webhook_settings, ada, project, now=outage) is Reason.UNVERIFIABLE

    # Nothing about the link changed while it was refused.
    assert RepositoryLink.objects.get(project=project).github_id == REPOSITORY["id"]


# ---------- Linking ----------


def linked_project(user, name="Space Game", *, now=NOW) -> Project:
    project = Project.objects.create(owner=user, name=name)
    with responses.RequestsMock() as mock:
        mock.get(REPO_URL, json=repo_reply("admin"), headers={"ETag": '"v1"'})
        services.link_repository(user, project, FULL_NAME, now=now)
    github.forget_permission(user, FULL_NAME)
    return project


@pytest.mark.django_db
@responses.activate
def test_linking_stores_githubs_details_and_needs_admin_now():
    ada = make_member()
    project = Project.objects.create(owner=ada, name="Space Game")
    responses.get(REPO_URL, json=repo_reply("maintain"))
    assert (
        refused(services.link_repository, ada, project, FULL_NAME, now=NOW) is Reason.INSUFFICIENT
    )
    assert not RepositoryLink.objects.exists()

    github.forget_permission(ada, FULL_NAME)
    responses.replace(responses.GET, REPO_URL, json=repo_reply("admin"), headers={"ETag": '"v1"'})
    link = services.link_repository(ada, project, f"https://github.com/{FULL_NAME}.git", now=NOW)
    assert (link.github_id, link.full_name, link.html_url) == (
        REPOSITORY["id"], FULL_NAME, REPOSITORY["html_url"]
    )  # fmt: skip
    assert (link.default_branch, link.private, link.fetched_at) == ("master", False, NOW)
    assert link.pushed_at == datetime(2011, 1, 26, 19, 6, 43, tzinfo=UTC)
    assert link.linked_by == ada
    # The request carried her token and GitHub's headers; the token isn't stored as typed.
    request = responses.calls[-1].request
    assert request.headers["Authorization"] == f"Bearer {ACCESS}"
    assert request.headers["X-GitHub-Api-Version"] and request.headers["User-Agent"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("octocat/Hello-World", "octocat/Hello-World"),
        ("  https://github.com/octocat/Hello-World/ ", "octocat/Hello-World"),
        ("github.com/octocat/Hello-World.git", "octocat/Hello-World"),
        ("octocat", ""),
        ("octocat/Hello/World", ""),
        ("../etc/passwd", ""),
        ("octocat/..", ""),
        ("-octocat/x", ""),
        ("https://evil.example/octocat/x", ""),
        ("octocat/x?y=1", ""),
    ],
)
def test_only_an_owner_slash_name_is_accepted(text, expected):
    assert github.normalize_full_name(text) == expected


@pytest.mark.django_db
@responses.activate
def test_a_repository_links_to_one_hub_project_only():
    ada, grace = make_member(), make_member("grace", github_uid="9001")
    linked_project(ada)
    theirs = Project.objects.create(owner=grace, name="Moon Base")
    responses.get(REPO_URL, json=repo_reply("admin"))
    with pytest.raises(services.RepositoryError) as error:
        services.link_repository(grace, theirs, FULL_NAME, now=NOW)
    assert str(error.value) == strings.REPOSITORY_TAKEN
    # Nor a second project of the same owner; nor a second repository on one project.
    mine = Project.objects.create(owner=ada, name="Second")
    with pytest.raises(services.RepositoryError) as again:
        services.link_repository(ada, mine, FULL_NAME, now=NOW)
    assert str(again.value) == strings.REPOSITORY_TAKEN
    with pytest.raises(services.RepositoryError) as twice:
        services.link_repository(ada, Project.objects.get(name="Space Game"), "a/b", now=NOW)
    assert str(twice.value) == strings.PROJECT_HAS_REPOSITORY
    assert RepositoryLink.objects.count() == 1
    # The database holds the rule too.
    with pytest.raises(IntegrityError), transaction.atomic():
        RepositoryLink.objects.create(
            project=theirs, github_id=REPOSITORY["id"], full_name=FULL_NAME, html_url="x"
        )


@pytest.mark.django_db
def test_without_a_github_account_or_with_one_needing_reconnection_nothing_asks_github():
    ada = make_member(github_uid=None)
    project = Project.objects.create(owner=ada, name="Space Game")
    assert refused(services.link_repository, ada, project, FULL_NAME, now=NOW) is Reason.NO_GITHUB
    grace = make_member("grace", github_uid="9001")
    GitHubLink.objects.filter(account__user=grace).update(needs_reconnect=True)
    theirs = Project.objects.create(owner=grace, name="Moon Base")
    assert refused(services.link_repository, grace, theirs, FULL_NAME, now=NOW) is Reason.RECONNECT


# ---------- GitHub's failures ----------


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    "reply, reason",
    [
        ({"status": 401, "json": {"message": "Bad credentials"}}, Reason.RECONNECT),
        ({"status": 403, "json": {"message": "Repository access blocked"}}, Reason.NO_ACCESS),
        ({"status": 404, "json": {"message": "Not Found"}}, Reason.NO_ACCESS),
        ({"status": 500}, Reason.UNAVAILABLE),
        ({"status": 503}, Reason.UNAVAILABLE),
        ({"body": requests.Timeout("timed out")}, Reason.UNAVAILABLE),
        ({"body": requests.ConnectionError("refused")}, Reason.UNAVAILABLE),
        ({"body": "not json"}, Reason.UNVERIFIABLE),
        ({"json": ["a", "list"]}, Reason.UNVERIFIABLE),
        ({"json": {**REPOSITORY, "permissions": {"admin": "yes"}}}, Reason.UNVERIFIABLE),
        ({"json": {**REPOSITORY, "id": True}}, Reason.UNVERIFIABLE),
        ({"json": {**REPOSITORY, "html_url": "https://evil.example/x"}}, Reason.UNVERIFIABLE),
    ],
)
def test_every_github_failure_refuses_the_action_without_raising(reply, reason):
    ada = make_member()
    project = Project.objects.create(owner=ada, name="Space Game")
    responses.get(REPO_URL, **reply)
    assert refused(services.link_repository, ada, project, FULL_NAME, now=NOW) is reason
    assert not RepositoryLink.objects.exists()
    # A 401 marks her GitHub link for reconnection (Phase 9's prompt), and stops asking.
    if reason is Reason.RECONNECT:
        assert GitHubLink.objects.get(account__user=ada).needs_reconnect is True
        assert refused(services.link_repository, ada, project, FULL_NAME, now=NOW) is reason
        assert len(responses.calls) == 1


@pytest.mark.django_db
@responses.activate
def test_an_expired_github_app_token_is_refreshed_before_asking():
    ada = make_member()
    link = GitHubLink.objects.get(account__user=ada)
    link.set_tokens(ACCESS, "ghr_refresh", NOW - timedelta(hours=1))
    link.save()
    project = Project.objects.create(owner=ada, name="Space Game")
    responses.post(
        account_github.TOKEN_URL,
        json={"access_token": "gho_new", "refresh_token": "ghr_new", "expires_in": 28800},
    )
    responses.get(REPO_URL, json=repo_reply("admin"))
    services.link_repository(ada, project, FULL_NAME, now=NOW)
    assert responses.calls[-1].request.headers["Authorization"] == "Bearer gho_new"


# ---------- Rate limits, budget and ETags ----------


@pytest.mark.django_db
@responses.activate
def test_githubs_rate_limit_backs_off_for_that_member_until_the_reset():
    ada, grace = make_member(), make_member("grace", github_uid="9001")
    mine = Project.objects.create(owner=ada, name="Space Game")
    reset = int((NOW + timedelta(minutes=20)).timestamp())
    responses.get(
        REPO_URL,
        status=403,
        json={"message": "API rate limit exceeded"},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
    )
    with pytest.raises(services.RepositoryError) as error:
        services.link_repository(ada, mine, FULL_NAME, now=NOW)
    assert error.value.reason is Reason.RATE_LIMITED
    assert error.value.retry_at == datetime.fromtimestamp(reset, UTC)
    # Until the reset GitHub isn't asked for her at all...
    later = NOW + timedelta(minutes=19)
    assert refused(services.link_repository, ada, mine, FULL_NAME, now=later) is Reason.RATE_LIMITED
    assert len(responses.calls) == 1
    # ...while another member's requests go ahead (GitHub's limit is per token).
    responses.replace(responses.GET, REPO_URL, json=repo_reply("admin"))
    theirs = Project.objects.create(owner=grace, name="Moon Base")
    assert refused(services.link_repository, grace, theirs, FULL_NAME, now=later) is None
    # After the reset she's asked about again.
    RepositoryLink.objects.all().delete()
    after = NOW + timedelta(minutes=21)
    assert refused(services.link_repository, ada, mine, FULL_NAME, now=after) is None


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    "reply",
    [
        {"status": 429, "headers": {"Retry-After": "120"}},
        {"status": 403, "headers": {"Retry-After": "120"}, "json": {"message": "secondary"}},
        {"status": 403, "json": {"message": "You have exceeded a secondary rate limit."}},
    ],
)
def test_retry_after_and_secondary_limits_back_off_too(reply):
    ada = make_member()
    project = Project.objects.create(owner=ada, name="Space Game")
    responses.get(REPO_URL, **reply)
    with pytest.raises(services.RepositoryError) as error:
        services.link_repository(ada, project, FULL_NAME, now=NOW)
    assert error.value.reason is Reason.RATE_LIMITED and error.value.retry_at > NOW
    assert (
        refused(services.link_repository, ada, project, FULL_NAME, now=NOW) is Reason.RATE_LIMITED
    )
    assert len(responses.calls) == 1


@pytest.mark.django_db
@responses.activate
def test_a_reply_spending_the_last_request_backs_off_after_using_it():
    ada = make_member()
    project = Project.objects.create(owner=ada, name="Space Game")
    reset = int((NOW + timedelta(minutes=5)).timestamp())
    responses.get(
        REPO_URL,
        json=repo_reply("admin"),
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
    )
    services.link_repository(ada, project, FULL_NAME, now=NOW)  # this reply is used
    assert github.backoff_until(ada, NOW) == datetime.fromtimestamp(reset, UTC)


@pytest.mark.django_db
@responses.activate
def test_the_hub_spends_at_most_the_hourly_budget_per_member(settings):
    settings.GITHUB_CALLS_PER_MEMBER_PER_HOUR = 2
    ada = make_member()
    project = linked_project(ada)  # one call
    responses.get(REPO_URL, json=repo_reply("admin"))
    assert refused(services.refresh_repository, ada, project, now=NOW) is None  # two
    with pytest.raises(services.RepositoryError) as error:
        services.refresh_repository(ada, project, now=NOW + timedelta(minutes=1))
    assert error.value.reason is Reason.RATE_LIMITED
    assert error.value.retry_at == NOW.replace(minute=0) + timedelta(hours=1)
    assert len(responses.calls) == 1  # (the link's call was its own mock)
    # The next hour has a new budget.
    assert refused(services.refresh_repository, ada, project, now=NOW + timedelta(hours=1)) is None


@pytest.mark.django_db
@responses.activate
def test_repeat_checks_send_the_etag_and_a_304_reuses_what_github_said():
    ada = make_member()
    project = Project.objects.create(owner=ada, name="Space Game")
    responses.get(REPO_URL, json=repo_reply("admin"), headers={"ETag": '"v1"'})
    services.link_repository(ada, project, FULL_NAME, now=NOW)
    responses.replace(responses.GET, REPO_URL, status=304, headers={"ETag": '"v1"'})
    # Expired, so asked again, conditionally: GitHub says nothing changed, admin stands.
    later = NOW + timedelta(minutes=2)
    assert refused(services.webhook_settings, ada, project, now=later) is None
    assert responses.calls[-1].request.headers["If-None-Match"] == '"v1"'
    assert refused(services.refresh_repository, ada, project, now=later) is None
    assert RepositoryLink.objects.get().fetched_at == later
    # A 304 without an earlier reply to reuse proves nothing: refused, unverifiable.
    github.forget_permission(ada, FULL_NAME)
    assert refused(services.refresh_repository, ada, project, now=later) is Reason.UNVERIFIABLE
    assert "If-None-Match" not in responses.calls[-1].request.headers


# ---------- Keeping details current ----------


@pytest.mark.django_db
@responses.activate
def test_refreshing_follows_githubs_changes_and_refuses_a_replaced_repository():
    ada = make_member()
    project = linked_project(ada)
    renamed = {
        "full_name": "octocat/Hello-Engine",
        "html_url": "https://github.com/octocat/Hello-Engine",
    }
    responses.get(
        REPO_URL, json=repo_reply("pull", description="Renamed", archived=True, **renamed)
    )
    services.refresh_repository(ada, project, now=NOW)
    link = RepositoryLink.objects.get()
    assert (link.full_name, link.description, link.archived) == (
        "octocat/Hello-Engine", "Renamed", True
    )  # fmt: skip
    # The name now answers with another repository's id: refused, nothing changed.
    responses.get(
        github.repository_url("octocat/Hello-Engine"), json=repo_reply("admin", id=42, **renamed)
    )
    with pytest.raises(services.RepositoryError) as error:
        services.refresh_repository(ada, project, now=NOW + timedelta(minutes=5))
    assert str(error.value) == strings.REPOSITORY_REPLACED
    assert RepositoryLink.objects.get().github_id == REPOSITORY["id"]


@pytest.mark.django_db
def test_unlinking_never_asks_github():
    ada = make_member()
    project = linked_project(ada)
    with responses.RequestsMock():  # any request would fail the test
        services.unlink_repository(ada, project)
    assert not RepositoryLink.objects.exists()
    # Another member can't unlink it (the views' 404).
    grace = make_member("grace", github_uid="9001")
    project = linked_project(ada, "Again")
    with pytest.raises(Project.DoesNotExist):
        services.unlink_repository(grace, project)
    assert RepositoryLink.objects.count() == 1


# ---------- The pages ----------


@pytest.mark.django_db
@responses.activate
def test_the_project_page_links_a_repository_and_shows_its_details(client):
    ada = make_member()
    client.force_login(ada)
    project = Project.objects.create(owner=ada, name="Space Game")
    page = client.get(project.get_absolute_url()).content.decode()
    assert 'data-repository="none"' in page and 'name="repository"' in page
    responses.get(REPO_URL, json=repo_reply("admin"))
    response = client.post(
        reverse("projects:link_repository", args=[project.slug]), {"repository": FULL_NAME}
    )
    assert response["Location"] == project.get_absolute_url()
    page = client.get(project.get_absolute_url()).content.decode()
    assert 'data-repository="linked"' in page and strings.REPOSITORY_LINKED in page
    assert FULL_NAME in page and REPOSITORY["html_url"] in page and "master" in page
    # Refused: the message says why, on the same page.
    other = Project.objects.create(owner=ada, name="Other")
    client.post(reverse("projects:link_repository", args=[other.slug]), {"repository": "nope"})
    assert strings.REPOSITORY_NAME_INVALID in unescape(
        client.get(other.get_absolute_url()).content.decode()
    )


@pytest.mark.django_db
def test_a_member_without_github_starts_at_step_one(client):
    ada = make_member(github_uid=None)
    client.force_login(ada)
    project = Project.objects.create(owner=ada, name="Space Game")
    page = unescape(client.get(project.get_absolute_url()).content.decode())
    assert re.search(r'id="setup-account" class="pj-step" data-state="current"', page)
    assert strings.STEPS["account"]["action"] in page
    assert reverse("socialaccount_connections") in page
    assert 'name="repository"' not in page  # step 2 waits behind step 1


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    "reply, message",
    [
        (
            {"status": 403, "json": {"message": "API rate limit exceeded"},
             "headers": {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"}},
            "rate_limited",
        ),
        ({"status": 401}, "reconnect"),
        ({"status": 404}, "no_access"),
        ({"status": 502}, "unavailable"),
        ({"body": requests.Timeout()}, "unavailable"),
    ],
)  # fmt: skip
def test_when_github_fails_the_page_shows_the_stored_details_with_a_notice(client, reply, message):
    ada = make_member()
    client.force_login(ada)
    project = linked_project(ada, now=NOW - timedelta(days=2))  # stale: fetched again on view
    responses.get(REPO_URL, **reply)
    response = client.get(project.get_absolute_url())
    assert response.status_code == 200
    page = unescape(response.content.decode())
    assert "data-repository-notice" in page and strings.REFUSED[message] in page
    assert FULL_NAME in page and "22 Nov 2026" in page  # the stored details and their date
    if message == "rate_limited":
        assert "Try again after" in page


@pytest.mark.django_db
@responses.activate
def test_a_fresh_page_view_doesnt_ask_github(client):
    ada = make_member()
    client.force_login(ada)
    project = linked_project(ada, now=datetime.now(UTC))
    assert client.get(project.get_absolute_url()).status_code == 200
    assert len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
def test_the_webhook_step_shows_the_links_url_and_secret_to_an_admin_only(client, settings):
    ada = make_member()
    client.force_login(ada)
    project = linked_project(ada, now=datetime.now(UTC))
    link = RepositoryLink.objects.get()
    secret = webhooks.secret_for(link.hook_id)
    # The project page alone never shows the secret, nor asks GitHub.
    page = client.get(project.get_absolute_url()).content.decode()
    assert secret not in page and "data-show-webhook" in page
    assert len(responses.calls) == 0

    responses.get(REPO_URL, json=repo_reply("admin"))
    response = client.get(project.get_absolute_url() + "?webhook=show")
    page = unescape(response.content.decode())
    assert response.status_code == 200 and "no-store" in response["Cache-Control"]
    assert secret in page
    assert f"http://testserver/projects/hooks/github/{link.hook_id}/" in page
    assert f"{REPOSITORY['html_url']}/settings/hooks/new" in page
    assert "application/json" in page and "Pushes and Repositories" in page
    assert settings.GITHUB_WEBHOOK_SECRET not in page
    assert RepositoryLink.objects.get().webhook_shown_at is not None
    # Not an admin any more (after the 60 s window): the reason, and no secret.
    github.forget_permission(ada, FULL_NAME)
    responses.replace(responses.GET, REPO_URL, json=repo_reply("push"))
    response = client.get(project.get_absolute_url() + "?webhook=show")
    page = unescape(response.content.decode())
    assert strings.REFUSED["insufficient"] in page and "data-webhook-error" in page
    assert secret not in page and "no-store" not in response.get("Cache-Control", "")
    # Webhooks off: the step says so, and showing does nothing.
    settings.GITHUB_WEBHOOK_SECRET = ""
    page = unescape(client.get(project.get_absolute_url() + "?webhook=show").content.decode())
    assert strings.STEPS["webhook"]["off"] in page and "data-show-webhook" not in page


@pytest.mark.django_db
@responses.activate
def test_no_token_reaches_the_logs(caplog):
    caplog.set_level(logging.DEBUG)
    ada = make_member()
    project = Project.objects.create(owner=ada, name="Space Game")
    for reply in [{"status": 500}, {"body": requests.Timeout()}, {"status": 401}]:
        responses.upsert(responses.GET, REPO_URL, **reply)
        assert refused(services.link_repository, ada, project, FULL_NAME, now=NOW) is not None
    assert ACCESS not in caplog.text
