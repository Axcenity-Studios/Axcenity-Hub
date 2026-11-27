"""Bug reports and feedback (Phase 14): the permitted status transitions and the access
matrix (both test-first), submitting and its validation, the daily limit, the verification
gate, assigning, commenting, the pages and their refusals."""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from accounts.access import EmailNotVerified
from projects.models import Project, ProjectMembership, Role
from reports import bugs
from reports.models import BugActivity, BugReport, BugStatus

User = get_user_model()
PASSWORD = "correct-horse-battery-staple-42"


def make_member(username="ada", *, verified: bool = True, **extra):
    email = f"{username}@example.com"
    user = User.objects.create_user(username, email, PASSWORD, **extra)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


def signed_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def make_report(submitter, project=None, **fields) -> BugReport:
    values = {
        "kind": BugReport.Kind.BUG,
        "title": "Decals spawn at the origin",
        "description": "After Touched fires, the decal appears at 0, 0, 0.",
        "steps": "1. Add a Part\n2. Wire When touched → Spawn decal\n3. Press F5",
        "engine_version": "0.4.0-alpha.2",
        "platform": BugReport.Platform.LINUX,
        **fields,
    }
    return BugReport.objects.create(project=project, submitter=submitter, **values)


@pytest.fixture
def team(db):
    """A project with an Owner, a Maintainer and a Viewer; an admin; an outsider."""
    owner = make_member("olive")
    project = Project.objects.create_with_owner(owner, name="Space Game")
    maintainer, viewer, other = make_member("max"), make_member("vera"), make_member("val")
    ProjectMembership.objects.create(project=project, user=maintainer, role=Role.MAINTAINER)
    ProjectMembership.objects.create(project=project, user=viewer, role=Role.VIEWER)
    ProjectMembership.objects.create(project=project, user=other, role=Role.VIEWER)
    return {
        "project": project,
        "owner": owner,
        "maintainer": maintainer,
        "viewer": viewer,
        "other_viewer": other,
        "admin": make_member("adam", is_staff=True),
        "outsider": make_member("otto"),
    }


# ---------- The permitted-transition table (TDD) ----------

# Written out here, not read from the code: this is the workflow the Hub promises.
ALLOWED = {
    ("new", "confirmed"),
    ("new", "wont_fix"),
    ("confirmed", "in_progress"),
    ("confirmed", "wont_fix"),
    ("in_progress", "resolved"),
    ("in_progress", "confirmed"),
    ("resolved", "closed"),
    ("resolved", "in_progress"),
    ("wont_fix", "closed"),
    ("wont_fix", "new"),
}
STATUSES = ["new", "confirmed", "in_progress", "resolved", "wont_fix", "closed"]


@pytest.mark.parametrize("old", STATUSES)
@pytest.mark.parametrize("new", [*STATUSES, "reopened", "", "CLOSED"])
def test_status_changes_follow_the_permitted_transition_table(team, old, new):
    report = make_report(team["viewer"], team["project"], status=old)
    if (old, new) in ALLOWED:
        bugs.change_status(team["owner"], report, new)
        report.refresh_from_db()
        assert report.status == new
        entry = BugActivity.objects.get(report=report)
        assert (entry.kind, entry.actor, entry.old_status, entry.new_status) == (
            BugActivity.Kind.STATUS,
            team["owner"],
            old,
            new,
        )
    else:
        with pytest.raises(bugs.TransitionRefused):
            bugs.change_status(team["owner"], report, new)
        report.refresh_from_db()
        assert report.status == old
        assert not BugActivity.objects.filter(report=report).exists()
    assert {status.value for status in BugStatus} == set(STATUSES)


# ---------- Who may see and handle a report (TDD) ----------

