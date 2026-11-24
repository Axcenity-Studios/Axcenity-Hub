"""The axcenity theme is the only source of colour, and every colour pair is readable.

Ported from the Axcenity Toolbox's theme tests (its type colours and page glows
aren't part of the Hub), plus the Hub's one accent and a contrast check of each
real foreground/background pair the pages use, in dark and light.
"""

import re

import pytest
from django.conf import settings

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

# Content colours: code and node graphs only, never chrome (the Logic loop and the Luau
# fallback). crates/editor-kit/src/lua_syntax.rs color(): (dark, light) for each kind.
LUAU_EDITOR = {
    "keyword": ("#C586C0", "#AF00DB"),
    "literal": ("#569CD6", "#0000FF"),
    "builtin": ("#4EC9B0", "#267F99"),
    "number": ("#B5CEA8", "#098658"),
    "string": ("#CE9178", "#A31515"),
    "comment": ("#6A9955", "#008000"),
}
# theme.rs Hue::base for the block categories (Events: Amber; Looks: Violet), and the block
# Graph view's pin colours (block_editor/graph/nodes.rs), the same in both schemes.
NODE_HUES = {"events": "#BE8012", "looks": "#7658E0"}
# The Blocks view's categories (theme.rs Hue: Events Amber, Looks Violet, Sensing Cyan) and its
# typed fields (block_editor.rs INPUT_FIELD, INPUT_TEXT).
BLOCK_HUES = {"events": "#BE8012", "looks": "#7658E0", "sensing": "#1282A8"}
BLOCK_FIELD = {"block-field": "#FAFAFC", "block-field-text": "#222634", "block-shade": "#000000"}
PIN_COLOURS = {
    "object": "#41C3DC",
    "any": "#AAAAB2",
    "text": "#F05AD2",
    "vector": "#F5C328",
    "number": "#8CDC46",
}


def _rgb(hex_value: str) -> tuple[int, ...]:
    return tuple(int(hex_value[i : i + 2], 16) for i in (1, 3, 5))


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _mix(hex_value: str, toward: str, t: float) -> str:
    """theme.rs mix(): each channel moved `t` of the way, rounded half away from zero."""
    return _hex(
        int(a + (b - a) * t + 0.5) for a, b in zip(_rgb(hex_value), _rgb(toward), strict=True)
    )


