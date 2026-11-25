"""Forums (Phase 12B): comments, ratings, the posting limits and the moderation hooks
(hidden and removed content), with and without HTMX."""

import re
import threading
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.limits import LimitReached
from forums import services
from forums.models import Comment, ForumPost, Rating
from reports.models import Report
from reports.moderation import Visibility

User = get_user_model()
PASSWORD = "correct-horse-battery-staple-42"
HTMX = {"HX-Request": "true"}


def make_member(username="ada", *, verified: bool = True, **extra):
    email = f"{username}@example.com"
    user = User.objects.create_user(username, email, PASSWORD, **extra)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


def make_post(author, title="How do I spawn a decal?", body="When touched → Spawn decal."):
    return ForumPost.objects.create(author=author, title=title, body=body)


def signed_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def is_fragment(html: str) -> bool:
    """An HTMX answer: a part of the page, not a document."""
    return "<html" not in html and "<body" not in html


# ---------- TDD 1: time-windowed limits ----------


@pytest.mark.django_db
def test_a_sixth_comment_within_a_minute_is_refused_and_allowed_once_the_window_passes():
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    for i in range(5):
        services.add_comment(ada, post, body=f"Comment {i}")
    now = timezone.now()
    Comment.objects.filter(author=ada).update(created=now - timedelta(seconds=18))

    # Five in the last minute: the sixth is refused, saying when Ada may comment again,
    # and nothing is written.
    with pytest.raises(LimitReached) as refused:
        services.add_comment(ada, post, body="Sixth", now=now)
    assert str(refused.value) == (
        "You've posted 5 comments in the last minute. You can comment again in 42 seconds."
    )
    assert Comment.objects.filter(author=ada).count() == 5

    # Ada's comments don't hold anyone else back.
    services.add_comment(grace, post, body="Grace's first", now=now)

    # A second before her oldest comment leaves the window, she's still refused...
    oldest = Comment.objects.filter(author=ada).order_by("pk").first()
    Comment.objects.filter(pk=oldest.pk).update(created=now - timedelta(seconds=59))
    with pytest.raises(LimitReached) as refused:
        services.add_comment(ada, post, body="Sixth", now=now)
    assert str(refused.value).endswith("You can comment again in 1 second.")

    # ...and once it's a minute old, the next comment goes through.
    Comment.objects.filter(pk=oldest.pk).update(created=now - timedelta(seconds=60))
    services.add_comment(ada, post, body="Sixth", now=now)
    assert Comment.objects.filter(author=ada).count() == 6

    # That fills the window again: four from 18 seconds ago and the one just posted.
    with pytest.raises(LimitReached) as refused:
        services.add_comment(ada, post, body="Seventh", now=now)
    assert str(refused.value).endswith("You can comment again in 42 seconds.")


# ---------- TDD 2: hidden and removed content ----------


def set_state(obj, state: str) -> None:
    type(obj).objects.filter(pk=obj.pk).update(state=state)


