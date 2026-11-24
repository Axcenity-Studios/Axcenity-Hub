"""The repository setup checklist (projects.setup) on the project page and the cards, and the
public setup guide."""

import json
import re
import uuid
from datetime import UTC, datetime
from html import unescape

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import GitHubLink
from projects import strings, webhooks
from projects.models import Project, RepositoryLink
from projects.setup import State, setup_for

User = get_user_model()
KEY = "eE5nY3VhTnJ0d1lCV0lQZ3VHWHZmS2F6c0p6Q0JxS0Q="  # test-only Fernet key
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _keys(settings):
    settings.GITHUB_TOKEN_KEYS = [KEY]
    settings.GITHUB_WEBHOOK_SECRET = "root-secret-for-tests-only"


def make_member(username="ada", *, github: bool = True):
    user = User.objects.create_user(username, f"{username}@example.com", "pw-correct-horse-42")
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    if github:
        account = SocialAccount.objects.create(
            user=user,
            provider="github",
            uid=str(abs(hash(username)) % 10**6),
            extra_data={"login": "octocat"},
        )
        GitHubLink.objects.store(account, access_token="gho_test_only_not_real")
    return user


def make_link(project, **fields) -> RepositoryLink:
    return RepositoryLink.objects.create(
        project=project,
        github_id=1296269,
        full_name="octocat/Hello-World",
        html_url="https://github.com/octocat/Hello-World",
        fetched_at=datetime.now(UTC),  # fresh: the page doesn't ask GitHub
        **fields,
    )


def states(user, link) -> list[str]:
    return [step.state.value for step in setup_for(user, link).steps]


# ---------- The steps' states ----------


@pytest.mark.django_db
def test_the_steps_follow_the_real_records_one_current_step_at_a_time(settings):
    ada = make_member(github=False)
    project = Project.objects.create(owner=ada, name="Space Game")
    assert states(ada, None) == ["current", "waiting", "waiting", "waiting"]

    ada = User.objects.get(pk=ada.pk)
    account = SocialAccount.objects.create(user=ada, provider="github", uid="1", extra_data={})
    GitHubLink.objects.store(account, access_token="gho_test_only_not_real")
    assert states(ada, None) == ["done", "current", "waiting", "waiting"]

    link = make_link(project)
    assert states(ada, link) == ["done", "done", "current", "waiting"]
    link.webhook_shown_at = NOW
    assert states(ada, link) == ["done", "done", "done", "current"]
    link.first_webhook_at = link.webhook_at = NOW
    setup = setup_for(ada, link)
    assert states(ada, link) == ["done", "done", "done", "done"]
    assert (setup.done, setup.total, setup.complete) == (4, 4, True)

    # A delivery proves the webhook was added even if the settings were never shown here.
    link.webhook_shown_at = None
    assert states(ada, link) == ["done", "done", "done", "done"]

    # GitHub refused the token: step 1 needs attention, and the webhook waits behind it.
    GitHubLink.objects.filter(account=account).update(needs_reconnect=True)
    fresh = RepositoryLink.objects.get(pk=link.pk)
    assert states(ada, fresh) == ["attention", "done", "waiting", "waiting"]

    # Deleted on GitHub: step 2 needs attention.
    GitHubLink.objects.filter(account=account).update(needs_reconnect=False)
    link.deleted_on_github, link.first_webhook_at, link.webhook_shown_at = True, None, None
    assert states(ada, link) == ["done", "attention", "waiting", "waiting"]

    # Webhooks off on this server: steps 3 and 4 are off, and the setup never claims to be
    # complete (the repository is linked, but GitHub can't send live updates).
    settings.GITHUB_WEBHOOK_SECRET = ""
    RepositoryLink.objects.filter(pk=link.pk).update(deleted_on_github=False)
    setup = setup_for(ada, RepositoryLink.objects.get(pk=link.pk))
    assert [s.state for s in setup.steps] == [State.DONE, State.DONE, State.OFF, State.OFF]
    assert (setup.done, setup.total, setup.complete, setup.live_updates_off) == (2, 4, False, True)


# ---------- The checklist on the page ----------


def step_state(page: str, key: str) -> str:
    return re.search(rf'id="setup-{key}" class="pj-step" data-state="(\w+)"', page)[1]


