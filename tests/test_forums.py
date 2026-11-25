"""Forums (Phase 12A): reading posts, writing them (verified members), and editing and
deleting them (their author only; everyone else a 404), with and without HTMX."""

import re

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse

from accounts.access import EmailNotVerified
from forums import services, strings
from forums.models import ForumPost

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


def snapshot(post: ForumPost) -> tuple:
    post.refresh_from_db()
    return post.title, post.body, post.edited_at


# ---------- Reading ----------


@pytest.mark.django_db
def test_anyone_reads_the_list_newest_first_and_each_post(client):
    ada = make_member()
    first = make_post(ada, title="First")
    second = make_post(ada, title="Second")
    html = client.get(reverse("forums:list")).content.decode()
    assert html.index("Second") < html.index("First")
    assert f'href="{first.get_absolute_url()}"' in html
    assert f'href="{reverse("account_login")}?next={reverse("forums:create")}"' in html
    assert "data-new-post" not in html
    page = client.get(second.get_absolute_url())
    assert page.status_code == 200
    body = page.content.decode()
    assert "Second" in body and ada.username in body
    # A visitor sees no controls.
    assert "data-edit" not in body and "data-delete" not in body


@pytest.mark.django_db
def test_the_empty_list_invites_the_first_post(client):
    client.force_login(make_member())
    html = client.get(reverse("forums:list")).content.decode()
    assert "data-empty" in html and strings.EMPTY_TITLE in html and "data-new-post" in html


@pytest.mark.django_db
def test_an_unknown_post_is_a_404(client):
    assert client.get(reverse("forums:detail", args=[999])).status_code == 404


@pytest.mark.django_db
def test_posts_are_escaped_and_keep_their_line_breaks(client):
    post = make_post(make_member(), title="<b>Bold</b>", body="<script>x</script>\nline two")
    html = client.get(post.get_absolute_url()).content.decode()
    assert "<script>x</script>" not in html and "&lt;script&gt;x&lt;/script&gt;<br>line two" in html
    assert "&lt;b&gt;Bold&lt;/b&gt;" in html
    listing = client.get(reverse("forums:list")).content.decode()
    assert "<script>x</script>" not in listing and "&lt;b&gt;Bold&lt;/b&gt;" in listing


# ---------- Creating ----------


@pytest.mark.django_db
def test_a_verified_member_publishes_a_post():
    ada = make_member()
    client = signed_in(ada)
    assert client.get(reverse("forums:create")).status_code == 200
    response = client.post(
        reverse("forums:create"), {"title": "  Terrain tips  ", "body": "Raise, then smooth."}
    )
    post = ForumPost.objects.get()
    assert response.status_code == 302 and response["Location"] == post.get_absolute_url()
    assert (post.author, post.title, post.body, post.edited_at) == (
        ada,
        "Terrain tips",
        "Raise, then smooth.",
        None,
    )
    page = client.get(post.get_absolute_url()).content.decode()
    assert strings.CREATED in page


@pytest.mark.django_db
def test_a_visitor_is_sent_to_sign_in_to_post(client):
    for method in ("get", "post"):
        response = getattr(client, method)(reverse("forums:create"), {"title": "t", "body": "b"})
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("account_login"))
    assert not ForumPost.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, field, message",
    [
        ({"title": "", "body": "Text"}, "title", strings.TITLE_REQUIRED),
        ({"title": "   ", "body": "Text"}, "title", strings.TITLE_REQUIRED),
        ({"title": "Title", "body": ""}, "body", strings.BODY_REQUIRED),
        ({"title": "Title", "body": " \n\t "}, "body", strings.BODY_REQUIRED),
        (
            {"title": "x" * (ForumPost.TITLE_MAX + 1), "body": "Text"},
            "title",
            "Keep the title to 120 characters (it has 121).",
        ),
        (
            {"title": "Title", "body": "x" * (ForumPost.BODY_MAX + 1)},
            "body",
            "Keep the post to 10000 characters (it has 10001).",
        ),
    ],
)
def test_invalid_posts_are_refused_with_a_clear_message(data, field, message):
    client = signed_in(make_member())
    response = client.post(reverse("forums:create"), data)
    assert response.status_code == 200
    assert response.context["form"].errors[field] == [message]
    assert message in response.content.decode()
    assert not ForumPost.objects.exists()


