"""The showcase reel without a browser: its markup and fallbacks, the scene contract as
written in the modules, and its fidelity to the editor's sources.

The behaviour (playback, keyboard, determinism, pausing) is checked in a real browser by
tests/test_reel_browser.py.
"""

import json
import re

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils.html import escape

from marketing import content

pytestmark = pytest.mark.django_db

REEL = settings.BASE_DIR / "static" / "reel"
SCENES = REEL / "scenes"
SOURCE = (settings.BASE_DIR / "styles" / "source.css").read_text(encoding="utf-8")


def _js(path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture
def hero(client):
    html = client.get(reverse("marketing:home")).content.decode()
    return html.split('id="hero"', 1)[1].split("</section>", 1)[0]


# ---------- Markup and accessibility ----------


def test_the_hero_holds_the_reel_with_its_caption_and_description(hero):
    reel = content.MEDIA["reel"]
    assert '<figure id="reel" class="reel" data-reel' in hero
    assert '<canvas class="reel-canvas" aria-hidden="true"></canvas>' in hero
    assert f'<figcaption class="media-cap micro">{escape(reel.caption)}</figcaption>' in hero
    assert f'<p id="reel-description" class="sr-only">{escape(reel.alt)}</p>' in hero


def test_the_description_explains_the_workspace_and_its_undocking():
    description = content.MEDIA["reel"].alt
    for words in ("Scene View", "Explorer", "Properties", "undocks", "second monitor", "logo"):
        assert words in description, words
    assert "Illustrative" in content.MEDIA["reel"].caption


def test_the_controls_are_a_labelled_button_and_range_hidden_until_the_reel_mounts(hero):
    labels = content.REEL_CONTROLS
    controls = hero.split('id="reel-controls"', 1)[1]
    assert f'role="group" aria-label="{labels["group"]}"' in controls.split(">", 1)[0]
    assert controls.split(">", 1)[0].rstrip().endswith("hidden")
    button = re.search(r"<button [^>]+>", controls).group()
    assert 'type="button"' in button and f'aria-label="{labels["play"]}"' in button
    assert 'aria-keyshortcuts="Space ArrowLeft ArrowRight"' in button
    rng = re.search(r'<input class="reel-range"[^>]+>', controls).group()
    assert 'type="range"' in rng and f'aria-label="{labels["scrub"]}"' in rng


def test_the_reels_words_come_from_the_content_module(hero):
    data = re.search(r'<script id="reel-labels" type="application/json">(.*?)</script>', hero, re.S)
    assert json.loads(data.group(1)) == json.loads(json.dumps(content.MEDIA["reel"].labels))


def test_the_reel_loads_as_a_versioned_module(hero):
    assert re.search(r'<script type="module" src="/static/reel/main\.js\?v=\d+"', hero)


def test_without_the_reel_the_renderer_capture_shows(hero):
    """No JavaScript, no ES modules or no 2D canvas: the capture shows, the controls don't."""
    fallback = hero.split('<figure class="reel-fallback">', 1)[1].split("</figure>", 1)[0]
    capture = content.MEDIA["renderer"]
    assert f'src="/static/{capture.src}"' in fallback and 'loading="lazy"' in fallback
    assert escape(capture.caption) in fallback
    # Only the inline probe (modules and a 2D canvas) hides it before layout; main.js
    # then marks the reel live, or falls back.
    assert (
        '"noModule" in HTMLScriptElement.prototype && probe.getContext && probe.getContext("2d")'
        in hero
    )
    assert (
        ".reel[data-live] > .reel-fallback, .reel[data-pending] > .reel-fallback { display: none; }"
        in SOURCE
    )
    assert (
        ".reel:not([data-live]) > .reel-canvas, .reel:not([data-live]) > figcaption { display: none; }"
        in SOURCE
    )
    main = _js(REEL / "main.js")
    assert 'reel.dataset.fallback = ""' in main and "controls.hidden = true" in main
    assert ".catch(fallBack)" in main


def test_the_controls_show_on_focus_when_paused_and_on_touch():
    assert (
        '.reel-controls:focus-within, .reel-controls[data-intent="paused"] { opacity: 1; }'
        in SOURCE
    )
    assert "html[data-pointer] .hero:hover .reel-controls { opacity: 1; }" in SOURCE
    assert "@media (hover: none) { .reel-controls { opacity: 1; } }" in SOURCE


# ---------- The scene contract, as written ----------

SCENE_FILES = sorted(SCENES.glob("*.js"))
REGISTERED = [
    ("workspace", 0, 4),
    ("renderer", 4, 4),
    ("world", 8, 4),
    ("logic", 12, 4),
    ("lockup", 16, 2),
]


def test_the_timeline_registers_every_scene_module_in_order():
    timeline = _js(REEL / "timeline.js")
    imports = re.findall(r'^import (\w+) from "\./scenes/(\w+)\.js";$', timeline, re.M)
    assert [name for name, _ in imports] == [entry[0] for entry in REGISTERED]
    assert "export const SCENES = Object.freeze([workspace, renderer, world, logic]);" in timeline
    assert "export const OUTRO = lockup;" in timeline
    assert "export const DURATION = 18;" in timeline
    assert {path.stem for path in SCENE_FILES} == {entry[0] for entry in REGISTERED}


@pytest.mark.parametrize(("name", "start", "duration"), REGISTERED)
def test_each_scene_satisfies_the_contract(name, start, duration):
    source = _js(SCENES / f"{name}.js")
    assert re.search(rf"^const START = {start};$", source, re.M)
    assert re.search(rf"^const DURATION = {duration};$", source, re.M)
    assert re.search(
        rf'export default Object\.freeze\(\{{\n  id: "{name}",\n  start: START,\n'
        r"  duration: DURATION,\n  render\(context, time, size\) \{",
        source,
    )


@pytest.mark.parametrize("path", SCENE_FILES, ids=lambda path: path.stem)
def test_scenes_hold_no_state_and_read_no_clock_or_device(path):
    """A scene is a pure function of (context, time, size): nothing at module level
    changes, and it never reads the real time, randomness or physical pixels."""
    source = _js(path)
    assert not re.search(r"^(let|var) ", source, re.M), "module-level state"
    for banned in (
        "Math.random",
        "Date.",
        "performance.",
        "requestAnimationFrame",
        "devicePixelRatio",
        "canvas.width",
        "canvas.height",
        "shadowBlur",  # device pixels, not logical ones
        "window.",
        "document.",
    ):
        assert banned not in source, banned


@pytest.mark.parametrize("path", sorted(REEL.rglob("*.js")), ids=lambda path: path.name)
def test_the_reel_has_no_colours_of_its_own(path):
    """Every colour comes from the site's tokens (canvas.js readPalette)."""
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|\b(rgb|hsl)a?\(", _js(path))


def test_scenes_use_only_the_tokens_the_canvas_reads():
    canvas = _js(REEL / "canvas.js")
    tokens = re.search(r"const TOKENS = \[(.*?)\];", canvas, re.S).group(1)
    names = {
        re.sub(r"-(\w)", lambda m: m.group(1).upper(), name)
        for name in re.findall(r'"([\w-]+)"', tokens)
    }
    used = set()
    for path in SCENE_FILES:
        used |= set(re.findall(r"colors\.(\w+)", _js(path)))
    assert used and used <= names, used - names


def test_the_pixel_ratio_is_capped_at_two_and_scenes_draw_in_logical_pixels():
    canvas = _js(REEL / "canvas.js")
    assert "export const MAX_PIXEL_RATIO = 2;" in canvas
    assert (
        "g.setTransform(canvas.width / size.width, 0, 0, canvas.height / size.height, 0, 0);"
        in canvas
    )
    assert "export const COMPACT_BELOW = 640;" in canvas


def test_compact_mode_reserves_the_same_space_above_the_copy():
    workspace = _js(SCENES / "workspace.js")
    assert "export const COMPACT_TOP = 108;" in workspace
    assert "export const COMPACT_ASPECT = 0.62;" in workspace
    assert (
        "@media (width < 40rem) { .hero-copy { padding-top: calc(108px - 4rem + (100vw - 2rem) * 0.62 + 1.5rem); } }"
        in SOURCE
    )


# ---------- Fidelity to the editor ----------

# crates/editor/src/layout.rs, Pane::label.
EDITOR_PANE_LABELS = {"scene": "Scene View", "explorer": "Explorer", "properties": "Properties"}

# crates/editor-kit/src/theme.rs, ThemeChoice::Dark's ThemeTokens, by site token.
EDITOR_DARK_THEME = {
    "app": "#171717",  # app_bg
    "panel": "#1E1E1E",
    "surface": "#242424",
    "elevated": "#292929",
    "inset": "#191919",
    "control": "#2A2A2A",
    "control-hover": "#323232",
    "control-active": "#3A3A3A",
    "line": "#303030",  # border
    "line-strong": "#424242",  # border_strong
    "fg": "#E8E8EA",  # text
    "fg-strong": "#FAFAFA",
    "fg-secondary": "#A1A1AA",
    "fg-weak": "#8E8E96",
    "fg-muted": "#63636B",
}


def test_the_panels_have_the_editors_names():
    assert content.MEDIA["reel"].labels["panels"] == EDITOR_PANE_LABELS


@pytest.mark.parametrize(("token", "value"), EDITOR_DARK_THEME.items())
def test_the_dark_tokens_the_reel_draws_with_are_the_editors_dark_theme(token, value):
    theme = SOURCE.split("@theme {", 1)[1].split("\n}", 1)[0]
    assert f"--color-{token}: {value};" in theme