# For each report and each person: whether they may see it (open it, find it in the list,
# comment) and whether they may handle it (change its status, assign it). Everyone else, a
# signed-out visitor included, gets a 404 for each, as for a report that doesn't exist.
# vera (a Viewer) sent the project's report; otto (in no project) sent the engine's.
ACCESS = {
    "project": {
        "submitter": (True, False),
        "owner": (True, True),
        "maintainer": (True, True),
        "admin": (True, True),
        "other_viewer": (False, False),
        "outsider": (False, False),
        "visitor": (False, False),
    },
    "engine": {
        "submitter": (True, False),
        "admin": (True, True),
        "owner": (False, False),
        "maintainer": (False, False),
        "viewer": (False, False),
        "visitor": (False, False),
    },
}


@pytest.mark.parametrize(
    ("about", "who"), [(about, who) for about, people in ACCESS.items() for who in people]
)
def test_only_the_submitter_the_projects_authorities_and_admins_reach_a_report(team, about, who):
    if about == "project":
        submitter = team["viewer"]
        report = make_report(submitter, team["project"])
        handler = team["owner"]
    else:
        submitter = team["outsider"]
        report = make_report(submitter, None)
        handler = team["admin"]
    sees, handles = ACCESS[about][who]
    person = submitter if who == "submitter" else team.get(who)
    client = signed_in(person) if person else Client()
    pk = report.pk

    page = client.get(reverse("reports:bug_detail", args=[pk]))
    assert page.status_code == (200 if sees else 404)

    listed = client.get(reverse("reports:bug_list"))
    if person is None:
        assert listed.status_code == 302 and "/accounts/login/" in listed["Location"]
    else:
        assert (f'data-bug="{pk}"' in listed.content.decode()) is sees

    comment = client.post(reverse("reports:bug_comment", args=[pk]), {"body": "Still happens."})
    assert comment.status_code == (302 if sees else 404)
    assert BugActivity.objects.filter(report=report, kind="comment").exists() is sees

    assign = client.post(reverse("reports:bug_assign", args=[pk]), {"assignee": handler.pk})
    status = client.post(reverse("reports:bug_status", args=[pk]), {"status": "confirmed"})
    assert (assign.status_code, status.status_code) == ((302, 302) if handles else (404, 404))
    report.refresh_from_db()
    assert (report.assignee, report.status) == (
        (handler, "confirmed") if handles else (None, "new")
    )


def test_a_submitter_who_leaves_the_project_still_sees_their_report(team):
    report = make_report(team["viewer"], team["project"])
    from projects import teams

    teams.leave(team["viewer"], team["project"])
    client = signed_in(team["viewer"])
    assert client.get(report.get_absolute_url()).status_code == 200
    assert (
        client.post(
            reverse("reports:bug_status", args=[report.pk]), {"status": "confirmed"}
        ).status_code
        == 404
    )


def test_a_member_whose_role_drops_to_viewer_loses_the_projects_other_reports(team):
    report = make_report(team["viewer"], team["project"])
    membership = team["project"].memberships.get(user=team["maintainer"])
    from projects import teams

    teams.change_role(team["owner"], team["project"], membership.pk, "viewer")
    assert signed_in(team["maintainer"]).get(report.get_absolute_url()).status_code == 404


# ---------- Submitting ----------

BUG = {
    "about": "engine",
    "kind": "bug",
    "title": "Decals spawn at the origin",
    "description": "The decal appears at 0, 0, 0.",
    "steps": "1. Wire When touched → Spawn decal\n2. Press F5",
    "expected": "At the touched point.",
    "engine_version": "0.4.0-alpha.2",
    "platform": "linux",
}


def test_a_member_sends_a_bug_about_the_engine_and_lands_on_it(team):
    client = signed_in(team["outsider"])
    page = client.get(reverse("reports:bug_create")).content.decode()
    assert "data-bug-form" in page and "Axcenity Engine" in page
    response = client.post(reverse("reports:bug_create"), BUG)
    report = BugReport.objects.get()
    assert response.status_code == 302 and response["Location"] == report.get_absolute_url()
    assert (report.project, report.submitter, report.status, report.assignee) == (
        None,
        team["outsider"],
        "new",
        None,
    )
    assert report.engine_version == "0.4.0-alpha.2" and report.platform == "linux"
    detail = client.get(report.get_absolute_url()).content.decode()
    assert "Report sent." in detail and "Decals spawn at the origin" in detail
    assert "0.4.0-alpha.2" in detail and "At the touched point." in detail


