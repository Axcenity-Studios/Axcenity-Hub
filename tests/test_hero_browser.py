"""The hero's film in headless Chromium: it plays, pauses with its button, never autoplays
under reduced motion or in a hidden tab, and stops off screen.

Each page may reach only the live server (browser_server); every other request is
aborted. They need the built stylesheet: `uv run python manage.py tailwind build`.
`open_home` and `CONTROL_VISIBILITY` are in tests/conftest.py.
"""

import os

import pytest

from marketing import content
from tests.conftest import CONTROL_VISIBILITY

# Playwright's sync API runs an event loop in this thread; the database teardown
# that the live server needs is synchronous and harmless here.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

CONTROLS = content.HOME_HERO["video_controls"]
BUTTON = "[data-film-toggle]"


def state(page) -> str:
    return page.get_attribute("[data-film]", "data-state")


def video(page) -> dict:
    return page.evaluate(
        """() => { const v = document.querySelector('.hero-film-video');
        return { paused: v.paused, time: v.currentTime, src: v.currentSrc.split('/').pop() }; }"""
    )


def test_the_film_plays_its_av1_source_with_no_console_errors(open_home):
    page, errors = open_home()
    page.wait_for_function("!document.querySelector('.hero-film-video').paused")
    assert state(page) == "playing"
    # Chromium decodes AV1, so it takes the first (smaller) source.
    assert video(page)["src"] == content.HOME_HERO["backdrop"].sources[0].file.rsplit("/", 1)[1]
    page.wait_for_function("document.querySelector('.hero-film-video').currentTime > 0.3")
    assert page.is_visible(BUTTON)
    assert page.get_attribute(BUTTON, "aria-label") == CONTROLS["pause"]
    assert not errors, errors


def test_the_button_pauses_and_plays_it(open_home):
    page, errors = open_home()
    page.wait_for_function("!document.querySelector('.hero-film-video').paused")
    page.click(BUTTON)
    assert state(page) == "paused" and video(page)["paused"]
    assert page.get_attribute(BUTTON, "aria-label") == CONTROLS["play"]
    held = video(page)["time"]
    page.wait_for_timeout(400)
    assert video(page)["time"] == held
    page.click(BUTTON)
    page.wait_for_function("!document.querySelector('.hero-film-video').paused")
    assert page.get_attribute(BUTTON, "aria-label") == CONTROLS["pause"]
    assert not errors, errors


def test_reduced_motion_shows_the_poster_and_follows_the_setting_live(open_home):
    page, errors = open_home(reduced_motion="reduce")
    page.wait_for_timeout(400)
    assert state(page) == "paused" and video(page)["time"] == 0  # the poster shows
    assert page.get_attribute(BUTTON, "aria-label") == CONTROLS["play"]
    page.emulate_media(reduced_motion="no-preference")
    page.wait_for_function("!document.querySelector('.hero-film-video').paused")
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_function("document.querySelector('.hero-film-video').paused")
    assert not errors, errors


def test_it_pauses_off_screen_and_never_autoplays_in_a_hidden_tab(open_home):
    page, _ = open_home(init="window.__startHidden = true;" + CONTROL_VISIBILITY)
    page.wait_for_timeout(400)
    assert state(page) == "paused" and video(page)["paused"]  # a background tab: no autoplay
    page.evaluate("window.__setVisibility('visible')")
    page.wait_for_function("!document.querySelector('.hero-film-video').paused")
    page.evaluate("window.__setVisibility('hidden')")
    assert state(page) == "paused" and video(page)["paused"]
    page.evaluate("window.__setVisibility('visible')")

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_function("document.querySelector('.hero-film-video').paused")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("!document.querySelector('.hero-film-video').paused")


@pytest.mark.parametrize(("width", "height"), [(360, 740), (1280, 800), (2560, 1440)])
def test_the_film_covers_the_hero_with_no_sideways_scroll(open_home, width, height):
    page, errors = open_home(width=width, height=height)
    hero = page.locator("#hero").bounding_box()
    film = page.locator(".hero-film-video").bounding_box()
    assert (film["width"], film["height"]) == (hero["width"], hero["height"])
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    # The caption sits above the button, not under it.
    caption = page.locator(".hero-film > .media-cap").bounding_box()
    button = page.locator(BUTTON).bounding_box()
    assert caption["y"] + caption["height"] <= button["y"]
    assert not errors, errors
