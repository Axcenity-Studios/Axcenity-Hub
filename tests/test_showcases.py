"""Showcases: publishing (the page, validation, the stored images), the one-a-day limit, the
verification gate, only the author editing or deleting (everyone else a 404), slugs, tags,
likes, moderation states, reporting, files leaving with their showcase, CSRF, the admin."""

import re
import threading
from datetime import timedelta
from io import BytesIO

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from PIL import Image

from accounts.access import EmailNotVerified
from accounts.limits import LimitReached
from reports.models import Report
from reports.moderation import Visibility
from showcases import images, services, strings
from showcases.models import Like, Showcase, Tag

User = get_user_model()
PASSWORD = "pw-correct-horse-42"
HTMX = {"HX-Request": "true"}


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def make_member(username="ada", *, verified: bool = True, **extra):
    email = f"{username}@example.com"
    user = User.objects.create_user(username, email, PASSWORD, **extra)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


def signed_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def image_bytes(size=(1280, 720), kind="PNG", mode="RGB", color="#3366aa", **save) -> bytes:
    out = BytesIO()
    Image.new(mode, size, color).save(out, kind, **save)
    return out.getvalue()


def image_file(size=(1280, 720), kind="PNG", name="shot.png", **kwargs) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name, image_bytes(size, kind, **kwargs), content_type=f"image/{kind.lower()}"
    )


def processed(size=(640, 360)) -> images.Processed:
    return images.process(image_file(size))


def make_showcase(author, title="A lit hall", *, tags=(), ago=timedelta(days=2), **fields):
    """A showcase by `author`, backdated by `ago` so the daily limit leaves room for more."""
    showcase = services.create_showcase(
        author,
        title=title,
        description=fields.pop("description", "Ray-traced reflections on a graybox hall."),
        image=processed(),
        tags=list(tags),
        **fields,
    )
    Showcase.objects.filter(pk=showcase.pk).update(created=timezone.now() - ago)
    showcase.refresh_from_db()
    return showcase


def stored(media) -> list[str]:
    folder = media / "showcases"
    return (
        sorted(str(p.relative_to(media)) for p in folder.rglob("*.webp")) if folder.exists() else []
    )


def form_data(**fields) -> dict:
    data = {
        "title": "Terrain at dusk",
        "description": "Hills sculpted with the terrain tools, then foliage scattered on them.",
        "image_alt": "",
        "tags": "terrain, foliage",
        "image": image_file(),
    }
    data.update(fields)
    return {k: v for k, v in data.items() if v is not None}


def errors(response) -> str:
    return response.content.decode()


# ---------- Publishing ----------


@pytest.mark.django_db
def test_a_member_publishes_a_showcase_and_it_is_shown(media):
    ada = make_member()
    client = signed_in(ada)
    response = client.post(reverse("showcases:create"), form_data(image_alt="Green hills"))
    showcase = Showcase.objects.get()
    assert response.status_code == 302 and response["Location"] == showcase.get_absolute_url()
    assert showcase.slug == "terrain-at-dusk" and showcase.author == ada
    assert [t.name for t in showcase.tags.order_by("name")] == ["foliage", "terrain"]
    assert stored(media) == sorted([showcase.image.name, showcase.card.name])
    page = client.get(response["Location"])
    html = page.content.decode()
    assert strings.CREATED in html and "Terrain at dusk" in html
    assert f'src="{showcase.image.url}"' in html and 'alt="Green hills"' in html
    assert f'width="{showcase.image_width}" height="{showcase.image_height}"' in html
    assert f'href="{reverse("showcases:list")}?tag=terrain"' in html
    assert "data-yours" in html and "data-edit" in html and "data-delete" in html


@pytest.mark.django_db
def test_the_publish_page_is_a_multipart_form_with_the_rules_said():
    html = signed_in(make_member()).get(reverse("showcases:create")).content.decode()
    assert 'enctype="multipart/form-data"' in html
    assert 'accept="image/png,image/jpeg,image/webp"' in html
    assert strings.CREATE_LEDE in html and "data-limit" not in html


