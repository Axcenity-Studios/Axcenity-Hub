"""The axcenity theme is the only source of colour, and every colour pair is readable.

Ported from the Axcenity Toolbox's theme tests (its type colours and page glows
aren't part of the Hub), plus the Hub's one accent and a contrast check of each
real foreground/background pair the pages use, in dark and light.
"""

import re

import pytest
from django.conf import settings
from django.urls import reverse

SOURCE_CSS = settings.BASE_DIR / "styles" / "source.css"

# The editor's dark palette (Axcenity Engine, crates/editor-kit/src/theme.rs).
EDITOR_PALETTE = {
    "#171717",  # app_bg
    "#1E1E1E",  # panel
    "#242424",  # surface
    "#292929",  # elevated
    "#191919",  # inset
    "#2A2A2A",  # control
    "#323232",  # control_hover
    "#3A3A3A",  # control_active
    "#303030",  # border
    "#424242",  # border_strong
    "#E8E8EA",  # text
    "#FAFAFA",  # text_strong
    "#A1A1AA",  # text_secondary
    "#8E8E96",  # text_weak
    "#63636B",  # text_muted
    "#4CC38A",  # success
    "#E5B454",  # warning
    "#F07178",  # error
}
# The Toolbox's light storm grey.
LIGHT_PALETTE = {
    "app": "#BEC0C2",
    "panel": "#CACCCE",
    "surface": "#D3D5D7",
    "elevated": "#DCDEE0",
    "inset": "#C4C6C8",
    "control": "#BABCBE",
    "control-hover": "#B2B4B6",
    "control-active": "#A9ABAD",
    "line": "#B5B7B9",
    "line-strong": "#9FA1A3",
    "fg": "#1F2022",
    "fg-strong": "#111214",
    "fg-secondary": "#3D3F43",
    "fg-weak": "#45474B",
    "fg-muted": "#6E7075",
    "shade": "#2B2D31",
    "ink": "#18181B",
}
LIGHT_STATUS = {"success": "#145A36", "warning": "#6B4800", "error": "#931F1F"}
# The one accent: the editor's selection blue, darker on light.
ACCENT = {"dark": "#19A0FF", "light": "#0B67B8"}
ALLOWED = (
    EDITOR_PALETTE
    | {"#FFFFFF", "#000000", "#18181B", "#2B2D31"}
    | set(LIGHT_PALETTE.values())
    | set(LIGHT_STATUS.values())
    | set(ACCENT.values())
)


@pytest.fixture(scope="module")
def css():
    return SOURCE_CSS.read_text(encoding="utf-8")


def _block(css: str, opener: str) -> str:
    return css.split(opener, 1)[1].split("\n}", 1)[0]


@pytest.fixture(scope="module")
def daisy_theme(css):
    return _block(css, '@plugin "../.django_tailwind_cli/daisyui-theme.mjs" {')


@pytest.fixture(scope="module")
def light_block(css):
    return _block(css, 'html[data-scheme="light"] {')


def _tokens(block: str) -> dict[str, str]:
    return {
        name: value.upper()
        for name, value in re.findall(r"--color-([\w-]+): (#[0-9A-Fa-f]{6});", block)
    }


@pytest.fixture(scope="module")
def palettes(css, daisy_theme, light_block):
    """Every colour token's value in each mode, read from the stylesheet itself."""
    dark = _tokens(_block(css, "@theme {")) | _tokens(daisy_theme)
    return {"dark": dark, "light": dark | _tokens(light_block)}


# ---------- The palette ----------


def test_tailwind_default_palette_is_reset(css):
    assert "--color-*: initial;" in _block(css, "@theme {")


def test_daisyui_builtin_themes_are_off(css):
    assert re.search(r'@plugin "[^"]*daisyui\.mjs" \{\s*themes: false;\s*\}', css)


def test_axcenity_is_the_only_and_default_theme(css, daisy_theme):
    names = re.findall(r"^\s*name: \"([^\"]+)\";", css, re.M)
    assert names == ["axcenity"]
    assert "default: true;" in daisy_theme
    assert "color-scheme: dark;" in daisy_theme


def test_every_colour_is_in_the_axcenity_palette(css):
    stray = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{3,8}\b", css)} - ALLOWED
    assert not stray, f"colours outside the axcenity palette: {sorted(stray)}"
    assert not re.search(r"\b(rgb|rgba|hsl|hsla|oklch|oklab)\(", css)


def test_chrome_tokens_are_monochrome(palettes):
    for mode, tokens in palettes.items():
        for token in ("base-100", "base-200", "base-300", "secondary", "neutral"):
            value = tokens[token]
            r, g, b = (int(value[i : i + 2], 16) for i in (1, 3, 5))
            assert max(r, g, b) - min(r, g, b) <= 4, f"{mode} {token} {value} is not grey"


# ---------- The one accent ----------


def test_the_accent_is_the_primary_and_accent_role(palettes):
    for mode, tokens in palettes.items():
        assert tokens["primary"] == tokens["accent"] == ACCENT[mode], mode


