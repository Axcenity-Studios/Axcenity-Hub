"""Project teams: the role matrix, the last Owner, invitations, the ownership limit, and the
team pages."""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.urls import reverse

from projects import services
from projects.models import Project, ProjectInvitation, ProjectMembership

User = get_user_model()
PASSWORD = "correct-horse-battery-staple-42"


def make_member(username="ada", *, verified: bool = True):
    user = User.objects.create_user(username, f"{username}@example.com", PASSWORD)
    EmailAddress.objects.create(
        user=user, email=f"{username}@example.com", primary=True, verified=verified
    )
    return user


def join(project, user, role):
    """Put `user` in `project`'s team directly (the invitation flow has its own tests)."""
    return ProjectMembership.objects.create(project=project, user=user, role=role)


# ---------- TDD 1: the role matrix ----------

# Each action, and the roles allowed it. Everyone else gets a 404 and changes nothing.
ALLOWED = {
    "view": {"owner", "maintainer", "viewer"},
    "edit": {"owner", "maintainer"},
    "rename": {"owner"},
    "manage members": {"owner"},
    "delete": {"owner"},
}
# The edit page itself, which renaming goes through: a Maintainer may open it (for the
# description), so their rename is ignored rather than a 404.
EDIT_PAGE = ALLOWED["edit"]


def attempt(client, action: str, project: Project):
    """Try `action` on `project` through its page; returns the response."""
    slug = project.slug
    if action == "view":
        return client.get(reverse("projects:detail", args=[slug]))
    if action == "edit":
        data = {"name": "Space Game", "description": "Changed"}
        return client.post(reverse("projects:edit", args=[slug]), data)
    if action == "rename":
        data = {"name": "Moon Base", "description": "Mine"}
        return client.post(reverse("projects:edit", args=[slug]), data)
    if action == "manage members":
        data = {"username": "linus", "role": "viewer"}
        return client.post(reverse("projects:invite", args=[slug]), data)
    if action == "delete":
        return client.post(reverse("projects:delete", args=[slug]))
    raise AssertionError(action)


def took_effect(action: str, project_pk: int) -> bool:
    """Whether `action` changed the project (viewing changes nothing: its status decides)."""
    project = Project.objects.filter(pk=project_pk).first()
    if action == "edit":
        return project.description == "Changed"
    if action == "rename":
        return project.name == "Moon Base"
    if action == "manage members":
        return ProjectInvitation.objects.filter(project_id=project_pk).exists()
    if action == "delete":
        return project is None
    raise AssertionError(action)


@pytest.mark.django_db
@pytest.mark.parametrize("action", list(ALLOWED))
@pytest.mark.parametrize("role", ["owner", "maintainer", "viewer", None])
def test_each_role_may_do_exactly_its_actions_and_everyone_else_gets_a_404(client, action, role):
    ada, grace = make_member("ada"), make_member("grace")
    make_member("linus")  # someone to invite
    project = services.create_project(ada, name="Space Game", description="Mine")
    if role == "owner":
        actor = ada
    else:
        actor = grace
        if role is not None:  # None: signed in, but not in the team
            join(project, grace, role)
    client.force_login(actor)

    response = attempt(client, action, project)

    if role in ALLOWED[action]:
        assert response.status_code in (200, 302), (role, action, response.status_code)
        if action == "view":
            assert "Space Game" in response.content.decode()
        else:
            assert took_effect(action, project.pk), (role, action)
    else:
        expected = 302 if (action == "rename" and role in EDIT_PAGE) else 404
        assert response.status_code == expected, (role, action, response.status_code)
        if action != "view":
            assert not took_effect(action, project.pk), (role, action)
        project.refresh_from_db()
        assert (project.name, project.description) == ("Space Game", "Mine")


# ---------- TDD 2: a project always keeps at least one Owner ----------

# Every way an Owner can stop being one: stepping down, removing themselves, leaving, and
# deleting their account (inside a transaction, as the admin's delete does).
WAYS = ["step down", "remove themselves", "leave", "delete account"]


def lose_ownership(way: str, owner, project: Project) -> None:
    from django.db import transaction

    from projects import teams

    own = ProjectMembership.objects.get(project=project, user=owner)
    if way == "step down":
        teams.change_role(owner, project, own.pk, "maintainer")
    elif way == "remove themselves":
        teams.remove(owner, project, own.pk)
    elif way == "leave":
        teams.leave(owner, project)
    elif way == "delete account":
        with transaction.atomic():
            User.objects.get(pk=owner.pk).delete()
    else:
        raise AssertionError(way)


