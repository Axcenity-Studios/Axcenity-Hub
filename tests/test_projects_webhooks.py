"""Repository webhooks: each link's own secret, signature verification, replays (scoped to
the link), the events that keep a repository's details current, and the endpoint's rules."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client

from projects import webhooks
from projects.models import Project, RepositoryLink, WebhookDelivery

User = get_user_model()
ROOT_SECRET = "root-secret-for-tests-only"
REPOSITORY = json.loads(
    (Path(__file__).parent / "fixtures" / "github" / "repository.json").read_text()
)


@pytest.fixture(autouse=True)
def _webhooks_on(settings):
    settings.GITHUB_WEBHOOK_SECRET = ROOT_SECRET


def make_link(name="Space Game", owner="ada", github_id=REPOSITORY["id"], full_name=None):
    user = User.objects.filter(username=owner).first() or User.objects.create_user(owner)
    project = Project.objects.create_with_owner(user, name=name)
    full_name = full_name or REPOSITORY["full_name"]
    return RepositoryLink.objects.create(
        project=project,
        github_id=github_id,
        full_name=full_name,
        html_url=f"https://github.com/{full_name}",
    )


def renamed_body(repository_id: int, new_name: str = "octocat/Hello-Engine") -> bytes:
    """A `repository` `renamed` delivery's body, as GitHub sends it (trimmed)."""
    repository = {
        **REPOSITORY,
        "id": repository_id,
        "full_name": new_name,
        "html_url": f"https://github.com/{new_name}",
    }
    del repository["permissions"]
    payload = {
        "action": "renamed",
        "changes": {"repository": {"name": {"from": "Hello-World"}}},
        "repository": repository,
    }
    return json.dumps(payload).encode()


def deliver(link, body: bytes, *, signature: str | None, delivery: str | None = None):
    headers = {"HTTP_X_GITHUB_EVENT": "repository"}
    headers["HTTP_X_GITHUB_DELIVERY"] = delivery or str(uuid.uuid4())
    if signature is not None:
        headers["HTTP_X_HUB_SIGNATURE_256"] = signature
    return Client(enforce_csrf_checks=True).post(
        webhooks.payload_path(link.hook_id), body, content_type="application/json", **headers
    )


def state(link) -> tuple:
    link = RepositoryLink.objects.get(pk=link.pk)
    return link.full_name, link.webhook_at, WebhookDelivery.objects.filter(link=link).count()


# ---------- TDD 1: only a valid signature is accepted; replays are refused ----------


@pytest.mark.django_db
def test_a_delivery_is_accepted_only_with_its_links_valid_signature_and_only_once_per_link():
    link, other = make_link(), make_link("Moon Base", github_id=999, full_name="octocat/Moon")
    body = renamed_body(link.github_id)
    secret = webhooks.secret_for(link.hook_id)
    before = state(link)

    # Refused, changing nothing: unsigned, signed with another link's secret or the root
    # secret, a signature of another body, the wrong algorithm, and a malformed header.
    forged = [
        None,
        webhooks.signature(webhooks.secret_for(other.hook_id), body),
        webhooks.signature(ROOT_SECRET, body),
        webhooks.signature(secret, body + b" "),
        "sha1=" + webhooks.signature(secret, body).removeprefix("sha256=")[:40],
        "sha256=not-hex",
        "",
    ]
    for signature in forged:
        response = deliver(link, body, signature=signature)
        assert response.status_code == 403, signature
        assert state(link) == before, signature

    # The link's own signature is accepted (with no CSRF token) and applied.
    good = webhooks.signature(secret, body)
    delivery = str(uuid.uuid4())
    assert deliver(link, body, signature=good, delivery=delivery).status_code == 200
    after = state(link)
    assert after[0] == "octocat/Hello-Engine" and after[2] == 1

    # Replays are refused and change nothing: the same delivery id with another (validly
    # signed) body, and the same body under a new delivery id.
    RepositoryLink.objects.filter(pk=link.pk).update(full_name="octocat/Hello-World")
    replayed = state(link)
    other_body = renamed_body(link.github_id, "octocat/Hello-Again")
    assert (
        deliver(link, other_body, signature=webhooks.signature(secret, other_body), delivery=delivery)
        .status_code == 409
    )  # fmt: skip
    assert deliver(link, body, signature=good).status_code == 409
    assert state(link) == replayed

    # Replay protection is per link: the identical body and delivery id, signed for another
    # link, aren't a replay there.
    other_signature = webhooks.signature(webhooks.secret_for(other.hook_id), body)
    response = deliver(other, body, signature=other_signature, delivery=delivery)
    assert response.status_code in (200, 202)
    assert WebhookDelivery.objects.filter(link=other).count() == 1


# ---------- Signatures and secrets ----------


def test_signatures_match_githubs_published_test_vector():
    # docs.github.com, "Validating webhook deliveries".
    secret, body = "It's a Secret to Everybody", b"Hello, World!"
    expected = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"
    assert webhooks.signature(secret, body) == expected
    assert webhooks.verify(secret, body, expected)
    assert not webhooks.verify(secret, body, expected.upper())
    assert not webhooks.verify(secret, body, expected[:-1])
    assert not webhooks.verify(secret, body, expected.removeprefix("sha256="))
    assert not webhooks.verify(secret, body + b"!", expected)