def test_the_stored_images_are_the_hubs_own_webps_scaled_down_never_up():
    for size, display, card in [
        ((3000, 1500), (1920, 960), (800, 400)),
        ((1000, 4000), (480, 1920), (200, 800)),
        ((640, 360), (640, 360), (640, 360)),  # small: kept at its size, never enlarged
    ]:
        made = images.process(image_file(size))
        for content, expected in [(made.display, display), (made.card, card)]:
            with Image.open(BytesIO(content.read())) as image:
                assert (image.format, image.size) == ("WEBP", expected), size


@pytest.mark.django_db
def test_the_stored_image_is_upright_and_carries_none_of_the_uploads_metadata():
    exif = Image.Exif()
    exif[0x010F] = "Secret Camera Co"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90 degrees to show upright
    made = images.process(image_file((1200, 700), "JPEG", "shot.jpg", exif=exif.tobytes()))
    data = made.display.read()
    assert b"Secret Camera Co" not in data
    with Image.open(BytesIO(data)) as image:
        assert image.size == (700, 1200) and not image.getexif()


def test_transparency_is_kept():
    made = images.process(image_file(kind="PNG", mode="RGBA", color=(10, 20, 30, 0)))
    with Image.open(BytesIO(made.card.read())) as image:
        assert image.mode == "RGBA" and image.getpixel((0, 0))[3] == 0


@pytest.mark.django_db
def test_a_truncated_image_is_a_form_error_and_nothing_is_stored(media):
    noisy = Image.effect_noise((1280, 720), 64).convert("RGB")
    out = BytesIO()
    noisy.save(out, "JPEG")
    data = out.getvalue()
    upload = SimpleUploadedFile("shot.jpg", data[: len(data) // 2], "image/jpeg")
    response = signed_in(make_member()).post(reverse("showcases:create"), form_data(image=upload))
    assert response.status_code == 200
    assert escape(images.MESSAGES["not_an_image"]) in errors(response)
    assert not Showcase.objects.exists() and stored(media) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("upload", "message"),
    [
        (lambda: image_file(kind="GIF", name="a.gif"), images.MESSAGES["wrong_format"]),
        (lambda: image_file((600, 400)), images.MESSAGES["too_small"]),
        (lambda: image_file((3000, 600)), images.MESSAGES["bad_ratio"]),
        (
            lambda: SimpleUploadedFile("a.png", b"<svg/>", "image/png"),
            images.MESSAGES["not_an_image"],
        ),
    ],
)
def test_a_refused_image_is_said_on_the_form_and_the_draft_kept(media, upload, message):
    response = signed_in(make_member()).post(reverse("showcases:create"), form_data(image=upload()))
    html = errors(response)
    assert response.status_code == 200 and escape(message) in html
    assert 'value="Terrain at dusk"' in html and 'aria-invalid="true"' in html
    assert not Showcase.objects.exists() and stored(media) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"title": "   "}, strings.TITLE_REQUIRED),
        ({"title": "x" * 101}, strings.TITLE_TOO_LONG),
        ({"description": ""}, strings.DESCRIPTION_REQUIRED),
        ({"description": "x" * 5001}, strings.DESCRIPTION_TOO_LONG),
        ({"image": None}, strings.IMAGE_REQUIRED),
        ({"image_alt": "x" * 201}, strings.ALT_TOO_LONG),
        ({"tags": "a b c d e f"}, strings.TAGS_TOO_MANY),
        ({"tags": "ray_tracing"}, strings.TAG_INVALID_NAMED.format(name="ray_tracing")),
        ({"tags": "x"}, strings.TAG_INVALID_NAMED.format(name="x")),
        ({"tags": "-terrain"}, strings.TAG_INVALID_NAMED.format(name="-terrain")),
        ({"tags": "x" * 25}, strings.TAG_INVALID_NAMED.format(name="x" * 25)),
    ],
)
def test_validation(media, fields, message):
    response = signed_in(make_member()).post(reverse("showcases:create"), form_data(**fields))
    assert response.status_code == 200
    assert escape(message) in errors(response)
    assert not Showcase.objects.exists() and stored(media) == []


def test_tags_are_read_in_lower_case_once_each_without_a_hash():
    assert Tag.parse("Terrain, #luau  terrain,,ray-tracing") == ["terrain", "luau", "ray-tracing"]
    assert Tag.parse("  ") == []
    with pytest.raises(ValidationError):
        Tag.parse("ok <script>")