def refused_as_last_owner(way: str, error: Exception) -> bool:
    """The last Owner's refusal. Deleting an account: a ProtectedError naming exactly the
    memberships that are a project's last Owner (Django's collector replaces the message with
    its own; the protected objects are what the admin lists)."""
    from django.db.models import ProtectedError

    from projects import strings, teams

    if way == "delete account":
        return (
            isinstance(error, ProtectedError)
            and len(error.protected_objects) == 1
            and all(m.role == "owner" for m in error.protected_objects)
            and all(owners_of(m.project) == [m.user.username] for m in error.protected_objects)
        )
    return isinstance(error, teams.TeamError) and str(error) == strings.LAST_OWNER


def all_at_once(attempts) -> list[object]:
    """Run each attempt in its own thread and database connection, released together; each
    result is None (it went through) or the exception it raised."""
    import threading

    from django.db import connection

    barrier = threading.Barrier(len(attempts))
    results: list[object] = [None] * len(attempts)

    def run(index, attempt):
        try:
            barrier.wait()
            attempt()
        except Exception as error:  # noqa: BLE001 (the result under test)
            results[index] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i, a)) for i, a in enumerate(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def owners_of(project: Project) -> list[str]:
    return sorted(
        ProjectMembership.objects.filter(project=project, role="owner").values_list(
            "user__username", flat=True
        )
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("way", WAYS)
def test_a_project_always_keeps_at_least_one_owner(way):
    ada, grace = make_member("ada"), make_member("grace")
    project = services.create_project(ada, name="Space Game")
    join(project, grace, "maintainer")

    # The only Owner is refused, and nothing changes: her account, her role, the project.
    with pytest.raises(Exception) as refused:
        lose_ownership(way, ada, project)
    assert refused_as_last_owner(way, refused.value), repr(refused.value)
    assert User.objects.filter(pk=ada.pk).exists()
    assert Project.objects.filter(pk=project.pk).exists()
    assert owners_of(project) == ["ada"]
    assert ProjectMembership.objects.get(project=project, user=grace).role == "maintainer"

    # With two Owners, either may go, but not both: when both try at the same moment,
    # exactly one goes through and the other is refused as the last Owner.
    ProjectMembership.objects.filter(project=project, user=grace).update(role="owner")
    results = all_at_once(
        [lambda: lose_ownership(way, ada, project), lambda: lose_ownership(way, grace, project)]
    )
    went = [r for r in results if r is None]
    stayed = [r for r in results if r is not None]
    assert len(went) == 1 and len(stayed) == 1, results
    assert refused_as_last_owner(way, stayed[0]), repr(stayed[0])
    assert Project.objects.filter(pk=project.pk).exists()
    assert len(owners_of(project)) == 1


# ---------- Invitations ----------


def owner_with_project(client=None, name="Space Game"):
    ada = make_member("ada")
    project = services.create_project(ada, name=name)
    if client is not None:
        client.force_login(ada)
    return ada, project


def invite_url(project):
    return reverse("projects:invite", args=[project.slug])


def messages_on(response) -> list[str]:
    return [str(m) for m in response.context["messages"]] if response.context else []


@pytest.mark.django_db
def test_an_invitee_accepts_and_joins_in_the_invitations_role(client):
    from projects import strings

    ada, project = owner_with_project(client)
    grace = make_member("grace")
    response = client.post(invite_url(project), {"username": "GRACE", "role": "maintainer"})
    assert response["Location"] == reverse("projects:members", args=[project.slug])
    invitation = ProjectInvitation.objects.get()
    assert (invitation.invitee, invitation.role, invitation.invited_by) == (
        grace,
        "maintainer",
        ada,
    )
    assert ProjectMembership.objects.filter(project=project, user=grace).count() == 0

    client.force_login(grace)
    listing = client.get(reverse("projects:list")).content.decode()
    assert "Space Game" in listing and "ada invited you to join as Maintainer." in listing
    accept = reverse("projects:accept_invitation", args=[invitation.pk])
    response = client.post(accept, follow=True)
    assert response.redirect_chain[-1][0] == project.get_absolute_url()
    assert strings.JOINED in messages_on(response)
    assert project.role_of(grace) == "maintainer"
    assert not ProjectInvitation.objects.exists()
    # Answered: a second accept finds nothing.
    assert client.post(accept).status_code == 404


@pytest.mark.django_db
def test_a_declined_invitation_is_gone_and_joins_nothing(client):
    _, project = owner_with_project()
    grace = make_member("grace")
    invitation = ProjectInvitation.objects.create(project=project, invitee=grace, role="viewer")
    client.force_login(grace)
    response = client.post(reverse("projects:decline_invitation", args=[invitation.pk]))
    assert response["Location"] == reverse("projects:list")
    assert not ProjectInvitation.objects.exists()
    assert project.role_of(grace) is None
    assert client.get(project.get_absolute_url()).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("who", ["the owner", "a team member", "a stranger"])
@pytest.mark.parametrize("answer", ["accept_invitation", "decline_invitation"])
def test_only_the_invitee_can_answer_an_invitation(client, who, answer):
    ada, project = owner_with_project()
    grace, linus = make_member("grace"), make_member("linus")
    join(project, linus, "maintainer")
    invitation = ProjectInvitation.objects.create(project=project, invitee=grace, role="owner")
    client.force_login({"the owner": ada, "a team member": linus}.get(who) or make_member("eve"))
    assert client.post(reverse(f"projects:{answer}", args=[invitation.pk])).status_code == 404
    assert ProjectInvitation.objects.filter(pk=invitation.pk).exists()
    assert project.role_of(grace) is None
    assert sorted(project.memberships.values_list("user__username", "role")) == [
        ("ada", "owner"),
        ("linus", "maintainer"),
    ]


@pytest.mark.django_db
def test_owners_cancel_invitations_and_no_one_else_can(client):
    ada, project = owner_with_project()
    grace, linus = make_member("grace"), make_member("linus")
    join(project, linus, "maintainer")
    invitation = ProjectInvitation.objects.create(project=project, invitee=grace, role="viewer")
    url = reverse("projects:cancel_invitation", args=[project.slug, invitation.pk])
    for outsider in [linus, grace]:  # a Maintainer, and the invitee (who declines instead)
        client.force_login(outsider)
        assert client.post(url).status_code == 404
    # An Owner of another project can't reach this one's invitation through their own.
    zoe = make_member("zoe")
    other = services.create_project(zoe, name="Moon Base")
    client.force_login(zoe)
    wrong = reverse("projects:cancel_invitation", args=[other.slug, invitation.pk])
    assert client.post(wrong).status_code == 404
    assert ProjectInvitation.objects.filter(pk=invitation.pk).exists()

    client.force_login(ada)
    assert client.post(url).status_code == 302
    assert not ProjectInvitation.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "username, role, message",
    [
        ("nobody", "viewer", "No Hub member is called “nobody”."),
        ("", "viewer", "Enter a username and choose a role."),
        ("ada", "viewer", "You're already in this project."),
        ("linus", "viewer", "linus is already in this project."),
        ("grace", "viewer", "grace already has an invitation to this project."),
        ("sleepy", "viewer", "No Hub member is called “sleepy”."),  # deactivated
        ("zoe", "admin", "Choose Owner, Maintainer or Viewer."),
        ("<b>zoe</b>", "viewer", "No Hub member is called “<b>zoe</b>”."),
    ],
)
def test_an_invitation_is_refused_with_a_clear_message(client, username, role, message):
    ada, project = owner_with_project(client)
    for name in ["grace", "linus", "zoe", "sleepy"]:
        make_member(name)
    User.objects.filter(username="sleepy").update(is_active=False)
    join(project, User.objects.get(username="linus"), "viewer")
    ProjectInvitation.objects.create(
        project=project, invitee=User.objects.get(username="grace"), role="viewer"
    )
    response = client.post(invite_url(project), {"username": username, "role": role}, follow=True)
    assert message in messages_on(response)
    assert "<b>zoe</b>" not in response.content.decode()
    assert ProjectInvitation.objects.count() == 1


@pytest.mark.django_db
def test_an_unverified_owner_is_sent_to_verify_before_inviting(client):
    ada = make_member("ada", verified=False)
    project = Project.objects.create_with_owner(ada, name="Space Game")
    make_member("grace")
    client.force_login(ada)
    response = client.post(invite_url(project), {"username": "grace", "role": "viewer"})
    assert response["Location"].startswith(reverse("accounts:verify_email"))
    assert not ProjectInvitation.objects.exists()


# ---------- The ownership limit when someone becomes an Owner ----------


def owning_five(username="grace"):
    member = make_member(username)
    for i in range(5):
        services.create_project(member, name=f"{username} {i}")
    return member


@pytest.mark.django_db
def test_accepting_an_owner_invitation_at_the_limit_is_refused_and_leaves_it_pending(client):
    from projects import strings

    _, project = owner_with_project()
    grace = owning_five()
    invitation = ProjectInvitation.objects.create(project=project, invitee=grace, role="owner")
    client.force_login(grace)
    response = client.post(reverse("projects:accept_invitation", args=[invitation.pk]), follow=True)
    assert strings.LIMIT_REACHED in messages_on(response)
    assert ProjectInvitation.objects.filter(pk=invitation.pk, role="owner").exists()
    assert project.role_of(grace) is None
    assert services.owned_count(grace) == 5
    # A Maintainer's or Viewer's invitation doesn't count: she can join as one.
    ProjectInvitation.objects.filter(pk=invitation.pk).update(role="viewer")
    client.post(reverse("projects:accept_invitation", args=[invitation.pk]))
    assert project.role_of(grace) == "viewer"


@pytest.mark.django_db
def test_making_a_member_an_owner_at_the_limit_is_refused_and_keeps_their_role(client):
    from projects import teams

    ada, project = owner_with_project(client)
    grace = owning_five()
    membership = join(project, grace, "maintainer")
    response = client.post(
        reverse("projects:change_role", args=[project.slug, membership.pk]),
        {"role": "owner"},
        follow=True,
    )
    assert "grace already owns 5 projects, the most one member can." in messages_on(response)
    membership.refresh_from_db()
    assert membership.role == "maintainer"
    assert services.owned_count(grace) == 5
    # Once she owns fewer, she can be made an Owner, and that counts against her limit.
    Project.objects.filter(name="grace 0").delete()
    teams.change_role(ada, project, membership.pk, "owner")
    assert services.owned_count(grace) == 5
    from accounts.limits import LimitReached

    with pytest.raises(LimitReached):
        services.create_project(grace, name="One more")


@pytest.mark.django_db(transaction=True)
def test_two_owner_invitations_accepted_at_once_at_four_owned_make_exactly_one_owner():
    from accounts.limits import LimitReached
    from projects import teams

    grace = make_member("grace")
    for i in range(4):
        services.create_project(grace, name=f"Grace {i}")
    invitations = []
    for name in ["ada", "linus"]:
        owner = make_member(name)
        project = services.create_project(owner, name=f"{name} project")
        invitations.append(
            ProjectInvitation.objects.create(project=project, invitee=grace, role="owner")
        )
    results = all_at_once([lambda i=i: teams.accept(grace, i.pk) for i in invitations])
    refusals = [r for r in results if isinstance(r, LimitReached)]
    assert len(refusals) == 1 and sum(r is None for r in results) == 1, results
    assert services.owned_count(grace) == 5
    assert ProjectInvitation.objects.count() == 1  # the refused one is still pending


# ---------- Re-checked inside the transaction ----------


@pytest.mark.django_db
def test_every_change_rereads_the_actors_role_and_its_target():
    from projects import teams

    ada, project = owner_with_project()
    grace, linus = make_member("grace"), make_member("linus")
    ada_member = ProjectMembership.objects.get(user=ada)
    grace_member = join(project, grace, "owner")
    linus_member = join(project, linus, "viewer")
    # Ada loaded the page as an Owner; Grace has since made her a Viewer.
    teams.change_role(grace, project, ada_member.pk, "viewer")
    for change in [
        lambda: teams.invite(ada, project, "zoe", "viewer"),
        lambda: teams.change_role(ada, project, linus_member.pk, "maintainer"),
        lambda: teams.remove(ada, project, linus_member.pk),
    ]:
        with pytest.raises(Project.DoesNotExist):
            change()
    assert project.role_of(linus) == "viewer"
    # A membership removed a moment ago, or one from another project, is not found.
    teams.remove(grace, project, linus_member.pk)
    with pytest.raises(ProjectMembership.DoesNotExist):
        teams.change_role(grace, project, linus_member.pk, "maintainer")
    other = services.create_project(make_member("zoe"), name="Moon Base")
    stranger = join(other, make_member("eve"), "viewer")
    with pytest.raises(ProjectMembership.DoesNotExist):
        teams.remove(grace, project, stranger.pk)
    # An invitation cancelled a moment ago can't be accepted.
    invitation = teams.invite(grace, project, "linus", "viewer")
    teams.cancel(grace, project, invitation.pk)
    with pytest.raises(ProjectInvitation.DoesNotExist):
        teams.accept(linus, invitation.pk)
    assert grace_member.pk and project.role_of(linus) is None


@pytest.mark.django_db
def test_the_database_holds_one_membership_and_one_invitation_per_member_and_valid_roles():
    from django.db import IntegrityError, transaction

    ada, project = owner_with_project()
    grace = make_member("grace")
    for make in [
        lambda: ProjectMembership.objects.create(project=project, user=ada, role="viewer"),
        lambda: ProjectMembership.objects.create(project=project, user=grace, role="admin"),
        lambda: ProjectInvitation.objects.create(project=project, invitee=grace, role="boss"),
    ]:
        with pytest.raises(IntegrityError), transaction.atomic():
            make()
    ProjectInvitation.objects.create(project=project, invitee=grace, role="viewer")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectInvitation.objects.create(project=project, invitee=grace, role="owner")


@pytest.mark.django_db
def test_an_invitee_who_joined_another_way_gets_a_message_not_an_error(client):
    from projects import strings

    _, project = owner_with_project()
    grace = make_member("grace")
    invitation = ProjectInvitation.objects.create(project=project, invitee=grace, role="owner")
    join(project, grace, "viewer")
    client.force_login(grace)
    response = client.post(reverse("projects:accept_invitation", args=[invitation.pk]), follow=True)
    assert strings.INVITATION_GONE in messages_on(response)
    assert project.role_of(grace) == "viewer" and not ProjectInvitation.objects.exists()


# ---------- Leaving, removing and stepping down ----------


@pytest.mark.django_db
def test_a_member_leaves_and_loses_access(client):
    from projects import strings

    _, project = owner_with_project()
    grace = make_member("grace")
    join(project, grace, "viewer")
    client.force_login(grace)
    response = client.post(reverse("projects:leave", args=[project.slug]), follow=True)
    assert response.redirect_chain[-1][0] == reverse("projects:list")
    assert strings.LEFT in messages_on(response)
    assert client.get(project.get_absolute_url()).status_code == 404


@pytest.mark.django_db
def test_the_last_owner_is_told_why_through_the_pages(client):
    from projects import strings

    ada, project = owner_with_project(client)
    own = ProjectMembership.objects.get(user=ada)
    page = client.get(reverse("projects:members", args=[project.slug])).content.decode()
    from django.utils.html import escape

    assert escape(strings.LAST_OWNER_NOTE) in page and "data-leave" not in page
    for url, data in [
        (reverse("projects:leave", args=[project.slug]), {}),
        (reverse("projects:change_role", args=[project.slug, own.pk]), {"role": "viewer"}),
        (reverse("projects:remove_member", args=[project.slug, own.pk]), {}),
    ]:
        response = client.post(url, data, follow=True)
        assert strings.LAST_OWNER in messages_on(response), url
    assert project.role_of(ada) == "owner"


@pytest.mark.django_db
def test_an_owner_hands_over_explicitly_then_steps_down(client):
    ada, project = owner_with_project(client)
    grace = make_member("grace")
    grace_member = join(project, grace, "maintainer")
    own = ProjectMembership.objects.get(user=ada)
    change = "projects:change_role"
    client.post(reverse(change, args=[project.slug, grace_member.pk]), {"role": "owner"})
    client.post(reverse(change, args=[project.slug, own.pk]), {"role": "maintainer"})
    assert (project.role_of(grace), project.role_of(ada)) == ("owner", "maintainer")
    # No longer an Owner: managing the team is a 404 for her now.
    response = client.post(
        reverse(change, args=[project.slug, grace_member.pk]), {"role": "viewer"}
    )
    assert response.status_code == 404 and project.role_of(grace) == "owner"


@pytest.mark.django_db
def test_deleting_a_co_owners_account_keeps_the_project_with_the_other_owner():
    ada, project = owner_with_project()
    grace = make_member("grace")
    join(project, grace, "owner")
    User.objects.get(pk=ada.pk).delete()
    assert owners_of(project) == ["grace"]


@pytest.mark.django_db
def test_the_admin_refuses_to_delete_a_last_owners_account_and_says_why(admin_client):
    ada, project = owner_with_project()
    url = reverse("admin:auth_user_delete", args=[ada.pk])
    page = admin_client.get(url).content.decode()
    assert "protected" in page and "Space Game" in page
    admin_client.post(url, {"post": "yes"})
    assert User.objects.filter(pk=ada.pk).exists() and owners_of(project) == ["ada"]


@pytest.mark.django_db
def test_the_admin_shows_teams_read_only(admin_client):
    _, project = owner_with_project()
    page = admin_client.get(reverse("admin:projects_project_change", args=[project.pk]))
    html = page.content.decode()
    assert "ada" in html and "Owner" in html
    assert 'name="memberships-0-role"' not in html
    assert 'name="memberships-0-DELETE"' not in html


# ---------- The pages per role ----------


def page_for(client, user, project, name="detail"):
    client.force_login(user)
    response = client.get(reverse(f"projects:{name}", args=[project.slug]))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_the_project_page_shows_each_role_only_what_it_may_do(client):
    ada, project = owner_with_project()
    grace, linus = make_member("grace"), make_member("linus")
    join(project, grace, "maintainer")
    join(project, linus, "viewer")
    slug = project.slug
    team = reverse("projects:members", args=[slug])
    edit, delete = reverse("projects:edit", args=[slug]), reverse("projects:delete", args=[slug])

    owner = page_for(client, ada, project)
    assert all(url in owner for url in [team, edit, delete]) and 'id="setup"' in owner
    maintainer = page_for(client, grace, project)
    assert team in maintainer and edit in maintainer and delete not in maintainer
    assert 'id="setup"' not in maintainer and "data-no-repository" in maintainer
    viewer = page_for(client, linus, project)
    assert team in viewer and edit not in viewer and delete not in viewer
    assert 'id="setup"' not in viewer and "data-role-tag>Viewer<" in viewer
    # The Maintainer's edit form has no name to change.
    client.force_login(grace)
    form = client.get(edit).content.decode()
    assert 'name="description"' in form and 'name="name"' not in form


@pytest.mark.django_db
def test_a_viewer_sees_stored_repository_details_without_asking_github(client):
    from projects.models import RepositoryLink

    _, project = owner_with_project()
    RepositoryLink.objects.create(
        project=project,
        github_id=1,
        full_name="octocat/hello-world",
        html_url="https://github.com/octocat/hello-world",
        fetched_at=None,  # stale: an Owner's view would refresh it
    )
    linus = make_member("linus")
    join(project, linus, "viewer")
    page = page_for(client, linus, project)  # the network guard fails any GitHub call
    assert "octocat/hello-world" in page
    assert reverse("projects:refresh_repository", args=[project.slug]) not in page
    assert reverse("projects:unlink_repository", args=[project.slug]) not in page
    # Nor does ?webhook=show do anything for them.
    client.force_login(linus)
    shown = client.get(project.get_absolute_url() + "?webhook=show").content.decode()
    assert "data-webhook-fields" not in shown


@pytest.mark.django_db
def test_the_team_page_shows_everyone_the_team_and_only_owners_the_controls(client):
    ada, project = owner_with_project()
    grace, linus = make_member("grace"), make_member("linus")
    join(project, grace, "viewer")
    ProjectInvitation.objects.create(
        project=project, invitee=linus, role="maintainer", invited_by=ada
    )

    owner = page_for(client, ada, project, "members")
    assert 'data-member="ada"' in owner and 'data-member="grace"' in owner
    assert "data-invite" in owner and 'data-invitee="linus"' in owner
    assert "Invited as Maintainer by ada" in owner
    assert reverse("projects:change_role", args=[project.slug, 2]) in owner

    viewer = page_for(client, grace, project, "members")
    assert 'data-member="ada"' in viewer and 'data-member="grace"' in viewer
    assert "data-invite" not in viewer and "linus" not in viewer
    assert "/role/" not in viewer and "/remove/" not in viewer and "data-leave" in viewer


@pytest.mark.django_db
def test_the_list_shows_every_project_with_its_role_and_counts_only_owned_ones(client):
    ada, project = owner_with_project()
    grace = make_member("grace")
    services.create_project(grace, name="Moon Base")
    join(project, grace, "viewer")
    listing = page_for(client, grace, project, "detail") and client.get(reverse("projects:list"))
    html = listing.content.decode()
    assert "Space Game" in html and "Moon Base" in html
    assert 'data-role="viewer"' in html and 'data-role="owner"' in html
    assert "1 of 5 projects" in html


@pytest.mark.django_db
def test_team_copy_is_escaped(client):
    ada, project = owner_with_project()
    bad = make_member("evil")
    from accounts.models import Profile

    Profile.objects.filter(user=bad).update(display_name="<script>x</script>")
    join(project, bad, "viewer")
    html = page_for(client, ada, project, "members")
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html


# ---------- CSRF and signed-out visitors ----------


def team_posts(project, membership_pk, invitation_pk) -> list[str]:
    slug = project.slug
    return [
        reverse("projects:invite", args=[slug]),
        reverse("projects:change_role", args=[slug, membership_pk]),
        reverse("projects:remove_member", args=[slug, membership_pk]),
        reverse("projects:cancel_invitation", args=[slug, invitation_pk]),
        reverse("projects:leave", args=[slug]),
        reverse("projects:accept_invitation", args=[invitation_pk]),
        reverse("projects:decline_invitation", args=[invitation_pk]),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("htmx", [False, True])
def test_every_team_post_without_a_csrf_token_is_refused(htmx):
    from django.test import Client

    ada, project = owner_with_project()
    grace = make_member("grace")
    member = join(project, grace, "viewer")
    invitation = ProjectInvitation.objects.create(project=project, invitee=ada, role="viewer")
    headers = {"HX-Request": "true"} if htmx else {}
    for user in [ada, grace]:
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        for url in team_posts(project, member.pk, invitation.pk):
            data = {"username": "grace", "role": "owner"}
            assert client.post(url, data, headers=headers).status_code == 403, url
    assert sorted(project.memberships.values_list("user__username", "role")) == [
        ("ada", "owner"),
        ("grace", "viewer"),
    ]
    assert ProjectInvitation.objects.count() == 1


@pytest.mark.django_db
def test_a_signed_out_visitor_is_sent_to_sign_in_from_every_team_url(client):
    _, project = owner_with_project()
    urls = team_posts(project, 1, 1) + [reverse("projects:members", args=[project.slug])]
    for url in urls:
        response = client.post(url) if not url.endswith("/members/") else client.get(url)
        assert response.status_code == 302 and "/accounts/login/" in response["Location"], url


# ---------- The migration ----------


@pytest.mark.django_db(transaction=True)
def test_the_teams_migration_makes_each_owner_an_owner_member_and_rolls_back():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    def migrate(to):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("projects", to)])
        return executor.loader.project_state(("projects", to)).apps

    try:
        old = migrate("0002_setup_progress")
        ada, grace = make_member("ada"), make_member("grace")
        Old = old.get_model("projects", "Project")
        Old.objects.create(owner_id=ada.pk, name="Space Game", slug="space-game")
        Old.objects.create(owner_id=grace.pk, name="Moon Base", slug="moon-base")

        new = migrate("0004_remove_project_owner")
        Membership = new.get_model("projects", "ProjectMembership")
        assert sorted(
            Membership.objects.values_list("project__name", "user__username", "role")
        ) == [
            ("Moon Base", "grace", "owner"),
            ("Space Game", "ada", "owner"),
        ]

        back = migrate("0002_setup_progress")
        rows = back.get_model("projects", "Project").objects.values_list("name", "owner__username")
        assert sorted(rows) == [("Moon Base", "grace"), ("Space Game", "ada")]
    finally:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes("projects"))