@pytest.mark.django_db
def test_the_longest_title_and_body_are_accepted():
    client = signed_in(make_member())
    client.post(
        reverse("forums:create"),
        {"title": "x" * ForumPost.TITLE_MAX, "body": "y" * ForumPost.BODY_MAX},
    )
    assert ForumPost.objects.count() == 1


# ---------- The verification gate ----------


@pytest.mark.django_db
def test_an_unverified_member_cant_post_or_edit_but_can_delete_their_own():
    eve = make_member("eve", verified=False)
    own = make_post(eve)  # from before the address stopped being verified
    before = snapshot(own)
    client = signed_in(eve)
    verify = reverse("accounts:verify_email")
    for method, url, data in [
        ("get", reverse("forums:create"), {}),
        ("post", reverse("forums:create"), {"title": "New", "body": "Text"}),
        ("get", reverse("forums:edit", args=[own.pk]), {}),
        ("post", reverse("forums:edit", args=[own.pk]), {"title": "Changed", "body": "Text"}),
    ]:
        response = getattr(client, method)(url, data)
        assert response.status_code == 302 and response["Location"].startswith(verify), url
        # Through HTMX, the browser is told to load the verify page in full.
        response = getattr(client, method)(url, data, headers=HTMX)
        assert response.status_code == 200 and response["HX-Redirect"].startswith(verify), url
    assert ForumPost.objects.count() == 1 and snapshot(own) == before
    # Deleting their own post never waits for verification.
    response = client.post(reverse("forums:delete", args=[own.pk]))
    assert response.status_code == 302 and not ForumPost.objects.exists()


@pytest.mark.django_db
def test_the_services_hold_the_gate_whichever_way_a_post_arrives():
    eve = make_member("eve", verified=False)
    with pytest.raises(EmailNotVerified):
        services.create_post(eve, title="t", body="b")
    own = make_post(eve)
    with pytest.raises(EmailNotVerified):
        services.edit_post(eve, own, title="t", body="b")
    assert not ForumPost.objects.filter(title="t").exists()


@pytest.mark.django_db
def test_the_services_validate_what_they_write():
    ada = make_member()
    with pytest.raises(ValidationError):
        services.create_post(ada, title="x" * (ForumPost.TITLE_MAX + 1), body="b")
    post = make_post(ada)
    before = snapshot(post)
    with pytest.raises(ValidationError):
        services.edit_post(ada, post, title="", body="b")
    assert snapshot(post) == before


# ---------- Ownership: only the author edits or deletes ----------


def outsiders() -> dict[str, Client]:
    """Everyone who isn't the post's author: another verified member, an administrator
    (staff and superuser), and a signed-out visitor."""
    grace = make_member("grace")
    admin = make_member("root", is_staff=True, is_superuser=True)
    return {"another member": signed_in(grace), "an admin": signed_in(admin), "a visitor": Client()}


@pytest.mark.django_db
def test_nobody_but_the_author_can_edit_or_delete_a_post_and_each_gets_a_404():
    ada = make_member()
    post = make_post(ada)
    before = snapshot(post)
    edit, delete = reverse("forums:edit", args=[post.pk]), reverse("forums:delete", args=[post.pk])
    for who, client in outsiders().items():
        for headers in ({}, HTMX):
            for method, url, data in [
                ("get", edit, {}),
                ("post", edit, {"title": "Hijacked", "body": "Mine now"}),
                ("get", delete, {}),
                ("post", delete, {}),
            ]:
                response = getattr(client, method)(url, data, headers=headers)
                assert response.status_code == 404, (who, method, url, headers)
                assert "HX-Redirect" not in response, (who, url)
                # The same answer as for a post that doesn't exist: nothing is revealed.
                missing = url.replace(f"/{post.pk}/", "/999/")
                assert getattr(client, method)(missing, data, headers=headers).status_code == 404
        # Their own view of the post has no controls.
        html = client.get(post.get_absolute_url()).content.decode()
        assert "data-edit" not in html and "data-delete" not in html, who
    assert snapshot(post) == before and ForumPost.objects.count() == 1