def test_each_link_has_its_own_secret_derived_from_the_root(settings):
    a, b = uuid.uuid4(), uuid.uuid4()
    assert webhooks.secret_for(a) != webhooks.secret_for(b)
    assert webhooks.secret_for(a) == webhooks.secret_for(str(a))
    assert ROOT_SECRET not in webhooks.secret_for(a)
    first = webhooks.secret_for(a)
    settings.GITHUB_WEBHOOK_SECRET = "another-root"
    assert webhooks.secret_for(a) != first  # a new root gives every link a new secret
    settings.GITHUB_WEBHOOK_SECRET = ""
    with pytest.raises(RuntimeError):
        webhooks.secret_for(a)


@pytest.mark.django_db
def test_no_secret_is_stored_in_the_database():
    link = make_link()
    secret = webhooks.secret_for(link.hook_id)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {RepositoryLink._meta.db_table}")
        rows = cursor.fetchall()
    assert not any(
        secret in str(value) or ROOT_SECRET in str(value) for row in rows for value in row
    )


# ---------- The endpoint ----------


def signed(link, body: bytes, event: str = "repository", delivery: str | None = None):
    return Client().post(
        webhooks.payload_path(link.hook_id),
        body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT=event,
        HTTP_X_GITHUB_DELIVERY=delivery or str(uuid.uuid4()),
        HTTP_X_HUB_SIGNATURE_256=webhooks.signature(webhooks.secret_for(link.hook_id), body),
    )


@pytest.mark.django_db
def test_unknown_hooks_and_webhooks_off_are_404_and_only_post_is_allowed(settings):
    link = make_link()
    body = renamed_body(link.github_id)
    client = Client()
    assert (
        client.post(
            webhooks.payload_path(uuid.uuid4()), body, content_type="application/json"
        ).status_code
        == 404
    )
    assert client.get(webhooks.payload_path(link.hook_id)).status_code == 405
    good = webhooks.signature(webhooks.secret_for(link.hook_id), body)
    settings.GITHUB_WEBHOOK_SECRET = ""
    response = client.post(
        f"/projects/hooks/github/{link.hook_id}/", body, content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=good, HTTP_X_GITHUB_EVENT="repository",
        HTTP_X_GITHUB_DELIVERY=str(uuid.uuid4()),
    )  # fmt: skip
    assert response.status_code == 404
    assert state(link)[2] == 0


@pytest.mark.django_db
def test_a_ping_is_acknowledged_and_recorded():
    link = make_link()
    body = json.dumps(
        {"zen": "Keep it logically awesome.", "hook_id": 1, "repository": REPOSITORY}
    ).encode()
    response = signed(link, body, event="ping")
    assert response.status_code == 200 and response["Content-Type"].startswith("text/plain")
    assert state(link)[1] is not None and state(link)[2] == 1


@pytest.mark.django_db
def test_a_push_updates_the_last_push_from_githubs_unix_time():
    link = make_link()
    repository = {**REPOSITORY, "pushed_at": 1764000000}
    del repository["permissions"]
    body = json.dumps({"ref": "refs/heads/master", "repository": repository}).encode()
    assert signed(link, body, event="push").status_code == 200
    link.refresh_from_db()
    assert link.pushed_at.timestamp() == 1764000000


@pytest.mark.django_db
def test_a_deleted_repository_is_marked_not_unlinked():
    link = make_link()
    body = json.dumps({"action": "deleted", "repository": {"id": link.github_id}}).encode()
    assert signed(link, body).status_code == 200
    link.refresh_from_db()
    assert link.deleted_on_github is True


@pytest.mark.django_db
def test_events_about_another_repository_or_of_other_kinds_are_ignored():
    link = make_link()
    before = state(link)[0]
    assert signed(link, renamed_body(12345)).status_code == 202
    assert signed(link, b'{"action": "created"}', event="star").status_code == 202
    assert state(link)[0] == before


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body, event, delivery",
    [
        (b"not json", "repository", None),
        (b"[1, 2]", "repository", None),
        (json.dumps({"action": "edited", "repository": {"id": REPOSITORY["id"]}}).encode(), "repository", None),
        (b"{}", "Not An Event!", None),
        (b"{}", "ping", "not a guid; drop table"),
    ],
)  # fmt: skip
def test_a_signed_but_malformed_delivery_is_refused_and_records_nothing(body, event, delivery):
    link = make_link()
    before = state(link)
    response = signed(link, body, event=event, delivery=delivery or str(uuid.uuid4()))
    assert response.status_code == 400
    assert state(link) == before


@pytest.mark.django_db
def test_an_oversized_delivery_is_refused(settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 1024
    link = make_link()
    body = json.dumps({"zen": "x" * 4096, "repository": REPOSITORY}).encode()
    assert signed(link, body, event="ping").status_code == 413
    assert state(link)[2] == 0


@pytest.mark.django_db
def test_hostile_strings_from_github_are_stored_as_text_and_escaped_on_the_page(client):
    link = make_link()
    repository = {**REPOSITORY, "description": "<script>alert(1)</script>"}
    del repository["permissions"]
    body = json.dumps({"action": "edited", "repository": repository}).encode()
    assert signed(link, body).status_code == 200
    # Fresh, so the page shows the stored details without asking GitHub.
    RepositoryLink.objects.filter(pk=link.pk).update(fetched_at=datetime.now(UTC))
    client.force_login(User.objects.get(username="ada"))
    page = client.get(link.project.get_absolute_url()).content.decode()
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