# ---------- Finding someone to invite ----------


def search(client, project, q):
    return client.get(reverse("projects:member_search", args=[project.slug]), {"q": q})


@pytest.mark.django_db
def test_finding_members_by_username_or_name_shows_who_can_be_invited():
    from accounts.models import Profile
    from projects import teams

    ada, project = owner_with_project()
    dan, dana, daniel, dave = (make_member(n) for n in ["dan", "dana", "Daniel", "dave"])
    Profile.objects.filter(user=make_member("zed")).update(display_name="Dante Zed")
    join(project, dana, "viewer")
    ProjectInvitation.objects.create(project=project, invitee=daniel, role="viewer")
    User.objects.filter(pk=dave.pk).update(is_active=False)

    found = teams.find_members(ada, project, "  DAN ")
    # The exact username first, then by username in any case; display names match too.
    assert [(c.user.username, c.state) for c in found] == [
        ("dan", "available"),
        ("dana", "member"),
        ("Daniel", "invited"),
        ("zed", "available"),
    ]
    assert [c.state for c in teams.find_members(ada, project, "ad")] == ["you"]
    # Too short, too long, or nothing: no one. Emails are never searched.
    for query in ["", "d", " d ", "x" * 151, "example.com", "dan@example.com"]:
        assert teams.find_members(ada, project, query) == [], query
    for i in range(8):
        make_member(f"many{i}")
    assert len(teams.find_members(ada, project, "many")) == teams.SEARCH_LIMIT


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["maintainer", "viewer", None])
def test_only_owners_can_search_members(client, role):
    from projects import teams

    _, project = owner_with_project()
    grace = make_member("grace")
    if role:
        join(project, grace, role)
    client.force_login(grace)
    assert search(client, project, "ad").status_code == 404
    with pytest.raises(Project.DoesNotExist):
        teams.find_members(grace, project, "ad")