def test_a_member_sends_a_report_about_their_project_chosen_from_the_address(team):
    client = signed_in(team["viewer"])
    page = client.get(reverse("reports:bug_create") + "?about=space-game").content.decode()
    assert '<option value="space-game" selected>Space Game</option>' in page
    client.post(reverse("reports:bug_create"), {**BUG, "about": "space-game"})
    assert BugReport.objects.get().project == team["project"]


def test_only_the_engine_and_the_members_own_projects_are_offered(team):
    page = signed_in(team["outsider"]).get(reverse("reports:bug_create") + "?about=space-game")
    html = page.content.decode()
    assert "Space Game" not in html and 'value="engine"' in html
    response = signed_in(team["outsider"]).post(
        reverse("reports:bug_create"), {**BUG, "about": "space-game"}
    )
    assert response.status_code == 200
    assert "Choose the engine or one of your projects." in response.content.decode()
    assert not BugReport.objects.exists()


def test_submitting_about_a_project_you_left_is_refused_by_the_service(team):
    with pytest.raises(bugs.PermissionDenied):
        bugs.submit(
            team["outsider"],
            project=team["project"],
            **{k: v for k, v in BUG.items() if k != "about"},
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("title", "", "Give the report a title."),
        ("title", "   ", "Give the report a title."),
        ("title", "x" * 121, "Keep this to 120 characters (it has 121)."),
        ("description", "", "Say what happened (or, for feedback, what you'd like)."),
        ("description", "\n\t ", "Say what happened (or, for feedback, what you'd like)."),
        ("steps", "", "List the steps that make the bug happen."),
        ("engine_version", "", "Give the engine version the bug happens in."),
        ("engine_version", "latest", "Write the version as its release names it"),
        ("engine_version", "0.4.0 alpha", "Write the version as its release names it"),
        ("engine_version", "<b>1.0</b>", "Write the version as its release names it"),
        ("platform", "", "Choose the platform the bug happens on."),
        ("platform", "amiga", "Choose the platform the bug happens on."),
        ("kind", "question", "Choose a bug or feedback."),
        ("about", "", "Choose the engine or one of your projects."),
        ("expected", "x" * 2001, "Keep this to 2000 characters (it has 2001)."),
    ],
)
def test_required_and_invalid_fields_are_refused_with_their_message(team, field, value, message):
    response = signed_in(team["outsider"]).post(
        reverse("reports:bug_create"), {**BUG, field: value}
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert message in html.replace("&#x27;", "'") and 'aria-invalid="true"' in html
    assert not BugReport.objects.exists()


@pytest.mark.parametrize("version", ["0.4", "0.4.0", "v0.4.0", "0.4.0-alpha.2", "12.0.3-rc1"])
def test_engine_versions_as_releases_name_them_pass(team, version):
    signed_in(team["outsider"]).post(
        reverse("reports:bug_create"), {**BUG, "engine_version": version}
    )
    assert BugReport.objects.get().engine_version == version


def test_feedback_needs_only_a_title_and_a_description(team):
    signed_in(team["outsider"]).post(
        reverse("reports:bug_create"),
        {"about": "engine", "kind": "feedback", "title": "Dark Console", "description": "Please."},
    )
    report = BugReport.objects.get()
    assert (report.kind, report.steps, report.engine_version, report.platform) == (
        "feedback",
        "",
        "",
        "",
    )


def test_text_is_trimmed_and_kept_as_plain_text(team):
    client = signed_in(team["outsider"])
    client.post(
        reverse("reports:bug_create"),
        {**BUG, "title": "  <script>x</script>   bug  ", "description": "<img src=x>"},
    )
    report = BugReport.objects.get()
    assert report.title == "<script>x</script> bug"
    html = client.get(report.get_absolute_url()).content.decode()
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html
    assert "<img src=x>" not in html


# ---------- The daily limit ----------


def submit_as(user, now=None, **fields):
    values = {k: v for k, v in BUG.items() if k != "about"}
    return bugs.submit(user, project=None, now=now, **{**values, **fields})


def test_the_sixth_report_in_a_day_is_refused_and_one_after_the_window_is_allowed(team):
    from datetime import timedelta

    from django.utils import timezone

    member, now = team["outsider"], timezone.now()
    for _ in range(5):
        submit_as(member, now=now)
    with pytest.raises(bugs.LimitReached) as refused:
        submit_as(member, now=now)
    assert str(refused.value).startswith("You've sent 5 reports in the last day")
    assert "You can send another in 1 day" in str(refused.value) or "23 hours" in str(refused.value)
    assert BugReport.objects.count() == 5
    # The oldest leaves the window: one more is allowed.
    first = BugReport.objects.order_by("pk").first()
    BugReport.objects.filter(pk=first.pk).update(created=now - timedelta(days=1))
    submit_as(member, now=now)
    assert BugReport.objects.count() == 6


def test_the_limit_counts_feedback_and_project_reports_and_each_member_alone(team):
    for index in range(3):
        submit_as(team["viewer"], kind="feedback", title=f"Idea {index}")
    for index in range(2):
        bugs.submit(
            team["viewer"],
            project=team["project"],
            **{**{k: v for k, v in BUG.items() if k != "about"}, "title": f"Bug {index}"},
        )
    with pytest.raises(bugs.LimitReached):
        submit_as(team["viewer"])
    submit_as(team["owner"])  # another member isn't affected


def test_the_page_says_so_at_the_limit_and_the_post_is_refused_with_the_message(team):
    for _ in range(5):
        submit_as(team["outsider"])
    client = signed_in(team["outsider"])
    page = client.get(reverse("reports:bug_create")).content.decode()
    assert "data-limit" in page and "You&#x27;ve sent 5 reports in the last day" in page
    response = client.post(reverse("reports:bug_create"), BUG)
    assert response.status_code == 200
    assert "You&#x27;ve sent 5 reports in the last day" in response.content.decode()
    assert BugReport.objects.count() == 5


# ---------- The verification gate ----------


def test_unverified_members_cant_submit_or_comment(team):
    unverified = make_member("una", verified=False)
    client = signed_in(unverified)
    for response in [
        client.get(reverse("reports:bug_create")),
        client.post(reverse("reports:bug_create"), BUG),
    ]:
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("accounts:verify_email"))
    assert not BugReport.objects.exists()
    with pytest.raises(EmailNotVerified):
        submit_as(unverified)
    # A submitter whose address is no longer verified can still read their report, not comment.
    report = make_report(team["viewer"], team["project"])
    EmailAddress.objects.filter(user=team["viewer"]).update(verified=False)
    viewer = signed_in(team["viewer"])
    assert viewer.get(report.get_absolute_url()).status_code == 200
    response = viewer.post(reverse("reports:bug_comment", args=[report.pk]), {"body": "Hi"})
    assert response["Location"].startswith(reverse("accounts:verify_email"))
    assert not BugActivity.objects.exists()


