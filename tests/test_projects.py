"""Projects: creating them under the per-member limit (concurrent requests included), names,
ownership, and the project pages."""

import re
import threading

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse

from accounts.limits import LimitReached
from projects import services, strings
from projects.models import Project

User = get_user_model()
PASSWORD = "correct-horse-battery-staple-42"


def make_member(username="ada", email=None, *, verified: bool = True):
    email = email or f"{username}@example.com"
    user = User.objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


def create_at_once(owner, names: list[str]) -> list[object]:
    """Create one project per name, each from its own thread and database connection, all
    released together; each result is the project or the exception raised."""
    barrier = threading.Barrier(len(names))
    results: list[object] = [None] * len(names)

    def attempt(index: int, name: str) -> None:
        try:
            barrier.wait()
            results[index] = services.create_project(owner, name=name)
        except Exception as error:  # noqa: BLE001 (the result under test)
            results[index] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(i, n)) for i, n in enumerate(names)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


# ---------- TDD 2: a sixth project is rejected ----------


@pytest.mark.django_db(transaction=True)
def test_a_sixth_project_is_rejected_one_at_a_time_and_concurrently_and_only_the_owners_count():
    ada, grace = make_member("ada"), make_member("grace")
    for i in range(5):
        services.create_project(grace, name=f"Grace {i}")

    # Grace's five don't count against Ada: she creates five of her own...
    for i in range(5):
        services.create_project(ada, name=f"Ada {i}")
    # ...and her sixth is refused with the page's message, writing nothing.
    with pytest.raises(LimitReached) as refused:
        services.create_project(ada, name="Ada 5")
    assert str(refused.value) == strings.LIMIT_REACHED
    assert not Project.objects.filter(name="Ada 5").exists()

    # Eight requests at the same moment from a member with none: exactly five succeed.
    linus = make_member("linus")
    results = create_at_once(linus, [f"Linus {i}" for i in range(8)])
    created = [r for r in results if isinstance(r, Project)]
    refusals = [r for r in results if isinstance(r, LimitReached)]
    assert (len(created), len(refusals)) == (5, 3), results
    assert Project.objects.filter(owner=linus).count() == 5
    assert Project.objects.filter(owner=ada).count() == 5
    assert Project.objects.filter(owner=grace).count() == 5


# ---------- The limit and the lock ----------


@pytest.mark.django_db(transaction=True)
def test_lock_member_refuses_to_run_outside_a_transaction():
    from django.db.transaction import TransactionManagementError

    from accounts.limits import lock_member

    with pytest.raises(TransactionManagementError):
        lock_member(make_member())


@pytest.mark.django_db
def test_an_unverified_member_cannot_create_a_project():
    from accounts.access import EmailNotVerified

    with pytest.raises(EmailNotVerified):
        services.create_project(make_member(verified=False), name="Space Game")
    assert not Project.objects.exists()


# ---------- Names ----------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "taken, name",
    [
        ("Space Game", "space game"),  # another case
        ("Space Game", "SPACE GAME"),
        ("Space Game", "space-game"),  # the same address
        ("Space Game", "  Space   Game "),  # spacing
    ],
)
def test_names_are_unique_across_the_hub_whatever_their_case(taken, name):
    from django.core.exceptions import ValidationError

    services.create_project(make_member("grace"), name=taken)
    with pytest.raises(ValidationError) as refused:
        services.create_project(make_member("ada"), name=name)
    assert refused.value.message_dict == {"name": [strings.NAME_TAKEN]}
    assert Project.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["!!!", "new", "New", "hooks", "   "])
def test_a_name_must_give_a_usable_address(name):
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        services.create_project(make_member(), name=name)
    assert not Project.objects.exists()


@pytest.mark.django_db
def test_the_database_refuses_a_name_in_another_case_even_past_the_checks(monkeypatch):
    from django.core.exceptions import ValidationError
    from django.db import IntegrityError, transaction

    Project.objects.create(owner=make_member("grace"), name="Space Game")
    # Straight to the database: the LOWER(name) constraint holds whatever the route.
    with pytest.raises(IntegrityError), transaction.atomic():
        Project.objects.create(owner=make_member("linus"), name="SPACE GAME!")
    # And a race the model's check can't see comes back as the form's message.
    monkeypatch.setattr(Project, "clean", lambda self: None)
    with pytest.raises(ValidationError) as refused:
        services.create_project(make_member("ada"), name="space game")
    assert refused.value.message_dict == {"name": [strings.NAME_TAKEN]}


@pytest.mark.django_db
def test_the_address_follows_the_name():
    project = services.create_project(make_member(), name="Space Game")
    assert project.slug == "space-game"
    assert project.get_absolute_url() == "/projects/space-game/"
    project.name = "Moon Base"
    project.full_clean()
    project.save()
    assert project.slug == "moon-base"


# ---------- Pages: owners only, others 404 ----------


def owner_client(client, **kwargs):
    owner = make_member(**kwargs)
    client.force_login(owner)
    return owner


def project_urls(slug: str) -> dict[str, list[str]]:
    """Every project URL by method."""
    get = ["detail", "edit", "delete", "webhook_settings"]
    post = ["edit", "delete", "link_repository", "unlink_repository", "refresh_repository"]
    return {
        "get": [reverse(f"projects:{n}", args=[slug]) for n in get],
        "post": [reverse(f"projects:{n}", args=[slug]) for n in post],
    }


