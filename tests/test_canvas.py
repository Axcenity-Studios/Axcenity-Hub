"""The animated loops' drawing kit (static/reel/) as written: the loops and their drawing
helpers are pure functions of time in the site's tokens, and they draw the editor as its
sources have it. Each loop's contract and markup are in tests/test_media.py; its behaviour
in a browser in tests/test_media_browser.py."""

import re

import pytest
from django.conf import settings

from marketing import content

KIT = settings.BASE_DIR / "static" / "reel"
DRAWING = KIT / "drawing"
SOURCE = (settings.BASE_DIR / "styles" / "source.css").read_text(encoding="utf-8")


def _js(path) -> str:
    return path.read_text(encoding="utf-8")


LOOP_FILES = sorted(
    path for path in (KIT / "loops").glob("*.js") if path.stem not in {"main", "player"}
)
# Everything a loop draws with: the loops and their drawing helpers.
PURE_FILES = LOOP_FILES + sorted(DRAWING.glob("*.js"))


def test_the_kit_holds_only_the_loops_and_their_helpers():
    """The hero's reel (its player, timeline and scenes) is gone; nothing points at it."""
    assert {path.name for path in KIT.glob("*.js")} == {"canvas.js", "easing.js"}
    assert sorted(path.name for path in KIT.iterdir() if path.is_dir()) == ["drawing", "loops"]
    for path in KIT.rglob("*.js"):
        assert "scenes/" not in _js(path) and "timeline" not in _js(path), path.name


@pytest.mark.parametrize("path", PURE_FILES, ids=lambda path: f"{path.parent.name}/{path.stem}")
def test_loops_hold_no_state_and_read_no_clock_or_device(path):
    """A loop is a pure function of (context, time, size): nothing at module level
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


@pytest.mark.parametrize("path", sorted(KIT.rglob("*.js")), ids=lambda path: path.name)
def test_the_kit_has_no_colours_of_its_own(path):
    """Every colour comes from the site's tokens (canvas.js readPalette)."""
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|\b(rgb|hsl)a?\(", _js(path))


def test_loops_use_only_the_tokens_the_canvas_reads():
    canvas = _js(KIT / "canvas.js")
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


def test_the_pixel_ratio_is_capped_at_two_and_loops_draw_in_logical_pixels():
    canvas = _js(KIT / "canvas.js")
    assert "export const MAX_PIXEL_RATIO = 2;" in canvas
    assert (
        "g.setTransform(canvas.width / size.width, 0, 0, canvas.height / size.height, 0, 0);"
        in canvas
    )


def test_every_font_the_loops_draw_with_is_loaded_before_the_first_ready_frame():
    """A face drawn before it has loaded paints in a fallback first, so the same moment
    would look different on its first draw: the player loads every one up front."""
    loaded = set(re.findall(r"'(\d{3}) \d+px \"([^\"]+)\"'", _js(KIT / "canvas.js")))
    used = set()
    for path in PURE_FILES:
        used |= set(re.findall(r'font\((\d{3}), [^,]+, "([^"]+)"\)', _js(path)))
    assert used and used <= loaded, used - loaded


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


@pytest.mark.parametrize("key", ["editor", "toolbox", "wipe", "animation"])
def test_every_editor_loop_uses_the_default_dock_and_its_pane_names(key):
    assert content.MEDIA[key].labels["tabs"] == EDITOR_DEFAULT_DOCK


def test_the_properties_pane_shows_the_editors_sections_for_a_part():
    """crates/editor/src/properties.rs: Data first, then the groups in panel order
    (properties/groups.rs), each property in its group; the values are Part's defaults
    (crates/core/src/class.rs) for an anchored 8 × 1 × 8 Pad."""
    pane = content.MEDIA["editor"].labels["properties"]
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
    labels = content.MEDIA["editor"].labels
    assert labels["console"]["prompt"] == "Lua, or a command such as help"  # console.rs hint
    opened = labels["console"]["lines"][0][1]
    # app/session.rs: Opened "<name>" from `<folder>`: N objects, N script(s). Press Play (F5) to run it.
    assert re.fullmatch(
        r'Opened "\w+" from `\w+`: \d+ objects, \d+ scripts?\. Press Play \(F5\) to run it\.',
        opened,
    )
    assert labels["window"].endswith(" - Axcenity Editor")


def test_the_toolbox_and_animation_panes_use_the_editors_words():
    """crates/editor-toolbox/src/lib.rs (kinds, the Search view) and
    crates/editor/src/animation/ (views, Record, the humanoid's bones in rig.py)."""
    toolbox = content.MEDIA["toolbox"].labels["toolbox"]
    assert toolbox["kinds"] == ["Textures", "Skies", "Models", "Sounds"]
    assert toolbox["button"] == "Toolbox" and toolbox["query"] == "rock"
    animation = content.MEDIA["animation"].labels["animation"]
    assert animation["views"] == ["Logic", "Clips & Rigging", "Sequencer"]
    assert [row.split(" · ")[0] for row in animation["rows"]] == [
        "RightUpperArm",
        "RightLowerArm",
        "Spine",
        "Head",
    ]


@pytest.mark.parametrize(("token", "value"), EDITOR_DARK_THEME.items())
def test_the_dark_tokens_the_loops_draw_with_are_the_editors_dark_theme(token, value):
    theme = SOURCE.split("@theme static {", 1)[1].split("\n}", 1)[0]
    assert f"--color-{token}: {value};" in theme