def test_signed_out_visitors_are_sent_to_sign_in_for_the_list_and_the_form(db):
    for name in ["reports:bug_list", "reports:bug_create"]:
        response = Client().get(reverse(name))
        assert response.status_code == 302 and response["Location"].startswith("/accounts/login/")


# ---------- Assigning ----------


def test_only_the_projects_owners_and_maintainers_can_be_assigned_its_report(team):
    report = make_report(team["viewer"], team["project"])
    assert list(bugs.assignable(report)) == [team["maintainer"], team["owner"]]
    for person in [team["viewer"], team["outsider"], team["admin"]]:
        with pytest.raises(bugs.AssigneeRefused):
            bugs.assign(team["owner"], report, person)
    bugs.assign(team["owner"], report, team["maintainer"])
    report.refresh_from_db()
    assert report.assignee == team["maintainer"]


def test_engine_reports_are_assigned_to_admins_only(team):
    report = make_report(team["outsider"])
    other_admin = make_member("ava", is_staff=True)
    assert list(bugs.assignable(report)) == [team["admin"], other_admin]
    with pytest.raises(bugs.AssigneeRefused):
        bugs.assign(team["admin"], report, team["owner"])


def test_assigning_records_once_and_unassigning_records_too(team):
    report = make_report(team["viewer"], team["project"])
    bugs.assign(team["owner"], report, team["owner"])
    bugs.assign(team["owner"], report, team["owner"])  # no change: nothing recorded
    bugs.assign(team["owner"], report, None)
    entries = list(BugActivity.objects.values_list("kind", "assignee"))
    assert entries == [("assigned", team["owner"].pk), ("assigned", None)]