@pytest.mark.django_db
def test_the_suggestions_show_people_never_emails_and_are_never_cached(client):
    from accounts.models import Profile

    _, project = owner_with_project(client)
    dan = make_member("dan")
    Profile.objects.filter(user=dan).update(display_name="<b>Dan</b>")
    join(project, make_member("dana"), "maintainer")
    response = search(client, project, "da")
    html = response.content.decode()
    assert response.status_code == 200 and "no-store" in response["Cache-Control"]
    assert 'role="listbox"' in html and html.count('role="option"') == 2
    assert 'data-username="dan" data-state="available"' in html
    assert 'aria-disabled="true" data-username="dana" data-state="member"' in html
    assert "Already in the team" in html and "2 members found." in html
    assert "@example.com" not in html
    assert "<b>Dan</b>" not in html and "&lt;b&gt;Dan&lt;/b&gt;" in html
    # Nothing found: a sentence, the query escaped; too short: nothing at all.
    none = search(client, project, "<i>zz").content.decode()
    assert "data-no-match" in none and "&lt;i&gt;zz" in none and "<i>" not in none
    assert search(client, project, "d").content.decode().strip() == ""


@pytest.mark.django_db
def test_the_invite_field_is_ready_for_suggestions_and_works_without_them(client):
    _, project = owner_with_project(client)
    page = page_for(client, User.objects.get(username="ada"), project, "members")
    assert "data-member-search" in page and 'autocomplete="off"' in page
    assert f'data-search-url="{reverse("projects:member_search", args=[project.slug])}"' in page
    assert "js/projects.js" in page
    # Viewers have no invite form, so no script.
    linus = make_member("linus")
    join(project, linus, "viewer")
    assert "js/projects.js" not in page_for(client, linus, project, "members")