@pytest.mark.django_db
def test_hidden_and_removed_content_is_invisible_to_all_but_staff_in_every_list_and_page():
    grace, ada, linus = make_member("grace"), make_member("ada"), make_member("linus")
    staff = make_member("sam", is_staff=True)
    shown = make_post(grace, title="Shown post")
    hidden = make_post(grace, title="Hidden post")
    removed = make_post(grace, title="Removed post")
    set_state(hidden, Visibility.HIDDEN)
    set_state(removed, Visibility.REMOVED)

    def comment(post, body, state=Visibility.VISIBLE):
        made = Comment.objects.create(post=post, author=ada, body=body)
        set_state(made, state)
        return made

    comment(shown, "Shown comment")
    hidden_comment = comment(shown, "Hidden comment", Visibility.HIDDEN)
    removed_comment = comment(shown, "Removed comment", Visibility.REMOVED)
    on_hidden_post = comment(hidden, "Comment on a hidden post")
    Rating.objects.create(post=hidden, user=linus, score=2)
    secrets = [
        "Hidden post",
        "Removed post",
        "Hidden comment",
        "Removed comment",
        "Comment on a hidden post",
    ]
    hidden_comments = [hidden_comment, removed_comment, on_hidden_post]
    # Every way to read or act on hidden content: each must be a 404.
    reads = [
        *(post.get_absolute_url() for post in (hidden, removed)),
        *(reverse(name, args=[hidden.pk]) for name in ("forums:edit", "forums:delete")),
        *(reverse("forums:comment", args=[c.pk]) for c in hidden_comments),
        *(reverse("forums:comment_delete", args=[c.pk]) for c in hidden_comments),
        reverse("reports:create", args=["post", hidden.pk]),
        *(reverse("reports:create", args=["comment", c.pk]) for c in hidden_comments),
    ]
    writes = [
        (reverse("forums:comment_create", args=[hidden.pk]), {"body": "Sneaky"}),
        (reverse("forums:rate", args=[hidden.pk]), {"score": "5"}),
        (reverse("forums:edit", args=[hidden.pk]), {"title": "Changed", "body": "Changed"}),
        (reverse("forums:delete", args=[hidden.pk]), {}),
        (reverse("forums:comment_delete", args=[hidden_comment.pk]), {}),
        (reverse("reports:create", args=["post", hidden.pk]), {"reason": "spam"}),
        (reverse("reports:create", args=["comment", hidden_comment.pk]), {"reason": "spam"}),
    ]
    before = (ForumPost.objects.count(), Comment.objects.count(), Rating.objects.count())

    viewers = {
        "a visitor": Client(),
        "another member": signed_in(linus),
        "the posts' author": signed_in(grace),
        "the comments' author": signed_in(ada),
    }
    for who, client in viewers.items():
        for headers in [{}, HTMX]:
            listing = client.get(reverse("forums:list"), headers=headers).content.decode()
            detail = client.get(shown.get_absolute_url(), headers=headers).content.decode()
            for html in (listing, detail):
                for secret in secrets:
                    assert secret not in html, (who, headers, secret)
            assert "Shown post" in listing and "1 comment<" in listing, who
            if not headers:
                assert "Shown comment" in detail and "1 comment<" in detail, who
            for url in reads:
                assert client.get(url, headers=headers).status_code == 404, (who, headers, url)
            for url, data in writes:
                response = client.post(url, data, headers=headers)
                assert response.status_code == 404, (who, headers, url)
    assert (ForumPost.objects.count(), Comment.objects.count(), Rating.objects.count()) == before
    assert not Report.objects.exists()

    # Staff see everything, marked with its state...
    sam = signed_in(staff)
    listing = sam.get(reverse("forums:list")).content.decode()
    detail = sam.get(shown.get_absolute_url()).content.decode()
    assert "Hidden post" in listing and "Removed post" in listing
    assert 'data-state="hidden"' in listing and 'data-state="removed"' in listing
    assert "Hidden comment" in detail and "Removed comment" in detail and "3 comments<" in detail
    hidden_page = sam.get(hidden.get_absolute_url())
    assert (
        hidden_page.status_code == 200
        and "Comment on a hidden post" in hidden_page.content.decode()
    )
    # ...but nobody, staff included, comments on, rates or reports what isn't visible.
    for url, data in writes[:2] + writes[5:]:
        assert sam.post(url, data).status_code == 404, url
    assert (ForumPost.objects.count(), Comment.objects.count(), Rating.objects.count()) == before


# ---------- The posting limits ----------