@pytest.mark.django_db
def test_another_member_gets_a_404_for_every_project_url_and_changes_nothing(client):
    grace = make_member("grace")
    project = services.create_project(grace, name="Space Game", description="Mine")
    owner_client(client, username="ada")
    urls = project_urls(project.slug)
    for url in urls["get"]:
        assert client.get(url).status_code == 404, url
    for url in urls["post"]:
        response = client.post(url, {"name": "Stolen", "repository": "a/b"})
        assert response.status_code == 404, url
    project.refresh_from_db()
    assert (project.name, project.description) == ("Space Game", "Mine")
    # And the list shows only her own.
    page = client.get(reverse("projects:list")).content.decode()
    assert "Space Game" not in page


@pytest.mark.django_db
def test_an_unknown_project_is_a_404(client):
    owner_client(client)
    for url in project_urls("no-such-project")["get"]:
        assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_an_owner_creates_edits_and_deletes_a_project(client):
    owner = owner_client(client)
    response = client.post(
        reverse("projects:create"), {"name": "Space Game", "description": "A game in space."}
    )
    project = Project.objects.get()
    assert project.owner == owner
    assert response["Location"] == "/projects/space-game/"
    page = client.get(response["Location"]).content.decode()
    assert "Space Game" in page and "A game in space." in page and strings.CREATED in page

    response = client.post(
        reverse("projects:edit", args=["space-game"]), {"name": "Moon Base", "description": ""}
    )
    assert response["Location"] == "/projects/moon-base/"
    assert client.get("/projects/space-game/").status_code == 404

    assert client.get(reverse("projects:delete", args=["moon-base"])).status_code == 200
    response = client.post(reverse("projects:delete", args=["moon-base"]))
    assert response["Location"] == reverse("projects:list")
    assert not Project.objects.exists()


@pytest.mark.django_db
def test_the_create_form_shows_the_name_rules_and_the_limit(client):
    owner = owner_client(client)
    services.create_project(make_member("grace"), name="Space Game")
    response = client.post(reverse("projects:create"), {"name": "SPACE game"})
    assert response.status_code == 200
    assert strings.NAME_TAKEN in response.content.decode()

    for i in range(5):
        services.create_project(owner, name=f"Mine {i}")
    page = client.get(reverse("projects:create")).content.decode()
    assert strings.LIMIT_REACHED in page and 'name="name"' not in page
    response = client.post(reverse("projects:create"), {"name": "One more"})
    assert response.status_code == 200 and strings.LIMIT_REACHED in response.content.decode()
    assert Project.objects.filter(owner=owner).count() == 5
    listing = client.get(reverse("projects:list")).content.decode()
    assert "5 of 5 projects" in listing and strings.LIMIT_REACHED in listing
    assert reverse("projects:create") not in listing


@pytest.mark.django_db
def test_an_unverified_member_is_sent_to_verify_before_creating_editing_or_linking(client):
    owner = owner_client(client, verified=False)
    project = Project.objects.create(owner=owner, name="Space Game")
    verify = reverse("accounts:verify_email")
    for method, url, data in [
        ("get", reverse("projects:create"), {}),
        ("post", reverse("projects:create"), {"name": "New one"}),
        ("post", reverse("projects:edit", args=[project.slug]), {"name": "Renamed"}),
        ("post", reverse("projects:link_repository", args=[project.slug]), {"repository": "a/b"}),
    ]:
        response = getattr(client, method)(url, data)
        assert response.status_code == 302 and response["Location"].startswith(verify), url
    assert list(Project.objects.values_list("name", flat=True)) == ["Space Game"]
    # Reading their own project still works.
    assert client.get(project.get_absolute_url()).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("htmx", [False, True])
def test_every_project_post_without_a_csrf_token_is_refused(htmx):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    owner = make_member()
    client.force_login(owner)
    project = Project.objects.create(owner=owner, name="Space Game")
    headers = {"HX-Request": "true"} if htmx else {}
    for url in [reverse("projects:list"), reverse("projects:create")] + project_urls(project.slug)[
        "post"
    ]:
        response = client.post(url, {"name": "Changed"}, headers=headers)
        assert response.status_code == 403, url
    assert list(Project.objects.values_list("name", flat=True)) == ["Space Game"]


@pytest.mark.django_db
def test_project_pages_sit_in_the_app_shell_under_projects(client):
    owner = owner_client(client)
    project = Project.objects.create(owner=owner, name="Space Game")
    for url in [reverse("projects:list"), reverse("projects:create"), project.get_absolute_url()]:
        html = client.get(url).content.decode()
        assert 'id="app-rail"' in html
        current = re.findall(r'aria-current="page">\s*<svg.*?</svg>\s*([^<]+?)\s*<', html, re.S)
        assert current == ["Projects"], url


@pytest.mark.django_db
def test_project_copy_is_escaped(client):
    owner = owner_client(client)
    project = Project.objects.create(
        owner=owner, name="Space <b>Game</b>", description="<script>x</script>"
    )
    response = client.get(project.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html
    assert "Space &lt;b&gt;Game&lt;/b&gt;" in html