@pytest.mark.django_db
def test_the_last_owner_gets_no_role_control_on_their_own_row(client):
    ada, project = owner_with_project()
    grace = make_member("grace")
    grace_member = join(project, grace, "maintainer")
    own = ProjectMembership.objects.get(user=ada)
    page = page_for(client, ada, project, "members")
    assert reverse("projects:change_role", args=[project.slug, own.pk]) not in page
    assert reverse("projects:change_role", args=[project.slug, grace_member.pk]) in page
    # With another Owner, she can step down from her own row.
    grace_member.role = "owner"
    grace_member.save()
    page = page_for(client, ada, project, "members")
    assert reverse("projects:change_role", args=[project.slug, own.pk]) in page


# ---------- The demo seed ----------


@pytest.mark.django_db
def test_the_team_demo_seed_runs_only_in_development(settings):
    from django.core.management import CommandError, call_command

    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_team_demo")
    assert not User.objects.exists()


@pytest.mark.django_db
def test_the_team_demo_seed_makes_plain_verified_members_once(settings):
    from django.contrib.auth import authenticate
    from django.core.management import call_command

    from projects.management.commands.seed_team_demo import DEMO_PASSWORD, MEMBERS, PROJECT

    settings.DEBUG = True
    real_bob = User.objects.create_user("Bob", "real@example.com", "bobs-own-password-9")
    call_command("seed_team_demo")
    call_command("seed_team_demo")  # again: nothing changes

    assert User.objects.count() == len(MEMBERS)
    assert not User.objects.filter(is_staff=True).exists()
    assert not User.objects.filter(is_superuser=True).exists()
    assert not User.objects.exclude(groups=None).exists()
    assert not User.objects.exclude(user_permissions=None).exists()
    # An existing account is left alone: its password and email stay its own.
    real_bob.refresh_from_db()
    assert real_bob.check_password("bobs-own-password-9") and real_bob.email == "real@example.com"
    alice = authenticate(username="alice", password=DEMO_PASSWORD)
    assert alice is not None
    assert EmailAddress.objects.filter(user=alice, verified=True).exists()

    project = Project.objects.get(name=PROJECT)
    assert sorted(project.memberships.values_list("user__username", "role")) == [
        ("Bob", "maintainer"),
        ("alice", "owner"),
        ("cara", "viewer"),
    ]
    assert list(project.invitations.values_list("invitee__username", "role")) == [
        ("erin", "maintainer")
    ]
    assert Project.objects.count() == 1 and ProjectMembership.objects.count() == 3


