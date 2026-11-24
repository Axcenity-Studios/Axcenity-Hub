"""The media pipeline and the animated recreations, without a browser.

The derivatives on disk and the manifest's sizes are checked in tests/test_home.py; the
loops' behaviour (playing, pausing, reduced motion, sharpness) in
tests/test_media_browser.py.
"""

import json
import re

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import reverse
from django.utils.html import escape
from PIL import Image

from marketing import content, media

pytestmark = pytest.mark.django_db

LOOPS = settings.BASE_DIR / "static" / "reel" / "loops"
SOURCE_CSS = (settings.BASE_DIR / "styles" / "source.css").read_text(encoding="utf-8")
ANIMATED = [item for item in content.MEDIA.values() if item.loop]


def _js(name: str) -> str:
    return (LOOPS / f"{name}.js").read_text(encoding="utf-8")


@pytest.fixture
def home(client):
    return client.get(reverse("marketing:home")).content.decode()


# The pillars' loops show inline and on the stage; each section's loop once, in its section.
SECTION_LOOPS = {"toolbox": "toolbox", "wipe": "community", "animation": "start"}


# ---------- The pipeline ----------


@pytest.fixture
def fake_source(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    Image.new("RGB", (1300, 731), (40, 60, 80)).save(sources / "shot.png")
    return sources, tmp_path / "out"


def test_widths_never_exceed_the_source():
    assert media.widths_for(2560) == (640, 960, 1280, 1920, 2560)
    assert media.widths_for(1300) == (640, 960, 1280)
    assert media.widths_for(500) == (500,)


def test_build_writes_every_format_at_every_width_in_proportion(fake_source):
    sources, out = fake_source
    written = media.build("shot", "shot.png", (1300, 731), sources_dir=sources, output_dir=out)
    assert len(written) == len(media.FORMATS) * 3
    for derivative in media.derivatives("shot", (1300, 731)):
        path = out / derivative.path.removeprefix(f"{media.STATIC_PREFIX}/")
        with Image.open(path) as image:
            assert image.format == derivative.format.pillow
            assert image.size == (derivative.width, round(derivative.width * 731 / 1300))
    assert sorted(p.name for p in sources.iterdir()) == ["shot.png"]  # the source is untouched


def test_build_is_idempotent_and_force_rewrites(fake_source):
    sources, out = fake_source
    media.build("shot", "shot.png", (1300, 731), sources_dir=sources, output_dir=out)
    assert media.build("shot", "shot.png", (1300, 731), sources_dir=sources, output_dir=out) == []
    forced = media.build(
        "shot", "shot.png", (1300, 731), sources_dir=sources, output_dir=out, force=True
    )
    assert len(forced) == 9


def test_build_refuses_a_source_whose_size_disagrees_with_the_manifest(fake_source):
    sources, out = fake_source
    with pytest.raises(ValueError, match="1300, 731"):
        media.build("shot", "shot.png", (2560, 1440), sources_dir=sources, output_dir=out)
    assert not out.exists()


def test_make_media_reports_each_capture_and_writes_nothing_when_current(capsys):
    call_command("make_media")
    output = capsys.readouterr().out
    for item in content.MEDIA.values():
        if item.source:
            assert f"{item.key}: 0 of {len(item.derivatives)} written" in output
    assert "Done: 0 files written." in output


# ---------- The loops as written ----------


def test_every_loop_module_is_registered_once():
    main = _js("main")
    registered = re.findall(r'^  (\w+): \(\) => import\("\./(\w+)\.js"\),$', main, re.M)
    assert [name for name, _ in registered] == [file for _, file in registered]
    assert set(name for name, _ in registered) == set(content.LOOPS)
    assert {item.loop for item in ANIMATED} == set(content.LOOPS)


@pytest.mark.parametrize("name", content.LOOPS)
def test_each_loop_satisfies_the_contract(name):
    """The reel's scene contract, with the loop's length and its reduced-motion still."""
    source = _js(name)
    duration = float(re.search(r"^const DURATION = ([\d.]+);$", source, re.M).group(1))
    still = float(re.search(r"^const STILL = ([\d.]+);$", source, re.M).group(1))
    assert 8 <= duration <= 16 and 0 < still < duration
    assert re.search(
        rf'export default Object\.freeze\(\{{\n  id: "{name}",\n  duration: DURATION,\n  still: STILL,\n'
        r"  render(\(context, time, size\) \{|,\n)",
        source,
    )
    assert "const COMPACT_BELOW = 480;" in source  # each has a phone layout


def test_the_player_runs_only_when_wanted_on_screen_visible_and_current():
    player = _js("player")
    assert "const VISIBLE_SHARE = 0.3;" in player
    assert (
        '!userPaused &&\n      onScreen &&\n      document.visibilityState === "visible" &&\n'
        '      (!stageItem || stageItem.hasAttribute("data-on"))' in player
    )
    # Reduced motion: no autoplay, the still frame, followed live.
    assert "let userPaused = reduce.matches;" in player
    assert "let time = reduce.matches ? loop.still : 0;" in player
    assert "if (reduce.matches) time = loop.still;" in player
    # While it isn't running, no animation frame is requested.
    assert "if (raf) cancelAnimationFrame(raf);" in player


# ---------- Markup and fallbacks ----------


@pytest.mark.parametrize("item", ANIMATED, ids=lambda item: item.key)
def test_each_loop_has_its_canvas_fallback_description_and_button(home, item):
    section = SECTION_LOOPS.get(item.key, "features")
    html = home.split(f'id="{section}"', 1)[1].split("</section>", 1)[0]
    figures = re.findall(
        rf'<figure class="media[^"]*" data-loop="{item.loop}" data-labels="([^"]*)"[^>]*>(.*?)</figure>',
        html,
        re.S,
    )
    assert len(figures) == (1 if item.key in SECTION_LOOPS else 2)
    for labels, body in figures:
        assert json.loads(
            labels.replace("&quot;", '"').replace("&#x27;", "'").replace("&amp;", "&")
        ) == (json.loads(json.dumps(item.labels)))
        assert f'<p class="sr-only loop-description">{escape(item.alt)}</p>' in body
        assert '<canvas class="loop-canvas" aria-hidden="true"></canvas>' in body
        assert '<div class="loop-fallback">' in body and escape(item.fallback_alt) in body
        button = re.search(r"<button [^>]+>", body).group()
        controls = content.LOOP_CONTROLS
        assert 'type="button"' in button and button.rstrip(">").rstrip().endswith("hidden")
        assert f'aria-label="{controls["pause"]}"' in button
        assert f'data-play-label="{controls["play"]}"' in button
        assert f'<figcaption class="media-cap micro">{escape(item.caption)}</figcaption>' in body


def test_the_loops_load_as_one_versioned_module(client):
    html = client.get(reverse("marketing:home")).content.decode()
    assert (
        len(re.findall(r'<script type="module" src="/static/reel/loops/main\.js\?v=\d+">', html))
        == 1
    )


def test_a_loop_shows_its_drawing_until_it_is_live():
    assert (
        ".media[data-loop]:not([data-live]) > .loop-canvas, "
        ".media[data-loop]:not([data-live]) > .loop-description { display: none; }" in SOURCE_CSS
    )
    assert ".media[data-live] > .loop-fallback { display: none; }" in SOURCE_CSS
    assert ".loop-button[hidden] { display: none; }" in SOURCE_CSS
    assert "toggle.hidden = false;" in _js("player") and 'figure.dataset.live = "";' in _js(
        "player"
    )


def test_illustrative_recreations_are_never_labelled_as_captures():
    for item in ANIMATED:
        assert item.kind == "illustrative" and item.caption.startswith("Illustrative")
        assert "capture" not in item.caption.lower()
    assert content.MEDIA["renderer"].caption.startswith("Engine capture")


# ---------- Fidelity to the editor ----------


def test_the_logic_nodes_are_the_block_editors():
    """crates/editor/src/block_editor/graph/nodes.rs: the titles, rows and pin types of
    When Touched (an Events node) and Spawn Decal (a Looks node)."""
    touched, decal = content.MEDIA["logic"].labels["nodes"]
    assert (touched["title"], touched["hue"]) == ("When Touched", "events")
    assert [row[0] for row in touched["rows"]] == ["Part", "Filter"]
    assert touched["outputs"] == [("", "exec"), ("Other Part", "object"), ("Player", "any")]
    assert (decal["title"], decal["hue"]) == ("Spawn Decal", "looks")
    assert [(row[0], row[2]) for row in decal["rows"]] == [
        ("", "exec"),
        ("Texture", "text"),
        ("Position", "vector"),
        ("Facing", "vector"),
        ("Size", "number"),
        ("Seconds", "number"),
    ]
    assert decal["outputs"] == [("", "exec"), ("Decal", "object")]


def test_the_logic_blocks_are_the_block_editors():
    """crates/editor/src/block_editor.rs sections(): When touched's one row and Spawn decal's
    two, with the touching part's Position as a Sensing reporter; scripts.rs mode_bar."""
    labels = content.MEDIA["logic"].labels
    assert labels["views"] == ["Code", "Blocks", "Graph"]
    assert labels["switch_hint"] == "Switch any time: the script runs the same either way."
    hat, decal = labels["stack"]
    assert (hat["category"], decal["category"]) == ("events", "looks")
    words = lambda row: [part[1] for part in row if part[0] == "label"]  # noqa: E731
    assert words(hat["rows"][0]) == ["when", "is touched"]
    assert [words(row) for row in decal["rows"]] == [
        ["spawn decal", "at", "facing"],
        ["size", "fading after", "seconds"],
    ]
    reporter = next(part for part in decal["rows"][0] if part[0] == "reporter")
    assert reporter[1] == "sensing" and reporter[2][-1] == [
        "reporter",
        "sensing",
        [["label", "touching part"]],
    ]
    # The values are the Graph's and the Luau's.
    assert ["text", "assets/textures/scorch.png"] in decal["rows"][0]
    assert ["number", "2.5"] in decal["rows"][1] and ["number", "4"] in decal["rows"][1]
    assert (
        '"assets/textures/scorch.png"' in content.LUAU_SAMPLE and "2.5, 4)" in content.LUAU_SAMPLE
    )


def test_the_logic_code_is_the_sample_the_page_shows():
    labels = content.MEDIA["logic"].labels
    assert (
        "\n".join("".join(text for _, text in line) for line in labels["lines"])
        == content.LUAU_SAMPLE
    )
    assert labels["lines"][labels["compact_from"]][0][1].startswith("part.Touched:Connect")


def test_the_terrain_loop_uses_the_studios_and_scatter_panes_words():
    labels = content.MEDIA["terrain"].labels
    assert labels["panes"] == ["Terrain", "Scatter"]  # layout.rs Pane::label
    assert labels["tabs"] == ["Sculpt", "Materials", "Terrain"]  # terrain_studio/tabs.rs
    assert labels["tools"][0] == "Raise / Lower"  # terrain_tool.rs, the Sculpt tab
    assert [name for name, _, _ in labels["brush"]] == ["Size", "Strength", "Falloff"]
    assert (labels["paint"], labels["painting"]) == ("Paint", "Stop painting")  # scatter_pane.rs
    assert {name for name, _ in labels["items"]} <= {"Grass", "Bush", "Flower", "Tree"}


def test_the_editor_loop_uses_the_default_dock_and_reset_layout():
    labels = content.MEDIA["editor"].labels
    assert labels["tabs"] == content.EDITOR_DOCK
    assert labels["menus"] == ["File", "Edit", "View", "Viewport", "Debug", "Help"]
    assert (labels["panels"], labels["reset"]) == ("Panels", "Reset Layout")  # chrome/menus.rs