@pytest.mark.django_db
def test_the_services_refuse_anyone_but_the_author():
    post = make_post(make_member())
    grace = make_member("grace")
    admin = make_member("root", is_staff=True, is_superuser=True)
    for user in (grace, admin):
        with pytest.raises(PermissionDenied):
            services.edit_post(user, post, title="t", body="b")
        with pytest.raises(PermissionDenied):
            services.delete_post(user, post)
    assert ForumPost.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_authored_by_finds_only_the_callers_posts():
    from django.contrib.auth.models import AnonymousUser

    ada, grace = make_member(), make_member("grace")
    mine, theirs = make_post(ada), make_post(grace)
    assert list(ForumPost.objects.authored_by(ada)) == [mine]
    assert list(ForumPost.objects.authored_by(grace)) == [theirs]
    assert not ForumPost.objects.authored_by(AnonymousUser()).exists()


# ---------- Editing and deleting without JavaScript ----------


@pytest.mark.django_db
def test_the_author_edits_through_the_full_page():
    ada = make_member()
    post = make_post(ada)
    client = signed_in(ada)
    page = client.get(reverse("forums:edit", args=[post.pk]))
    assert page.status_code == 200 and 'id="app-rail"' in page.content.decode()
    assert page.context["form"].initial == {"title": post.title, "body": post.body}
    response = client.post(
        reverse("forums:edit", args=[post.pk]), {"title": "Better title", "body": "More detail."}
    )
    assert response.status_code == 302 and response["Location"] == post.get_absolute_url()
    title, body, edited_at = snapshot(post)
    assert (title, body) == ("Better title", "More detail.") and edited_at is not None
    html = client.get(post.get_absolute_url()).content.decode()
    assert strings.SAVED in html and "data-edited" in html
    assert strings.EDITED in client.get(reverse("forums:list")).content.decode()


@pytest.mark.django_db
def test_an_invalid_edit_changes_nothing():
    ada = make_member()
    post = make_post(ada)
    before = snapshot(post)
    response = signed_in(ada).post(
        reverse("forums:edit", args=[post.pk]), {"title": "", "body": "x"}
    )
    assert response.status_code == 200 and strings.TITLE_REQUIRED in response.content.decode()
    assert snapshot(post) == before


@pytest.mark.django_db
def test_the_author_deletes_through_the_confirmation_page():
    ada = make_member()
    post = make_post(ada)
    client = signed_in(ada)
    page = client.get(reverse("forums:delete", args=[post.pk])).content.decode()
    assert strings.DELETE_TITLE in page and 'id="app-rail"' in page and "hx-post" not in page
    response = client.post(reverse("forums:delete", args=[post.pk]))
    assert response.status_code == 302 and response["Location"] == reverse("forums:list")
    assert not ForumPost.objects.exists()
    assert strings.DELETED in client.get(reverse("forums:list")).content.decode()


@pytest.mark.django_db
def test_the_authors_controls_are_links_that_also_work_without_javascript():
    ada = make_member()
    post = make_post(ada)
    html = signed_in(ada).get(post.get_absolute_url()).content.decode()
    edit, delete = reverse("forums:edit", args=[post.pk]), reverse("forums:delete", args=[post.pk])
    # Real links (followed without JavaScript), which htmx turns into in-place swaps of #post.
    assert re.search(
        rf'<a [^>]*href="{edit}" hx-get="{edit}" hx-target="#post" hx-swap="outerHTML"', html
    )
    assert re.search(
        rf'<a [^>]*href="{delete}" hx-get="{delete}" hx-target="#post" hx-swap="outerHTML"', html
    )
    assert 'id="post"' in html and "data-yours" in html
    # The live region the swaps announce through, empty until then.
    assert re.search(r'<div id="post-status" [^>]*role="status" aria-live="polite"></div>', html)