@pytest.mark.django_db
def test_a_tag_is_stored_once_in_lower_case_and_the_database_insists():
    ada, grace = make_member("ada"), make_member("grace")
    make_showcase(ada, tags=["terrain"])
    make_showcase(grace, tags=["terrain", "luau"])
    assert sorted(Tag.objects.values_list("name", flat=True)) == ["luau", "terrain"]
    with pytest.raises(IntegrityError):
        Tag.objects.create(name="Terrain")


@pytest.mark.django_db
def test_the_service_checks_tags_and_words_again():
    ada = make_member()
    with pytest.raises(ValidationError):
        services.create_showcase(ada, title="T", description="D", image=processed(), tags=["A B"])
    with pytest.raises(ValidationError):
        services.create_showcase(ada, title="", description="D", image=processed())
    assert not Showcase.objects.exists()


@pytest.mark.django_db
def test_markup_is_escaped():
    ada = make_member()
    showcase = make_showcase(ada, "<script>x</script>", description="<b>bold</b>")
    html = Client().get(showcase.get_absolute_url()).content.decode()
    assert "<script>x</script>" not in html and "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<b>bold</b>" not in html
    listing = Client().get(reverse("showcases:list")).content.decode()
    assert "<script>x</script>" not in listing


# ---------- Slugs ----------


@pytest.mark.django_db
def test_slugs_come_from_the_title_and_numbered_when_taken():
    ada, grace = make_member("ada"), make_member("grace")
    assert make_showcase(ada, "Lit Hall!").slug == "lit-hall"
    assert make_showcase(grace, "lit hall").slug == "lit-hall-2"
    assert make_showcase(ada, "New").slug == "new-2"  # /showcases/new/ is the publish page
    assert make_showcase(grace, "日本の庭").slug == "showcase"
    long = make_showcase(ada, "word " * 20)
    assert len(long.slug) <= Showcase.SLUG_MAX and not long.slug.endswith("-")


@pytest.mark.django_db
def test_the_slug_stays_when_the_title_changes():
    ada = make_member()
    showcase = make_showcase(ada, "First name")
    services.edit_showcase(ada, showcase, title="Second name", description="D")
    showcase.refresh_from_db()
    assert showcase.slug == "first-name" and showcase.title == "Second name"


def test_after_the_numbered_slugs_a_random_one():
    candidates = services.slug_candidates("hall")
    taken = [next(candidates) for _ in range(services.SLUG_ATTEMPTS + 1)]
    assert taken[0] == "hall" and taken[-1] == f"hall-{services.SLUG_ATTEMPTS + 1}"
    assert re.fullmatch(r"hall-[0-9a-f]{8}", next(candidates))


# ---------- The daily limit ----------


@pytest.mark.django_db
def test_a_second_showcase_within_a_day_is_refused_with_when_to_publish_again(media):
    ada, grace = make_member("ada"), make_member("grace")
    now = timezone.now()
    first = services.create_showcase(ada, title="One", description="D", image=processed(), now=now)
    Showcase.objects.filter(pk=first.pk).update(created=now - timedelta(hours=20, minutes=48))
    files = stored(media)
    with pytest.raises(LimitReached) as refused:
        services.create_showcase(ada, title="Two", description="D", image=processed(), now=now)
    assert str(refused.value) == (
        "You can publish 1 showcase a day. You can publish again in 3 hours, 12 minutes."
    )
    assert stored(media) == files  # the refused one's images were never written
    # Another member isn't held back, and exactly a day later ada may publish again.
    services.create_showcase(grace, title="Grace's", description="D", image=processed(), now=now)
    later = now + timedelta(hours=3, minutes=12)
    services.create_showcase(ada, title="Two", description="D", image=processed(), now=later)
    assert Showcase.objects.filter(author=ada).count() == 2


@pytest.mark.django_db
def test_hidden_showcases_count_and_deleted_ones_do_not():
    ada = make_member()
    showcase = services.create_showcase(ada, title="One", description="D", image=processed())
    Showcase.objects.filter(pk=showcase.pk).update(state=Visibility.REMOVED)
    with pytest.raises(LimitReached):
        services.create_showcase(ada, title="Two", description="D", image=processed())
    Showcase.objects.all().delete()
    services.create_showcase(ada, title="Two", description="D", image=processed())


