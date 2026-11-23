"""The Cinematic Home: sections, copy as data, media manifest, motion fallbacks and honesty."""

import dataclasses
import json
import re
import struct
from html.parser import HTMLParser

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.urls import reverse
from django.utils.html import escape

from marketing import content, drawings

pytestmark = pytest.mark.django_db

SOURCE = (settings.BASE_DIR / "styles" / "source.css").read_text(encoding="utf-8")
HOME_JS = (settings.BASE_DIR / "static" / "js" / "home.js").read_text(encoding="utf-8")
HOME_BLOCKS = [
    content.HOME_HERO,
    content.HOME_FEATURES,
    content.HOME_WORKFLOW,
    content.HOME_FACTS,
    content.HOME_TOOLBOX,
    content.HOME_COMMUNITY,
    content.HOME_FINAL,
]
# Fields that are data about the copy rather than copy a visitor reads.
NOT_COPY = {"key", "kind", "provenance", "src", "drawn", "url_name", "external", "fragment", "code"}
# Shared shell labels rendered by partials, not by the Home's own content.
SHELL_LABELS = {"Soon"}


@pytest.fixture
def home(client):
    response = client.get(reverse("marketing:home"))
    assert response.status_code == 200
    return response.content.decode()


def _copy(value) -> list[str]:
    """Every string a visitor reads in a content value (labels, prose, captions, alt text)."""
    if isinstance(value, str):
        return [value]
    if dataclasses.is_dataclass(value):
        return [
            text
            for f in dataclasses.fields(value)
            if f.name not in NOT_COPY
            for text in _copy(getattr(value, f.name))
        ]
    if isinstance(value, dict):
        return [text for key, item in value.items() if key not in NOT_COPY for text in _copy(item)]
    if isinstance(value, list | tuple):
        return [text for item in value for text in _copy(item)]
    return []


HOME_COPY = {text for block in HOME_BLOCKS for text in _copy(block)}