# ---------- Editing and deleting in place (HTMX) ----------


def is_fragment(html: str) -> bool:
    return 'id="app-rail"' not in html and "<html" not in html


@pytest.mark.django_db
def test_edit_swaps_the_post_for_its_form_with_the_title_focused():
    ada = make_member()
    post = make_post(ada)
    response = signed_in(ada).get(reverse("forums:edit", args=[post.pk]), headers=HTMX)
    html = response.content.decode()
    assert response.status_code == 200 and is_fragment(html)
    assert "HX-Request" in response["Vary"]
    assert re.search(r'<article id="post" [^>]*data-editing', html)
    edit = reverse("forums:edit", args=[post.pk])
    # A real form (method and action) that htmx posts, with its CSRF token.
    assert f'method="post" action="{edit}"' in html and f'hx-post="{edit}"' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert re.search(r'<input [^>]*name="title"[^>]*autofocus', html)
    assert 'value="How do I spawn a decal?"' in html
    assert re.search(r'<a [^>]*href="[^"]+" hx-get="[^"]+"[^>]*data-cancel', html)


@pytest.mark.django_db
def test_saving_swaps_back_the_post_announces_it_and_focuses_its_heading():
    ada = make_member()
    post = make_post(ada)
    response = signed_in(ada).post(
        reverse("forums:edit", args=[post.pk]),
        {"title": "Updated in place", "body": "New text"},
        headers=HTMX,
    )
    html = response.content.decode()
    assert response.status_code == 200 and is_fragment(html)
    assert "HX-Request" in response["Vary"]
    assert re.search(r'<h1 id="post-title"[^>]*tabindex="-1" autofocus>Updated in place</h1>', html)
    assert (
        f'<div hx-swap-oob="innerHTML:#post-status"><p class="app-message">{strings.SAVED}' in html
    )
    assert "data-edited" in html and "data-edit" in html
    assert snapshot(post)[:2] == ("Updated in place", "New text")


@pytest.mark.django_db
def test_an_invalid_edit_in_place_shows_the_form_again_with_the_field_to_fix_focused():
    ada = make_member()
    post = make_post(ada)
    before = snapshot(post)
    response = signed_in(ada).post(
        reverse("forums:edit", args=[post.pk]), {"title": "Kept", "body": ""}, headers=HTMX
    )
    html = response.content.decode()
    assert response.status_code == 200 and is_fragment(html) and "data-editing" in html
    assert strings.BODY_REQUIRED in html and 'role="alert"' in html
    body_field = re.search(r"<textarea [^>]*>", html)[0]
    assert 'aria-invalid="true"' in body_field and "autofocus" in body_field
    assert "autofocus" not in re.search(r'<input [^>]*name="title"[^>]*>', html)[0]
    assert 'value="Kept"' in html  # what they typed stays
    assert snapshot(post) == before


@pytest.mark.django_db
def test_cancel_swaps_back_the_post_unchanged_with_its_heading_focused():
    ada = make_member()
    post = make_post(ada)
    response = signed_in(ada).get(post.get_absolute_url(), headers=HTMX)
    html = response.content.decode()
    assert is_fragment(html) and "HX-Request" in response["Vary"]
    assert re.search(r'<h1 id="post-title"[^>]*autofocus>', html) and "hx-swap-oob" not in html
    # The full page never carries autofocus (nothing was swapped).
    assert "autofocus" not in signed_in(ada).get(post.get_absolute_url()).content.decode()


@pytest.mark.django_db
def test_delete_asks_in_place_then_leaves_a_notice_where_the_post_was():
    ada = make_member()
    post = make_post(ada)
    client = signed_in(ada)
    delete = reverse("forums:delete", args=[post.pk])
    response = client.get(delete, headers=HTMX)
    html = response.content.decode()
    assert is_fragment(html) and "data-confirming" in html and "HX-Request" in response["Vary"]
    assert re.search(r'<h2 id="delete-title"[^>]*tabindex="-1" autofocus>', html)
    assert f'method="post" action="{delete}"' in html and f'hx-post="{delete}"' in html
    assert 'name="csrfmiddlewaretoken"' in html and "data-keep" in html
    assert ForumPost.objects.exists()

    response = client.post(delete, headers=HTMX)
    html = response.content.decode()
    assert response.status_code == 200 and is_fragment(html)
    assert re.search(r'<section id="post" [^>]*data-deleted', html)
    assert re.search(r'<h2 id="deleted-title"[^>]*autofocus>Post deleted</h2>', html)
    assert "“How do I spawn a decal?” is gone." in html
    assert f'href="{reverse("forums:list")}"' in html
    assert not ForumPost.objects.exists()