@pytest.mark.parametrize("value", ["abc", "-1", "٣", "99999", "1 OR 1=1"])
def test_an_unknown_assignee_from_the_form_is_refused_and_changes_nothing(team, value):
    report = make_report(team["viewer"], team["project"])
    client = signed_in(team["owner"])
    response = client.post(
        reverse("reports:bug_assign", args=[report.pk]), {"assignee": value}, follow=True
    )
    assert "Only someone who handles this report" in response.content.decode()
    report.refresh_from_db()
    assert report.assignee is None and not BugActivity.objects.exists()


def test_losing_the_role_removal_and_leaving_unassign_a_member(team):
    from projects import teams

    project = team["project"]
    first = make_report(team["viewer"], project)
    second = make_report(team["viewer"], project)
    engine = make_report(team["outsider"])
    bugs.assign(team["owner"], first, team["maintainer"])
    bugs.assign(team["owner"], second, team["owner"])
    bugs.assign(team["admin"], engine, team["admin"])
    membership = project.memberships.get(user=team["maintainer"])
    teams.change_role(team["owner"], project, membership.pk, "viewer")
    first.refresh_from_db()
    assert first.assignee is None
    # Back to Maintainer, assigned again, then removed.
    teams.change_role(team["owner"], project, membership.pk, "maintainer")
    bugs.assign(team["owner"], first, team["maintainer"])
    teams.remove(team["owner"], project, membership.pk)
    first.refresh_from_db()
    assert first.assignee is None
    # An Owner who leaves (another Owner stays) is unassigned too; the engine report keeps its.
    co_owner = make_member("cora")
    ProjectMembership.objects.create(project=project, user=co_owner, role=Role.OWNER)
    teams.leave(team["owner"], project)
    second.refresh_from_db()
    engine.refresh_from_db()
    assert second.assignee is None and engine.assignee == team["admin"]


def test_a_maintainer_promoted_to_owner_keeps_their_assignment(team):
    from projects import teams

    report = make_report(team["viewer"], team["project"])
    bugs.assign(team["owner"], report, team["maintainer"])
    membership = team["project"].memberships.get(user=team["maintainer"])
    teams.change_role(team["owner"], team["project"], membership.pk, "owner")
    report.refresh_from_db()
    assert report.assignee == team["maintainer"]


# ---------- Commenting and the timeline ----------


def test_comments_and_changes_build_the_timeline_in_order(team):
    report = make_report(team["viewer"], team["project"])
    client = signed_in(team["viewer"])
    response = client.post(
        reverse("reports:bug_comment", args=[report.pk]), {"body": "  Also on Windows.  "}
    )
    entry = BugActivity.objects.get()
    assert response["Location"] == f"{report.get_absolute_url()}#activity-{entry.pk}"
    assert entry.body == "Also on Windows."
    bugs.change_status(team["owner"], report, "confirmed")
    bugs.assign(team["owner"], report, team["maintainer"])
    html = signed_in(team["owner"]).get(report.get_absolute_url()).content.decode()
    assert html.index("Also on Windows.") < html.index("changed the status from New to Confirmed")
    assert html.index("changed the status from New to Confirmed") < html.index("assigned it to max")


