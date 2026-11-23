"""The marketing pages' copy, links and media, kept as data.

Templates loop over these values; the tests check that every internal link
reverses, every external one is well-formed, every media file exists, and
that the Home's visible prose comes from here. A link to a page that
doesn't exist yet is marked `soon`: it renders as a "Soon" label, never as
a dead link.
"""

from dataclasses import dataclass, field

from django.urls import reverse

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
# recreated, and its caption says so. Phase 5 replaces the drawn stand-ins with
# final animated recreations and adds responsive derivatives.

MEDIA_KINDS = {"capture": "Engine capture", "illustrative": "Illustrative"}


@dataclass(frozen=True)
class Media:
    """One media item: a static file (`src`) or a drawing rendered by a template (`drawn`)."""

    key: str
    kind: str
    caption: str
    alt: str
    provenance: str
    src: str = ""
    drawn: str = ""
    # Pixel size of the source file (files only), and the largest CSS size it's shown at.
    source_size: tuple[int, int] | None = None
    display_size: dict[str, tuple[int, int]] = field(default_factory=dict)
    # Words drawn inside a recreation (panel names and the like), or its code.
    labels: dict = field(default_factory=dict)
    code: str = ""

    def __post_init__(self) -> None:
        if self.kind not in MEDIA_KINDS:
            raise ValueError(f"{self.key}: kind must be one of {sorted(MEDIA_KINDS)}")
        if not self.caption.startswith(MEDIA_KINDS[self.kind]):
            raise ValueError(f"{self.key}: a {self.kind} caption starts {MEDIA_KINDS[self.kind]!r}")
        if bool(self.src) == bool(self.drawn):
            raise ValueError(f"{self.key}: give exactly one of src or drawn")
        if self.kind == "capture" and not self.src:
            raise ValueError(f"{self.key}: a capture is a file, never a drawing")
        if self.src and not self.source_size:
            raise ValueError(f"{self.key}: a file records its source pixel size")


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
            "Showcase-Renderer project, axcenity-player v0.3.0-alpha.1 at 2560×1440, "
            "--graphics settings/rt-ultra.json, window capture with no retouching "
            "(Showcase/README.md)."
        ),
        src="marketing/media/renderer-2560x1440.png",
        source_size=(2560, 1440),
        display_size={"hero": (1440, 900), "stage": (680, 425), "inline": (720, 450)},
    ),
    "terrain": Media(
        key="terrain",
        kind="illustrative",
        caption="Illustrative · drawn",
        alt="A drawing of a wireframe terrain rising into hills, with trees scattered across it.",
        provenance=(
            "Drawn stand-in (marketing/drawings.py terrain_wireframe), after the Terrain Studio "
            "and Scatter pane. Replaced in Phase 5."
        ),
        drawn="marketing/media/terrain.html",
    ),
    "logic": Media(
        key="logic",
        kind="illustrative",
        caption="Illustrative · blocks as Luau",
        alt="Luau code: when the part is touched, spawn a scorch decal where it was hit.",
        provenance=(
            "Written after crates/blocks-runtime/src/translate.rs (WhenTouched, SpawnDecal) and "
            "documentation/api/classes/Workspace.md. Replaced in Phase 5."
        ),
        drawn="marketing/media/luau.html",
        code=LUAU_SAMPLE,
    ),
    "editor": Media(
        key="editor",
        kind="illustrative",
        caption="Illustrative · editor layout",
        alt=(
            "A drawing of the Axcenity editor: the Scene, Explorer and Console docked in one "
            "window, with Properties floated out onto a second monitor."
        ),
        provenance=(
            "Drawn after documentation/learn/editor-interface.md and the editor's panel names "
            "(crates/editor). Replaced in Phase 5."
        ),
        drawn="marketing/media/editor.html",
        labels={
            "window": "Axcenity Editor",
            "scene": "Scene",
            "explorer": "Explorer",
            "console": "Console",
            "assets": "Assets",
            "properties": "Properties",
            "floating": "Floating · Monitor 2",
            "tree": [
                ("Workspace", 0),
                ("Arena", 1),
                ("Pad", 2),
                ("Terrain", 1),
                ("Lighting", 0),
                ("ServerScriptService", 0),
            ],
            "selected": "Pad",
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
            "of three panels that spring together inside one editor window: the 3D Scene View on "
            "the left, the Explorer's tree of Workspace, Arena and Pad beside it, and Properties "
            "for the selected Pad docked below the Explorer. Properties then undocks: it lifts out "
            "of the window and floats onto a second monitor as its own window, and the Explorer "
            "grows to fill the space it left. The workspace holds in that layout, then gives way "
            "to the Axcenity logo before the film starts again. On narrow screens it shows only "
            "the Scene View and the Explorer, docked side by side."
        ),
        provenance=(
            "Drawn live on a canvas by static/reel/ in the site's colour tokens, whose dark values "
            "are the editor's Dark theme (crates/editor-kit/src/theme.rs ThemeTokens), with the "
            "editor's pane labels (crates/editor/src/layout.rs Pane::label)."
        ),
        drawn="marketing/media/reel.html",
        labels={
            "panels": {"scene": "Scene View", "explorer": "Explorer", "properties": "Properties"},
            "window": "Axcenity Editor",
            "floating": "Floating · Monitor 2",
            "tree": [
                ("Workspace", 0),
                ("Arena", 1),
                ("Pad", 2),
                ("Terrain", 1),
                ("Lighting", 0),
                ("ServerScriptService", 0),
            ],
            "selected": "Pad",
            "rows": [("Name", "Pad"), ("Anchored", "true"), ("Size", "8, 1, 8")],
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