# ---------- CSRF ----------


@pytest.mark.django_db
@pytest.mark.parametrize("htmx", [False, True])
def test_every_forum_post_without_a_csrf_token_is_refused(htmx):
    ada = make_member()
    post = make_post(ada)
    before = snapshot(post)
    client = Client(enforce_csrf_checks=True)
    client.force_login(ada)
    headers = HTMX if htmx else {}
    for url in [
        reverse("forums:list"),
        reverse("forums:create"),
        post.get_absolute_url(),
        reverse("forums:edit", args=[post.pk]),
        reverse("forums:delete", args=[post.pk]),
    ]:
        response = client.post(url, {"title": "Changed", "body": "Changed"}, headers=headers)
        assert response.status_code == 403, url
    assert snapshot(post) == before and ForumPost.objects.count() == 1


@pytest.mark.django_db
def test_an_htmx_post_with_the_forms_token_goes_through():
    ada = make_member()
    post = make_post(ada)
    client = Client(enforce_csrf_checks=True)
    client.force_login(ada)
    html = client.get(reverse("forums:edit", args=[post.pk]), headers=HTMX).content.decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)[1]
    response = client.post(
        reverse("forums:edit", args=[post.pk]),
        {"csrfmiddlewaretoken": token, "title": "With token", "body": "Fine"},
        headers=HTMX,
    )
    assert response.status_code == 200 and snapshot(post)[0] == "With token"


# ---------- The shell, the nav and the rest ----------


@pytest.mark.django_db
def test_forum_pages_sit_in_the_app_shell_under_forums_with_htmx_loaded():
    ada = make_member()
    post = make_post(ada)
    client = signed_in(ada)
    urls = [
        reverse("forums:list"),
        reverse("forums:create"),
        post.get_absolute_url(),
        reverse("forums:edit", args=[post.pk]),
        reverse("forums:delete", args=[post.pk]),
    ]
    for url in urls:
        html = client.get(url).content.decode()
        current = re.findall(r'aria-current="page">\s*<svg.*?</svg>\s*([^<]+?)\s*<', html, re.S)
        assert current == ["Forums"], url
        assert re.search(r'<script src="/static/django_htmx/htmx-2(\.min)?\.js', html), url
    detail = client.get(post.get_absolute_url()).content.decode()
    assert re.search(r'<script src="/static/js/forums\.js\?v=\d+" defer>', detail)


@pytest.mark.django_db
def test_the_marketing_nav_and_footer_link_to_the_forums(client):
    html = client.get(reverse("marketing:home")).content.decode()
    forums = reverse("forums:list")
    assert re.search(rf'<a href="{forums}"[^>]*>Community</a>', html)
    assert re.search(rf'<a href="{forums}"[^>]*>Forums</a>', html)


@pytest.mark.django_db
def test_a_members_posts_go_with_their_account():
    ada = make_member()
    make_post(ada)
    ada.delete()
    assert not ForumPost.objects.exists()


@pytest.mark.django_db
def test_the_admin_shows_posts_read_only(admin_client):
    post = make_post(make_member())
    assert admin_client.get(reverse("admin:forums_forumpost_changelist")).status_code == 200
    change = reverse("admin:forums_forumpost_change", args=[post.pk])
    assert admin_client.get(change).status_code == 200
    admin_client.post(change, {"title": "Changed by admin", "body": "x"})
    assert snapshot(post)[0] == "How do I spawn a decal?"
    assert admin_client.get(reverse("admin:forums_forumpost_add")).status_code == 403