@pytest.mark.django_db
def test_the_publish_page_says_so_at_the_limit_and_keeps_the_draft(media):
    ada = make_member()
    client = signed_in(ada)
    assert client.post(reverse("showcases:create"), form_data()).status_code == 302
    page = client.get(reverse("showcases:create")).content.decode()
    assert "data-limit" in page and "You can publish again in" in page
    response = client.post(reverse("showcases:create"), form_data(title="Another"))
    html = errors(response)
    assert response.status_code == 200 and "You can publish again in" in html
    assert 'value="Another"' in html and Showcase.objects.count() == 1
    assert len(stored(media)) == 2


def at_once(attempts) -> list[object]:
    """Run each attempt from its own thread and database connection, all released together."""
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


@pytest.mark.django_db(transaction=True)
def test_simultaneous_showcases_are_held_to_the_limit(media):
    ada = make_member()
    made = [processed() for _ in range(4)]
    results = at_once(
        [
            lambda m=m, i=i: services.create_showcase(
                ada, title=f"Same {i}", description="D", image=m
            )
            for i, m in enumerate(made)
        ]
    )
    assert sum(isinstance(r, Showcase) for r in results) == 1
    assert sum(isinstance(r, LimitReached) for r in results) == 3
    assert Showcase.objects.count() == 1 and len(stored(media)) == 2


@pytest.mark.django_db(transaction=True)
def test_simultaneous_showcases_of_one_title_get_their_own_addresses(media):
    people = [make_member(f"m{i}") for i in range(4)]
    made = [processed() for _ in people]
    results = at_once(
        [
            lambda p=p, m=m: services.create_showcase(p, title="Hall", description="D", image=m)
            for p, m in zip(people, made, strict=True)
        ]
    )
    assert all(isinstance(r, Showcase) for r in results), results
    assert sorted(Showcase.objects.values_list("slug", flat=True)) == [
        "hall", "hall-2", "hall-3", "hall-4",
    ]  # fmt: skip


# ---------- The verification gate ----------


@pytest.mark.django_db
def test_an_unverified_member_cant_publish_edit_or_like_but_can_delete(media):
    ada = make_member("ada", verified=False)
    grace = make_member("grace")
    own = make_showcase(make_member("ada2"))
    Showcase.objects.filter(pk=own.pk).update(author=ada)
    own.refresh_from_db()
    theirs = make_showcase(grace)
    client = signed_in(ada)
    verify = reverse("accounts:verify_email")
    assert client.get(reverse("showcases:create"))["Location"].startswith(verify)
    response = client.post(reverse("showcases:create"), form_data())
    assert response["Location"].startswith(verify) and Showcase.objects.count() == 2
    response = client.post(reverse("showcases:edit", args=[own.slug]), form_data(title="X"))
    assert response["Location"].startswith(verify)
    response = client.post(reverse("showcases:like", args=[theirs.slug]), {"action": "like"})
    assert response["Location"].startswith(verify) and not Like.objects.exists()
    with pytest.raises(EmailNotVerified):
        services.create_showcase(ada, title="T", description="D", image=processed())
    with pytest.raises(EmailNotVerified):
        services.like(ada, theirs)
    assert client.post(reverse("showcases:delete", args=[own.slug])).status_code == 302
    assert not Showcase.objects.filter(pk=own.pk).exists()


@pytest.mark.django_db
def test_a_visitor_is_sent_to_sign_in_to_publish_or_like():
    showcase = make_showcase(make_member())
    client = Client()
    login = reverse("account_login")
    assert client.get(reverse("showcases:create"))["Location"].startswith(login)
    response = client.post(reverse("showcases:like", args=[showcase.slug]), {"action": "like"})
    assert response["Location"].startswith(login)
    html = client.get(reverse("showcases:list")).content.decode()
    assert "data-sign-in-to-publish" in html
    assert "data-sign-in-to-like" in client.get(showcase.get_absolute_url()).content.decode()


# ---------- Only the author edits or deletes ----------