def test_the_accent_hex_appears_only_on_its_token_lines(css):
    for line in css.splitlines():
        if any(value.lower() in line.lower() for value in ACCENT.values()):
            assert re.match(r"\s*--color-(primary|accent): #", line), line


def test_the_accent_is_used_only_by_the_badge_dot_and_the_reel_progress(css):
    """The primary button reads it through DaisyUI; Phase 4's scan line is drawn on the canvas."""
    users = [
        line.strip().split(" {", 1)[0] for line in css.splitlines() if "var(--color-accent)" in line
    ]
    assert users == [".badge-dot", ".reel-fill"]
    assert "var(--color-primary)" not in css


# ---------- Light mode ----------


def test_light_mode_is_chosen_on_html(css, light_block):
    """<html data-scheme="light"> turns the site light: the visitor's choice, or the
    system's when they chose System (base.html resolves it before first paint)."""
    assert '&, & [data-theme="axcenity"] {' in light_block
    assert "color-scheme: light;" in light_block
    # No media query of its own: System is resolved in base.html, so Light and Dark
    # can override the computer's setting.
    assert "@media (prefers-color-scheme" not in css


@pytest.mark.parametrize(("token", "hex_value"), LIGHT_PALETTE.items())
def test_light_mode_uses_the_storm_grey_palette(light_block, token, hex_value):
    assert f"--color-{token}: {hex_value};" in light_block


def test_light_mode_flips_the_contrast_tokens(light_block):
    assert "--color-ink: #18181B;" in light_block
    assert "--color-on-ink: #FFFFFF;" in light_block
    assert "--color-primary-content: #FFFFFF;" in light_block
    for status, hex_value in LIGHT_STATUS.items():
        assert f"--color-{status}: {hex_value};" in light_block


def test_light_mode_inverts_the_logo(light_block):
    assert "--logo-filter: invert(1);" in light_block