@pytest.mark.parametrize(
    ("body", "message"),
    [("", "Write a comment first."), ("   ", "Write a comment first."),
     ("x" * 2001, "Keep this to 2000 characters (it has 2001).")],
)  # fmt: skip
def test_an_empty_or_over_long_comment_is_refused_on_the_page(team, body, message):
    report = make_report(team["viewer"], team["project"])
    response = signed_in(team["viewer"]).post(
        reverse("reports:bug_comment", args=[report.pk]), {"body": body}
    )
    assert response.status_code == 200 and message in response.content.decode()
    assert not BugActivity.objects.exists()


def test_commenting_moves_a_report_up_recently_updated(team):
    from datetime import timedelta

    from django.utils import timezone

    report = make_report(team["viewer"], team["project"])
    BugReport.objects.filter(pk=report.pk).update(updated=timezone.now() - timedelta(days=3))
    bugs.comment(team["viewer"], report, "Bump")
    report.refresh_from_db()
    assert timezone.now() - report.updated < timedelta(minutes=1)


# ---------- A report's page ----------


def test_the_page_shows_handling_controls_only_to_those_who_handle_it(team):
    report = make_report(team["viewer"], team["project"])
    owner = signed_in(team["owner"]).get(report.get_absolute_url()).content.decode()
    assert "data-manage" in owner and "data-status-form" in owner and "data-assign-form" in owner
    assert '<option value="confirmed">Confirmed</option>' in owner
    assert '<option value="wont_fix">Won&#x27;t fix</option>' in owner
    assert 'value="resolved"' not in owner  # not reachable from New
    assert (
        f'value="{team["maintainer"].pk}"' in owner and f'value="{team["viewer"].pk}"' not in owner
    )
    submitter = signed_in(team["viewer"]).get(report.get_absolute_url()).content.decode()
    assert "data-manage" not in submitter and "data-comment-form" in submitter
    assert "data-yours" in submitter


def test_a_closed_report_says_its_status_is_final(team):
    report = make_report(team["viewer"], team["project"], status="closed")
    html = signed_in(team["owner"]).get(report.get_absolute_url()).content.decode()
    assert "data-final" in html and "data-status-form" not in html


def test_a_refused_status_from_the_form_shows_its_message(team):
    report = make_report(team["viewer"], team["project"])
    client = signed_in(team["owner"])
    url = reverse("reports:bug_status", args=[report.pk])
    page = client.post(url, {"status": "closed"}, follow=True).content.decode()
    assert "A report that&#x27;s new can&#x27;t change to closed." in page
    page = client.post(url, {"status": "<b>x</b>"}, follow=True).content.decode()
    assert "Choose one of the statuses offered." in page and "<b>x</b>" not in page
    page = client.post(url, {"status": "confirmed"}, follow=True).content.decode()
    assert "Status changed to Confirmed." in page


def test_a_report_with_a_deleted_submitter_stays_and_says_so(team):
    report = make_report(make_member("gone"), team["project"])
    User.objects.get(username="gone").delete()
    html = signed_in(team["owner"]).get(report.get_absolute_url()).content.decode()
    assert "A deleted member" in html


def test_deleting_a_project_deletes_its_reports(team):
    make_report(team["viewer"], team["project"])
    engine = make_report(team["outsider"])
    team["project"].delete()
    assert list(BugReport.objects.all()) == [engine]


def test_unknown_reports_are_404_even_for_admins(team):
    client = signed_in(team["admin"])
    for name in ["reports:bug_detail"]:
        assert client.get(reverse(name, args=[999])).status_code == 404
    for name in ["reports:bug_status", "reports:bug_assign", "reports:bug_comment"]:
        assert client.post(reverse(name, args=[999]), {}).status_code == 404


def test_the_action_urls_take_post_only(team):
    report = make_report(team["viewer"], team["project"])
    client = signed_in(team["owner"])
    for name in ["reports:bug_status", "reports:bug_assign", "reports:bug_comment"]:
        assert client.get(reverse(name, args=[report.pk])).status_code == 405