@pytest.mark.django_db
@pytest.mark.parametrize("who", ["another member", "staff", "superuser", "visitor"])
@pytest.mark.parametrize("action", ["edit", "delete"])
@pytest.mark.parametrize("htmx", [False, True])
def test_only_the_author_may_edit_or_delete_everyone_else_gets_a_404(who, action, htmx):
    ada = make_member("ada")
    showcase = make_showcase(ada)
    client = Client()
    if who != "visitor":
        extra = {"is_staff": True} if who == "staff" else {}
        if who == "superuser":
            extra = {"is_staff": True, "is_superuser": True}
        client.force_login(make_member("other", **extra))
    url = reverse(f"showcases:{action}", args=[showcase.slug])
    headers = HTMX if htmx else {}
    assert client.get(url, headers=headers).status_code == 404
    assert client.post(url, form_data(title="Taken"), headers=headers).status_code == 404
    showcase.refresh_from_db()
    assert showcase.title == "A lit hall"
    missing = reverse(f"showcases:{action}", args=["no-such-showcase"])
    assert client.get(missing).status_code == 404


@pytest.mark.django_db
def test_the_services_check_the_author_again():
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada)
    with pytest.raises(PermissionDenied):
        services.edit_showcase(grace, showcase, title="T", description="D")
    with pytest.raises(PermissionDenied):
        services.delete_showcase(grace, showcase)


@pytest.mark.django_db
def test_editing_changes_the_words_and_tags_and_keeps_the_image(media):
    ada = make_member()
    showcase = make_showcase(ada, tags=["terrain"])
    files = stored(media)
    client = signed_in(ada)
    url = reverse("showcases:edit", args=[showcase.slug])
    page = client.get(url).content.decode()
    assert 'value="A lit hall"' in page and 'value="terrain"' in page
    assert "data-current-image" in page and strings.IMAGE_HELP_EDIT in page
    response = client.post(url, form_data(title="A brighter hall", tags="luau decals", image=None))
    assert response.status_code == 302 and response["Location"] == showcase.get_absolute_url()
    showcase.refresh_from_db()
    assert showcase.title == "A brighter hall" and showcase.edited_at is not None
    assert sorted(t.name for t in showcase.tags.all()) == ["decals", "luau"]
    assert stored(media) == files
    html = client.get(showcase.get_absolute_url()).content.decode()
    assert strings.SAVED in html and "data-edited" in html


@pytest.mark.django_db
def test_a_new_image_replaces_the_old_and_its_files_are_deleted(media):
    ada = make_member()
    showcase = make_showcase(ada)
    old = stored(media)
    client = signed_in(ada)
    response = client.post(
        reverse("showcases:edit", args=[showcase.slug]), form_data(image=image_file((2000, 1000)))
    )
    assert response.status_code == 302
    showcase.refresh_from_db()
    assert stored(media) == sorted([showcase.image.name, showcase.card.name])
    assert not set(old) & set(stored(media))
    assert (showcase.image_width, showcase.image_height) == (1920, 960)


@pytest.mark.django_db
def test_a_refused_new_image_leaves_the_showcase_as_it_was(media):
    ada = make_member()
    showcase = make_showcase(ada)
    files = stored(media)
    response = signed_in(ada).post(
        reverse("showcases:edit", args=[showcase.slug]),
        form_data(title="Changed", image=image_file((100, 100))),
    )
    assert response.status_code == 200 and escape(images.MESSAGES["too_small"]) in errors(response)
    showcase.refresh_from_db()
    assert showcase.title == "A lit hall" and stored(media) == files


@pytest.mark.django_db
def test_deleting_asks_first_then_takes_the_showcase_its_files_and_likes(media):
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada, tags=["terrain"])
    services.like(grace, showcase)
    client = signed_in(ada)
    url = reverse("showcases:delete", args=[showcase.slug])
    page = client.get(url).content.decode()
    assert escape(strings.DELETE_LEDE) in page and strings.KEEP in page
    response = client.post(url)
    assert response.status_code == 302 and response["Location"] == reverse("showcases:list")
    assert not Showcase.objects.exists() and not Like.objects.exists()
    assert stored(media) == [] and Tag.objects.filter(name="terrain").exists()
    assert strings.DELETED in client.get(response["Location"]).content.decode()