def _luminance(hex_value: str) -> float:
    channels = [int(hex_value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_light_mode_is_a_storm_grey_not_white():
    for token in ("app", "panel", "surface", "elevated", "inset"):
        assert _luminance(LIGHT_PALETTE[token]) < 0.75, token


# ---------- Contrast: every real pair, in both modes ----------
# (what, foreground token, background token). Text needs 4.5:1 (WCAG AA);
# focus rings, indicators and control edges need 3:1 (WCAG 1.4.11).
TEXT_PAIRS = [
    ("body text", "fg", "app"),
    ("body text on a panel", "fg", "panel"),
    ("headline", "fg-strong", "app"),
    ("nav link, pitch, footer link, badge text", "fg-secondary", "app"),
    ("secondary text on a panel", "fg-secondary", "panel"),
    ("current or hovered nav link", "fg-strong", "app"),
    ("Soon label, footer heading, signature", "fg-weak", "app"),
    ("Soon label on a panel", "fg-weak", "panel"),
    ("primary button", "primary-content", "primary"),
    ("primary button hovered or focused", "ink", "on-ink"),
    ("quiet button", "fg-strong", "app"),
    ("quiet button or nav icon hovered or focused", "on-ink", "ink"),
    ("status: success", "success", "app"),
    ("status: warning", "warning", "app"),
    ("status: error", "error", "app"),
    ("media caption chip", "fg-secondary", "app"),
    ("Toolbox feature title", "fg-strong", "panel"),
    ("Luau sample text", "fg", "inset"),
    ("Luau keyword", "fg-strong", "inset"),
    ("Luau string", "fg-secondary", "inset"),
    ("Luau comment", "fg-weak", "inset"),
    ("drawn editor: panel text", "fg", "panel"),
    ("drawn editor: active tab", "fg-strong", "surface"),
    ("drawn editor: selected row", "fg-strong", "control-active"),
    # The reel's canvas (static/reel/scenes) draws only these pairs, plus ones above.
    ("reel: Explorer rows", "fg-secondary", "panel"),
    ("reel: Properties names", "fg-weak", "panel"),
    ("reel: window titles", "fg-weak", "app"),
    ("reel: play and pause button", "fg-strong", "app"),
    ("reel: button hovered", "on-ink", "ink"),
]
NON_TEXT_PAIRS = [
    ("focus ring on the page", "ink", "app"),
    ("focus ring on a panel", "ink", "panel"),
    ("focus ring on a surface", "ink", "surface"),
    ("badge dot", "accent", "app"),
    ("primary button edge", "primary", "app"),
    ("current-page underline", "ink", "app"),
    ("theme switch and menu icons", "fg-secondary", "app"),
    ("workflow numeral outline", "fg-weak", "app"),
    ("drawn terrain lines", "fg-weak", "inset"),
    ("reel progress", "accent", "app"),
    ("reel scene markers", "fg-weak", "app"),
    ("reel scrubber thumb", "ink", "app"),
    ("reel viewport grid", "fg-weak", "inset"),
    ("reel viewport block", "fg-strong", "inset"),
]
PAIRS = [(*pair, 4.5) for pair in TEXT_PAIRS] + [(*pair, 3.0) for pair in NON_TEXT_PAIRS]


@pytest.mark.parametrize("mode", ["dark", "light"])
@pytest.mark.parametrize(("what", "fg", "bg", "minimum"), PAIRS, ids=[p[0] for p in PAIRS])
def test_each_pair_is_readable(palettes, mode, what, fg, bg, minimum):
    tokens = palettes[mode]
    ratio = _contrast(tokens[fg], tokens[bg])
    assert ratio >= minimum, f"{mode}: {what} ({fg} on {bg}) is {ratio:.2f}:1"


# The pairs above are the ones the code really uses: these tie each to its rule.
RULES = {
    ".nav-link {": "color: var(--color-fg-secondary);",
    "html[data-pointer] .nav-link:hover {": "color: var(--color-fg-strong);",
    '.nav-link[aria-current="page"] {': "box-shadow: inset 0 -2px 0 var(--color-ink);",
    ".nav-icon {": "color: var(--color-fg-secondary);",
    "html[data-pointer] .nav-icon:hover {": "color: var(--color-on-ink); background: var(--color-ink);",
    ".soon {": "color: var(--color-fg-weak);",
    ".footer-link {": "color: var(--color-fg-secondary);",
    ".badge-dot {": "background: var(--color-accent);",
    ".btn-quiet {": "color: var(--color-fg-strong);",
    ".btn:focus-visible {": "outline: 2px solid var(--color-ink);",
    ":focus-visible {": "outline: 2px solid var(--color-ink);",
    ".media-cap {": "color: var(--color-fg-secondary); background: var(--color-app);",
    ".flow-num {": "-webkit-text-stroke: 1px var(--color-fg-weak);",
    ".drawn-code {": "color: var(--color-fg); background: var(--color-inset);",
    ".tok-k {": "color: var(--color-fg-strong);",
    ".tok-s {": "color: var(--color-fg-secondary);",
    ".tok-c {": "color: var(--color-fg-weak);",
    ".drawn-grid {": "stroke: var(--color-fg-weak);",
    ".ed-tab[data-on] {": "background: var(--color-surface); color: var(--color-fg-strong);",
    ".ed-tree li[data-on] {": "background: var(--color-control-active); color: var(--color-fg-strong);",
    ".reel-fill {": "background: var(--color-accent);",
    ".reel-marker {": "background: var(--color-fg-weak);",
    ".reel-button {": "color: var(--color-fg-strong);",
    "html[data-pointer] .reel-button:hover {": "color: var(--color-on-ink); background: var(--color-ink);",
    ".reel-controls {": "background: var(--color-app);",
    ".reel-range::-webkit-slider-thumb {": "background: var(--color-ink);",
}


@pytest.mark.parametrize(("selector", "declaration"), RULES.items())
def test_each_pair_matches_its_rule(css, selector, declaration):
    rules = [line for line in css.splitlines() if line.strip().startswith(selector)]
    assert rules, selector
    assert any(declaration in rule for rule in rules), (selector, rules)


def test_button_hover_and_focus_invert(css):
    assert (
        "html[data-pointer] .btn:hover, .btn:focus-visible { background-color: var(--color-ink); "
        "color: var(--color-on-ink);" in css
    )
    assert (
        "html[data-pointer] .btn-primary:hover, .btn-primary:focus-visible { background-color: "
        "var(--color-on-ink); color: var(--color-ink);" in css
    )


TESTED_TEXT_TOKENS = {pair[1] for pair in TEXT_PAIRS if pair[2] in {"app", "panel"}}


@pytest.mark.django_db
def test_pages_use_only_tested_text_colours(client):
    """fg-muted, for one, is under 4.5:1 on the app background, so no text may use it."""
    html = client.get(reverse("marketing:home")).content.decode()
    classes = " ".join(re.findall(r'class="([^"]*)"', html))
    used = set(
        re.findall(r"(?<![\w-])(?:[\w-]+:)?text-((?:fg|ink|on-ink|accent|primary)[\w-]*)", classes)
    )
    assert used, "no text colour classes found"
    assert used <= TESTED_TEXT_TOKENS, f"untested text colours: {sorted(used - TESTED_TEXT_TOKENS)}"


def test_chrome_uses_contrast_tokens_not_fixed_white_or_black(css):
    assert "var(--color-black)" not in css
    assert "var(--color-white)" not in css


def test_every_block_in_the_stylesheet_is_closed_once(css):
    """A stray line once closed @layer components early, and Tailwind refused the file."""
    depth = 0
    for number, line in enumerate(re.sub(r"/\*.*?\*/", "", css, flags=re.S).splitlines(), 1):
        depth += line.count("{") - line.count("}")
        assert depth >= 0, f"source.css closes a block that isn't open near line {number}"
    assert depth == 0
