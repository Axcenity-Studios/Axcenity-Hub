"""The marketing pages' copy, links and media, kept as data.

Templates loop over these values; the tests check that every internal link
reverses, every external one is well-formed, every media file exists, and
that the Home's visible prose comes from here. A link to a page that
doesn't exist yet is marked `soon`: it renders as a "Soon" label, never as
a dead link.
"""

import json
from dataclasses import dataclass, field

from django.templatetags.static import static
from django.urls import reverse

from marketing import drawings, media

# The engine's canonical repository (the README's older account redirects here).
ENGINE_REPO_URL = "https://github.com/Axcenity-Studios/Axcenity-Engine"
# Every release is a prerelease, so link the list, never /releases/latest (it 404s).
RELEASES_URL = f"{ENGINE_REPO_URL}/releases"
# The engine's documentation, as published in its repository.
DOCS_URL = f"{ENGINE_REPO_URL}/tree/main/documentation"
GETTING_STARTED_URL = f"{ENGINE_REPO_URL}/blob/main/documentation/learn/getting-started.md"
# The engine's newest release tag (Cargo.toml's workspace version). Phase 7 reads it from GitHub.
ENGINE_VERSION = "v0.3.0-alpha.1"


@dataclass(frozen=True)
class Link:
    """One link: internal (a URL name, optionally with a #fragment), external (an https URL)
    or coming soon."""

    label: str
    url_name: str = ""
    external: str = ""
    soon: bool = False
    fragment: str = ""

    def __post_init__(self) -> None:
        targets = bool(self.url_name) + bool(self.external)
        if self.soon and targets:
            raise ValueError(f"{self.label}: a coming-soon link has no target")
        if not self.soon and targets != 1:
            raise ValueError(f"{self.label}: give exactly one of url_name or external")
        if self.fragment and not self.url_name:
            raise ValueError(f"{self.label}: only an internal link takes a fragment")

    @property
    def href(self) -> str:
        """The URL to link to, or "" for a coming-soon item."""
        if self.url_name:
            url = reverse(self.url_name)
            return f"{url}#{self.fragment}" if self.fragment else url
        return self.external

    @property
    def is_external(self) -> bool:
        return bool(self.external)


@dataclass(frozen=True)
class FooterColumn:
    heading: str
    links: list[Link] = field(default_factory=list)


# ---------- Media manifest ----------
# Every image or drawing on the site, with what it is and where it came from.
# kind "capture" is a real, unretouched engine frame; "illustrative" is drawn or
# recreated, and its caption says so. A capture's source file lives in
# marketing/media_sources/ and is served only as the derivatives `make_media`
# writes (marketing/media.py). An animated recreation is a canvas loop
# (static/reel/loops/), with a static drawing as its fallback.

MEDIA_KINDS = {"capture": "Engine capture", "illustrative": "Illustrative"}
# The canvas loops (static/reel/loops/<name>.js) a media item may run.
LOOPS = ("editor", "terrain", "logic")


@dataclass(frozen=True)
class Display:
    """Where an item shows: the `sizes` attribute for that slot and the largest CSS size it's
    drawn at in each range of viewport widths. For a capture that's the picture's own drawn
    size (a 16:9 picture covering a 16:10 frame is wider than the frame)."""

    sizes: str
    breakpoints: dict[str, tuple[int, int]]


# The feature pillars' frames (16:10): inline below 1024 px (the page's gutters are 16 px,
# then 32 px from 768 px), on the sticky stage from 1024 px ((min(100vw, 1400) − 128) × 5/9).
FRAME_INLINE = {"360–767 px": (735, 459), "768–1023 px": (959, 599)}
FRAME_STAGE = {"1024–1439 px": (707, 442), "1440 px and up": (707, 442)}
FRAME_SIZES = {
    "inline": "(min-width: 768px) calc(100vw - 64px), calc(100vw - 32px)",
    "stage": "calc((min(100vw, 1400px) - 128px) * 0.5556)",
}
# A 16:9 picture covering a 16:10 frame is drawn 10/9 as wide as the frame.
COVER_16_9 = 10 / 9