# ---------- Inviting several people at once ----------


@pytest.mark.django_db
def test_several_people_are_invited_at_once_one_value_each_or_comma_separated(client):
    _, project = owner_with_project(client)
    for name in ["dan", "dana", "erin"]:
        make_member(name)
    # As projects.js sends them (one value per chip), plus a typed list, with a repeat.
    response = client.post(
        invite_url(project),
        {"username": ["dan", "DANA", "erin, dan  "], "role": "maintainer"},
        follow=True,
    )
    assert "Invited dan, dana and erin. They'll see it on their Projects page." in messages_on(
        response
    )
    assert sorted(project.invitations.values_list("invitee__username", "role")) == [
        ("dan", "maintainer"),
        ("dana", "maintainer"),
        ("erin", "maintainer"),
    ]


@pytest.mark.django_db
def test_a_batch_invites_who_it_can_and_names_each_refusal(client):
    _, project = owner_with_project(client)
    make_member("dan")
    linus = make_member("linus")
    join(project, linus, "viewer")
    response = client.post(
        invite_url(project),
        {"username": ["dan", "linus", "nobody", "ada"], "role": "viewer"},
        follow=True,
    )
    said = messages_on(response)
    assert "Invited dan. They'll see it on their Projects page." in said
    assert "linus is already in this project." in said
    assert "No Hub member is called “nobody”." in said
    assert "You're already in this project." in said
    assert list(project.invitations.values_list("invitee__username", flat=True)) == ["dan"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, message",
    [
        (
            {"username": [f"m{i}" for i in range(11)], "role": "viewer"},
            "Invite at most 10 people at a time.",
        ),
        ({"username": ["dan", "dana"], "role": "boss"}, "Choose Owner, Maintainer or Viewer."),
        ({"username": [" , ", ""], "role": "viewer"}, "Enter a username and choose a role."),
        ({"role": "viewer"}, "Enter a username and choose a role."),
    ],
)
def test_a_batch_is_refused_whole_when_it_is_too_big_empty_or_has_no_valid_role(
    client, data, message
):
    _, project = owner_with_project(client)
    for name in ["dan", "dana"] + [f"m{i}" for i in range(11)]:
        make_member(name)
    response = client.post(invite_url(project), data, follow=True)
    assert messages_on(response) == [message]
    assert not ProjectInvitation.objects.exists()


def test_usernames_are_read_from_every_value_and_separator_once_each():
    from projects.teams import parse_usernames

    assert parse_usernames(["dan", " Dana,erin ", "DAN", "", None, "zoe\tzed\n,,"]) == [
        "dan",
        "Dana",
        "erin",
        "zoe",
        "zed",
    ]
    assert parse_usernames([]) == [] and parse_usernames([" , "]) == []


@pytest.mark.django_db
def test_without_javascript_the_field_says_how_to_invite_several(client):
    _, project = owner_with_project(client)
    page = client.get(reverse("projects:members", args=[project.slug])).content.decode()
    assert "Usernames" in page and "Separate several usernames with commas." in page
    assert 'data-batch-max="10"' in page and "data-invite-submit" in page
