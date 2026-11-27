"""Showcases in headless Chromium: the card grid and a showcase's page at 360 and 1280 px, dark
and light, with no sideways scroll and every image drawn; choosing a tag swaps the list in
place with the address following; a tag on a card opens its list; liking and taking it back
by keyboard in place, with no reload; publishing through the form with a real file.
Screenshots go to screenshots/showcases/."""

import os
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

from showcases import strings
from showcases.models import Like, Showcase
from tests.test_showcases import image_bytes, make_showcase

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PASSWORD = "a-Long-pass-7731"
CARDS = "document.querySelectorAll('#showcase-list .sc-card').length"


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.DEBUG = True  # the development server serves the uploads (config/media.py)
    return tmp_path


def make_member(username: str):
    email = f"{username}@example.com"
    user = get_user_model().objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
    return user


def fill() -> Showcase:
    """Five showcases by ada, a day apart; the newest ("Lantern court") tagged terrain and
    lighting, two more tagged terrain."""
    ada = make_member("ada")
    names = ["Lantern court", "Canyon flyover", "Mirror hall", "Moss path", "Graybox arena"]
    made = []
    for n, name in enumerate(names):
        tags = ["terrain", "lighting"] if n == 0 else (["terrain"] if n < 3 else ["graybox"])
        made.append(make_showcase(ada, name, tags=tags, ago=timedelta(days=2 + n)))
    return made[0]


def sign_in(page, username="grace") -> None:
    page.fill("input[name=login]", f"{username}@example.com")
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit].btn-primary")


def fits(page, width: int) -> None:
    """No sideways scroll, nothing past a panel's edge, every image drawn."""
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.evaluate(
        "[...document.querySelectorAll('.pj-panel, .sc-card, .ls-controls select')].every(box =>"
        " box.getBoundingClientRect().right <= innerWidth + 0.5)"
    )
    page.wait_for_function(
        "[...document.querySelectorAll('img.sc-card-image, img.sc-image')]"
        ".every(i => i.complete && i.naturalWidth > 0)"
    )


def watch(page) -> None:
    page.evaluate(
        "window.__noReload = 1; window.__loads = 0;"
        "document.addEventListener('htmx:load', () => window.__loads++)"
    )


def swap(page, action) -> None:
    before = page.evaluate("window.__loads")
    action()
    page.wait_for_function(f"window.__loads > {before}")


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_the_grid_filters_by_tag_in_place_and_fits(open_home, width, scheme):
    newest = fill()
    shots = f"screenshots/showcases/{{}}-{width}-{scheme}.png"
    page, errors = open_home(path="/showcases/", width=width, scheme=scheme)
    for _ in range(3):  # lazy images below the fold load as they come into view
        page.mouse.wheel(0, 2000)
    page.wait_for_function(f"{CARDS} === 5")
    fits(page, width)
    page.screenshot(path=shots.format("list"), full_page=True)

    watch(page)
    swap(page, lambda: page.select_option("#showcase-list-tag", "terrain"))
    page.wait_for_url("**/showcases/?tag=terrain")
    page.wait_for_function(f"{CARDS} === 3")
    assert page.text_content("#showcases-title").strip() == strings.TAGGED.format(tag="terrain")
    assert page.inner_text("#showcase-list-status") == "3 showcases"
    assert page.evaluate("window.__noReload") == 1

    # A tag on a card is its own link, above the card's stretched title link.
    page.click(f'[data-showcase="{newest.slug}"] [data-tag="lighting"]')
    page.wait_for_url("**/showcases/?tag=lighting")
    page.wait_for_function(f"{CARDS} === 1")
    assert errors == []


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_a_member_likes_and_takes_it_back_by_keyboard_in_place(open_home, width, scheme):
    showcase = fill()
    make_member("grace")
    page, errors = open_home(
        path=f"/accounts/login/?next={showcase.get_absolute_url()}", width=width, scheme=scheme
    )
    sign_in(page)
    page.wait_for_url(f"**{showcase.get_absolute_url()}")
    fits(page, width)
    page.screenshot(path=f"screenshots/showcases/detail-{width}-{scheme}.png", full_page=True)

    watch(page)
    page.focus("[data-like-button]")
    swap(page, lambda: page.keyboard.press("Enter"))
    page.wait_for_selector("[data-unlike]")
    assert page.get_attribute("[data-unlike]", "aria-pressed") == "true"
    assert page.evaluate("document.activeElement.hasAttribute('data-unlike')")
    assert page.inner_text("[data-like-count]") == "1 like"
    assert page.inner_text("#showcase-status") == strings.LIKED
    assert Like.objects.count() == 1

    swap(page, lambda: page.keyboard.press("Enter"))
    page.wait_for_selector("[data-like-button]")
    assert page.inner_text("[data-like-count]") == "0 likes"
    assert page.evaluate("window.__noReload") == 1 and errors == []
    assert not Like.objects.exists()


def test_publishing_through_the_form_with_a_real_file(open_home, tmp_path):
    make_member("grace")
    picture = tmp_path / "hall.png"
    picture.write_bytes(image_bytes((1600, 900)))
    page, errors = open_home(path="/accounts/login/?next=/showcases/new/", width=1280)
    sign_in(page)
    page.wait_for_url("**/showcases/new/")
    page.fill("#id_title", "A hall I built")
    page.set_input_files("#id_image", str(picture))
    page.fill("#id_description", "Lit with the ray tracer.")
    page.fill("#id_tags", "Lighting, #ray-tracing")
    page.click("button[type=submit].btn-primary")
    page.wait_for_url("**/showcases/a-hall-i-built/")
    fits(page, 1280)
    assert page.locator("[data-tag]").all_inner_texts() == ["lighting", "ray-tracing"]
    assert page.evaluate("document.querySelector('img.sc-image').naturalWidth") == 1600
    assert errors == []