def _covered(sizes: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    return {where: (round(w * COVER_16_9), h) for where, (w, h) in sizes.items()}


FRAME_DISPLAY = {
    "inline": Display(FRAME_SIZES["inline"], FRAME_INLINE),
    "stage": Display(FRAME_SIZES["stage"], FRAME_STAGE),
}
COVER_DISPLAY = {
    "inline": Display(
        "(min-width: 768px) calc((100vw - 64px) * 1.112), calc((100vw - 32px) * 1.112)",
        _covered(FRAME_INLINE),
    ),
    "stage": Display("calc((min(100vw, 1400px) - 128px) * 0.6173)", _covered(FRAME_STAGE)),
    # The reel's fallback: 16:9, at most 1280 px wide (half the capture, so 2× screens stay sharp).
    "hero": Display("min(100vw - 32px, 1280px)", {"every width": (1280, 720)}),
}


@dataclass(frozen=True)
class Media:
    """One media item: a captured image (`source`, cut into derivatives) or a drawing
    rendered by a template (`drawn`), which a canvas `loop` may animate."""

    key: str
    kind: str
    caption: str
    alt: str
    provenance: str
    # What a loop's static drawing shows, for when the loop can't run (its `alt` describes the film).
    fallback_alt: str = ""
    source: str = ""
    drawn: str = ""
    loop: str = ""
    # Pixel size of the source file (captures only).
    source_size: tuple[int, int] | None = None
    # Where it shows, by slot ("inline", "stage", "hero").
    display: dict[str, Display] = field(default_factory=dict)
    # Words drawn inside a recreation (panel names and the like), or its code.
    labels: dict = field(default_factory=dict)
    code: str = ""

    def __post_init__(self) -> None:
        if self.kind not in MEDIA_KINDS:
            raise ValueError(f"{self.key}: kind must be one of {sorted(MEDIA_KINDS)}")
        if not self.caption.startswith(MEDIA_KINDS[self.kind]):
            raise ValueError(f"{self.key}: a {self.kind} caption starts {MEDIA_KINDS[self.kind]!r}")
        if bool(self.source) == bool(self.drawn):
            raise ValueError(f"{self.key}: give exactly one of source or drawn")
        if self.kind == "capture" and not self.source:
            raise ValueError(f"{self.key}: a capture is a file, never a drawing")
        if self.source and not self.source_size:
            raise ValueError(f"{self.key}: a file records its source pixel size")
        if self.loop and (self.loop not in LOOPS or not self.drawn or not self.fallback_alt):
            raise ValueError(f"{self.key}: a loop is one of {LOOPS}, with a described fallback")
        if not self.display:
            raise ValueError(f"{self.key}: record where it's displayed and how large")

    @property
    def derivatives(self) -> tuple[media.Derivative, ...]:
        """The files `make_media` writes for a capture (none for a drawing)."""
        return media.derivatives(self.key, self.source_size) if self.source else ()

    def srcset(self, extension: str) -> str:
        """The `srcset` of one format's derivatives."""
        return ", ".join(
            f"{static(item.path)} {item.width}w"
            for item in self.derivatives
            if item.format.extension == extension
        )

    @property
    def sources(self) -> list[tuple[str, str]]:
        """(MIME type, srcset) for each <source> in a <picture>, best format first."""
        return [(fmt.mime, self.srcset(fmt.extension)) for fmt in media.FORMATS[:-1]]

    @property
    def fallback(self) -> media.Derivative:
        """The <img>'s own file: the fallback format, 1280 wide (or the widest there is)."""
        files = [d for d in self.derivatives if d.format == media.FALLBACK]
        return next((d for d in files if d.width == 1280), files[-1])

    @property
    def fallback_srcset(self) -> str:
        """The <img>'s own `srcset`: the fallback format's derivatives."""
        return self.srcset(media.FALLBACK.extension)

    @property
    def labels_json(self) -> str:
        """The drawn words as JSON, for a loop's canvas (escaped into an attribute)."""
        return json.dumps(self.labels, ensure_ascii=False)


# The editor's words, shared by the reel and the Editor pillar's loop.
# The default dock (crates/editor/src/layout.rs default_dock), each place's tabs in order.
EDITOR_DOCK = {
    "scene": ["Scene View", "Animation", "UI Designer"],
    "explorer": ["Explorer"],
    "properties": ["Properties", "Terrain"],
    "console": ["Console", "Assets", "Profiler"],
}
EDITOR_WINDOW = "Arena - Axcenity Editor"
EDITOR_TREE = [
    ("Workspace", 0),
    ("Arena", 1),
    ("Pad", 2),
    ("Terrain", 1),
    ("Lighting", 0),
    ("ServerScriptService", 0),
]
# The selected Pad (an anchored 8 × 1 × 8 Part, otherwise Part's defaults).
EDITOR_PROPERTIES = {
    "name": "Pad",
    "class": "Part",
    "filter": "Filter properties",
    "sections": [
        ("Data", [("Name", "Pad", "field")]),
        (
            "Appearance",
            [
                ("Color", "163, 163, 163", "color"),
                ("Material", "Plastic", "field"),
                ("Transparency", "0", "field"),
            ],
        ),
        ("Behavior", [("Anchored", "true", "check"), ("CanCollide", "true", "check")]),
        (
            "Part",
            [
                ("Shape", "Block", "field"),
                ("Position", "0, 0.5, 0", "field"),
                ("Size", "8, 1, 8", "field"),
            ],
        ),
    ],
}
EDITOR_CONSOLE = {
    "filter": "Filter logs",
    "lines": [
        (
            "12:04:28",
            'Opened "Arena" from `Arena`: 6 objects, 1 script. Press Play (F5) to run it.',
            "info",
        ),
        ("", "select Pad", "command"),
    ],
    "prompt": "Lua, or a command such as help",
}
EDITOR_TERRAIN = {"tabs": ["Sculpt", "Materials"], "tools": ["Raise / Lower", "Smooth", "Flatten"]}
EDITOR_ASSETS = ["scorch.png", "grass.png", "rock.png", "Pad.glb", "theme.ogg"]

# The Luau a "When touched → Spawn decal" block script becomes. The shape follows the
# engine's translator (crates/blocks-runtime/src/translate.rs, WhenTouched and SpawnDecal)
# and the Workspace:SpawnDecal API (texture path, CFrame, size, lifetime).
LUAU_SAMPLE = """\
-- When touched → Spawn decal, as Luau
local part = workspace.Arena.Pad

part.Touched:Connect(function(otherPart)
  local pos = otherPart.Position
  workspace:SpawnDecal("assets/textures/scorch.png",
    CFrame.lookAt(pos, pos + Vector3.yAxis, Vector3.zAxis), 2.5, 4)
end)"""
# Phones show the part from the Connect call down (no comment, no lookup line).
LUAU_COMPACT_FROM = 3

MEDIA = {
    "renderer": Media(
        key="renderer",
        kind="capture",
        caption="Engine capture · ray traced",
        alt=(
            "A gallery interior rendered by Axcenity Engine with hardware ray tracing: "
            "reflections on the floor and spheres, soft shadows and bounced light."
        ),
        provenance=(
            "Showcase-Renderer project, axcenity-player v0.3.0-alpha.1 run fullscreen at "
            "2560×1440 with --graphics settings/rt-ultra.json, captured after 15 s with "
            "tools/capture.sh (import -window); not painted over, cropped or rescaled "
            "(Showcase/README.md)."
        ),
        source="renderer-2560x1440.png",
        source_size=(2560, 1440),
        display=COVER_DISPLAY,
    ),
    "terrain": Media(
        key="terrain",
        kind="illustrative",
        caption="Illustrative · terrain recreation",
        alt=(
            "An animated recreation of the Terrain Studio. A brush ring sweeps across a flat "
            "grid in the Scene View with Raise / Lower chosen, and hills rise under it. Then "
            "the Scatter pane takes over: its brush paints trees, bushes, flowers and grass "
            "across the hills, each growing in where the brush passes, before the ground "
            "settles flat again."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/loops/terrain.js in the site's colour tokens. "
            "The Terrain Studio's tabs, tools and brush defaults follow "
            "crates/editor/src/terrain_studio/tabs.rs, crates/editor-tools/src/terrain_tool.rs "
            "and crates/terrain/src/brush.rs; the Scatter pane follows "
            "crates/editor/src/scatter_pane.rs and the built-in plants in "
            "crates/core/src/terrain.rs; the brush ring follows "
            "crates/editor/src/viewport/overlays.rs, in ink rather than the editor's accent. "
            "Without JavaScript: the wireframe drawing in marketing/drawings.py."
        ),
        fallback_alt=(
            "A drawing of a wireframe terrain rising into hills, with trees scattered across it."
        ),
        drawn="marketing/media/terrain.html",
        loop="terrain",
        display=FRAME_DISPLAY,
        labels={
            "viewport": "Scene View",
            "panes": ["Terrain", "Scatter"],
            "studio": "Terrain Studio",
            "tabs": ["Sculpt", "Materials", "Terrain"],
            "tools": ["Raise / Lower", "Smooth", "Flatten", "Sculpt"],
            "brush": [
                ("Size", "12 studs", 0.45),
                ("Strength", "0.5", 0.5),
                ("Falloff", "0.6", 0.6),
            ],
            "scatter": "Scatter",
            "palette": "Palette",
            "paint": "Paint",
            "painting": "Stop painting",
            "scatter_brush": [("Size", "12 studs", 0.45), ("Density", "8 per 100 studs²", 0.3)],
            "items": [("Tree", "25%"), ("Bush", "25%"), ("Flower", "25%"), ("Grass", "25%")],
        },
    ),
    "logic": Media(
        key="logic",
        kind="illustrative",
        caption="Illustrative · blocks as Luau",
        alt=(
            "An animated recreation of the block editor's Graph view. A When Touched node for "
            "the Pad and a Spawn Decal node appear, a wire joins them, and beside them the Luau "
            "they become types out: when the part is touched, spawn a scorch decal where it "
            "was hit. A pulse then runs along the wire, as when the Pad is touched."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/loops/logic.js. Nodes follow the block "
            "editor's Graph view (crates/editor/src/block_editor/graph.rs and graph/nodes.rs: "
            "titles, rows, pin types and colours, the Events and Looks hues) and the shared "
            "canvas (crates/editor-node-graph/src/canvas.rs: grid, exec and value pins, "
            "wires). The Luau is the translator's output (crates/blocks-runtime/src/"
            "translate.rs), coloured as crates/editor-kit/src/lua_syntax.rs colours it, its "
            "light colours darkened to 4.5:1 on the site's light grey. Without JavaScript: "
            "the same code, highlighted."
        ),
        fallback_alt="Luau code: when the part is touched, spawn a scorch decal where it was hit.",
        drawn="marketing/media/luau.html",
        loop="logic",
        display=FRAME_DISPLAY,
        code=LUAU_SAMPLE,
        labels={
            "graph": "Graph",
            "code": "Luau",
            # Each node: title, header hue, then its rows as (label, value, pin type, side).
            "nodes": [
                {
                    "title": "When Touched",
                    "hue": "events",
                    "rows": [
                        ("Part", "Pad", "object", "in"),
                        ("Filter", "Any Part", "", "field"),
                    ],
                    "outputs": [("", "exec"), ("Other Part", "object"), ("Player", "any")],
                },
                {
                    "title": "Spawn Decal",
                    "hue": "looks",
                    "rows": [
                        ("", "", "exec", "in"),
                        ("Texture", "scorch.png", "text", "in"),
                        ("Position", "Other Part.Position", "vector", "wired"),
                        ("Facing", "0, 1, 0", "vector", "in"),
                        ("Size", "2.5", "number", "in"),
                        ("Seconds", "4", "number", "in"),
                    ],
                    "outputs": [("", "exec"), ("Decal", "object")],
                },
            ],
            # The code as the editor colours it: lines of (kind, text) tokens.
            "lines": drawings.luau_lines(LUAU_SAMPLE),
            "compact_from": LUAU_COMPACT_FROM,
        },
    ),
    "editor": Media(
        key="editor",
        kind="illustrative",
        caption="Illustrative · editor recreation",
        alt=(
            "An animated recreation of the Axcenity editor's docking. In the default layout, a "
            "pointer drags the Console tab onto the right half of the Scene View, which splits "
            "to show them side by side. It then drags the Properties tab out of the window "
            "onto a second monitor, where it floats in a window of its own. Finally it chooses "
            "View, Reset Layout, and every panel springs back to where it started."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/loops/editor.js with the reel's editor pieces "
            "(static/reel/drawing/editor.js). The dock, its tabs and the floating window follow "
            "crates/editor/src/layout.rs (default_dock, Pane::label), the menu bar and Reset "
            "Layout follow crates/editor/src/app/chrome/menus.rs, and the drop preview follows "
            "the dock overlay, in ink rather than the editor's accent. Without JavaScript: the "
            "drawn layout in templates/marketing/media/editor.html."
        ),
        fallback_alt=(
            "A drawing of the Axcenity editor: the Scene, Explorer and Console docked in one "
            "window, with Properties floated out onto a second monitor."
        ),
        drawn="marketing/media/editor.html",
        loop="editor",
        display=FRAME_DISPLAY,
        labels={
            "window": EDITOR_WINDOW,
            "menus": ["File", "Edit", "View", "Viewport", "Debug", "Help"],
            # The View menu (menus.rs): its "Panels" section, then Reset Layout.
            "panels": "Panels",
            "reset": "Reset Layout",
            # The floating window's title, as the reel names its monitors.
            "monitor": "Monitor 2",
            "tabs": EDITOR_DOCK,
            "tree": EDITOR_TREE,
            "selected": "Pad",
            "properties": EDITOR_PROPERTIES,
            "console": EDITOR_CONSOLE,
            "terrain": EDITOR_TERRAIN,
            "assets": EDITOR_ASSETS,
            # The static fallback drawing's words.
            "floating": "Floating · Monitor 2",
            "rows": [("Name", "Pad"), ("Anchored", "true"), ("Size", "8, 1, 8")],
            "console_line": "Press Play (F5) to test.",
        },
    ),
    # The hero's showcase reel, drawn live on a canvas by static/reel/ (docs/frontend/reel.md).
    # Its labels go to the page as JSON; the alt text is the reel's screen-reader description.
    "reel": Media(
        key="reel",
        kind="illustrative",
        caption="Illustrative · editor recreation",
        alt=(
            "A looping film, about 18 seconds long, recreating the Axcenity editor. The words "
            "Scene View, Explorer and Properties appear in large type, then shrink into the tabs "
            "of panels that spring together into the editor's default layout: the 3D Scene View "
            "with the Console docked below it, and beside them the Explorer's tree of Workspace, "
            "Arena and Pad above the Properties. A pointer then drags the Properties tab out of "
            "the window onto a second monitor to the right, where it shows the selected Pad's "
            "Data, Appearance, Behavior and Part settings, and drags the Console onto a third "
            "monitor to the left. The Terrain and Assets tabs that shared their places take "
            "over. The workspace holds in that layout, then gives way to the Axcenity logo "
            "before the film starts again. On narrow screens it shows only the Scene View and "
            "the Explorer, docked side by side."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/ in the site's colour tokens, whose dark values "
            "are the editor's Dark theme (crates/editor-kit/src/theme.rs ThemeTokens). The dock "
            "and its tabs follow crates/editor/src/layout.rs (default_dock, style, Pane::label); "
            "the Properties pane follows crates/editor/src/properties.rs and Part's defaults in "
            "crates/core/src/class.rs; the Console follows output.rs, console.rs and the "
            "project-opened message in app/session.rs; the window title follows the editor's "
            '"<project> - Axcenity Editor".'
        ),
        drawn="marketing/media/reel.html",
        display={
            "hero": Display(
                "100vw", {"360–639 px (compact)": (639, 900), "640 px and up": (2560, 1440)}
            )
        },
        labels={
            "tabs": EDITOR_DOCK,
            "window": EDITOR_WINDOW,
            "monitors": {"properties": "Monitor 2", "console": "Monitor 3"},
            "tree": EDITOR_TREE,
            "selected": "Pad",
            "properties": EDITOR_PROPERTIES,
            "console": EDITOR_CONSOLE,
            "terrain": EDITOR_TERRAIN,
            "assets": EDITOR_ASSETS,
            # Each segment of the timeline by its module id, for the scrubber's spoken position.
            "segments": {
                "workspace": "Scene 1, Workspace",
                "renderer": "Scene 2, Renderer",
                "world": "Scene 3, World",
                "logic": "Scene 4, Logic",
                "lockup": "Logo",
            },
        },
    ),
}

# The reel's control labels (screen-reader names; the controls show icons).
REEL_CONTROLS = {
    "group": "Reel controls",
    "play": "Play reel",
    "pause": "Pause reel",
    "scrub": "Reel position",
    "of": "of",
}


# ---------- Shell: nav and footer ----------

NAV_LINKS = [
    Link("Engine", url_name="marketing:home"),
    Link("Features", url_name="marketing:home", fragment="features"),
    Link("Toolbox", soon=True),
    Link("Docs", external=DOCS_URL),
    Link("Community", soon=True),
]
SIGN_IN = Link("Sign in", soon=True)
DOWNLOAD = Link("Download", external=RELEASES_URL)

FOOTER_TAGLINE = "Free and open source. Alpha software: expect breaking changes."
FOOTER_SIGNATURE = "Axcenity Studios · 2026"
FOOTER_COLUMNS = [
    FooterColumn(
        "Engine",
        [Link("Download", external=RELEASES_URL), Link("GitHub", external=ENGINE_REPO_URL)],
    ),
    FooterColumn(
        "Learn",
        [
            Link("Docs", external=DOCS_URL),
            Link("Getting started", external=GETTING_STARTED_URL),
            Link("Toolbox", soon=True),
        ],
    ),
    FooterColumn(
        "Community",
        [Link("Forums", soon=True), Link("Showcases", soon=True), Link("Projects", soon=True)],
    ),
]


# ---------- Home ----------


@dataclass(frozen=True)
class Pillar:
    number: str
    label: str
    title: str
    body: str
    media: Media


@dataclass(frozen=True)
class Item:
    """A titled line of copy: a workflow step, a stat, a Toolbox feature, a community card."""

    title: str
    body: str
    number: str = ""


HOME_HERO = {
    "badge": f"{ENGINE_VERSION} · Free and open source",
    "headline": "Axcenity Engine.",
    # Every phrase shares one grid cell, so the box is always as tall as the longest.
    "rotating": [
        "Build worlds.",
        "Script in Luau.",
        "Ray trace in real time.",
        "Ship to every desktop.",
    ],
    # What a screen reader hears in place of the rotation.
    "rotating_summary": (
        "Build worlds, script in Luau, ray trace in real time and ship to every desktop."
    ),
    "pitch": (
        "A free, open-source 3D game engine and editor written in Rust, now in alpha. "
        "Build worlds, script in Luau, test with F5 and export for Windows, macOS and Linux."
    ),
    "primary": Link("Download alpha", external=RELEASES_URL),
    "secondary": Link("Read the docs", external=DOCS_URL),
    # The full-bleed reel behind the hero, and what shows when it can't run (no JavaScript,
    # no ES modules or no canvas).
    "reel": MEDIA["reel"],
    "reel_controls": REEL_CONTROLS,
    "fallback": MEDIA["renderer"],
}

# The pause button on each animated recreation (screen-reader names; it shows icons).
LOOP_CONTROLS = {"play": "Play animation", "pause": "Pause animation"}

HOME_FEATURES = {
    "eyebrow": "Features",
    "title": "One editor, from the first block to the export.",
    "pillars": [
        Pillar(
            "01",
            "Renderer",
            "Ray traced, in real time.",
            "Optional hardware ray tracing for shadows, reflections, ambient occlusion and "
            "global illumination, plus a path-traced view to check your lighting against.",
            MEDIA["renderer"],
        ),
        Pillar(
            "02",
            "World",
            "Sculpt terrain. Scatter life.",
            "Shape hills with the Terrain Studio's brushes, paint its materials, then cover the "
            "ground with grass, plants and trees from the Scatter pane or scatter rules.",
            MEDIA["terrain"],
        ),
        Pillar(
            "03",
            "Logic",
            "Blocks or Luau. Same game.",
            "Snap blocks together, like When touched → Spawn decal, and they become Luau. Or "
            "write Luau yourself: Scripts run on the server, LocalScripts on each player.",
            MEDIA["logic"],
        ),
        Pillar(
            "04",
            "Editor",
            "Your layout, every monitor.",
            "The Scene, Explorer, Properties and Console are tabs in one docking area. Split "
            "them, float any panel onto another monitor, or reset the layout.",
            MEDIA["editor"],
        ),
    ],
    "loop_controls": LOOP_CONTROLS,
}

HOME_WORKFLOW = {
    "eyebrow": "Workflow",
    "title": "Build, script, test, export.",
    "steps": [
        Item("Build", "Parts, models and terrain in the 3D Scene.", "01"),
        Item("Script", "Luau or visual blocks, on the server and on each player.", "02"),
        Item("Test", "Press Play (F5) to play your game inside the editor.", "03"),
        Item("Export", "Standalone games for Windows, macOS and Linux.", "04"),
    ],
}

HOME_FACTS = {
    "title": "At a glance",
    "stats": [
        Item("Free", "Open source under the Apache 2.0 licence. No royalties."),
        Item("Rust", "A native, memory-safe core."),
        Item("3 OS", "Windows, macOS and Linux desktops."),
        Item("Alpha", "Early days: expect breaking changes."),
    ],
}

HOME_TOOLBOX = {
    "eyebrow": "Companion tool",
    "title": "Axcenity Toolbox",
    "body": (
        "Find free game assets from ambientCG, Poly Haven and Openverse, save them to a "
        "library, and build packs the engine imports."
    ),
    "features": [
        Item("Discover", "Search every provider at once, with no API keys."),
        Item("Library", "Save assets with your notes, ratings and tags."),
        Item("Packs", "Group assets for a project, with credits, ready to import."),
    ],
    # The Toolbox page arrives in Phase 6.
    "cta": Link("Explore the Toolbox", soon=True),
}

HOME_COMMUNITY = {
    "eyebrow": "Community",
    "title": "Forums, showcases and projects are on the way.",
    "tag": "Coming soon",
    "cards": [
        Item("Forums", "Ask, answer and share what you know about the engine."),
        Item("Showcases", "Publish what you've built with Axcenity."),
        Item("Projects", "Connect GitHub repositories and organise your team."),
    ],
}

HOME_FINAL = {
    "title": "Start building.",
    "body": "Download the alpha for Windows, macOS or Linux, then follow the getting-started guide.",
    "primary": Link("Download alpha", external=RELEASES_URL),
    "secondary": Link("Getting started", external=GETTING_STARTED_URL),
}


def all_links() -> list[Link]:
    """Every link in this module, for the link checks in the tests."""
    links = [*NAV_LINKS, SIGN_IN, DOWNLOAD, HOME_TOOLBOX["cta"]]
    for block in (HOME_HERO, HOME_FINAL):
        links += [block["primary"], block["secondary"]]
    for column in FOOTER_COLUMNS:
        links.extend(column.links)
    return links
