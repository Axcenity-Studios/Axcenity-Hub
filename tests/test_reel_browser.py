"""Browser smoke tests for the showcase reel (static/reel/), in headless Chromium.

Each page may reach only the live server (browser_server); every other request is
aborted. They need the built stylesheet: `uv run python manage.py tailwind build`.
`open_home`, `COUNT_FRAMES` and `CONTROL_VISIBILITY` are in tests/conftest.py.
"""

import os

import pytest

from tests.conftest import CONTROL_VISIBILITY

# Playwright's sync API runs an event loop in this thread; the database teardown
# that the live server needs is synchronous and harmless here.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser


def state(page) -> str:
    return page.get_attribute("#reel", "data-state")


def position(page) -> float:
    return float(page.input_value(".reel-range"))


def seek(page, time: float) -> None:
    """Seek the way the scrubber does: set the range, then fire its input and change events."""
    page.evaluate(
        """time => { const range = document.querySelector('.reel-range');
        range.value = String(time);
        range.dispatchEvent(new Event('input', { bubbles: true }));
        range.dispatchEvent(new Event('change', { bubbles: true })); }""",
        time,
    )


def frame(page) -> str:
    return page.evaluate("document.querySelector('#reel canvas').toDataURL()")


def frames_requested(page) -> int:
    return page.evaluate("window.__frames")


def pause(page) -> None:
    """Pause the way a visitor does. It goes by their intent (data-intent, set at mount),
    not by data-state: just after load the reel may not have been seen on screen yet."""
    if page.get_attribute(".reel-controls", "data-intent") == "playing":
        page.click("[data-reel-toggle]")
    page.wait_for_function("document.querySelector('#reel').dataset.state === 'paused'")


def test_the_reel_mounts_sharp_with_no_console_errors(open_home):
    page, errors = open_home(scale=3)
    assert page.get_attribute("#reel", "data-live") == ""
    assert page.is_visible(".reel-controls") and not page.is_visible(".reel-fallback")
    assert page.get_attribute("#reel", "aria-describedby") == "reel-description"
    size = page.evaluate(
        """() => { const c = document.querySelector('#reel canvas'), b = c.getBoundingClientRect();
        return [c.width, c.height, Math.round(b.width), Math.round(b.height)]; }"""
    )
    assert size[0] == size[2] * 2 and size[1] == size[3] * 2  # DPR 3 is capped at 2
    assert page.locator(".reel-marker").count() == 6  # one per scene
    # Every colour the canvas reads resolves, in both schemes (Tailwind emits each token).
    for scheme in ("dark", "light"):
        page.evaluate(f"document.documentElement.dataset.scheme = '{scheme}'")
        palette = page.evaluate(
            """async () => (await import('/static/reel/canvas.js')).readPalette(document.documentElement)"""
        )
        assert all(value.startswith("#") for value in palette.values()), (scheme, palette)
    page.wait_for_function("document.querySelector('#reel').dataset.state === 'playing'")
    assert errors == []


def test_play_and_pause_toggle_and_a_paused_reel_requests_no_frames(open_home):
    page, _ = open_home()
    page.wait_for_function("document.querySelector('#reel').dataset.state === 'playing'")
    page.click("[data-reel-toggle]")
    assert state(page) == "paused"
    assert page.get_attribute("[data-reel-toggle]", "aria-label") == "Play reel"
    requested, at = frames_requested(page), position(page)
    page.wait_for_timeout(400)
    assert frames_requested(page) == requested and position(page) == at
    page.click("[data-reel-toggle]")
    assert state(page) == "playing"
    assert page.get_attribute("[data-reel-toggle]", "aria-label") == "Pause reel"
    page.wait_for_function(f"window.__frames > {requested + 5}")


def test_space_toggles_and_arrows_jump_scene_markers_but_leave_the_range_alone(open_home):
    page, _ = open_home()
    pause(page)
    page.focus("[data-reel-toggle]")
    seek(page, 1)
    stops = []
    for _ in range(6):
        page.keyboard.press("ArrowRight")
        stops.append(position(page))
    assert stops == [4, 8, 12, 16, 20, 0]  # after the last scene, the loop's first frame
    page.keyboard.press("ArrowLeft")
    assert position(page) == 20  # before the first scene's grace, round to the last scene
    seek(page, 5)
    page.keyboard.press("ArrowLeft")
    assert position(page) == 4  # the start of the current scene
    seek(page, 4.1)
    page.keyboard.press("ArrowLeft")
    assert position(page) == 0  # just after a marker: the scene before
    page.keyboard.press("Space")
    assert state(page) == "playing"
    page.keyboard.press("Space")
    assert state(page) == "paused"

    # On the range, arrows keep their own fine seeking; Space still toggles.
    seek(page, 5)
    page.focus(".reel-range")
    page.keyboard.press("ArrowRight")
    assert position(page) == pytest.approx(5.1)
    page.keyboard.press("Space")
    assert state(page) == "playing"


def test_reduced_motion_shows_the_lockup_and_follows_the_setting_live(open_home):
    page, errors = open_home(reduced_motion="reduce")
    page.wait_for_timeout(300)
    assert state(page) == "paused" and position(page) == 25
    assert page.get_attribute("[data-reel-toggle]", "aria-label") == "Play reel"
    assert (
        page.evaluate("getComputedStyle(document.querySelector('.reel-controls')).opacity") == "1"
    )
    lockup = frame(page)
    seek(page, 3)
    seek(page, 25)
    assert frame(page) == lockup  # the lockup frame, not some other paused moment
    page.click("[data-reel-toggle]")
    assert state(page) == "playing"

    # Turning reduced motion on while the page is open stops it on the lockup.
    # (Wait for each change to land: two switches within one frame cancel out.)
    page.emulate_media(reduced_motion="no-preference")
    page.wait_for_function("document.querySelector('#reel').dataset.motion === 'full'")
    assert state(page) == "playing"
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_function("document.querySelector('#reel').dataset.motion === 'reduced'")
    assert state(page) == "paused" and position(page) == 25
    assert errors == []


