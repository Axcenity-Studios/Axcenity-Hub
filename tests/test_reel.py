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
DRAWING = REEL / "drawing"
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
    for words in (
        "Scene View",
        "Explorer",
        "Properties",
        "Console",
        "pointer",
        "drags",
        "second monitor",
        "third",
        "Terrain and Assets",
        "logo",
    ):
        assert words in description, words
    assert "Illustrative" in content.MEDIA["reel"].caption


def test_the_description_walks_through_every_later_scene_in_order():
    description = content.MEDIA["reel"].alt
    steps = [
        "Toolbox",
        "rock texture",
        "Animation tab",
        "Wave clip",
        "dope sheet",
        "ray-traced render",
        "Raise / Lower",
        "Scatter",
        "When Touched",
        "Spawn Decal",
        "Luau",
        "Axcenity logo",
    ]
    places = [description.find(step) for step in steps]
    assert -1 not in places, [s for s, p in zip(steps, places, strict=True) if p == -1]
    assert places == sorted(places)
    assert "about 26 seconds" in description


def test_the_spoken_position_names_every_segment():
    segments = content.MEDIA["reel"].labels["segments"]
    assert list(segments) == [entry[0] for entry in REGISTERED]
    assert [segments[entry[0]] for entry in REGISTERED[:-1]] == [
        f"Scene {number}, {name}"
        for number, name in enumerate(
            ["Workspace", "Toolbox", "Animation", "Renderer", "World", "Logic"], start=1
        )
    ]


def test_the_wipe_draws_a_renderer_derivative_that_is_never_upscaled(hero):
    """The renderer scene's lit end is one of the capture's own derivatives, wide enough
    that covering the Scene View (at most ~850 CSS px wide, pushed in) at 2x needs no
    upscaling."""
    src = re.search(r'data-capture="/static/([^"]+)"', hero).group(1)
    derivative = next(d for d in content.MEDIA["renderer"].derivatives if d.path == src)
    assert derivative.width >= 2 * 850
    assert "most ~850 CSS px wide" in _js(DRAWING / "renderer.js")


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
    assert f'src="/static/{capture.fallback.path}"' in fallback and 'loading="lazy"' in fallback
    assert f'sizes="{capture.display["hero"].sizes}"' in fallback
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


DEMO = content.BackdropVideo(
    "marketing/media/demo.mp4", "capture", "Engine capture · Demo", "Recorded in the editor"
)


def test_there_is_no_backdrop_video_until_one_is_configured(hero):
    assert content.HOME_HERO["backdrop"] is None
    assert "<video" not in hero and "data-backdrop" not in hero


def test_a_backdrop_video_loops_muted_behind_the_canvas_with_its_caption(client, monkeypatch):
    monkeypatch.setitem(content.HOME_HERO, "backdrop", DEMO)
    html = client.get(reverse("marketing:home")).content.decode()
    reel = html.split('<figure id="reel"', 1)[1].split("</figure>", 1)[0]
    assert "data-backdrop" in reel.split(">", 1)[0]
    video = reel.split("<video", 1)[1].split("</video>", 1)[0]
    # The player starts it, so it obeys Pause, reduced motion and visibility: never autoplay.
    for attribute in ("muted", "loop", "playsinline", 'aria-hidden="true"'):
        assert attribute in video
    assert "autoplay" not in video
    assert '<source src="/static/marketing/media/demo.mp4" type="video/mp4">' in video
    assert reel.index("<video") < reel.index("<canvas")
    assert f'<p class="media-cap micro reel-backdrop-cap">{escape(DEMO.caption)}</p>' in reel
    player = _js(REEL / "player.js")
    assert "backdrop.play()" in player and "backdrop.pause()" in player
    # It shows only with the live reel, under the canvas and lighter scrims.
    assert ".reel-canvas { position: relative;" in SOURCE
    assert ".reel[data-backdrop]::after" in SOURCE
    assert ".reel:not([data-live]) > .reel-backdrop," in SOURCE


def test_a_backdrop_video_is_labelled_for_what_it_is():
    with pytest.raises(ValueError):  # a capture's caption says so
        content.BackdropVideo("a.mp4", "capture", "Illustrative · demo", "p")
    with pytest.raises(ValueError):
        content.BackdropVideo("a.mp4", "screenshot", "Engine capture", "p")
    with pytest.raises(ValueError):  # a format browsers play
        content.BackdropVideo("a.mov", "capture", "Engine capture", "p")
    assert content.BackdropVideo("a.webm", "capture", "Engine capture", "p").mime == "video/webm"


def test_the_controls_show_on_focus_when_paused_and_on_touch():
    assert (
        '.reel-controls:focus-within, .reel-controls[data-intent="paused"] { opacity: 1; }'
        in SOURCE
    )
    assert "html[data-pointer] .hero:hover .reel-controls { opacity: 1; }" in SOURCE
    assert "@media (hover: none) { .reel-controls { opacity: 1; } }" in SOURCE


# ---------- The scene contract, as written ----------

SCENE_FILES = sorted(SCENES.glob("*.js"))
# The feature pillars' loops follow the same contract (tests/test_media.py).
LOOP_FILES = sorted(
    path for path in (REEL / "loops").glob("*.js") if path.stem not in {"main", "player"}
)
# Everything a scene or loop draws with: the scenes, the loops and their drawing helpers.
PURE_FILES = SCENE_FILES + LOOP_FILES + sorted(DRAWING.glob("*.js"))
REGISTERED = [
    ("workspace", 0, 4),
    ("toolbox", 4, 4),
    ("animation", 8, 4),
    ("renderer", 12, 4),
    ("world", 16, 4),
    ("logic", 20, 4),
    ("lockup", 24, 2),
]


