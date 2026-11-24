"""Browser checks for the Home's media frames, in headless Chromium.

One parametrised test opens Home at each width, scheme and pixel ratio, checks that every
pillar's and section's media is sharp and framed, and saves a screenshot of each to screenshots/media/
(git-ignored) for review by eye: they're not compared pixel by pixel. The rest check how
the animated recreations play. They need the built stylesheet
(`uv run python manage.py tailwind build`).
"""

import os
import re

import pytest
from django.conf import settings

from marketing import content

# Playwright's sync API runs an event loop in this thread; see test_hero_browser.py.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

SCREENSHOTS = settings.BASE_DIR / "screenshots" / "media"
PILLARS = [(pillar.label.lower(), pillar.media) for pillar in content.HOME_FEATURES["pillars"]]
# The section loops, by the section they sit in.
SECTIONS = [
    ("toolbox", content.MEDIA["toolbox"]),
    ("community", content.MEDIA["wipe"]),
    ("start", content.MEDIA["animation"]),
]
STILLS = {"editor": 6.5, "terrain": 9.6, "logic": 6.5, "toolbox": 7, "wipe": 4.5, "animation": 4.5}
DURATIONS = {"editor": 12, "terrain": 12, "logic": 16, "toolbox": 12, "wipe": 10, "animation": 10}


def show_pillar(page, label: str) -> str:
    """Scrolls a pillar to the middle and returns the selector of the frame now showing it."""
    page.evaluate(f"document.getElementById('feature-{label}').scrollIntoView({{block: 'center'}})")
    if page.viewport_size["width"] >= 1024:
        index = [name for name, _ in PILLARS].index(label)
        page.wait_for_selector(f'[data-stage-item="{index}"][data-on]')
        page.wait_for_timeout(900)  # the stage's cross-fade
        return f'[data-stage-item="{index}"] .media'
    page.wait_for_timeout(200)
    return f"#feature-{label} .media"


def show_section(page, section: str) -> str:
    """Scrolls a section's loop to the middle and returns its frame's selector."""
    selector = f"#{section} .media"
    page.evaluate(f"document.querySelector('{selector}').scrollIntoView({{block: 'center'}})")
    page.wait_for_timeout(200)
    return selector


def show(page, where: str) -> str:
    """A pillar's frame (by label) or a section's (by id)."""
    return show_section(page, where) if where in dict(SECTIONS) else show_pillar(page, where)


def seek(page, selector: str, time: float) -> None:
    page.evaluate(
        "([selector, time]) => document.querySelector(selector)"
        ".dispatchEvent(new CustomEvent('loop-seek', { detail: time }))",
        [selector, time],
    )


def snapshot(page, selector: str, name: str) -> None:
    """Keeps the loop's canvas pixels in the page as `name`."""
    page.evaluate(
        """([selector, name]) => { const c = document.querySelector(selector + ' canvas');
        (window.__snaps ||= {})[name] = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; }""",
        [selector, name],
    )


def changed_share(page, a: str, b: str) -> float:
    """The share of pixels that differ between two snapshots by more than a faint shimmer."""
    return page.evaluate(
        """([a, b]) => { const x = window.__snaps[a], y = window.__snaps[b]; let changed = 0;
        for (let i = 0; i < x.length; i += 4) {
          if (Math.max(Math.abs(x[i] - y[i]), Math.abs(x[i + 1] - y[i + 1]), Math.abs(x[i + 2] - y[i + 2])) > 24) changed += 1;
        }
        return changed / (x.length / 4); }""",
        [a, b],
    )


def pause_loop(page, selector: str) -> None:
    if page.get_attribute(f"{selector} [data-loop-toggle]", "data-intent") == "playing":
        page.click(f"{selector} [data-loop-toggle]")