@pytest.mark.django_db
def test_a_deleted_account_takes_its_showcases_and_their_files(media):
    ada = make_member()
    make_showcase(ada)
    assert stored(media)
    ada.delete()
    assert not Showcase.objects.exists() and stored(media) == []


@pytest.mark.django_db
def test_a_failed_save_leaves_no_files_behind(media, monkeypatch):
    ada = make_member()
    monkeypatch.setattr(services, "_set_tags", lambda *a: (_ for _ in ()).throw(RuntimeError))
    with pytest.raises(RuntimeError):
        services.create_showcase(ada, title="T", description="D", image=processed())
    assert not Showcase.objects.exists() and stored(media) == []


# ---------- Likes ----------


@pytest.mark.django_db
def test_a_member_likes_once_and_can_take_it_back():
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada)
    client = signed_in(grace)
    url = reverse("showcases:like", args=[showcase.slug])
    response = client.post(url, {"action": "like"})
    assert response.status_code == 302 and response["Location"].endswith("#like")
    client.post(url, {"action": "like"})  # again: still one
    assert Like.objects.filter(showcase=showcase).count() == 1
    html = client.get(showcase.get_absolute_url()).content.decode()
    assert "1 like" in html and 'aria-pressed="true"' in html and "data-unlike" in html
    client.post(url, {"action": "unlike"})
    assert not Like.objects.exists()
    assert client.post(url, {"action": "nonsense"}).status_code == 302
    assert not Like.objects.exists()


@pytest.mark.django_db
def test_the_author_cant_like_their_own_showcase():
    ada = make_member()
    showcase = make_showcase(ada)
    with pytest.raises(services.LikeRefused):
        services.like(ada, showcase)
    client = signed_in(ada)
    html = client.get(showcase.get_absolute_url()).content.decode()
    assert "data-own-showcase" in html and "data-like-button" not in html
    response = client.post(reverse("showcases:like", args=[showcase.slug]), {"action": "like"})
    assert response.status_code == 302 and not Like.objects.exists()
    response = client.post(
        reverse("showcases:like", args=[showcase.slug]), {"action": "like"}, headers=HTMX
    )
    html = response.content.decode()
    assert escape(strings.LIKE_OWN) in html and 'role="alert"' in html


@pytest.mark.django_db
def test_one_like_per_member_per_showcase_is_the_databases_rule():
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada)
    Like.objects.create(showcase=showcase, user=grace)
    with pytest.raises(IntegrityError):
        Like.objects.create(showcase=showcase, user=grace)


@pytest.mark.django_db
def test_liking_in_place_swaps_the_like_and_announces_it():
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada)
    client = signed_in(grace)
    response = client.post(
        reverse("showcases:like", args=[showcase.slug]), {"action": "like"}, headers=HTMX
    )
    html = response.content.decode()
    assert response.status_code == 200 and 'id="like"' in html
    assert "<html" not in html and "autofocus" in html and "1 like" in html
    assert 'hx-swap-oob="innerHTML:#showcase-status"' in html and strings.LIKED in html
    assert "HX-Request" in response["Vary"]


@pytest.mark.django_db
def test_the_list_shows_each_showcases_likes():
    ada, grace, lin = make_member("ada"), make_member("grace"), make_member("lin")
    showcase = make_showcase(ada)
    services.like(grace, showcase)
    services.like(lin, showcase)
    assert "2 likes" in Client().get(reverse("showcases:list")).content.decode()


# ---------- Moderation states ----------


