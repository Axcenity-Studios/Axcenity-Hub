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

from marketing import credits, drawings, github, legal, media, releases

# The engine's canonical repository (the README's older account redirects here).
ENGINE_REPO_URL = github.ENGINE_REPO_URL
# Every release is a prerelease, so link the list, never /releases/latest (it 404s).
RELEASES_URL = f"{ENGINE_REPO_URL}/releases"
# The engine's newest release tag (Cargo.toml's workspace version), for Home's badge. Only
# /download/ reads releases from GitHub (marketing/releases.py).
ENGINE_VERSION = "v0.3.0-alpha.1"

# The Axcenity Toolbox: its own repository for now (it moves into the Hub in a later phase).
TOOLBOX_REPO_URL = "https://github.com/pj1163928/project-two-building-with-apis"
# The commit the /toolbox/ page's commands and screenshots were taken from.
TOOLBOX_COMMIT = "5b17c1d9146201ef2bb4fa7abf68f3f909d695e8"
# How the Toolbox screenshots were made and what each showed (beside them, in media_sources/).
TOOLBOX_CAPTURE_RECORD = "marketing/media_sources/toolbox-capture.json"


@dataclass(frozen=True)
class Link:
    """One link: internal (a URL name with its args, optionally a #fragment), external (an
    https URL) or coming soon. An internal link's `section` (a URL namespace) marks it as
    the current page anywhere in that section, as Docs is on every /docs/ page."""

    label: str
    url_name: str = ""
    external: str = ""
    soon: bool = False
    fragment: str = ""
    args: tuple[str, ...] = ()
    section: str = ""

    def __post_init__(self) -> None:
        targets = bool(self.url_name) + bool(self.external)
        if self.soon and targets:
            raise ValueError(f"{self.label}: a coming-soon link has no target")
        if not self.soon and targets != 1:
            raise ValueError(f"{self.label}: give exactly one of url_name or external")
        if (self.fragment or self.args or self.section) and not self.url_name:
            raise ValueError(
                f"{self.label}: only an internal link takes a fragment, args or section"
            )

    @property
    def href(self) -> str:
        """The URL to link to, or "" for a coming-soon item."""
        if self.url_name:
            url = reverse(self.url_name, args=self.args)
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
# What a capture shows, and the caption it must start with: a frame of the engine, or a
# screenshot of the Toolbox (a real capture, but never of the engine).
CAPTURE_SUBJECTS = {"engine": "Engine capture", "toolbox": "Toolbox screenshot"}
# The canvas loops (static/reel/loops/<name>.js) a media item may run.
LOOPS = ("editor", "terrain", "logic", "toolbox", "wipe", "animation")


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
# The frames beside the Toolbox banner's, Community's and the closing section's copy (16:10):
# full width below 1024 px, then half the page ((min(100vw, 1400) − 64) / 2).
FRAME_SECTION = {"360–767 px": (735, 459), "768–1023 px": (959, 599), "1024 px and up": (668, 418)}
SECTION_SIZES = (
    "(min-width: 1024px) calc((min(100vw, 1400px) - 64px) / 2), "
    "(min-width: 768px) calc(100vw - 64px), calc(100vw - 32px)"
)
# A 16:9 picture covering a 16:10 frame is drawn 10/9 as wide as the frame.
COVER_16_9 = 10 / 9