@pytest.mark.parametrize("scale", [1, 2])
@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 768, 1280, 1440, 2560])
def test_media_is_sharp_and_framed_at_every_width(open_home, width, scheme, scale):
    page, errors = open_home(width=width, height=900, scale=scale, scheme=scheme)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    for label, item in PILLARS + SECTIONS:
        selector = show(page, label)
        frame = page.locator(selector)
        box = frame.bounding_box()
        assert abs(box["width"] / box["height"] - 1.6) < 0.02, (label, box)
        if item.source:
            page.wait_for_function(
                "s => { const i = document.querySelector(s + ' img'); return i.complete && i.naturalWidth; }",
                arg=selector,
            )
            image = page.evaluate(
                """s => { const i = document.querySelector(s + ' img');
                return { natural: i.naturalWidth, drawn: Math.max(i.clientWidth, i.clientHeight * 16 / 9),
                         src: i.currentSrc }; }""",
                selector,
            )
            # The browser picked a file at least as wide as the picture is drawn, in device pixels
            # (naturalWidth is already divided by the density it chose, so read the file's own).
            chosen = int(re.search(r"-(\d+)\.avif$", image["src"]).group(1))
            assert chosen >= image["drawn"] * scale - 1, (label, image)
            assert image["src"].endswith(".avif"), image["src"]
        else:
            page.wait_for_selector(f"{selector}[data-live][data-ready]")
            pause_loop(page, selector)
            seek(page, selector, STILLS[item.loop])
            canvas = page.evaluate(
                "s => { const c = document.querySelector(s + ' canvas'); return [c.width, c.clientWidth]; }",
                selector,
            )
            assert canvas[0] == round(canvas[1] * min(scale, 2)), (label, canvas)
            if item.capture:
                # The wipe's lit end: the derivative the player picked covers the frame, pushed in.
                files = page.evaluate(
                    "performance.getEntriesByType('resource').map(e => e.name)"
                    ".filter(n => /renderer-\\d+\\.webp/.test(n))"
                )
                assert len(files) == 1, files
                chosen = int(re.search(r"-(\d+)\.webp", files[0]).group(1))
                drawn = box["width"] * 1.2 * min(scale, 2)
                assert chosen >= min(drawn, 2560) - 1, (chosen, drawn)
        frame.screenshot(path=SCREENSHOTS / f"{width}-{scheme}-{scale}x-{item.key}.png")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors, errors


def test_loops_play_only_on_screen_and_pause_with_their_button(open_home):
    page, errors = open_home(width=1280, height=900)
    for _, item in PILLARS:
        if item.loop:
            assert (
                page.get_attribute(f'.stage-item [data-loop="{item.loop}"]', "data-state")
                == "paused"
            )
    selector = show_pillar(page, "logic")
    page.wait_for_selector(f"{selector}[data-state='playing']")
    # Only the current stage item plays: the inline copies are hidden, the others aren't current.
    assert page.get_attribute('.pillar [data-loop="logic"]', "data-state") == "paused"
    assert page.get_attribute('.stage-item [data-loop="editor"]', "data-state") == "paused"

    button = f"{selector} [data-loop-toggle]"
    page.click(button)
    assert page.get_attribute(selector, "data-state") == "paused"
    assert page.get_attribute(button, "aria-label") == content.LOOP_CONTROLS["play"]
    # With the other loops paused or off screen, nothing on the page asks for frames.
    before = page.evaluate("window.__frames")
    page.wait_for_timeout(300)
    assert page.evaluate("window.__frames") == before
    page.click(button)
    assert page.get_attribute(selector, "data-state") == "playing"
    assert page.get_attribute(button, "aria-label") == content.LOOP_CONTROLS["pause"]
    assert not errors, errors


def test_reduced_motion_shows_each_loops_still_without_autoplay(open_home):
    page, errors = open_home(width=1280, height=900, reduced_motion="reduce")
    selector = show_pillar(page, "world")
    page.wait_for_selector(f"{selector}[data-ready]")
    assert page.get_attribute(selector, "data-state") == "paused"
    assert page.get_attribute(selector, "data-motion") == "reduced"
    assert (
        page.get_attribute(f"{selector} [data-loop-toggle]", "aria-label")
        == content.LOOP_CONTROLS["play"]
    )
    snapshot(page, selector, "shown")
    seek(page, selector, STILLS["terrain"])
    snapshot(page, selector, "still")
    assert changed_share(page, "shown", "still") == 0
    page.click(f"{selector} [data-loop-toggle]")
    assert page.get_attribute(selector, "data-state") == "playing"
    assert not errors, errors


@pytest.mark.parametrize("label", ["editor", "world", "logic", "toolbox", "community", "start"])
def test_each_loop_is_a_pure_function_of_time_and_wraps_seamlessly(open_home, label):
    page, errors = open_home(width=1280, height=900)
    selector = show(page, label)
    page.wait_for_selector(f"{selector}[data-ready]")
    pause_loop(page, selector)
    loop = page.get_attribute(selector, "data-loop")
    seek(page, selector, 3.3)
    snapshot(page, selector, "first")
    seek(page, selector, 7.1)
    seek(page, selector, 3.3)
    snapshot(page, selector, "again")
    assert changed_share(page, "first", "again") == 0
    # The last moment of the loop is (almost) its first: no visible reset at the wrap.
    seek(page, selector, 0)
    snapshot(page, selector, "start")
    seek(page, selector, DURATIONS[loop] - 0.004)
    snapshot(page, selector, "end")
    assert changed_share(page, "start", "end") < 0.002
    assert not errors, errors