ALLOWED = (
    EDITOR_PALETTE
    | {"#FFFFFF", "#000000", "#18181B", "#2B2D31"}
    | set(LIGHT_PALETTE.values())
    | set(LIGHT_STATUS.values())
    | set(ACCENT.values())
    | set(PIN_COLOURS.values())
    | {dark for dark, _ in LUAU_EDITOR.values()}
    | {"#A06C0F", "#94640E", "#7658E0", "#5C45AF", "#117DA1", "#0E6583"}
    | set(BLOCK_FIELD.values())
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
    dark = _tokens(_block(css, "@theme static {")) | _tokens(daisy_theme)
    return {"dark": dark, "light": dark | _tokens(light_block)}


# ---------- The palette ----------


def test_tailwind_default_palette_is_reset(css):
    assert "--color-*: initial;" in _block(css, "@theme static {")


def test_daisyui_builtin_themes_are_off(css):
    assert re.search(r'@plugin "[^"]*daisyui\.mjs" \{\s*themes: false;\s*\}', css)


def test_axcenity_is_the_only_and_default_theme(css, daisy_theme):
    names = re.findall(r"^\s*name: \"([^\"]+)\";", css, re.M)
    assert names == ["axcenity"]
    assert "default: true;" in daisy_theme
    assert "color-scheme: dark;" in daisy_theme


def test_every_colour_is_in_the_axcenity_palette(css, palettes):
    # The darkened light Luau colours and the node headers are derived from the editor's
    # own values; the content-colour tests below check each derivation.
    derived = {
        value
        for tokens in palettes.values()
        for name, value in tokens.items()
        if name.startswith(("luau-", "node-"))
    }
    stray = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{3,8}\b", css)} - ALLOWED - derived
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


def test_the_accent_is_used_only_by_the_badge_dot(css):
    """The primary button reads it through DaisyUI; the wipe's scan line is drawn on the canvas."""
    users = [
        line.strip().split(" {", 1)[0] for line in css.splitlines() if "var(--color-accent)" in line
    ]
    assert users == [".badge-dot"]
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
    *[(f"Luau {kind}", f"luau-{kind}", bg) for kind in LUAU_EDITOR for bg in ("inset", "panel")],
    # The Logic loop's Graph view (static/reel/drawing/blocks.js).
    ("node titles: Events", "node-title", "node-events"),
    ("node titles: Looks", "node-title", "node-looks"),
    ("block words: Events", "node-title", "block-events"),
    ("block words: Looks", "node-title", "block-looks"),
    ("block words: Sensing", "node-title", "block-sensing"),
    ("block typed values", "block-field-text", "block-field"),
    ("node rows and values", "fg", "surface"),
    ("node value boxes", "fg", "inset"),
    # The Editor and Terrain loops (static/reel/loops/).
    ("loop: menu bar and Scatter shares", "fg-secondary", "app"),
    ("loop: open menu, hovered item", "fg-strong", "control-active"),
    ("loop: menu section label", "fg-weak", "app"),
    ("loop: Scatter's item names", "fg", "panel"),
    ("loop: Terrain's tool chip", "fg-strong", "app"),
    ("drawn editor: panel text", "fg", "panel"),
    ("drawn editor: active tab", "fg-strong", "surface"),
    ("drawn editor: selected row", "fg-strong", "control-active"),
    # The editor pieces the loops draw with (static/reel/drawing/editor.js, toolbox.js,
    # animation.js), and the Toolbox and Animation loops' drawings.
    ("editor: Explorer rows, Properties names, section titles", "fg-secondary", "panel"),
    ("editor: buttons and Terrain tools", "fg-secondary", "control"),
    ("editor: chosen tab or button", "fg-strong", "control-active"),
    ("editor: field values, the Console log", "fg", "inset"),
    ("editor: field placeholders, dope sheet rows", "fg-weak", "inset"),
    ("editor: Properties names", "fg-weak", "panel"),
    ("editor: window titles", "fg-weak", "app"),
    ("editor: Toolbox card names", "fg-strong", "surface"),
    ("editor: Toolbox card details", "fg-weak", "surface"),
    # The hero film's pause button.
    ("film button", "fg-strong", "app"),
    ("film button hovered", "on-ink", "ink"),
    # The docs (/docs/): the sidebar, the article and its code, tables and figures.
    ("docs: sidebar links, breadcrumbs, outline", "fg-secondary", "app"),
    ("docs: sidebar on a phone's panel", "fg-secondary", "panel"),
    ("docs: section titles, anchors, provenance", "fg-weak", "app"),
    ("docs: article text and links", "fg", "app"),
    ("docs: inline code", "fg", "surface"),
    ("docs: code blocks", "fg", "inset"),
    ("docs: table headers", "fg-strong", "panel"),
    ("docs: status badge", "fg-strong", "app"),
    ("docs: copy button", "fg-secondary", "app"),
    ("docs: copy button hovered or focused", "on-ink", "ink"),
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
    ("renderer wipe's scan line", "accent", "inset"),
    ("viewport grid", "fg-weak", "inset"),
    ("viewport block", "fg-strong", "inset"),
    ("drawn dope sheet keys", "fg-secondary", "inset"),
    ("node wire and exec pins", "fg-secondary", "inset"),
    ("terrain brush ring", "fg-strong", "surface"),
    ("loop pause button edge", "fg-strong", "app"),
    ("docs: current sidebar page's bar, status badge edge", "ink", "app"),
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
    ".flow-num {": "color: var(--color-app); -webkit-text-stroke: 2px var(--color-fg-weak); paint-order: stroke fill;",
    ".drawn-code {": "color: var(--color-fg); background: var(--color-inset);",
    **{f".luau-{kind} {{": f"color: var(--color-luau-{kind});" for kind in LUAU_EDITOR},
    ".loop-button {": "color: var(--color-fg-strong); background: var(--color-app);",
    "html[data-pointer] .loop-button:hover {": "color: var(--color-on-ink); background: var(--color-ink);",
    ".drawn-grid {": "stroke: var(--color-fg-weak);",
    ".ed-tab[data-on] {": "background: var(--color-surface); color: var(--color-fg-strong);",
    ".ed-tree li[data-on] {": "background: var(--color-control-active); color: var(--color-fg-strong);",
    ".film-button {": "color: var(--color-fg-strong); background: var(--color-app);",
    "html[data-pointer] .film-button:hover {": "color: var(--color-on-ink); background: var(--color-ink);",
    ".tb-name {": "color: var(--color-fg-strong);",
    ".tb-detail {": "color: var(--color-fg-weak);",
    ".an-sheet dt {": "color: var(--color-fg-weak);",
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
@pytest.mark.parametrize(
    "url", ["/", "/toolbox/", "/docs/", "/docs/learn/scripting/", "/docs/api/classes/part/"]
)
def test_pages_use_only_tested_text_colours(client, url):
    """fg-muted, for one, is under 4.5:1 on the app background, so no text may use it."""
    html = client.get(url).content.decode()
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


# ---------- Content colours: code and node graphs ----------


@pytest.mark.parametrize("kind", LUAU_EDITOR)
def test_dark_luau_colours_are_the_editors(palettes, kind):
    assert palettes["dark"][f"luau-{kind}"] == LUAU_EDITOR[kind][0]


@pytest.mark.parametrize("kind", LUAU_EDITOR)
def test_light_luau_colours_are_the_editors_darkened_just_enough(palettes, kind):
    """The editor shows its light colours on near-white; on the site's storm grey each is
    mixed toward black in 2 % steps until it reads at 4.5:1 on inset and panel."""
    light = palettes["light"]
    expected, t = LUAU_EDITOR[kind][1], 0.0
    while min(_contrast(expected, light[bg]) for bg in ("inset", "panel")) < 4.5:
        t += 0.02
        expected = _mix(LUAU_EDITOR[kind][1], "#000000", t)
    assert light[f"luau-{kind}"] == expected


@pytest.mark.parametrize("hue", NODE_HUES)
def test_node_headers_are_the_editors_category_hues(palettes, hue):
    """theme.rs Canvas::header: the hue mixed 12 % toward black, then 4 % more at a time,
    until its white title reads at 4.5:1. The same in both schemes."""
    t = 0.12
    expected = _mix(NODE_HUES[hue], "#000000", t)
    while _contrast("#FFFFFF", expected) < 4.5 and t < 1:
        t += 0.04
        expected = _mix(NODE_HUES[hue], "#000000", t)
    for mode in ("dark", "light"):
        assert palettes[mode][f"node-{hue}"] == expected, mode
        assert palettes[mode]["node-title"] == "#FFFFFF", mode


def _under_white_text(hex_value: str) -> str:
    """theme.rs Palette::under_white_text with Increase contrast: mixed toward black 4 % at a
    time until white reads on it at 4.5:1."""
    t, fill = 0.0, hex_value
    while _contrast("#FFFFFF", fill) < 4.5 and t < 1:
        t += 0.04
        fill = _mix(hex_value, "#000000", t)
    return fill


@pytest.mark.parametrize("hue", BLOCK_HUES)
def test_block_fills_and_edges_are_the_editors_with_increase_contrast(palettes, hue):
    """theme.rs Hue::fill (the base, under white text) and Hue::edge (the base at 78 %, under
    white text). Content colours: the same in both schemes."""
    base = BLOCK_HUES[hue]
    edge = _hex(int(channel * 0.78 + 0.5) for channel in _rgb(base))
    for mode in ("dark", "light"):
        assert palettes[mode][f"block-{hue}"] == _under_white_text(base), mode
        assert palettes[mode][f"block-{hue}-edge"] == _under_white_text(edge), mode


@pytest.mark.parametrize(("token", "hex_value"), BLOCK_FIELD.items())
def test_block_fields_are_the_editors_in_both_schemes(palettes, token, hex_value):
    for mode in ("dark", "light"):
        assert palettes[mode][token] == hex_value, mode


@pytest.mark.parametrize("pin", PIN_COLOURS)
def test_pin_colours_are_the_editors_in_both_schemes(palettes, pin):
    """Pin colours are content in the editor too: unchanged in light mode. A pin is never
    the only mark of its meaning (its row is labelled), so it isn't a contrast pair."""
    for mode in ("dark", "light"):
        assert palettes[mode][f"pin-{pin}"] == PIN_COLOURS[pin], mode


def test_content_colours_stay_in_code_and_node_graphs(css):
    """They're never chrome: the stylesheet uses only the Luau ones, in the .luau-* rules, and
    on the canvas only the code and node drawings read them."""
    for line in css.splitlines():
        if re.search(r"var\(--color-(luau|node|pin|block)-", line):
            assert re.match(r"\.luau-(\w+) \{ color: var\(--color-luau-\1\); \}$", line), line
    reel = settings.BASE_DIR / "static" / "reel"
    for path in reel.rglob("*.js"):
        uses = re.findall(
            r"colors\.(luau|node|pin|block)\w*|\"(luau|node|pin|block)[\w-]+\"", path.read_text()
        )
        if uses:
            assert path.relative_to(reel).as_posix() in {
                "canvas.js",
                "drawing/blocks.js",
                "drawing/stacks.js",
                "drawing/code.js",
            }, path