@pytest.mark.django_db
def test_the_checklist_opens_the_current_step_and_folds_once_done(client):
    ada = make_member()
    client.force_login(ada)
    project = Project.objects.create(owner=ada, name="Space Game")
    page = unescape(client.get(project.get_absolute_url()).content.decode())
    assert (
        '<details id="setup" class="panel pj-panel pj-setup" data-setup="incomplete" open>' in page
    )
    assert step_state(page, "account") == "done" and "Linked as octocat." in page
    assert step_state(page, "repository") == "current" and 'name="repository"' in page
    assert "1 / 4" in page

    link = make_link(project)
    page = unescape(client.get(project.get_absolute_url()).content.decode())
    assert step_state(page, "webhook") == "current" and "data-show-webhook" in page
    assert "octocat/Hello-World on GitHub." in page and 'name="repository"' not in page
    assert strings.REPOSITORY_POLLED in page

    RepositoryLink.objects.filter(pk=link.pk).update(webhook_shown_at=NOW)
    page = unescape(client.get(project.get_absolute_url()).content.decode())
    assert step_state(page, "delivery") == "current"
    assert strings.STEPS["delivery"]["trouble"] in page and reverse("projects:guide") in page

    RepositoryLink.objects.filter(pk=link.pk).update(first_webhook_at=NOW, webhook_at=NOW)
    page = unescape(client.get(project.get_absolute_url()).content.decode())
    assert '<details id="setup" class="panel pj-panel pj-setup" data-setup="complete">' in page
    assert strings.SETUP_DONE_TITLE in page and "4 / 4" in page
    assert "First delivery 24 Nov 2026, 12:00 UTC." in page
    assert strings.REPOSITORY_LIVE in page


@pytest.mark.django_db
def test_the_setup_reaches_done_through_a_real_ping(client):
    ada = make_member()
    client.force_login(ada)
    project = Project.objects.create(owner=ada, name="Space Game")
    link = make_link(project, webhook_shown_at=NOW)
    body = json.dumps({"zen": "Design for failure.", "repository": {"id": link.github_id}}).encode()
    response = client.post(
        webhooks.payload_path(link.hook_id),
        body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT="ping",
        HTTP_X_GITHUB_DELIVERY=str(uuid.uuid4()),
        HTTP_X_HUB_SIGNATURE_256=webhooks.signature(webhooks.secret_for(link.hook_id), body),
    )
    assert response.status_code == 200
    page = client.get(project.get_absolute_url()).content.decode()
    assert 'data-setup="complete"' in page


@pytest.mark.django_db
def test_the_webhook_values_come_with_copy_buttons_and_a_local_warning(client, settings):
    import responses

    ada = make_member()
    client.force_login(ada)
    project = Project.objects.create(owner=ada, name="Space Game")
    link = make_link(project)
    payload = {
        "id": link.github_id, "full_name": link.full_name, "html_url": link.html_url,
        "private": False, "archived": False,
        "permissions": {"admin": True, "push": True, "pull": True},
    }  # fmt: skip
    with responses.RequestsMock() as mock:
        mock.get("https://api.github.com/repos/octocat/Hello-World", json=payload)
        html = client.get(project.get_absolute_url() + "?webhook=show").content.decode()
    # Copy buttons for the URL and the secret only, hidden until projects.js shows them.
    buttons = re.findall(
        r'<button type="button" class="pj-copy" data-copy="([\w-]+)"[^>]*hidden>', html
    )
    assert len(buttons) == 2
    for target in buttons:
        assert f'id="{target}"' in html
    assert "js/projects.js" in html
    # The test server's host is "testserver": no warning. On 127.0.0.1 there is one.
    assert "data-local-warning" not in html
    settings.ALLOWED_HOSTS = ["127.0.0.1"]
    # (Within 60 s of the last check, so GitHub isn't asked again.)
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        mock.get("https://api.github.com/repos/octocat/Hello-World", json=payload)
        html = client.get(
            project.get_absolute_url() + "?webhook=show", HTTP_HOST="127.0.0.1:8000"
        ).content.decode()
    assert "data-local-warning" in html and "127.0.0.1:8000" in html and "HUB_PUBLIC_URL" in html


@pytest.mark.django_db
@pytest.mark.parametrize("debug", [True, False])
def test_with_webhooks_off_the_page_says_live_updates_are_unavailable_not_done(
    client, settings, debug
):
    settings.GITHUB_WEBHOOK_SECRET = ""
    settings.DEBUG = debug
    ada = make_member()
    client.force_login(ada)
    project = Project.objects.create(owner=ada, name="Space Game")
    make_link(project)
    page = unescape(client.get(project.get_absolute_url()).content.decode())
    assert 'data-setup="incomplete"' in page and strings.SETUP_DONE_TITLE not in page
    assert strings.STEPS["webhook"]["off"] in page and strings.SETUP_OFF_NOTE in page
    assert "2 / 4" in page
    # The server's own .env is a development hint only: members of a hosted Hub never see it.
    assert ("data-operator-hint" in page) is debug
    assert ("GITHUB_WEBHOOK_SECRET" in page) is debug