def test_the_timeline_registers_every_scene_module_in_order():
    timeline = _js(REEL / "timeline.js")
    imports = re.findall(r'^import (\w+) from "\./scenes/(\w+)\.js";$', timeline, re.M)
    assert [name for name, _ in imports] == [entry[0] for entry in REGISTERED]
    assert (
        "export const SCENES = Object.freeze([workspace, toolbox, animation, renderer, world, logic]);"
        in timeline
    )
    assert "export const OUTRO = lockup;" in timeline
    assert "export const DURATION = 26;" in timeline
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


@pytest.mark.parametrize("path", PURE_FILES, ids=lambda path: f"{path.parent.name}/{path.stem}")
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
    for path in PURE_FILES:
        used |= set(re.findall(r"colors\.(\w+)", _js(path)))
    assert used and used <= names, used - names


def test_only_the_renderer_wipes_scan_line_draws_with_the_accent():
    """The accent has fixed uses (docs/frontend/theme.md); on the canvas it's the scan line."""
    drawing_with_it = {path.name for path in PURE_FILES if "colors.accent" in _js(path)}
    assert drawing_with_it == {"renderer.js"}


def test_the_pixel_ratio_is_capped_at_two_and_scenes_draw_in_logical_pixels():
    canvas = _js(REEL / "canvas.js")
    assert "export const MAX_PIXEL_RATIO = 2;" in canvas
    assert (
        "g.setTransform(canvas.width / size.width, 0, 0, canvas.height / size.height, 0, 0);"
        in canvas
    )
    assert "export const COMPACT_BELOW = 640;" in canvas


def test_compact_mode_reserves_the_same_space_above_the_copy():
    layout = _js(DRAWING / "layout.js")
    assert "export const COMPACT_TOP = 108;" in layout
    assert "export const COMPACT_ASPECT = 0.62;" in layout
    assert (
        "@media (width < 40rem) { .hero-copy { padding-top: calc(108px - 4rem + (100vw - 2rem) * 0.62 + 1.5rem); } }"
        in SOURCE
    )


# ---------- Fidelity to the editor ----------

# crates/editor/src/layout.rs default_dock, with each pane's Pane::label.
EDITOR_DEFAULT_DOCK = {
    "scene": ["Scene View", "Animation", "UI Designer"],
    "explorer": ["Explorer"],
    "properties": ["Properties", "Terrain"],
    "console": ["Console", "Assets", "Profiler"],
}

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


def test_the_dock_is_the_editors_default_layout_with_its_pane_names():
    assert content.MEDIA["reel"].labels["tabs"] == EDITOR_DEFAULT_DOCK


def test_the_properties_pane_shows_the_editors_sections_for_a_part():
    """crates/editor/src/properties.rs: Data first, then the groups in panel order
    (properties/groups.rs), each property in its group; the values are Part's defaults
    (crates/core/src/class.rs) for an anchored 8 × 1 × 8 Pad."""
    pane = content.MEDIA["reel"].labels["properties"]
    assert (pane["name"], pane["class"], pane["filter"]) == ("Pad", "Part", "Filter properties")
    sections = {title: [row[0] for row in rows] for title, rows in pane["sections"]}
    assert list(sections) == ["Data", "Appearance", "Behavior", "Part"]
    assert sections["Data"] == ["Name"]
    assert set(sections["Appearance"]) <= {"Color", "Material", "Transparency"}
    assert set(sections["Behavior"]) <= {"Locked", "Anchored", "CanCollide", "CanTouch"}
    assert set(sections["Part"]) <= {"Shape", "Position", "Orientation", "Size"}
    values = {row[0]: row[1] for _, rows in pane["sections"] for row in rows}
    assert values["Color"] == "163, 163, 163" and values["Material"] == "Plastic"


def test_the_console_uses_the_editors_messages():
    pane = content.MEDIA["reel"].labels["console"]
    assert pane["prompt"] == "Lua, or a command such as help"  # console.rs hint
    opened = pane["lines"][0][1]
    # app/session.rs: Opened "<name>" from `<folder>`: N objects, N script(s). Press Play (F5) to run it.
    assert re.fullmatch(
        r'Opened "\w+" from `\w+`: \d+ objects, \d+ scripts?\. Press Play \(F5\) to run it\.',
        opened,
    )
    assert content.MEDIA["reel"].labels["window"].endswith(" - Axcenity Editor")


@pytest.mark.parametrize(("token", "value"), EDITOR_DARK_THEME.items())
def test_the_dark_tokens_the_reel_draws_with_are_the_editors_dark_theme(token, value):
    theme = SOURCE.split("@theme static {", 1)[1].split("\n}", 1)[0]
    assert f"--color-{token}: {value};" in theme


def test_every_font_the_scenes_draw_with_is_loaded_before_the_first_ready_frame():
    """A face drawn before it has loaded paints in a fallback first, so the same moment
    would look different on its first draw: the player loads every one up front."""
    loaded = set(re.findall(r"'(\d{3}) \d+px \"([^\"]+)\"'", _js(REEL / "canvas.js")))
    used = set()
    for path in PURE_FILES:
        used |= set(re.findall(r'font\((\d{3}), [^,]+, "([^"]+)"\)', _js(path)))
    assert used and used <= loaded, used - loaded