@pytest.mark.django_db
@pytest.mark.parametrize("state", [Visibility.HIDDEN, Visibility.REMOVED])
def test_hidden_and_removed_showcases_are_for_staff_only(state):
    ada, grace = make_member("ada"), make_member("grace")
    staff = make_member("mod", is_staff=True)
    showcase = make_showcase(ada, "Moderated one", tags=["secret-tag"])
    Showcase.objects.filter(pk=showcase.pk).update(state=state)
    for viewer in [Client(), signed_in(grace), signed_in(ada)]:
        assert viewer.get(showcase.get_absolute_url()).status_code == 404
        listing = viewer.get(reverse("showcases:list")).content.decode()
        assert "Moderated one" not in listing and "secret-tag" not in listing
        for action in ["edit", "delete"]:
            assert (
                viewer.get(reverse(f"showcases:{action}", args=[showcase.slug])).status_code == 404
            )
    moderator = signed_in(staff)
    html = moderator.get(showcase.get_absolute_url()).content.decode()
    assert f'data-state="{state}"' in html and "data-report" not in html
    assert "data-like-button" not in html
    assert "Moderated one" in moderator.get(reverse("showcases:list")).content.decode()
    # Nobody may interact with it, staff included.
    for client in [signed_in(grace), moderator]:
        response = client.post(reverse("showcases:like", args=[showcase.slug]), {"action": "like"})
        assert response.status_code == 404
        assert (
            client.get(reverse("reports:create", args=["showcase", showcase.pk])).status_code == 404
        )
    assert not Like.objects.exists()


# ---------- Reporting ----------


@pytest.mark.django_db
def test_a_member_reports_someone_elses_showcase_once():
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada)
    client = signed_in(grace)
    page = client.get(showcase.get_absolute_url()).content.decode()
    url = reverse("reports:create", args=["showcase", showcase.pk])
    assert f'href="{url}"' in page
    response = client.post(url, {"reason": "spam", "details": ""})
    assert response.status_code == 302 and response["Location"] == showcase.get_absolute_url()
    report = Report.objects.get()
    assert report.target == showcase and report.reporter == grace
    assert "data-reported" in client.get(showcase.get_absolute_url()).content.decode()
    # Its own author can't, and the report goes with the showcase.
    assert signed_in(ada).get(url).status_code == 404
    showcase.delete()
    assert not Report.objects.exists()


# ---------- CSRF, the admin, the shell ----------


def snapshot(showcase):
    showcase.refresh_from_db()
    return (showcase.title, showcase.description, Like.objects.count(), Showcase.objects.count())


@pytest.mark.django_db
@pytest.mark.parametrize("htmx", [False, True])
def test_every_showcase_post_without_a_csrf_token_is_refused(htmx):
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada)
    before = snapshot(showcase)
    headers = HTMX if htmx else {}
    for user, urls in [
        (
            ada,
            [
                reverse("showcases:create"),
                reverse("showcases:edit", args=[showcase.slug]),
                reverse("showcases:delete", args=[showcase.slug]),
            ],
        ),
        (grace, [reverse("showcases:like", args=[showcase.slug])]),
    ]:
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        for url in urls:
            response = client.post(url, form_data(action="like"), headers=headers)
            assert response.status_code == 403, url
    assert snapshot(showcase) == before


@pytest.mark.django_db
def test_the_like_form_carries_its_token_and_htmx_goes_through():
    ada, grace = make_member("ada"), make_member("grace")
    showcase = make_showcase(ada)
    client = Client(enforce_csrf_checks=True)
    client.force_login(grace)
    html = client.get(showcase.get_absolute_url()).content.decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)[1]
    url = reverse("showcases:like", args=[showcase.slug])
    assert f'hx-post="{url}"' in html
    response = client.post(url, {"action": "like", "csrfmiddlewaretoken": token}, headers=HTMX)
    assert response.status_code == 200 and Like.objects.count() == 1


@pytest.mark.django_db
def test_the_admin_is_read_only(admin_client):
    showcase = make_showcase(make_member())
    assert admin_client.get(reverse("admin:showcases_showcase_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:showcases_showcase_add")).status_code == 403
    page = admin_client.get(reverse("admin:showcases_showcase_change", args=[showcase.pk]))
    assert page.status_code == 200 and 'name="title"' not in page.content.decode()
    assert admin_client.get(reverse("admin:showcases_tag_changelist")).status_code == 200


@pytest.mark.django_db
def test_the_rail_and_the_footer_lead_to_showcases():
    html = Client().get(reverse("showcases:list")).content.decode()
    assert 'class="app-bar"' in html
    rail = html[html.index('id="app-rail"') :]
    assert re.search(
        rf'href="{reverse("showcases:list")}" class="app-rail-link" aria-current="page"', rail
    )
    home = Client().get(reverse("marketing:home")).content.decode()
    assert f'href="{reverse("showcases:list")}"' in home
