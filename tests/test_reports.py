"""Reports (Phase 12B): members reporting a post or comment, once each, enforced by the
database; the page, its refusals and the 404s; and what happens to reports over time."""

import threading

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.urls import reverse

from forums.models import Comment, ForumPost
from reports import services
from reports.models import Report

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


@pytest.fixture
def content(db):
    """Grace's post, with a comment by Grace; Ada is the member who reports them."""
    grace, ada = make_member("grace"), make_member("ada")
    post = ForumPost.objects.create(author=grace, title="Buy cheap gold", body="Spam")
    comment = Comment.objects.create(post=post, author=grace, body="More spam")
    return {"grace": grace, "ada": ada, "post": post, "comment": comment}


def report_url(kind: str, pk: int) -> str:
    return reverse("reports:create", args=[kind, pk])


# ---------- Reporting ----------


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["post", "comment"])
def test_a_member_reports_a_post_or_comment_and_goes_back_to_it(content, kind):
    target = content[kind]
    client = signed_in(content["ada"])
    page = client.get(report_url(kind, target.pk)).content.decode()
    assert f"Report {kind}" in page and "data-report-form" in page
    for reason in ["Spam or advertising", "Harassment or abuse", "Off-topic", "Something else"]:
        assert reason in page
    response = client.post(
        report_url(kind, target.pk), {"reason": "spam", "details": "  Selling gold.  "}
    )
    assert response.status_code == 302 and response["Location"] == target.get_absolute_url()
    report = Report.objects.get()
    assert (report.reporter, report.target, report.kind) == (content["ada"], target, "abuse")
    assert (report.reason, report.details) == ("spam", "Selling gold.")
    shown = client.get(
        target.post.get_absolute_url() if kind == "comment" else target.get_absolute_url()
    )
    html = shown.content.decode()
    assert f"Thanks for the report. A moderator will look at this {kind}." in html
    assert "data-reported" in html


@pytest.mark.django_db
def test_a_member_reports_each_thing_once(content):
    ada, post = content["ada"], content["post"]
    client = signed_in(ada)
    client.post(report_url("post", post.pk), {"reason": "spam"})
    page = client.get(report_url("post", post.pk)).content.decode()
    assert "You&#x27;ve already reported this post." in page and "data-report-form" not in page
    again = client.post(report_url("post", post.pk), {"reason": "off_topic"}, follow=True)
    assert "You&#x27;ve already reported this post." in again.content.decode()
    assert Report.objects.count() == 1 and Report.objects.get().reason == "spam"
    with pytest.raises(services.AlreadyReported):
        services.report_content(ada, post, reason="abuse")
    # Another member may still report it, and Ada may report something else.
    services.report_content(make_member("linus"), post, reason="spam")
    services.report_content(ada, content["comment"], reason="spam")
    assert Report.objects.count() == 3


@pytest.mark.django_db
def test_the_database_refuses_a_second_abuse_report_by_the_same_member(content):
    ada, post = content["ada"], content["post"]
    Report.objects.create(reporter=ada, reason="spam", target=post)
    with pytest.raises(IntegrityError), transaction.atomic():
        Report.objects.create(reporter=ada, reason="off_topic", target=post)
    # The rule is for abuse reports: feedback (Phase 14) isn't limited to one.
    Report.objects.create(reporter=ada, kind="feedback", reason="other", target=post)
    Report.objects.create(reporter=ada, kind="feedback", reason="other", target=post)
    assert Report.objects.count() == 3