def _covered(sizes: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    return {where: (round(w * COVER_16_9), h) for where, (w, h) in sizes.items()}


FRAME_DISPLAY = {
    "inline": Display(FRAME_SIZES["inline"], FRAME_INLINE),
    "stage": Display(FRAME_SIZES["stage"], FRAME_STAGE),
}
SECTION_DISPLAY = {"section": Display(SECTION_SIZES, FRAME_SECTION)}
COVER_DISPLAY = {
    "inline": Display(
        "(min-width: 768px) calc((100vw - 64px) * 1.112), calc((100vw - 32px) * 1.112)",
        _covered(FRAME_INLINE),
    ),
    "stage": Display("calc((min(100vw, 1400px) - 128px) * 0.6173)", _covered(FRAME_STAGE)),
    # The wipe's still, without JavaScript (Community).
    "section": Display(
        "(min-width: 1024px) calc((min(100vw, 1400px) - 64px) * 0.5556), "
        "(min-width: 768px) calc((100vw - 64px) * 1.112), calc((100vw - 32px) * 1.112)",
        _covered(FRAME_SECTION),
    ),
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
    # Where it shows, by slot ("inline", "stage", "section").
    display: dict[str, Display] = field(default_factory=dict)
    # Words drawn inside a recreation (panel names and the like), or its code.
    labels: dict = field(default_factory=dict)
    code: str = ""
    # A capture a loop draws (the wipe's lit end): its WebP derivatives go to the canvas.
    capture: "Media | None" = None
    # What a capture shows (CAPTURE_SUBJECTS): the engine, or the Toolbox.
    subject: str = "engine"
    # The same capture in light colours, shown instead whenever the site is light.
    light: "Media | None" = None

    def __post_init__(self) -> None:
        if self.kind not in MEDIA_KINDS:
            raise ValueError(f"{self.key}: kind must be one of {sorted(MEDIA_KINDS)}")
        if self.subject not in CAPTURE_SUBJECTS:
            raise ValueError(f"{self.key}: subject must be one of {sorted(CAPTURE_SUBJECTS)}")
        if self.kind == "illustrative" and self.subject != "engine":
            raise ValueError(f"{self.key}: only a capture has a subject")
        if not self.caption.startswith(self.label):
            raise ValueError(f"{self.key}: a {self.kind} caption starts {self.label!r}")
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
        if self.light and not self.light.is_light_twin_of(self):
            raise ValueError(f"{self.key}: its light twin is the same capture, framed the same")

    def is_light_twin_of(self, dark: "Media") -> bool:
        """Whether this is `dark` in light colours: a capture of the same subject, size,
        caption and display, with no twin of its own."""
        return (
            self.kind == dark.kind == "capture"
            and self.subject == dark.subject
            and self.source_size == dark.source_size
            and self.caption == dark.caption
            and self.display == dark.display
            and self.light is None
            and self.key != dark.key
        )

    @property
    def label(self) -> str:
        """What its caption must start with: "Engine capture", "Toolbox screenshot" or
        "Illustrative"."""
        return CAPTURE_SUBJECTS[self.subject] if self.kind == "capture" else MEDIA_KINDS[self.kind]

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
    def capture_srcset(self) -> str:
        """The WebP derivatives of the capture this loop draws, for its player to pick from."""
        return self.capture.srcset("webp") if self.capture else ""

    @property
    def labels_json(self) -> str:
        """The drawn words as JSON, for a loop's canvas (escaped into an attribute)."""
        return json.dumps(self.labels, ensure_ascii=False)


VIDEO_TYPES = {".mp4": "video/mp4", ".webm": "video/webm"}


@dataclass(frozen=True)
class VideoSource:
    """One encoding of a video: a path under static/ and its RFC 6381 codecs string. The
    codecs go in the `<source>`'s type, so a browser that can't decode them (Safari
    without AV1) skips to the next source instead of failing on this one."""

    file: str
    codecs: str

    def __post_init__(self) -> None:
        if not any(self.file.endswith(ext) for ext in VIDEO_TYPES):
            raise ValueError(f"{self.file}: a video is one of {sorted(VIDEO_TYPES)}")
        if not self.codecs:
            raise ValueError(f"{self.file}: give its codecs string")

    @property
    def mime(self) -> str:
        container = next(t for ext, t in VIDEO_TYPES.items() if self.file.endswith(ext))
        return f'{container}; codecs="{self.codecs}"'


@dataclass(frozen=True)
class BackdropVideo:
    """A film looping full bleed behind the hero's copy. `sources` are tried in order
    (the smallest first, then what every browser plays); `poster` is a path under static/
    that shows while it loads and under reduced motion."""

    sources: tuple[VideoSource, ...]
    kind: str
    caption: str
    provenance: str
    poster: str = ""

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("a backdrop video needs at least one source")
        name = self.sources[0].file
        if self.kind not in MEDIA_KINDS:
            raise ValueError(f"{name}: kind must be one of {sorted(MEDIA_KINDS)}")
        if not self.caption.startswith(MEDIA_KINDS[self.kind]):
            raise ValueError(f"{name}: a {self.kind} caption starts {MEDIA_KINDS[self.kind]!r}")


# The editor's words, shared by the loops.
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

# The Toolbox (crates/editor-toolbox/src/lib.rs): its kind tabs, toolbar, source
# chips, cards ("Source · category · maps") and the messages a drop onto the Scene View
# prints (app/toolbox.rs, install.rs). The cards' names are illustrative search results.
EDITOR_TOOLBOX = {
    "button": "Toolbox",  # the Assets pane's button that opens it
    "kinds": ["Textures", "Skies", "Models", "Sounds"],
    "toolbar": ["Search", "Packs", "All sources"],
    "placeholder": "Search materials",
    "query": "rock",
    "search": "Search",
    "options": ["2K", "JPG"],
    "chips": ["All", "ambientCG 12", "Poly Haven 12"],
    "searching": "Searching…",
    "get": "Get",
    # Each card: name, detail line, and the pattern its picture is drawn with.
    "cards": [
        ("Rock 030", "ambientCG · Rock · Color, Normal", "rock"),
        ("Rocks 011", "ambientCG · Rock · Color, Normal", "pebbles"),
        ("Rock Wall 08", "Poly Haven · Rock · Color, Normal", "wall"),
        ("Cliff Strata", "Poly Haven · Rock · Color, Rough", "strata"),
        ("Gravel 022", "ambientCG · Ground · Color, Normal", "gravel"),
        ("Slate Plates", "Poly Haven · Rock · Color, Normal", "slate"),
        ("Rock 051", "ambientCG · Rock · Color, Normal", "rock"),
        ("Rocks 004", "ambientCG · Rock · Color, Normal", "pebbles"),
    ],
    "downloading": "Downloading Rock 030…",
    "cancel": "Cancel",
}
# The Animation pane (crates/editor/src/animation/: chrome.rs, clip_ui.rs,
# property_editor/dope_sheet.rs, transport.rs), keying a Wave clip on the default
# humanoid's bones (assets/characters/humanoid/rig.py) at 30 fps.
EDITOR_ANIMATION = {
    "views": ["Logic", "Clips & Rigging", "Sequencer"],
    "new": "+ New",
    "record": "Record",
    "bones": "Show Bones",
    "preview": "Preview on Character",
    "recording": "Recording: moving something in the preview sets a key at {t} s",
    "modes": ["Dope sheet", "Curves"],
    "rows": ["RightUpperArm · Bone", "RightLowerArm · Bone", "Spine · Bone", "Head · Bone"],
    "clip": "Wave",
    "fps": 30,
}

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

# The Terrain Studio's and Scatter pane's words, drawn by the World pillar's loop.
TERRAIN_LABELS = {
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
}

# The block graph's and its Luau's words, drawn by the Logic pillar's loop.
LOGIC_LABELS = {
    "graph": "Graph",
    "code": "Luau",
    # The script's tab (layout.rs sync_scripts) and the bar above it that switches it between
    # Code, Blocks and Graph, with its hint (scripts.rs mode_bar).
    "script": "Script",
    "views": ["Code", "Blocks", "Graph"],
    "switch_hint": "Switch any time: the script runs the same either way.",
    # The same script in the Blocks view (block_editor.rs sections()): an Events hat and a
    # Looks block under it, the position a Sensing reporter (Position of touching part).
    # Each part: ["label", words], ["menu", choice], ["text" | "number", value],
    # ["vector", [x, y, z]] or ["reporter", category, parts].
    "stack": [
        {
            "category": "events",
            "icon": "hand",
            "rows": [
                [["label", "when"], ["menu", "Pad"], ["label", "is touched"], ["menu", "Any Part"]],
            ],
        },
        {
            "category": "looks",
            "icon": "sparkle",
            "rows": [
                [
                    ["label", "spawn decal"],
                    ["text", "assets/textures/scorch.png"],
                    ["label", "at"],
                    [
                        "reporter",
                        "sensing",
                        [
                            ["menu", "Position"],
                            ["label", "of"],
                            ["reporter", "sensing", [["label", "touching part"]]],
                        ],
                    ],
                    ["label", "facing"],
                    ["vector", ["0", "1", "0"]],
                ],
                [
                    ["label", "size"],
                    ["number", "2.5"],
                    ["label", "fading after"],
                    ["number", "4"],
                    ["label", "seconds"],
                ],
            ],
        },
    ],
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
}

RENDERER = Media(
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
)

# The Toolbox page's screenshots: real captures of the running Toolbox, never of the engine,
# each in the Toolbox's dark theme with its light-theme twin (shown when the site is light).
# TOOLBOX_CAPTURE_RECORD holds how they were made and what each one showed.


def _toolbox_screenshot(screen: str, caption: str, alt: str, shows: str, scroll: int) -> Media:
    """One screen of the Toolbox, dark, with its `light` twin: the same capture settings and
    content, in the Toolbox's light theme. `alt` has a {theme} slot."""
    shots = {}
    for scheme in ("light", "dark"):
        suffix = "-light" if scheme == "light" else ""
        scrolled = f", work area scrolled {scroll} px" if scroll else ""
        shots[scheme] = Media(
            key=f"toolbox-{screen}{suffix}",
            kind="capture",
            subject="toolbox",
            caption=caption,
            alt=alt.format(theme=f"in its {scheme} theme"),
            provenance=(
                f"The Axcenity Toolbox ({TOOLBOX_REPO_URL}) at commit {TOOLBOX_COMMIT[:7]}, run "
                f"locally after seed_demo and signed in as the demo member demo_mira. {shows} "
                "Captured 2026-11-24 in headless Chromium 159 at 1280×800 and a 2× pixel ratio, "
                f"{scheme} scheme, reduced motion{scrolled}. Not edited, cropped or rescaled. "
                f'Full record (screen "{screen}{suffix}"): {TOOLBOX_CAPTURE_RECORD}.'
            ),
            source=f"toolbox-{screen}{suffix}-2560x1600.png",
            source_size=(2560, 1600),
            display=SECTION_DISPLAY,
            light=shots.get("light"),
        )
    return shots["dark"]


TOOLBOX_SCREENS = [
    _toolbox_screenshot(
        "discover",
        "Toolbox screenshot · Discover",
        "The Axcenity Toolbox's Discover page {theme}, signed in as a demo member. The search "
        "box holds rock, the Textures tile is chosen beside HDRIs, Models and Sounds, and the "
        "ambientCG shelf shows 12 results, the first row Ground 111, Rock 064, Rock 063 and "
        "Rock 058 as material spheres, each marked CC0 with buttons to save, add to a pack, "
        "open and show details. The side panel lists Discover, Library, Packs and Attribution "
        "above the licence filters.",
        "/discover/?type=textures&q=rock with live ambientCG and Poly Haven results (12 each).",
        225,
    ),
    _toolbox_screenshot(
        "library",
        "Toolbox screenshot · Library",
        "The Toolbox's Library page {theme}, Your library, showing 1 to 12 of 17 entries "
        "newest first: the Goegap HDRI marked Testing, a birds forest sound marked Approved, "
        "the Metal Plates 006 texture marked Approved with four stars, and a forge blacksmith "
        "sound marked To review, each with its community rating, then a row of sky HDRIs. The "
        "side panel filters by type, provider and status.",
        "/library/ (the seeded entries; thumbnails from the providers' CDNs).",
        0,
    ),
    _toolbox_screenshot(
        "packs",
        "Toolbox screenshot · Packs",
        "The Toolbox's pack builder {theme}, for the Medieval Village pack. Its Items list "
        "shows Cobblestone Floor 03, Church Bricks 03 and Planks 037 A, each with a file "
        "variant such as 2K JPG, 9 files, 12.0 MB, and an import path such as "
        "textures/cobblestone_floor_03/. Beside it, Add from my library lists saved HDRIs, "
        "sounds and textures, each with an Add button.",
        "/packs/1/edit/ (the seeded Medieval Village pack).",
        700,
    ),
]

MEDIA = {
    "renderer": RENDERER,
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
        labels=TERRAIN_LABELS,
    ),
    "logic": Media(
        key="logic",
        kind="illustrative",
        caption="Illustrative · blocks as Luau",
        alt=(
            "An animated recreation of a script in the block editor, with its Luau below. In "
            "the Blocks view an amber When touched block for the Pad appears, and a violet Spawn "
            "decal block snaps on under it: spawn the scorch texture at the position of the "
            "touching part, facing up, size 2.5, fading after 4 seconds. The Luau they become "
            "types out below. The bar above the script then switches from Blocks to Graph, which "
            "shows the same script as a When Touched node and a Spawn Decal node; a wire joins "
            "them and a pulse runs along it, as when the Pad is touched. It switches back to "
            "Blocks before the blocks and the code fade away."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/loops/logic.js. The bar follows the script "
            "tab's mode bar (crates/editor/src/scripts.rs mode_bar: Code, Blocks, Graph and its "
            "hint). The Blocks view follows crates/editor/src/block_editor.rs (each block's "
            "sections, its sizes, categories and icons) and block_editor/painter.rs and "
            "canvas.rs (hats, statements, menus, typed fields, reporters, the dot grid), in the "
            "editor's category colours with Increase contrast, drawn icons standing in for its "
            "icon font. The Graph view follows block_editor/graph.rs and graph/nodes.rs "
            "(titles, rows, pin types and colours, the Events and Looks hues) and the shared "
            "canvas (crates/editor-node-graph/src/canvas.rs: grid, exec and value pins, wires). "
            "The Luau is the translator's output (crates/blocks-runtime/src/translate.rs), "
            "coloured as crates/editor-kit/src/lua_syntax.rs colours it, its light colours "
            "darkened to 4.5:1 on the site's light grey. Without JavaScript: the same code, "
            "highlighted."
        ),
        fallback_alt="Luau code: when the part is touched, spawn a scorch decal where it was hit.",
        drawn="marketing/media/luau.html",
        loop="logic",
        display=FRAME_DISPLAY,
        code=LUAU_SAMPLE,
        labels=LOGIC_LABELS,
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
            "Drawn live on a canvas by static/reel/loops/editor.js with the editor pieces "
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
            # The floating window's title.
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
    "toolbox": Media(
        key="toolbox",
        kind="illustrative",
        caption="Illustrative · Toolbox",
        alt=(
            "An animated recreation of the Axcenity editor's Toolbox. Above the Assets pane the "
            "Scene View shows a grey block, the Pad, turning slowly. A pointer presses the Toolbox "
            "button, which opens the Toolbox as a tab beside Assets. It types rock into the search "
            "field and presses Search, and texture cards from ambientCG and Poly Haven pop in. It "
            "drags the first, Rock 030, onto the Pad: the Toolbox reports the download and the Pad "
            "takes on the rock texture. Then the Toolbox closes and the texture fades away."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/loops/toolbox.js with the editor pieces in "
            "static/reel/drawing/ (editor.js, toolbox.js). The Toolbox's kind tabs, toolbar, "
            "source chips and cards follow crates/editor-toolbox/src/lib.rs, the drop onto the "
            "Scene View and its download follow app/toolbox.rs and install.rs, and the Assets "
            "pane's Toolbox button follows asset_browser/panel.rs. The cards' names are "
            "illustrative search results and their pictures are drawn stand-ins. Without "
            "JavaScript: the drawn results in templates/marketing/media/toolbox.html."
        ),
        fallback_alt=(
            "A drawing of the Toolbox's search for rock: a grid of texture cards from ambientCG "
            "and Poly Haven, each with Get."
        ),
        drawn="marketing/media/toolbox.html",
        loop="toolbox",
        display=SECTION_DISPLAY,
        labels={
            "tabs": EDITOR_DOCK,
            "assets": EDITOR_ASSETS,
            "toolbox": EDITOR_TOOLBOX,
        },
    ),
    "wipe": Media(
        key="wipe",
        kind="illustrative",
        caption="Illustrative · renderer wipe",
        alt=(
            "An animated recreation of the editor's Scene View. A gallery room is blocked out in "
            "plain grey shapes: walls, plinths, a tall slab, a cylinder and a sphere rising from "
            "the floor. A scan line sweeps across and leaves behind the ray-traced render of the "
            "same room, with reflections on the floor and spheres, soft shadows and bounced "
            "light, as the camera pushes slowly in. The lit room then dissolves back to grey."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/loops/wipe.js with static/reel/drawing/"
            "renderer.js. The lit end is the Showcase-Renderer engine capture (one "
            "of its WebP derivatives, never upscaled); the grey room is drawn "
            "over the capture's own layout, as no graybox capture of that camera exists. "
            "Without JavaScript: the capture itself."
        ),
        # Its fallback is the capture's own <picture>, described by the capture's alt.
        fallback_alt=RENDERER.alt,
        drawn="marketing/media/wipe.html",
        loop="wipe",
        display=SECTION_DISPLAY,
        labels={"tabs": EDITOR_DOCK},
        capture=RENDERER,
    ),
    "animation": Media(
        key="animation",
        kind="illustrative",
        caption="Illustrative · Animation pane",
        alt=(
            "An animated recreation of the editor's Animation pane, in its Clips & Rigging view. "
            "A character stands in the preview beside an empty Wave clip. A pointer turns Record "
            "on and poses the character's arm by its hand; at each step a column of diamond keys "
            "appears in the dope sheet for the RightUpperArm, RightLowerArm, Spine and Head "
            "bones. It presses Play, and the character waves as the playhead runs the clip. "
            "Then the keys fade, leaving the empty clip."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/loops/animation.js with static/reel/drawing/"
            "animation.js. The pane follows crates/editor/src/animation/ (chrome.rs, clip_ui.rs, "
            "property_editor/dope_sheet.rs, transport.rs) and the humanoid's bone names in "
            "assets/characters/humanoid/rig.py, with the character drawn as a simple mannequin "
            "and the playhead in ink rather than the editor's red. Without JavaScript: the drawn "
            "dope sheet in templates/marketing/media/animation.html."
        ),
        fallback_alt=(
            "A drawing of the Animation pane's dope sheet: a Wave clip with keys on the "
            "RightUpperArm, RightLowerArm, Spine and Head bones."
        ),
        drawn="marketing/media/animation.html",
        loop="animation",
        display=SECTION_DISPLAY,
        labels={"tabs": EDITOR_DOCK, "animation": EDITOR_ANIMATION},
    ),
    **{shot.key: shot for screen in TOOLBOX_SCREENS for shot in (screen, screen.light)},
}

# ---------- Shell: nav and footer ----------

NAV_LINKS = [
    Link("Engine", url_name="marketing:home"),
    Link("Features", url_name="marketing:home", fragment="features"),
    Link("Toolbox", url_name="marketing:toolbox"),
    Link("Docs", url_name="documentation:index", section="documentation"),
    Link("Community", soon=True),
]
# allauth's sign-in page (its URL names aren't namespaced); signed in, the nav shows Account.
SIGN_IN = Link("Sign in", url_name="account_login")
ACCOUNT = Link("Account", url_name="accounts:profile", section="accounts")
# The engine docs, served by the documentation app from its snapshot (/docs/).
GETTING_STARTED = Link(
    "Getting started", url_name="documentation:page", args=("learn/getting-started",)
)
DOWNLOAD = Link("Download", url_name="marketing:download")

FOOTER_TAGLINE = "Free and open source. Alpha software: expect breaking changes."
FOOTER_SIGNATURE = "Axcenity Studios · 2026"
FOOTER_COLUMNS = [
    FooterColumn(
        "Engine",
        [
            Link("Download", url_name="marketing:download"),
            Link("GitHub", external=ENGINE_REPO_URL),
            Link("Credits", url_name="marketing:credits"),
        ],
    ),
    FooterColumn(
        "Learn",
        [
            Link("Docs", url_name="documentation:index"),
            GETTING_STARTED,
            Link("Toolbox", url_name="marketing:toolbox"),
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
    # A line icon from partials/icon.html, drawn beside it (decorative).
    icon: str = ""


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
    "primary": Link("Download alpha", url_name="marketing:download"),
    "secondary": Link("Read the docs", url_name="documentation:index"),
    # The film filling the hero (docs/frontend/media.md has its cut list), and its button's
    # screen-reader names.
    "backdrop": BackdropVideo(
        sources=(
            VideoSource("marketing/media/homestead/homestead-1920.webm", "av01.0.08M.08"),
            VideoSource("marketing/media/homestead/homestead-1280.mp4", "avc1.64001F"),
        ),
        kind="capture",
        caption="Engine capture · Desert Homestead film",
        provenance=(
            "The engine's examples/desert-homestead project, filmed by its authoring/film "
            "tool: the engine's own renderer at 1920×804, frame by frame at a fixed step, "
            "hardware ray tracing on a Radeon RX 9070 XT (desert-homestead-cinematic-1080p-v3"
            ".mp4). Cut to 53 s for the hero: the picture only (no title, captions or end "
            "card), eleven of its shots cross-dissolved, no lightning, no grading, opening "
            "and closing on the same frame so it loops. AV1, and H.264 at 1280×536."
        ),
        poster="marketing/media/homestead/homestead-poster.webp",
    ),
    "video_controls": {"play": "Play video", "pause": "Pause video"},
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
        Item("Build", "Parts, models and terrain in the 3D Scene.", "01", "build"),
        Item("Script", "Luau or visual blocks, on the server and on each player.", "02", "script"),
        Item("Test", "Press Play (F5) to play your game inside the editor.", "03", "test"),
        Item("Export", "Standalone games for Windows, macOS and Linux.", "04", "export"),
    ],
}

HOME_FACTS = {
    "title": "At a glance",
    "stats": [
        Item("Free", "Open source under the Apache 2.0 licence. No royalties.", icon="free"),
        Item("Rust", "A native, memory-safe core.", icon="rust"),
        Item("3 OS", "Windows, macOS and Linux desktops.", icon="os"),
        Item("Alpha", "Early days: expect breaking changes.", icon="alpha"),
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
    "cta": Link("Explore the Toolbox", url_name="marketing:toolbox"),
    "media": MEDIA["toolbox"],
    "loop_controls": LOOP_CONTROLS,
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
    "media": MEDIA["wipe"],
    "loop_controls": LOOP_CONTROLS,
}

HOME_FINAL = {
    "title": "Start building.",
    "body": "Download the alpha for Windows, macOS or Linux, then follow the getting-started guide.",
    "primary": Link("Download alpha", url_name="marketing:download"),
    "secondary": GETTING_STARTED,
    # The getting-started guide's first steps (documentation/learn/getting-started.md).
    "steps": [
        Item("Install", "A Windows setup wizard, a macOS disk image or a Linux package.", "01"),
        Item("New Project", "Start from Baseplate, Empty or a playable genre template.", "02"),
        Item("Play", "Press F5 to run it, and Shift+F5 to put the world back.", "03"),
    ],
    "media": MEDIA["animation"],
    "loop_controls": LOOP_CONTROLS,
}


# ---------- Toolbox page (/toolbox/) ----------


@dataclass(frozen=True)
class ToolboxFeature:
    """One of the Toolbox's three core features, beside its screenshot."""

    number: str
    label: str
    title: str
    body: str
    points: list[str]
    media: Media


@dataclass(frozen=True)
class Provider:
    """A provider Discover searches: what it offers and under which licence."""

    name: str
    offers: str
    licence: str


@dataclass(frozen=True)
class Command:
    """A shell command and what it does (rendered as a trailing # comment)."""

    line: str
    note: str = ""


TOOLBOX_PAGE = {
    "title": "Axcenity Toolbox",
    "description": (
        "Axcenity Toolbox: find free game assets from ambientCG, Poly Haven and Openverse, "
        "save them to a library and build packs the engine imports. Run it locally with uv."
    ),
    "eyebrow": "Companion tool",
    "lede": (
        "Find free game assets from ambientCG, Poly Haven and Openverse, save them to your "
        "own library, and build packs the engine imports."
    ),
    "note": (
        "A Django app styled like the editor. For now it runs on your own machine, and no "
        "provider needs an API key."
    ),
    "primary": Link("View on GitHub", external=TOOLBOX_REPO_URL),
    "secondary": Link("Run it locally", url_name="marketing:toolbox", fragment="run"),
    "features": [
        ToolboxFeature(
            "01",
            "Discover",
            "Search every provider at once.",
            "Pick Textures, HDRIs, Models or Sounds and search. Each provider gets its own "
            "shelf, with Load more and Shuffle. If one provider is down, its shelf shows an "
            "error and a Retry button, and the others keep working.",
            [
                "Filter results by licence and commercial use",
                "Save a result, or add it straight to a pack",
                "Open details, or play a sound before you save it",
            ],
            MEDIA["toolbox-discover"],
        ),
        ToolboxFeature(
            "02",
            "Library",
            "Your assets, with your notes.",
            "Every asset you save keeps your notes, a 1–5 rating, tags and a review status: "
            "To review, Testing, Approved or Rejected. Search, filter, sort and page through "
            "it, even when every provider is offline.",
            [
                "A status history for every change",
                "Community ratings where other members rated the same asset",
                "Download bundles at the resolution and format you choose",
            ],
            MEDIA["toolbox-library"],
        ),
        ToolboxFeature(
            "03",
            "Packs",
            "Packs the engine imports.",
            "Group saved assets for one project. Choose each item's file variant and import "
            "path, then export the pack as a JSON manifest or a zip of its files, with "
            "CREDITS.txt and the licence notice written for you.",
            [
                "Private, unlisted (shared by link) or public",
                "A warning when an item isn't cleared for commercial use",
                "A gallery of public packs on the Toolbox's main page",
            ],
            MEDIA["toolbox-packs"],
        ),
    ],
    "providers_title": "Where Discover searches",
    "providers": [
        Provider("ambientCG", "PBR materials, HDRIs and 3D models", "CC0"),
        Provider("Poly Haven", "Textures, HDRIs and models", "CC0"),
        Provider("Openverse Audio", "Sound effects and music", "Per item: CC0, CC BY and others"),
    ],
    "run": {
        "eyebrow": "Run it locally",
        "title": "Clone it, run four commands, open your browser.",
        "body": (
            "All you need is uv: it installs Python 3.13 if it's missing, and SQLite comes "
            "with Python. No pip and no Node."
        ),
        "terminal": "Terminal",
        # The Toolbox README's Setup and Running blocks, at TOOLBOX_COMMIT.
        "commands": [
            Command(f"git clone {TOOLBOX_REPO_URL}"),
            Command("cd project-two-building-with-apis"),
            Command("uv sync", "install the dependencies"),
            Command("uv run python manage.py migrate", "create db.sqlite3"),
            Command(
                "uv run python manage.py seed_demo", "load the demo members, libraries and packs"
            ),
            Command(
                "uv run python manage.py tailwind runserver",
                "starts Django and the Tailwind watcher",
            ),
        ],
        "open_label": "Then open",
        "open_url": "http://127.0.0.1:8000/",
        "offline": (
            "Discover needs the internet to reach the providers. Everything else works "
            "offline on the demo data: the library, packs, the gallery, exports and the API."
        ),
        "demo": {
            "title": "Demo credentials",
            "body": (
                "For your local copy only. seed_demo creates three demo members, demo_mira, "
                "demo_otto and demo_juno, with the password the README publishes:"
            ),
            "password": "toolbox-demo",
            "privileges": (
                "They're regular members with no staff or admin rights. Never run seed_demo "
                "on a server other people can reach, and never give a demo account more."
            ),
        },
        "readme": Link("Read the README", external=f"{TOOLBOX_REPO_URL}#readme"),
    },
}


# ---------- Download page (/download/) ----------
# The engine's LICENSE and NOTICE, copied in unchanged (the engine repository is read only)
# from LEGAL_COMMIT by `manage.py refresh_credits`, shown in full in the download agreement
# and on /credits/, with the crate and package lists it generates (marketing/credits.py).
LEGAL_DIR = credits.LEGAL_DIR
ENGINE_CREDITS = credits.load(LEGAL_DIR / "engine.json")
HUB_CREDITS = credits.load(LEGAL_DIR / "hub.json")
LEGAL_COMMIT = ENGINE_CREDITS["commit"]
ENGINE_LICENSE = (LEGAL_DIR / "LICENSE").read_text(encoding="utf-8")
ENGINE_NOTICE = (LEGAL_DIR / "NOTICE").read_text(encoding="utf-8")

# The release itself comes from GitHub (marketing/releases.py); this is the page's frame.
# The labels, hints and commands are the engine's own release notes
# (packaging/release-notes.md.tpl in the engine repository).

DOWNLOAD_BUILDS = [
    releases.BuildKind(
        "windows",
        "Setup wizard",
        "Run the setup wizard. If SmartScreen appears, choose More info, then Run anyway.",
        tail="-windows-x86_64.exe",
        icon="installer",
        primary=True,
    ),
    releases.BuildKind(
        "macos",
        "Disk image",
        "Agree to the license and drag Axcenity Editor onto Applications. It's unsigned, "
        "so Control-click the app and choose Open the first time.",
        tail="-macos-universal.dmg",
        icon="disk",
        primary=True,
    ),
    releases.BuildKind(
        "linux",
        "Any Linux, no install (AppImage)",
        "Make it executable, then run it.",
        command="chmod +x {file}",
        tail="-linux-x86_64.AppImage",
        icon="app",
        primary=True,
    ),
    releases.BuildKind(
        "linux",
        "Debian / Ubuntu",
        command="sudo apt install ./{file}",
        tail="-linux-x86_64.deb",
        icon="package",
    ),
    releases.BuildKind(
        "linux",
        "Fedora / RHEL / openSUSE",
        command="sudo dnf install ./{file}",
        tail="-linux-x86_64.rpm",
        icon="package",
    ),
    releases.BuildKind(
        "linux",
        "Arch Linux",
        command="sudo pacman -U {file}",
        tail="-linux-x86_64.pkg.tar.zst",
        icon="package",
    ),
    releases.BuildKind(
        "linux",
        "Any Linux, portable (tar.gz)",
        "Extract it and run ./axcenity-editor.",
        tail="-linux-x86_64.tar.gz",
        icon="archive",
    ),
    releases.BuildKind(
        "other",
        "Updater archive",
        "What the editor's own updater installs. You don't need it.",
        tail="-windows-x86_64-update.zip",
        icon="archive",
    ),
    releases.BuildKind(
        "other",
        "Checksums",
        "Every file's SHA-256, one per line.",
        name="SHA256SUMS.txt",
        icon="hash",
    ),
    releases.BuildKind(
        "other",
        "Signed release manifest",
        "Lists every file's SHA-256 and is signed with minisign.",
        name="axcenity-release.json",
        icon="manifest",
    ),
    releases.BuildKind(
        "other",
        "Manifest signature",
        "Check the manifest with the engine's public key, axcenity-release.pub:",
        command="minisign -Vm axcenity-release.json -p axcenity-release.pub",
        name="axcenity-release.json.minisig",
        icon="key",
    ),
    releases.BuildKind(
        "other",
        "Release history",
        "The history the editor's Version Explorer reads.",
        name="axcenity-history.json",
        icon="history",
    ),
]

# Each system's line icon (templates/partials/icon.html): drawn for the Hub, not the
# systems' trademarked logos.
DOWNLOAD_SYSTEM_ICONS = {"windows": "windows", "macos": "macos", "linux": "linux", "other": "files"}

DOWNLOAD_PAGE = {
    "title": "Download",
    "description": (
        "Download Axcenity Engine, the free and open-source 3D game engine, for Windows, "
        "macOS or Linux: the newest alpha with its file sizes and SHA-256 checksums."
    ),
    "eyebrow": "Download",
    "headline": "Download Axcenity Engine.",
    "lede": (
        "Free and open source, for Windows, macOS and Linux. Each editor build includes "
        "players for all three, so File > Build Game can target any of them."
    ),
    "systems": {"windows": "Windows", "macos": "macOS", "linux": "Linux", "other": "Other files"},
    "alpha": "Alpha",
    "alpha_note": ("Alpha software: file formats and some APIs can still change between releases."),
    "download_for": "Download for",
    "other_systems": Link("Other systems", url_name="marketing:download", fragment="builds"),
    "choose": Link("Choose your build", url_name="marketing:download", fragment="builds"),
    "unknown_system": "We couldn't tell your system. Pick its build below.",
    "released": "Released",
    "notes": "Release notes on GitHub",
    "all_releases": Link("All releases on GitHub", external=RELEASES_URL),
    "stale": "GitHub didn't answer just now, so this is the release list as of",
    "unavailable": {
        "title": "The builds are on GitHub.",
        "body": (
            "We couldn't reach GitHub to list the newest release just now. Every build, "
            "with its checksums, is on the engine's Releases page."
        ),
        "link": Link("Open GitHub Releases", external=RELEASES_URL),
    },
    "builds_title": "Every build",
    "detected": "Your system",
    "download": "Download",
    "sha256": "SHA-256",
    "no_digest": "GitHub didn't publish one for this file. See SHA256SUMS.txt.",
    "verify": {
        "eyebrow": "Checking the download",
        "title": "Compare the checksum.",
        "body": (
            "GitHub computes each file's SHA-256 when it's uploaded. Hash your copy and "
            "compare it with the one listed beside the file."
        ),
        "commands": [
            ("Windows", "certutil -hashfile <file> SHA256"),
            ("macOS", "shasum -a 256 <file>"),
            ("Linux", "sha256sum <file>"),
        ],
    },
    "data_note": "Release data from the GitHub API, refreshed about once an hour.",
    # The agreement every download goes through (a dialog, or /download/agree/ without
    # JavaScript). The terms are the engine's own words: README.md's "License and trademark"
    # and LICENSE (Apache 2.0) sections 6 and 7. `quotes` are checked against the README.
    "agreement": {
        "title": "Before you download",
        "page_title": "License agreement",
        "description": (
            "The Apache License 2.0 and the Axcenity trademark terms you agree to before "
            "downloading Axcenity Engine."
        ),
        "lede": (
            "Axcenity Engine is free and open source. Downloading it means agreeing to "
            "its license and trademark terms:"
        ),
        "file_label": "You're downloading",
        "terms": [
            {
                "title": "Apache License 2.0",
                "body": "Axcenity Engine is licensed under the Apache License 2.0.",
            },
            {
                "title": "Your games are yours",
                "body": (
                    "Games you create with Axcenity belong entirely to you—no royalties and "
                    "no fees. Sell or distribute them however you choose."
                ),
            },
            {
                "title": "Forks are welcome",
                "body": (
                    "You may fork and modify the engine freely under the Apache License 2.0. "
                    "Keep the LICENSE and NOTICE files, mark any files you modify, and "
                    "distribute your fork under a different name."
                ),
            },
            {
                "title": "Trademark",
                "body": (
                    "Axcenity™ and Axcenity Engine™ (the word marks) are pending trademarks of "
                    "Paul Janota. The Apache License 2.0 does not grant permission to use the "
                    "Axcenity name or trademarks, except as required for reasonable and "
                    "customary use in describing the origin of the work and reproducing the "
                    "content of the NOTICE file."
                ),
            },
            {
                "title": "No warranty",
                "body": (
                    "The engine is provided \u201cas is\u201d, without warranties or conditions "
                    "of any kind (Apache License 2.0, section 7)."
                ),
            },
        ],
        # The engine's LICENSE and NOTICE in full, beside the terms (copies in marketing/legal/,
        # checked against the engine's checkout when it's on the machine).
        "full_text": {
            "label": "Full text",
            "tabs": [
                # Set as prose: the files' hard wraps joined so the pane can wrap them.
                {"key": "license", "label": "LICENSE", "blocks": legal.reflow(ENGINE_LICENSE)},
                {"key": "notice", "label": "NOTICE", "blocks": legal.reflow(ENGINE_NOTICE)},
            ],
            "credits_lede": "Every crate, package and font the engine is built from:",
            "credits": Link("Credits", url_name="marketing:credits"),
        },
        "checkbox": (
            "I have read and agree to the Apache License 2.0 and the Axcenity trademark terms."
        ),
        "agree": "Agree and download",
        "cancel": "Cancel",
        "back": Link("Back to every build", url_name="marketing:download", fragment="builds"),
        "required": "Tick the box to agree before downloading.",
    },
    # Cards that fill the gap a full-width system panel's last row leaves (Linux, Other files).
    "tips": {
        "linux": {
            "icon": "app",
            "title": "Not sure which?",
            "body": (
                "Start with the AppImage: it runs on any distribution without installing "
                "anything. The packages install through your distribution's package manager."
            ),
        },
        "other": {
            "icon": "hash",
            "title": "Check your download",
            "body": (
                "The checksums, the signed manifest and its signature confirm each file is "
                "the one this release published."
            ),
            "link": Link("How to check", url_name="marketing:download", fragment="verify"),
        },
    },
    # Beside the checksum commands: the engine's own from-source steps
    # (documentation/learn/getting-started.md, Install).
    "from_source": {
        "eyebrow": "From source",
        "title": "Or build it yourself.",
        "body": "Install Rust with rustup, then clone the engine and run the editor from its folder:",
        "terminal": "Terminal",
        "commands": [
            f"git clone {ENGINE_REPO_URL}.git",
            "cd Axcenity-Engine",
            "cargo run -p axcenity-editor",
        ],
        "note": (
            "Windows and Linux are the main platforms and are checked on every change. "
            "macOS works but is checked less often."
        ),
        "links": [
            GETTING_STARTED,
            Link(
                "System requirements",
                url_name="documentation:page",
                args=("reference/system-requirements",),
            ),
        ],
    },
}


# ---------- Credits (/credits/) ----------
# Who made what the engine and the Hub are built from. The crate and package lists are
# generated (marketing/credits.py); the fonts and build tools below are the Hub's own.
_CRATES = ENGINE_CREDITS["crates"]
_PACKAGES = HUB_CREDITS["packages"]
_TOOLS = HUB_CREDITS.get("tools", {})

CREDITS_PAGE = {
    "title": "Credits",
    "description": (
        "Everyone whose code, fonts and assets Axcenity Engine and the Axcenity Hub are "
        "built on: the engine's NOTICE, every Rust crate and every Python package."
    ),
    "eyebrow": "Credits",
    "headline": "Built on other people's work",
    "lede": (
        "Axcenity Engine and this Hub stand on open-source code, fonts and assets made by "
        "thousands of people. Every one of them is listed here, from their own records."
    ),
    "note": (
        f"Generated from the engine's Cargo.lock at commit {LEGAL_COMMIT[:12]} and the "
        "Hub's uv.lock, and checked against both, so a new dependency can't go uncredited."
    ),
    "jump_label": "On this page",
    "sections": {
        "notice": {
            "number": "01",
            "label": "NOTICE",
            "title": "In the engine",
            "body": (
                "The models, programs, code and characters the engine's NOTICE file credits, "
                "in its own words."
            ),
            "blocks": legal.reflow(ENGINE_NOTICE),
            "source": Link(
                "Read NOTICE on GitHub", external=f"{ENGINE_REPO_URL}/blob/{LEGAL_COMMIT}/NOTICE"
            ),
        },
        "crates": {
            "number": "02",
            "label": "Crates",
            "title": f"{len(_CRATES)} Rust crates",
            "body": (
                "Every crate the engine's Cargo.lock resolves, for every system it builds for "
                "and with every optional feature on, grouped by licence. A crate that names "
                "no authors is credited to its contributors."
            ),
            "groups": credits.by_license(_CRATES),
            "count_label": "crates",
            "contributors": "Its contributors",
            "vendored": "Patched copy in the engine's vendor/",
        },
        "hub": {
            "number": "03",
            "label": "Hub",
            "title": "In this Hub",
            "body": (
                "The Python packages this website runs on and is tested with, from their own "
                "package metadata, and the fonts and stylesheet tools it ships."
            ),
            "groups": [
                {
                    "title": "Runs the site",
                    "entries": [p for p in _PACKAGES if p["group"] == "runtime"],
                },
                {
                    "title": "Builds and tests it",
                    "entries": [p for p in _PACKAGES if p["group"] != "runtime"],
                },
            ],
            "columns": ["Package", "Version", "Licence", "By"],
            "assets_title": "Fonts and styles",
            "assets": [
                {
                    "name": "Plus Jakarta Sans",
                    "by": "The Plus Jakarta Sans Project Authors (Tokotype)",
                    "license": "OFL-1.1",
                    "url": "https://github.com/tokotype/PlusJakartaSans",
                    "use": "Headings",
                },
                {
                    "name": "Inter",
                    "by": "The Inter Project Authors (Rasmus Andersson)",
                    "license": "OFL-1.1",
                    "url": "https://github.com/rsms/inter",
                    "use": "Body text",
                },
                {
                    "name": "JetBrains Mono",
                    "by": "The JetBrains Mono Project Authors (JetBrains)",
                    "license": "OFL-1.1",
                    "url": "https://github.com/JetBrains/JetBrainsMono",
                    "use": "Labels and code",
                },
                {
                    "name": "Tailwind CSS",
                    "version": _TOOLS.get("tailwindcss", ""),
                    "by": "Tailwind Labs",
                    "license": "MIT",
                    "url": "https://github.com/tailwindlabs/tailwindcss",
                    "use": "The stylesheet's base and utilities",
                },
                {
                    "name": "daisyUI",
                    "version": _TOOLS.get("daisyui", ""),
                    "by": "Pouya Saadeghi",
                    "license": "MIT",
                    "url": "https://github.com/saadeghi/daisyui",
                    "use": "Buttons and form controls",
                },
            ],
        },
    },
}


def all_links() -> list[Link]:
    """Every link in this module, for the link checks in the tests."""
    links = [*NAV_LINKS, SIGN_IN, ACCOUNT, DOWNLOAD, HOME_TOOLBOX["cta"]]
    links += [
        DOWNLOAD_PAGE["other_systems"],
        DOWNLOAD_PAGE["choose"],
        DOWNLOAD_PAGE["all_releases"],
        DOWNLOAD_PAGE["unavailable"]["link"],
        DOWNLOAD_PAGE["tips"]["other"]["link"],
        DOWNLOAD_PAGE["agreement"]["back"],
        DOWNLOAD_PAGE["agreement"]["full_text"]["credits"],
        CREDITS_PAGE["sections"]["notice"]["source"],
        *DOWNLOAD_PAGE["from_source"]["links"],
    ]
    links += [TOOLBOX_PAGE["primary"], TOOLBOX_PAGE["secondary"], TOOLBOX_PAGE["run"]["readme"]]
    for block in (HOME_HERO, HOME_FINAL):
        links += [block["primary"], block["secondary"]]
    for column in FOOTER_COLUMNS:
        links.extend(column.links)
    return links