class _VisibleText(HTMLParser):
    """Collects the text a sighted visitor reads inside <main>: not attributes, not the
    screen-reader-only labels, not scripts or data, and not code (checked on its own)."""

    VOID = {"img", "br", "hr", "input", "meta", "link", "source", "path", "i"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.chunks: list[str] = []
        self.code: list[str] = []
        self.in_main = False

    def _skipping(self) -> bool:
        return any(skip for _, skip in self.stack)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "main":
            self.in_main = True
        if tag in self.VOID:
            return
        skip = "sr-only" in (attrs.get("class") or "").split() or tag in {"pre", "script", "style"}
        self.stack.append((tag, skip))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False
        if tag in self.VOID:
            return
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if not self.in_main:
            return
        if any(t in {"script", "style"} for t, _ in self.stack):
            return
        if any(t == "pre" for t, _ in self.stack):
            self.code.append(data)
        elif not self._skipping() and data.strip():
            self.chunks.append(" ".join(data.split()))


def _visible(html: str) -> _VisibleText:
    parser = _VisibleText()
    parser.feed(html)
    return parser


def _section(html: str, section_id: str) -> str:
    return html.split(f'id="{section_id}"', 1)[1].split("</section>", 1)[0]


# ---------- Sections ----------


def test_home_has_every_section_in_order(home):
    order = ["hero", "features", "workflow", "facts", "toolbox", "community", "start"]
    positions = [home.index(f'<section id="{section_id}"') for section_id in order]
    assert positions == sorted(positions)


def test_features_is_in_the_nav_and_points_at_the_section(home):
    features = next(link for link in content.NAV_LINKS if link.label == "Features")
    assert features.href == "/#features"
    assert 'id="features"' in home


def test_every_section_renders_from_the_content_module(home):
    for text in HOME_COPY:
        # The reel's words reach the page as JSON for its canvas (json_script), not as HTML.
        assert escape(text) in home or json.dumps(text)[1:-1] in home, text


def test_the_visible_prose_and_labels_come_from_the_content_module(home):
    """Every heading, paragraph, button and caption a visitor reads is content data.
    Screen-reader labels and attributes (aria-label, alt) aren't held to this."""
    stray = [chunk for chunk in _visible(home).chunks if chunk not in HOME_COPY | SHELL_LABELS]
    assert not stray, f"copy written into a template: {stray}"


def test_the_prose_check_ignores_accessibility_labels():
    page = (
        '<main><h2>Start building.</h2><span class="sr-only">Opens in a new tab</span>'
        '<button aria-label="Pause the reel">Start building.</button></main>'
    )
    assert _visible(page).chunks == ["Start building.", "Start building."]


def test_the_prose_check_catches_hard_coded_copy():
    assert _visible("<main><p>Coming next week!</p></main>").chunks == ["Coming next week!"]


# ---------- The hero and its rotating headline ----------


def test_the_hero_shows_the_version_badge_and_both_calls_to_action(home):
    hero = _section(home, "hero")
    assert content.ENGINE_VERSION in hero and 'class="badge-dot"' in hero
    assert f'href="{content.RELEASES_URL}"' in hero and "btn btn-primary" in hero
    assert f'href="{content.DOCS_URL}"' in hero


def test_the_rotating_headline_shares_one_grid_cell(home):
    """Every phrase occupies the same cell, so the line is always as tall as its longest
    phrase and switching between one- and two-line phrases never moves what's below."""
    assert ".rotator { display: grid; }" in SOURCE
    assert ".rotator > span { grid-area: 1 / 1;" in SOURCE
    h1 = home.split("<h1", 1)[1].split("</h1>", 1)[0]
    rotator = re.search(
        r'<span class="rotator" data-rotator aria-hidden="true">(.*?)</span>\s*$', h1, re.S
    )
    phrases = re.findall(r"<span( data-on)?>([^<]+)</span>", rotator.group(1))
    assert [text for _, text in phrases] == content.HOME_HERO["rotating"]
    assert [on for on, _ in phrases] == [" data-on", "", "", ""]  # the first shows without JS


def test_screen_readers_hear_the_rotation_once_as_a_sentence(home):
    h1 = home.split("<h1", 1)[1].split("</h1>", 1)[0]
    assert f'<span class="sr-only">{escape(content.HOME_HERO["rotating_summary"])}</span>' in h1


# ---------- Motion fallbacks ----------


def test_reveals_never_hide_content_without_javascript():
    """Only home.js turns reveals on (html[data-reveals]), after marking what's in view."""
    for selector in re.findall(r"([^{}\n]*\[data-reveal\][^{}]*)\{", SOURCE):
        for part in selector.split(","):
            assert part.strip().startswith("html[data-reveals] "), part
    assert "if (onScreen(element)) element.dataset.in" in HOME_JS
    assert HOME_JS.index("onScreen(element)") < HOME_JS.index('root.dataset.reveals = ""')


def test_nothing_above_the_fold_waits_for_a_reveal(home):
    assert "data-reveal" not in _section(home, "hero")


def test_reduced_motion_shows_final_states():
    reduced = SOURCE.split("@media (prefers-reduced-motion: reduce) {", 1)[1].split("\n}", 1)[0]
    assert (
        "html[data-reveals] [data-reveal]:not([data-in]) { opacity: 1; transform: none; "
        "filter: none; }" in reduced
    )
    # home.js neither turns reveals on nor rotates the headline under reduced motion.
    assert "if (observes && !reduce.matches && reveals.length)" in HOME_JS
    assert "if (reduce.matches || document.hidden || phrases.length < 2) return;" in HOME_JS


def test_home_js_loads_deferred(home):
    assert re.search(r'<script src="/static/js/home\.js\?v=\d+" defer></script>', home)


# ---------- Feature pillars ----------


def test_each_pillar_has_inline_media_and_a_stage_item(home):
    features = _section(home, "features")
    pillars = content.HOME_FEATURES["pillars"]
    assert len(re.findall(r'<article id="feature-[\w-]+" class="pillar"', features)) == len(pillars)
    assert features.count('class="media pillar-media mt-8"') == len(pillars)
    assert len(re.findall(r'data-stage-item="\d"', features)) == len(pillars)
    assert 'data-stage-item="0" data-on' in features  # the first shows without JS


def test_the_stage_is_sticky_on_desktop_and_inline_media_shows_on_phones():
    desktop = SOURCE.split("@media (min-width: 64rem) {\n  .pillars", 1)[1].split("\n}", 1)[0]
    assert ".stage { position: sticky;" in desktop and ".pillar-media { display: none; }" in desktop
    assert ".stage-col { display: none; }" in SOURCE  # below lg


# ---------- Media manifest ----------


def _png_size(path: str) -> tuple[int, int]:
    with open(path, "rb") as f:
        header = f.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", header[16:24])


@pytest.mark.parametrize("media", content.MEDIA.values(), ids=lambda media: media.key)
def test_every_media_item_exists_and_is_labelled_for_what_it_is(media):
    assert media.caption.startswith(content.MEDIA_KINDS[media.kind])
    assert media.alt and media.provenance
    if media.src:
        path = finders.find(media.src)
        assert path, f"{media.src} is missing"
        assert _png_size(path) == media.source_size
    else:
        assert media.kind == "illustrative"
        get_template(media.drawn)  # raises TemplateDoesNotExist


def test_the_media_manifest_refuses_mislabelled_items():
    base = dict(key="x", alt="a", provenance="p", src="a.png", source_size=(1, 1))
    with pytest.raises(ValueError):
        content.Media(kind="capture", caption="Illustrative · drawn", **base)
    with pytest.raises(ValueError):
        content.Media(kind="screenshot", caption="Engine capture", **base)
    with pytest.raises(ValueError):
        content.Media(
            key="x", kind="capture", caption="Engine capture", alt="a", provenance="p", drawn="t"
        )
    with pytest.raises(ValueError):
        content.Media(
            key="x", kind="capture", caption="Engine capture", alt="a", provenance="p", src="a.png"
        )


def test_every_image_and_caption_on_the_page_is_in_the_manifest(home):
    files = {f"/static/{media.src}" for media in content.MEDIA.values() if media.src}
    for src in re.findall(r'<img src="([^"]+)"', _part_main(home)):
        assert src in files, src
    captions = {escape(media.caption) for media in content.MEDIA.values()}
    for caption in re.findall(r'<figcaption class="media-cap micro">([^<]+)<', home):
        assert caption in captions, caption


def test_images_carry_intrinsic_size_and_below_the_fold_ones_lazy_load(home):
    main = _part_main(home)
    for img in re.findall(r"<img [^>]+>", main):
        assert re.search(r'width="\d+" height="\d+"', img), img
    # The hero's capture is only the reel's fallback: lazy, so a browser running the reel
    # never downloads it (an inline script hides it before layout).
    hero_img = re.search(r"<img [^>]+>", _section(home, "hero")).group()
    assert 'loading="lazy"' in hero_img
    for img in re.findall(r"<img [^>]+>", _section(home, "features")):
        assert 'loading="lazy"' in img


def _part_main(html: str) -> str:
    return html.split('<main id="content"', 1)[1].split("</main>", 1)[0]


# ---------- The Luau sample and the drawings ----------


def test_the_luau_sample_is_the_real_translation_of_when_touched_spawn_decal(home):
    sample = content.LUAU_SAMPLE
    assert "part.Touched:Connect(function(otherPart)" in sample
    assert "workspace:SpawnDecal(" in sample and sample.rstrip().endswith("end)")
    logic = next(p for p in content.HOME_FEATURES["pillars"] if p.label == "Logic")
    assert "When touched → Spawn decal" in logic.body
    assert logic.media.kind == "illustrative"


def test_the_luau_sample_renders_exactly(home):
    code = "".join(_visible(home).code)
    # It renders twice: inline (phones) and on the stage (desktop).
    assert code.count(content.LUAU_SAMPLE + "\n") == 2


def test_luau_lines_rejoin_to_the_source_and_mark_keywords():
    lines = drawings.luau_lines(content.LUAU_SAMPLE)
    assert "\n".join("".join(text for _, text in line) for line in lines) == content.LUAU_SAMPLE
    kinds = {text: kind for line in lines for kind, text in line}
    assert kinds["local"] == kinds["function"] == kinds["end"] == "k"
    assert kinds['"assets/textures/scorch.png"'] == "s"
    assert lines[0][0][0] == "c"


def test_the_terrain_drawing_is_deterministic():
    drawing = drawings.terrain_wireframe()
    assert drawing.view_box == "0 0 800 500"
    assert len(drawing.grid) == 23 + 31 and len(drawing.trees) == 46
    assert drawings.terrain_wireframe.__wrapped__() == drawing


def test_drawn_media_uses_only_the_tokens(home):
    for name in ("terrain", "luau", "editor", "reel"):
        source = (
            settings.BASE_DIR / "templates" / "marketing" / "media" / f"{name}.html"
        ).read_text()
        assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|\b(fill|stroke)=\"(?!none)", source), name


# ---------- Honesty ----------


def test_copy_says_alpha_luau_free_open_source_and_the_three_desktops(home):
    text = " ".join(_visible(home).chunks)
    for phrase in ("alpha", "Luau", "Free", "open-source", "Windows, macOS and Linux"):
        assert phrase in text, phrase


def test_copy_never_claims_what_the_engine_lacks(home):
    text = " ".join(_visible(home).chunks) + " " + content.LUAU_SAMPLE
    assert not re.search(r"\bLua\b", text), "scripting is Luau, never Lua"
    assert "OnTriggerEnter" not in home, "the engine's block is When touched"
    assert not re.search(
        r"\b(iOS|Android|mobile|PlayStation|Xbox|Nintendo|WebGL|WebAssembly)\b", text
    )