@pytest.mark.django_db
def test_the_payload_url_uses_the_public_address_when_one_is_set(client, settings):
    import responses

    settings.HUB_PUBLIC_URL = "https://hub-dev.example.com"
    settings.ALLOWED_HOSTS = ["127.0.0.1", "hub-dev.example.com"]
    ada = make_member()
    client.force_login(ada)
    project = Project.objects.create(owner=ada, name="Space Game")
    link = make_link(project)
    payload = {
        "id": link.github_id, "full_name": link.full_name, "html_url": link.html_url,
        "private": False, "archived": False,
        "permissions": {"admin": True, "push": True, "pull": True},
    }  # fmt: skip
    with responses.RequestsMock() as mock:
        mock.get("https://api.github.com/repos/octocat/Hello-World", json=payload)
        html = client.get(
            project.get_absolute_url() + "?webhook=show", HTTP_HOST="127.0.0.1:8000"
        ).content.decode()
    assert f"https://hub-dev.example.com/projects/hooks/github/{link.hook_id}/" in html
    assert "http://127.0.0.1:8000/projects/hooks" not in html
    assert "data-local-warning" not in html  # GitHub can reach the public address


# ---------- The cards ----------


@pytest.mark.django_db
def test_the_list_shows_each_projects_setup_progress(client):
    ada = make_member()
    client.force_login(ada)
    empty = client.get(reverse("projects:list")).content.decode()
    assert strings.EMPTY_TITLE in empty and reverse("projects:create") in empty
    assert all(strings.STEPS[key]["title"].replace("'", "&#x27;") in empty for key in strings.STEPS)

    first = Project.objects.create(owner=ada, name="Space Game", description="A game in space.")
    second = Project.objects.create(owner=ada, name="Moon Base")
    make_link(second, first_webhook_at=NOW, webhook_at=NOW, webhook_shown_at=NOW)
    page = unescape(client.get(reverse("projects:list")).content.decode())
    assert page.count('class="panel pj-panel pj-card"') == 2
    assert 'data-setup="complete"' in page and 'data-setup="incomplete"' in page
    assert "1 of 4" in page and strings.SETUP_COMPLETE in page
    assert strings.NO_REPOSITORY_YET in page and "octocat/Hello-World" in page
    assert first.get_absolute_url() in page and "A game in space." in page
    assert "2 of 5 projects" in page


# ---------- The guide ----------


@pytest.mark.django_db
@pytest.mark.parametrize("signed_in", [False, True])
def test_the_guide_is_public_and_covers_every_step_and_response(client, signed_in):
    if signed_in:
        client.force_login(make_member())
    response = client.get(reverse("projects:guide"))
    assert response.status_code == 200
    page = unescape(response.content.decode())
    assert strings.GUIDE_TITLE in page
    for key in strings.STEPS:
        assert strings.STEPS[key]["title"] in page
        assert all(paragraph in page for paragraph in strings.GUIDE_STEPS[key])
    for code, _, _ in strings.GUIDE_TROUBLE:
        assert code in page
    for anchor in ["before", "steps", "access", "trouble", "unlink", "local"]:
        assert f'id="{anchor}"' in page
    # The guide's responses are the webhook's real ones.
    from projects.webhooks import ACCEPTED, IGNORED, MALFORMED, REPLAYED, UNSIGNED

    for outcome in [ACCEPTED, IGNORED, MALFORMED, REPLAYED, UNSIGNED]:
        assert f"{outcome.status} {outcome.text}" in page
    rail = page[page.index('id="app-rail"') : page.index("</details>", page.index('id="app-rail"'))]
    if signed_in:
        assert strings.GUIDE_START in page and "Profile" in rail
    else:
        # A visitor sees the Hub's items, a way to sign in, and no account pages.
        assert strings.GUIDE_SIGN_IN in page and "Profile" not in rail and "Setup guide" in rail
        assert f"{reverse('account_login')}?next=" in page


@pytest.mark.django_db
def test_guide_is_not_a_usable_project_name():
    from django.core.exceptions import ValidationError

    from projects import services

    with pytest.raises(ValidationError):
        services.create_project(make_member(), name="Guide")