def test_every_report_post_without_a_csrf_token_is_refused(team):
    report = make_report(team["viewer"], team["project"])
    client = Client(enforce_csrf_checks=True)
    client.force_login(team["owner"])
    urls = [reverse("reports:bug_create")] + [
        reverse(name, args=[report.pk])
        for name in ["reports:bug_status", "reports:bug_assign", "reports:bug_comment"]
    ]
    for url in urls:
        for headers in [{}, {"HX-Request": "true"}]:
            response = client.post(
                url, {**BUG, "status": "confirmed", "body": "x"}, headers=headers
            )
            assert response.status_code == 403, url
    report.refresh_from_db()
    assert report.status == "new" and BugReport.objects.count() == 1
    assert not BugActivity.objects.exists()


# ---------- Around the Hub ----------


def test_the_project_page_links_its_reports_for_those_who_handle_them(team):
    make_report(team["viewer"], team["project"])
    make_report(team["viewer"], team["project"], status="closed")
    url = team["project"].get_absolute_url()
    owner = signed_in(team["owner"]).get(url).content.decode()
    assert 'href="/reports/bugs/?about=space-game"' in owner and "Bug reports · 1 open" in owner
    assert 'href="/reports/bugs/new/?about=space-game"' in owner
    viewer = signed_in(team["viewer"]).get(url).content.decode()
    assert "data-project-reports" not in viewer and "data-report-bug" in viewer


def test_report_pages_sit_in_the_app_shell_under_reports(team):
    import re

    report = make_report(team["viewer"], team["project"])
    client = signed_in(team["viewer"])
    for url in [
        reverse("reports:bug_list"),
        reverse("reports:bug_create"),
        report.get_absolute_url(),
    ]:
        html = client.get(url).content.decode()
        current = re.findall(r'aria-current="page">\s*<svg.*?</svg>\s*([^<]+?)\s*<', html, re.S)
        assert current == ["Reports"], url


def test_the_admin_shows_reports_read_only(team, admin_client, admin_user, rf):
    report = make_report(team["viewer"], team["project"])
    bugs.comment(team["viewer"], report, "Hello")
    from django.contrib import admin as django_admin

    model_admin = django_admin.site._registry[BugReport]
    request = rf.get("/")
    request.user = admin_user
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, report)
    assert not model_admin.has_delete_permission(request, report)
    page = admin_client.get(reverse("admin:reports_bugreport_change", args=[report.pk]))
    assert page.status_code == 200 and "Hello" in page.content.decode()


@pytest.mark.django_db
def test_seed_report_demo_is_development_only_idempotent_and_makes_no_admin(settings):
    from django.core.management import CommandError, call_command

    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_report_demo")
    settings.DEBUG = True
    call_command("seed_report_demo", stdout=__import__("io").StringIO())
    assert BugReport.objects.count() == 24 and BugReport.objects.filter(project=None).count() == 8
    assert {status for status in BugReport.objects.values_list("status", flat=True)} == set(
        STATUSES
    )
    for report in BugReport.objects.exclude(status="new"):
        steps = list(report.activity.filter(kind="status").values_list("old_status", "new_status"))
        assert steps and steps[0][0] == "new" and steps[-1][1] == report.status
        assert all(step in ALLOWED for step in steps)
    for report in BugReport.objects.exclude(assignee=None):
        assert bugs.assignable(report).filter(pk=report.assignee_id).exists()
    activity = BugActivity.objects.count()
    call_command("seed_report_demo", stdout=__import__("io").StringIO())
    assert BugReport.objects.count() == 24 and BugActivity.objects.count() == activity
    assert not User.objects.filter(is_staff=True).exists()
    from datetime import timedelta

    from django.utils import timezone

    recent = BugReport.objects.filter(created__gt=timezone.now() - timedelta(days=1))
    for user in User.objects.all():
        assert recent.filter(submitter=user).count() <= 1
