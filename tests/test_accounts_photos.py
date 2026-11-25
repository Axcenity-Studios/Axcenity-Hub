"""Profile photos (accounts.avatars, ProfileForm): what an upload must be, the one image the
Hub keeps from it, and that replaced, removed and deleted photos leave no file behind."""

from io import BytesIO

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from accounts import avatars
from accounts.models import Profile

User = get_user_model()


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def member(client):
    user = User.objects.create_user("ada", "ada@example.com", "pw-correct-horse-42")
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    client.force_login(user)
    return user


def image_file(
    size=(300, 200), kind="PNG", name="me.png", mode="RGB", **save
) -> SimpleUploadedFile:
    out = BytesIO()
    Image.new(mode, size, "#3366aa").save(out, kind, **save)
    return SimpleUploadedFile(name, out.getvalue(), content_type=f"image/{kind.lower()}")


def upload(client, photo=None, **fields):
    data = {"display_name": "", "bio": "", **fields}
    if photo is not None:
        data["photo"] = photo
    return client.post(reverse("accounts:profile"), data)


def stored(media) -> list:
    return sorted((media / "avatars").glob("*")) if (media / "avatars").exists() else []


@pytest.mark.django_db
def test_an_upload_is_stored_as_the_hubs_own_square_webp_and_shown(client, member, media):
    response = upload(client, image_file((300, 200)))
    assert response.status_code == 302
    profile = Profile.objects.get(user=member)
    [path] = stored(media)
    assert profile.avatar.name == f"avatars/{path.name}" and path.suffix == ".webp"
    with Image.open(path) as image:
        assert (image.format, image.size) == ("WEBP", (avatars.SIZE, avatars.SIZE))
    # The bar, the settings header and the preview all show it.
    html = client.get(reverse("accounts:profile")).content.decode()
    assert html.count(f'src="{profile.avatar.url}"') >= 3
    assert 'enctype="multipart/form-data"' in html


@pytest.mark.django_db
def test_without_a_photo_the_members_initial_is_shown(client, member):
    html = client.get(reverse("accounts:profile")).content.decode()
    assert 'class="app-avatar app-avatar-initial"' in html and ">A</span>" in html
    assert 'data-photo="none"' in html and "Remove my photo" not in html


@pytest.mark.django_db
def test_the_stored_photo_carries_none_of_the_uploads_metadata(client, member, media):
    exif = Image.Exif()
    exif[0x010F] = "Secret Camera Co"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90 degrees to show upright
    upload(client, image_file((400, 200), "JPEG", "me.jpg", exif=exif.tobytes()))
    [path] = stored(media)
    data = path.read_bytes()
    assert b"Secret Camera Co" not in data
    with Image.open(path) as image:
        assert not image.getexif()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "photo, message",
    [
        (SimpleUploadedFile("big.png", b"x" * (avatars.MAX_BYTES + 1)), avatars.TOO_BIG),
        (SimpleUploadedFile("me.png", b"not an image at all"), avatars.NOT_AN_IMAGE),
        (image_file(kind="BMP", name="me.bmp"), avatars.WRONG_FORMAT),
        (image_file((32, 32)), avatars.TOO_SMALL),
        (image_file((avatars.MAX_SIDE + 1, 100)), avatars.TOO_LARGE),
    ],
    ids=["too-big", "not-an-image", "wrong-format", "too-small", "too-large"],
)
def test_an_upload_is_refused_for_its_size_type_or_dimensions(
    client, member, media, photo, message
):
    response = upload(client, photo)
    assert response.status_code == 200
    assert message.replace("'", "&#x27;") in response.content.decode()
    assert not Profile.objects.get(user=member).avatar and stored(media) == []


@pytest.mark.django_db
def test_a_truncated_image_is_a_form_error_not_a_crash(client, member, media):
    whole = image_file((300, 300), "JPEG", "me.jpg").read()
    response = upload(client, SimpleUploadedFile("me.jpg", whole[: len(whole) // 2]))
    assert response.status_code == 200
    assert avatars.NOT_AN_IMAGE.replace("'", "&#x27;") in response.content.decode()
    assert stored(media) == []


@pytest.mark.django_db
def test_replacing_or_removing_a_photo_deletes_the_old_file(client, member, media):
    upload(client, image_file())
    [first] = stored(media)
    upload(client, image_file((500, 500), "WEBP", "new.webp"))
    [second] = stored(media)
    assert second != first and not first.exists()

    # Saving the profile without a new photo keeps it.
    upload(client, display_name="Ada")
    assert stored(media) == [second]

    upload(client, remove_photo="on")
    assert stored(media) == [] and not Profile.objects.get(user=member).avatar


@pytest.mark.django_db
def test_deleting_a_member_deletes_their_photo(client, member, media):
    upload(client, image_file())
    assert len(stored(media)) == 1
    member.delete()
    assert stored(media) == []


@pytest.mark.django_db
@pytest.mark.parametrize("debug", [True, False])
def test_photos_are_served_by_a_development_server_only(client, member, media, settings, debug):
    upload(client, image_file())
    url = Profile.objects.get(user=member).avatar.url
    settings.DEBUG = debug
    response = client.get(url)
    assert response.status_code == (200 if debug else 404)
    if debug:
        assert response["Content-Type"] == "image/webp"