@pytest.mark.parametrize("width, height", [(1280, 720), (1920, 1080), (390, 844)])
def test_the_lockup_logo_is_centred_across_the_hero_above_the_copy(open_home, width, height):
    page, _ = open_home(width=width, height=height, reduced_motion="reduce")  # opens on the lockup
    page.wait_for_timeout(300)
    assert position(page) == 25
    left, right, bottom, canvas_width, copy_top = page.evaluate(
        """() => { const c = document.querySelector('#reel canvas');
        const data = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let left = c.width, right = -1, bottom = -1;
        for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++)
          if (data[(y * c.width + x) * 4 + 3] > 0) {
            left = Math.min(left, x); right = Math.max(right, x); bottom = y; }
        const ratio = c.width / c.getBoundingClientRect().width;
        const badge = document.querySelector('.hero-copy .badge-pill').getBoundingClientRect();
        const reel = document.querySelector('#reel').getBoundingClientRect();
        return [left, right, bottom / ratio, c.width, badge.top - reel.top]; }"""
    )
    assert right > left  # the logo is drawn, and nothing else is
    assert abs((left + right) / 2 - canvas_width / 2) <= 2
    assert bottom < copy_top


def test_every_frame_is_a_pure_function_of_time(open_home):
    page, _ = open_home()
    pause(page)
    # Straight into the middle of a scene, with no frames drawn before it...
    seek(page, 2.7)
    direct = frame(page)
    # ...is the same picture as arriving there after playing and seeking elsewhere.
    seek(page, 0.3)
    page.click("[data-reel-toggle]")
    page.wait_for_timeout(500)
    pause(page)
    seek(page, 13.4)
    seek(page, 2.7)
    assert frame(page) == direct
    # Resizing changes the canvas, not the moment: back at the same size, the same frame.
    page.set_viewport_size({"width": 900, "height": 700})
    page.wait_for_function("document.querySelector('#reel').dataset.size.startsWith('900x')")
    assert position(page) == pytest.approx(2.7)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_function("document.querySelector('#reel').dataset.size === '1280x800'")
    assert frame(page) == direct
    # The end of the loop is its first frame.
    seek(page, 0)
    first = frame(page)
    seek(page, 26)
    assert frame(page) == first
    # Every registered segment keeps the contract and stays frozen after drawing.
    contract = page.evaluate(
        """async () => {
          const t = await import('/static/reel/timeline.js');
          return {
            markers: [...t.MARKERS], duration: t.DURATION, wrapped: t.wrap(26),
            segments: t.SEGMENTS.map(s => [s.id, s.start, s.duration, s.render.length, Object.isFrozen(s)]),
          };
        }"""
    )
    assert contract == {
        "markers": [0, 4, 8, 12, 16, 20],
        "duration": 26,
        "wrapped": 0,
        "segments": [
            ["workspace", 0, 4, 3, True],
            ["toolbox", 4, 4, 3, True],
            ["animation", 8, 4, 3, True],
            ["renderer", 12, 4, 3, True],
            ["world", 16, 4, 3, True],
            ["logic", 20, 4, 3, True],
            ["lockup", 24, 2, 3, True],
        ],
    }


def test_it_pauses_off_screen_and_never_autoplays_in_a_hidden_tab(open_home):
    page, _ = open_home(init="window.__startHidden = true;" + CONTROL_VISIBILITY)
    page.wait_for_timeout(400)
    assert state(page) == "paused"  # loaded in a background tab: no autoplay
    page.evaluate("window.__setVisibility('visible')")
    assert state(page) == "playing"
    page.evaluate("window.__setVisibility('hidden')")
    assert state(page) == "paused"
    page.evaluate("window.__setVisibility('visible')")

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_function("document.querySelector('#reel').dataset.state === 'paused'")
    requested = frames_requested(page)
    page.wait_for_timeout(400)
    assert frames_requested(page) == requested
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("document.querySelector('#reel').dataset.state === 'playing'")


def test_phone_width_is_compact_with_no_sideways_scroll(open_home):
    page, errors = open_home(width=360, height=740, scale=2, has_touch=True, is_mobile=True)
    assert page.evaluate("document.documentElement.scrollWidth") <= 360
    assert page.get_attribute("#reel", "data-size").startswith("360x")
    assert (
        page.evaluate("getComputedStyle(document.querySelector('.reel-controls')).opacity") == "1"
    )
    # The copy starts below the compact workspace.
    badge_top = page.evaluate(
        "document.querySelector('#hero .badge-pill').getBoundingClientRect().top"
    )
    assert badge_top >= 108 + (360 - 32) * 0.62
    assert errors == []


def test_without_a_canvas_the_capture_shows_and_the_controls_stay_hidden(open_home):
    page, errors = open_home(
        init="HTMLCanvasElement.prototype.getContext = () => null;", wait_ready=False
    )
    page.wait_for_selector("#reel[data-fallback]", state="attached")
    assert page.is_visible(".reel-fallback img")
    assert not page.is_visible(".reel-canvas") and not page.is_visible(".reel-controls")
    assert errors == []