@pytest.mark.django_db(transaction=True)
def test_simultaneous_duplicate_reports_give_one_report_and_no_error():
    grace, ada = make_member("grace"), make_member("ada")
    post = ForumPost.objects.create(author=grace, title="Spam", body="Spam")
    barrier = threading.Barrier(6)
    results: list[object] = [None] * 6

    def attempt(index: int) -> None:
        try:
            barrier.wait()
            results[index] = services.report_content(ada, post, reason="spam")
        except Exception as error:  # noqa: BLE001 (the result under test)
            results[index] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=[i]) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(isinstance(r, Report) for r in results) == 1, results
    assert sum(isinstance(r, services.AlreadyReported) for r in results) == 5, results
    assert Report.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, field, message",
    [
        ({}, "reason", "Choose what&#x27;s wrong."),
        ({"reason": "lies"}, "reason", "Choose what&#x27;s wrong."),
        (
            {"reason": "other"},
            "details",
            "Say what&#x27;s wrong, since you chose “Something else”.",
        ),
        ({"reason": "other", "details": "   "}, "details", "Say what&#x27;s wrong"),
        (
            {"reason": "spam", "details": "x" * 1001},
            "details",
            "Keep the details to 1000 characters (it has 1001).",
        ),
    ],
)
def test_invalid_reports_are_refused_with_a_clear_message(content, data, field, message):
    response = signed_in(content["ada"]).post(report_url("post", content["post"].pk), data)
    assert response.status_code == 200 and message in response.content.decode()
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_the_service_validates_what_it_writes(content):
    with pytest.raises(ValidationError):
        services.report_content(content["ada"], content["post"], reason="lies")
    with pytest.raises(ValidationError):
        services.report_content(content["ada"], content["post"], reason="spam", details="x" * 1001)
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_members_cant_report_their_own_content_and_get_a_404(content):
    grace = content["grace"]
    client = signed_in(grace)
    for kind in ["post", "comment"]:
        url = report_url(kind, content[kind].pk)
        assert client.get(url).status_code == 404
        assert client.post(url, {"reason": "spam"}).status_code == 404
        with pytest.raises(PermissionDenied):
            services.report_content(grace, content[kind], reason="spam")
    html = client.get(content["post"].get_absolute_url()).content.decode()
    assert "data-report" not in html
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_unknown_kinds_and_missing_content_are_a_404(content):
    client = signed_in(content["ada"])
    for url in [
        report_url("user", content["grace"].pk),
        report_url("Post", content["post"].pk),
        report_url("post", 999),
        report_url("comment", 999),
    ]:
        assert client.get(url).status_code == 404, url
        assert client.post(url, {"reason": "spam"}).status_code == 404, url
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_a_visitor_is_sent_to_sign_in_to_report(client, content):
    url = report_url("post", content["post"].pk)
    response = client.get(url)
    assert response["Location"].startswith(reverse("account_login"))
    assert client.post(url, {"reason": "spam"})["Location"].startswith(reverse("account_login"))
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_report_links_show_for_other_members_only(client, content):
    post, comment = content["post"], content["comment"]
    other = signed_in(content["ada"]).get(post.get_absolute_url()).content.decode()
    assert f'href="{report_url("post", post.pk)}"' in other
    assert f'href="{report_url("comment", comment.pk)}"' in other
    for viewer in [client, signed_in(content["grace"])]:
        html = viewer.get(post.get_absolute_url()).content.decode()
        assert "/reports/" not in html


@pytest.mark.django_db
def test_reports_go_with_their_target_and_stay_when_the_reporter_leaves(content):
    ada, post, comment = content["ada"], content["post"], content["comment"]
    services.report_content(ada, comment, reason="spam")
    services.report_content(make_member("linus"), post, reason="spam")
    comment.delete()
    assert list(Report.objects.values_list("object_id", flat=True)) == [post.pk]
    linus_report = Report.objects.get()
    User.objects.get(username="linus").delete()
    linus_report.refresh_from_db()
    assert linus_report.reporter is None and linus_report.target == post
    post.delete()
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_reported_ids_find_only_the_members_own_abuse_reports(content):
    ada, comment = content["ada"], content["comment"]
    assert services.reported_ids(ada, Comment, [comment.pk]) == set()
    services.report_content(ada, comment, reason="spam")
    assert services.reported_ids(ada, Comment, [comment.pk]) == {comment.pk}
    assert services.reported_ids(content["grace"], Comment, [comment.pk]) == set()
    assert services.reported_ids(ada, ForumPost, [comment.pk]) == set()
    assert Report.objects.get().content_type == ContentType.objects.get_for_model(Comment)


@pytest.mark.django_db
def test_the_report_page_escapes_what_it_shows(content):
    post = content["post"]
    ForumPost.objects.filter(pk=post.pk).update(title="<script>alert(1)</script>")
    html = signed_in(content["ada"]).get(report_url("post", post.pk)).content.decode()
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html


@pytest.mark.django_db
def test_the_admin_shows_reports_read_only(admin_client, content):
    report = services.report_content(content["ada"], content["post"], reason="spam")
    assert admin_client.get(reverse("admin:reports_report_changelist")).status_code == 200
    change = reverse("admin:reports_report_change", args=[report.pk])
    assert admin_client.get(change).status_code == 200
    admin_client.post(change, {"reason": "other"})
    report.refresh_from_db()
    assert report.reason == "spam"
    assert admin_client.get(reverse("admin:reports_report_add")).status_code == 403
