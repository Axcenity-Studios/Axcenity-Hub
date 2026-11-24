"""The hero's film without a browser: the Desert Homestead files, the video's markup and
captions, and home.js's rules for playing it. Its behaviour in Chromium is checked by
tests/test_hero_browser.py."""

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils.html import escape

from marketing import content

pytestmark = pytest.mark.django_db

SOURCE = (settings.BASE_DIR / "styles" / "source.css").read_text(encoding="utf-8")
HOME_JS = (settings.BASE_DIR / "static" / "js" / "home.js").read_text(encoding="utf-8")
STATIC = settings.BASE_DIR / "static"
FILM = content.HOME_HERO["backdrop"]

# The film's bytes, all sources together, and the poster's.
FILM_BUDGET = 24 * 1024 * 1024
POSTER_BUDGET = 300 * 1024


@pytest.fixture
def hero(client):
    html = client.get(reverse("marketing:home")).content.decode()
    return html.split('id="hero"', 1)[1].split("</section>", 1)[0]


def test_the_film_is_the_homestead_capture_with_its_files_in_static():
    assert FILM.kind == "capture" and FILM.caption == "Engine capture · Desert Homestead film"
    # AV1 first (a third the size), then H.264 for browsers without AV1.
    assert [source.codecs.split(".")[0] for source in FILM.sources] == ["av01", "avc1"]
    files = [STATIC / source.file for source in FILM.sources]
    assert all(path.is_file() for path in files) and (STATIC / FILM.poster).is_file()
    assert sum(path.stat().st_size for path in files) <= FILM_BUDGET
    assert (STATIC / FILM.poster).stat().st_size <= POSTER_BUDGET


def test_the_hero_is_the_film_alone(hero):
    """No canvas, reel or fallback capture: the film, its caption and its button."""
    assert "<canvas" not in hero and "reel" not in hero and "<picture" not in hero
    assert hero.index('<figure class="hero-film" data-film>') < hero.index('id="hero-copy"')


def test_the_film_loops_muted_and_never_autoplays(hero):
    video = hero.split("<video", 1)[1].split("</video>", 1)[0]
    # home.js starts it, so it obeys Pause, reduced motion and visibility: never autoplay.
    for attribute in ("muted", "loop", "playsinline", 'preload="metadata"', 'aria-hidden="true"'):
        assert attribute in video
    assert "autoplay" not in video
    assert f'poster="/static/{FILM.poster}"' in video
    # Each source typed with its codecs, in order, so a browser skips one it can't decode.
    positions = [video.index(f'<source src="/static/{source.file}"') for source in FILM.sources]
    assert positions == sorted(positions)
    for source in FILM.sources:
        assert f'type="{escape(source.mime)}"' in video


def test_the_film_is_captioned_as_a_capture(hero):
    assert f'<figcaption class="media-cap micro">{escape(FILM.caption)}</figcaption>' in hero


def test_the_pause_button_is_labelled_and_hidden_until_home_js_runs(hero):
    controls = content.HOME_HERO["video_controls"]
    button = hero.split("<button", 1)[1].split("</button>", 1)[0]
    assert "data-film-toggle" in button and " hidden>" in button
    assert f'aria-label="{controls["pause"]}"' in button
    assert f'data-play-label="{controls["play"]}"' in button
    assert "filmToggle.hidden = false;" in HOME_JS


def test_home_js_plays_it_only_when_wanted_on_screen_and_visible():
    assert (
        'var running = !filmPaused && filmOnScreen && document.visibilityState === "visible";'
        in HOME_JS
    )
    # Reduced motion: no autoplay (the poster shows), followed live.
    assert "var filmPaused = reduce.matches;" in HOME_JS
    assert "filmPaused = reduce.matches;\n      updateFilm();" in HOME_JS
    assert 'document.addEventListener("visibilitychange", updateFilm);' in HOME_JS
    assert "video.pause();" in HOME_JS


def test_the_scrim_and_controls_are_drawn_in_tokens():
    assert ".hero-film::after {" in SOURCE
    film_css = SOURCE.split(".hero-film {", 1)[1].split("/* The rotating line", 1)[0]
    assert "#" not in film_css.replace("#content", "")
    assert '.film-button[data-intent="playing"] .media-icon-play' in SOURCE


def test_a_film_is_labelled_for_what_it_is():
    mp4 = (content.VideoSource("a.mp4", "avc1.64001F"),)
    with pytest.raises(ValueError):  # a capture's caption says so
        content.BackdropVideo(mp4, "capture", "Illustrative · demo", "p")
    with pytest.raises(ValueError):
        content.BackdropVideo(mp4, "screenshot", "Engine capture", "p")
    with pytest.raises(ValueError):
        content.BackdropVideo((), "capture", "Engine capture", "p")
    with pytest.raises(ValueError):  # a format browsers play
        content.VideoSource("a.mov", "avc1.64001F")
    with pytest.raises(ValueError):  # and what's in it
        content.VideoSource("a.webm", "")
    assert content.VideoSource("a.webm", "vp9").mime == 'video/webm; codecs="vp9"'