def at_once(attempts) -> list[object]:
    """Run each attempt from its own thread and database connection, all released together;
    each result is the return value or the exception raised."""
    barrier = threading.Barrier(len(attempts))
    results: list[object] = [None] * len(attempts)

    def run(index, attempt) -> None:
        try:
            barrier.wait()
            results[index] = attempt()
        except Exception as error:  # noqa: BLE001 (the result under test)
            results[index] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=pair) for pair in enumerate(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


@pytest.mark.django_db
def test_a_sixth_post_within_a_day_is_refused_with_when_to_post_again():
    ada, grace = make_member("ada"), make_member("grace")
    for i in range(5):
        services.create_post(ada, title=f"Post {i}", body="Text")
    now = timezone.now()
    ForumPost.objects.filter(author=ada).update(created=now - timedelta(hours=20, minutes=48))
    # Hidden posts count too: hiding a spammer's posts doesn't free their quota.
    set_state(ForumPost.objects.filter(author=ada).first(), Visibility.HIDDEN)
    with pytest.raises(LimitReached) as refused:
        services.create_post(ada, title="Sixth", body="Text", now=now)
    assert str(refused.value) == (
        "You've published 5 posts in the last 24 hours. You can post again in 3 hours, 12 minutes."
    )
    assert ForumPost.objects.filter(author=ada).count() == 5
    services.create_post(grace, title="Grace's", body="Text", now=now)
    # A day after the oldest, the next goes through.
    ForumPost.objects.filter(author=ada).update(created=now - timedelta(days=1))
    services.create_post(ada, title="Sixth", body="Text", now=now)


@pytest.mark.django_db
def test_the_new_post_page_shows_the_limit_and_keeps_the_draft():
    ada = make_member()
    for i in range(5):
        make_post(ada, title=f"Post {i}")
    response = signed_in(ada).post(
        reverse("forums:create"), {"title": "My draft", "body": "Draft text"}
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "You&#x27;ve published 5 posts in the last 24 hours." in html
    assert 'role="alert"' in html and 'value="My draft"' in html and "Draft text" in html
    assert ForumPost.objects.count() == 5


@pytest.mark.django_db(transaction=True)
def test_simultaneous_comments_from_one_member_cant_slip_past_the_limit():
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    services.add_comment(ada, post, body="First")
    results = at_once(
        [lambda i=i: services.add_comment(ada, post, body=f"At once {i}") for i in range(8)]
    )
    made = [r for r in results if isinstance(r, Comment)]
    refused = [r for r in results if isinstance(r, LimitReached)]
    assert (len(made), len(refused)) == (4, 4), results
    assert Comment.objects.filter(author=ada).count() == 5


@pytest.mark.django_db(transaction=True)
def test_simultaneous_posts_from_one_member_cant_slip_past_the_limit():
    ada = make_member()
    results = at_once(
        [lambda i=i: services.create_post(ada, title=f"P{i}", body="Text") for i in range(8)]
    )
    assert sum(isinstance(r, ForumPost) for r in results) == 5, results
    assert sum(isinstance(r, LimitReached) for r in results) == 3, results
    assert ForumPost.objects.filter(author=ada).count() == 5


def test_next_allowed_counts_only_the_window_and_waits_are_worded():
    from accounts.limits import wait_words

    now = timezone.now()
    assert wait_words(now + timedelta(seconds=1), now) == "1 second"
    assert wait_words(now + timedelta(seconds=0.2), now) == "1 second"
    assert wait_words(now + timedelta(seconds=59), now) == "59 seconds"
    assert wait_words(now + timedelta(minutes=1), now) == "1 minute"
    assert wait_words(now + timedelta(hours=3, minutes=12), now) == "3 hours, 12 minutes"


# ---------- Comments ----------


@pytest.mark.django_db
def test_the_services_refuse_over_long_bodies_whichever_way_they_arrive():
    ada = make_member()
    with pytest.raises(ValidationError):
        services.create_post(ada, title="t", body="x" * (ForumPost.BODY_MAX + 1))
    post = make_post(ada)
    with pytest.raises(ValidationError):
        services.edit_post(ada, post, title="t", body="x" * (ForumPost.BODY_MAX + 1))
    with pytest.raises(ValidationError):
        services.add_comment(ada, post, body="x" * (Comment.BODY_MAX + 1))
    with pytest.raises(ValidationError):
        services.add_comment(ada, post, body="")
    services.add_comment(ada, post, body="x" * Comment.BODY_MAX)
    assert ForumPost.objects.count() == 1 and Comment.objects.count() == 1


@pytest.mark.django_db
def test_a_member_comments_through_the_page_and_lands_on_their_comment():
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    response = signed_in(ada).post(
        reverse("forums:comment_create", args=[post.pk]), {"body": "  Use <b>Touched</b>.  "}
    )
    comment = Comment.objects.get()
    assert (comment.author, comment.post, comment.body) == (ada, post, "Use <b>Touched</b>.")
    assert response.status_code == 302
    assert response["Location"] == f"{post.get_absolute_url()}#comment-{comment.pk}"
    html = Client().get(post.get_absolute_url()).content.decode()
    assert "Use &lt;b&gt;Touched&lt;/b&gt;." in html and f'id="comment-{comment.pk}"' in html
    assert "1 comment<" in html


@pytest.mark.django_db
def test_comments_show_oldest_first_and_the_list_counts_them(client):
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    Comment.objects.create(post=post, author=ada, body="Earlier")
    Comment.objects.create(post=post, author=grace, body="Later")
    html = client.get(post.get_absolute_url()).content.decode()
    assert html.index("Earlier") < html.index("Later") and "2 comments<" in html
    assert "2 comments<" in client.get(reverse("forums:list")).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body, message",
    [
        ("", "Write something in the comment."),
        ("   ", "Write something in the comment."),
        ("x" * (Comment.BODY_MAX + 1), "Keep the comment to 2000 characters (it has 2001)."),
    ],
)
def test_invalid_comments_are_refused_with_a_clear_message(body, message):
    ada = make_member()
    post = make_post(ada)
    url = reverse("forums:comment_create", args=[post.pk])
    page = signed_in(ada).post(url, {"body": body})
    assert page.status_code == 200 and message in page.content.decode()
    swap = signed_in(ada).post(url, {"body": body}, headers=HTMX).content.decode()
    assert message in swap and 'aria-invalid="true"' in swap and "autofocus" in swap
    assert not Comment.objects.exists()


@pytest.mark.django_db
def test_commenting_in_place_swaps_the_comments_focuses_the_new_one_and_announces_it():
    ada = make_member()
    post = make_post(ada)
    response = signed_in(ada).post(
        reverse("forums:comment_create", args=[post.pk]), {"body": "Mine"}, headers=HTMX
    )
    html = response.content.decode()
    comment = Comment.objects.get()
    assert is_fragment(html) and 'id="comments"' in html
    assert re.search(rf'id="comment-{comment.pk}"[^>]*autofocus', html)
    assert 'hx-swap-oob="innerHTML:#post-status"' in html and "Your comment is posted." in html
    assert "HX-Request" in response["Vary"]


@pytest.mark.django_db
def test_the_comment_limit_shows_in_the_form_in_place():
    ada = make_member()
    post = make_post(ada)
    for i in range(5):
        services.add_comment(ada, post, body=f"C{i}")
    html = (
        signed_in(ada)
        .post(reverse("forums:comment_create", args=[post.pk]), {"body": "Sixth"}, headers=HTMX)
        .content.decode()
    )
    assert "You&#x27;ve posted 5 comments in the last minute." in html
    assert 'role="alert"' in html and re.search(r">\s*Sixth</textarea>", html)
    assert Comment.objects.count() == 5


@pytest.mark.django_db
def test_visitors_are_asked_to_sign_in_to_comment_and_rate(client):
    post = make_post(make_member())
    html = client.get(post.get_absolute_url()).content.decode()
    assert "data-sign-in-to-comment" in html and "data-sign-in-to-rate" in html
    assert "data-comment-form" not in html and "data-star" not in html and "data-report" not in html
    response = client.post(reverse("forums:comment_create", args=[post.pk]), {"body": "Hi"})
    assert response["Location"].startswith(reverse("account_login"))
    response = client.post(
        reverse("forums:comment_create", args=[post.pk]), {"body": "Hi"}, headers=HTMX
    )
    assert response["HX-Redirect"].startswith(reverse("account_login"))
    assert not Comment.objects.exists()


@pytest.mark.django_db
def test_an_unverified_member_cant_comment_rate_or_report():
    from accounts.access import EmailNotVerified

    grace, newbie = make_member("grace"), make_member("newbie", verified=False)
    post = make_post(grace)
    comment = Comment.objects.create(post=post, author=grace, body="Hello")
    client = signed_in(newbie)
    for url, data in [
        (reverse("forums:comment_create", args=[post.pk]), {"body": "Hi"}),
        (reverse("forums:rate", args=[post.pk]), {"score": "4"}),
        (reverse("reports:create", args=["post", post.pk]), {"reason": "spam"}),
        (reverse("reports:create", args=["comment", comment.pk]), {"reason": "spam"}),
    ]:
        response = client.post(url, data)
        assert response["Location"].startswith(reverse("accounts:verify_email")), url
        if url.startswith("/forums/"):  # the report form is a page of its own, never HTMX
            swap = client.post(url, data, headers=HTMX)
            assert swap["HX-Redirect"].startswith(reverse("accounts:verify_email")), url
    from reports import services as reporting

    with pytest.raises(EmailNotVerified):
        services.add_comment(newbie, post, body="Hi")
    with pytest.raises(EmailNotVerified):
        services.rate_post(newbie, post, 4)
    with pytest.raises(EmailNotVerified):
        reporting.report_content(newbie, post, reason="spam")
    assert (Comment.objects.count(), Rating.objects.count(), Report.objects.count()) == (1, 0, 0)


@pytest.mark.django_db
def test_only_a_comments_author_deletes_it_and_everyone_else_gets_a_404():
    ada, grace, staff = make_member("ada"), make_member("grace"), make_member("sam", is_staff=True)
    post = make_post(grace)  # Grace wrote the post, not the comment
    comment = Comment.objects.create(post=post, author=ada, body="Ada's")
    url = reverse("forums:comment_delete", args=[comment.pk])
    for client in [Client(), signed_in(grace), signed_in(staff)]:
        for headers in [{}, HTMX]:
            assert client.get(url, headers=headers).status_code == 404
            assert client.post(url, headers=headers).status_code == 404
    assert Comment.objects.filter(pk=comment.pk).exists()
    with pytest.raises(PermissionDenied):
        services.delete_comment(grace, comment)


@pytest.mark.django_db
def test_the_author_deletes_a_comment_through_the_confirmation_page():
    ada = make_member()
    post = make_post(ada)
    comment = Comment.objects.create(post=post, author=ada, body="Ada's")
    client = signed_in(ada)
    page = client.get(reverse("forums:comment_delete", args=[comment.pk])).content.decode()
    assert "Delete this comment?" in page and "Ada&#x27;s" in page
    response = client.post(reverse("forums:comment_delete", args=[comment.pk]))
    assert response["Location"] == f"{post.get_absolute_url()}#comments"
    assert not Comment.objects.exists()


@pytest.mark.django_db
def test_deleting_a_comment_in_place_asks_then_swaps_the_comments_without_it():
    ada = make_member()
    post = make_post(ada)
    comment = Comment.objects.create(post=post, author=ada, body="Ada's")
    client = signed_in(ada)
    url = reverse("forums:comment_delete", args=[comment.pk])
    ask = client.get(url, headers=HTMX).content.decode()
    assert is_fragment(ask) and f'id="comment-{comment.pk}"' in ask and "data-confirming" in ask
    assert re.search(r"<h3[^>]*autofocus[^>]*>Delete this comment\?", ask)
    keep = client.get(reverse("forums:comment", args=[comment.pk]), headers=HTMX).content.decode()
    assert is_fragment(keep) and re.search(rf'id="comment-{comment.pk}"[^>]*autofocus', keep)
    plain = client.get(reverse("forums:comment", args=[comment.pk]))
    assert plain["Location"] == comment.get_absolute_url()
    done = client.post(url, headers=HTMX).content.decode()
    assert is_fragment(done) and 'id="comments"' in done and "Ada&#x27;s" not in done
    assert re.search(r'id="comments-title"[^>]*autofocus', done)
    assert "Your comment was deleted." in done and "0 comments<" in done


@pytest.mark.django_db
def test_deleting_a_post_in_place_removes_its_comments_too():
    ada = make_member()
    post = make_post(ada)
    Comment.objects.create(post=post, author=ada, body="Ada's")
    html = signed_in(ada).post(reverse("forums:delete", args=[post.pk]), headers=HTMX)
    assert '<div id="comments" hx-swap-oob="delete"></div>' in html.content.decode()
    assert not Comment.objects.exists()


@pytest.mark.django_db
def test_a_members_comments_and_ratings_go_with_their_account():
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    Comment.objects.create(post=post, author=ada, body="Ada's")
    Rating.objects.create(post=post, user=ada, score=4)
    ada.delete()
    assert not Comment.objects.exists() and not Rating.objects.exists()


# ---------- Ratings ----------


@pytest.mark.django_db
def test_one_rating_per_member_per_post_changeable_not_stackable():
    ada, grace, linus = make_member("ada"), make_member("grace"), make_member("linus")
    post = make_post(grace)
    services.rate_post(ada, post, 2)
    services.rate_post(ada, post, 5)
    assert list(Rating.objects.values_list("user__username", "score")) == [("ada", 5)]
    services.rate_post(linus, post, 4)
    stats = ForumPost.objects.with_stats(ada).get()
    assert (stats.rating_count, stats.rating_average) == (2, 4.5)
    services.clear_rating(ada, post)
    assert list(Rating.objects.values_list("user__username", flat=True)) == ["linus"]
    # The database holds the rule whatever the way in.
    with pytest.raises(IntegrityError), transaction.atomic():
        Rating.objects.create(post=post, user=linus, score=1)


@pytest.mark.django_db
def test_scores_outside_one_to_five_are_refused():
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    for score in [0, 6, -1, "3", 2.5]:
        with pytest.raises(ValidationError):
            services.rate_post(ada, post, score)
    with pytest.raises(IntegrityError), transaction.atomic():
        Rating.objects.create(post=post, user=ada, score=6)
    client = signed_in(ada)
    for raw in ["0", "6", "10", "x", "", "٣"]:
        html = client.post(reverse("forums:rate", args=[post.pk]), {"score": raw}, headers=HTMX)
        assert "Choose from 1 to 5 stars." in html.content.decode(), raw
    assert not Rating.objects.exists()


@pytest.mark.django_db
def test_authors_cant_rate_their_own_posts():
    grace = make_member("grace")
    post = make_post(grace)
    with pytest.raises(services.RatingRefused):
        services.rate_post(grace, post, 5)
    client = signed_in(grace)
    html = client.get(post.get_absolute_url()).content.decode()
    assert "data-own-post" in html and "data-star" not in html
    swap = client.post(reverse("forums:rate", args=[post.pk]), {"score": "5"}, headers=HTMX)
    assert "You can&#x27;t rate your own post." in swap.content.decode()
    page = client.post(reverse("forums:rate", args=[post.pk]), {"score": "5"})
    assert page["Location"] == f"{post.get_absolute_url()}#rating"
    assert not Rating.objects.exists()


@pytest.mark.django_db
def test_rating_in_place_shows_the_average_to_one_decimal_and_the_members_own():
    ada, grace, linus, kay = (make_member(n) for n in ("ada", "grace", "linus", "kay"))
    post = make_post(grace)
    services.rate_post(linus, post, 4)
    services.rate_post(kay, post, 5)
    client = signed_in(ada)
    response = client.post(reverse("forums:rate", args=[post.pk]), {"score": "5"}, headers=HTMX)
    html = response.content.decode()
    assert is_fragment(html) and 'id="rating"' in html
    assert "<strong>4.7 out of 5</strong>" in html and "3 ratings" in html
    assert "You rated it 5 out of 5." in html and "Your rating is saved." in html
    assert re.search(r'data-star="5"', html)
    assert re.search(r'aria-pressed="true" autofocus data-star="5"', html)
    assert html.count("fm-star fm-star-on") == 5
    cleared = client.post(reverse("forums:rate", args=[post.pk]), {"score": "clear"}, headers=HTMX)
    html = cleared.content.decode()
    assert "<strong>4.5 out of 5</strong>" in html and "2 ratings" in html
    assert "Your rating is cleared." in html and "data-my-rating" not in html
    # A whole number keeps its decimal; no ratings says so.
    services.clear_rating(kay, post)
    page = Client().get(post.get_absolute_url()).content.decode()
    assert "<strong>4.0 out of 5</strong>" in page and "1 rating<" in page
    services.clear_rating(linus, post)
    assert "No ratings yet" in Client().get(post.get_absolute_url()).content.decode()


@pytest.mark.django_db
def test_rating_without_javascript_redirects_back_to_the_rating():
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    response = signed_in(ada).post(reverse("forums:rate", args=[post.pk]), {"score": "3"})
    assert response["Location"] == f"{post.get_absolute_url()}#rating"
    assert Rating.objects.get().score == 3


@pytest.mark.django_db
def test_the_list_shows_each_posts_average_rating():
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    services.rate_post(ada, post, 4)
    html = Client().get(reverse("forums:list")).content.decode()
    assert "4.0</span>" in html and '<span class="sr-only">4.0 out of 5</span>' in html


# ---------- CSRF, the shell and the admin ----------


@pytest.mark.django_db
@pytest.mark.parametrize("htmx", [False, True])
def test_every_comment_rating_and_report_post_without_a_csrf_token_is_refused(htmx):
    ada, grace = make_member("ada"), make_member("grace")
    post = make_post(grace)
    comment = Comment.objects.create(post=post, author=ada, body="Ada's")
    client = Client(enforce_csrf_checks=True)
    client.force_login(ada)
    headers = HTMX if htmx else {}
    for url, data in [
        (reverse("forums:comment_create", args=[post.pk]), {"body": "Hi"}),
        (reverse("forums:comment_delete", args=[comment.pk]), {}),
        (reverse("forums:rate", args=[post.pk]), {"score": "4"}),
        (reverse("reports:create", args=["post", post.pk]), {"reason": "spam"}),
    ]:
        assert client.post(url, data, headers=headers).status_code == 403, url
    assert (Comment.objects.count(), Rating.objects.count(), Report.objects.count()) == (1, 0, 0)


@pytest.mark.django_db
def test_the_admin_shows_comments_read_only(admin_client):
    ada = make_member()
    comment = Comment.objects.create(post=make_post(ada), author=ada, body="Ada's")
    assert admin_client.get(reverse("admin:forums_comment_changelist")).status_code == 200
    change = reverse("admin:forums_comment_change", args=[comment.pk])
    assert admin_client.get(change).status_code == 200
    admin_client.post(change, {"body": "Changed by admin"})
    comment.refresh_from_db()
    assert comment.body == "Ada's"
    assert admin_client.get(reverse("admin:forums_comment_add")).status_code == 403
