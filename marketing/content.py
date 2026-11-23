"""The marketing pages' copy and links, kept as data.

Templates loop over these values; tests check that every internal link
reverses and every external one is well-formed. A link to a page that
doesn't exist yet is marked `soon`: it renders as a "Soon" label, never as
a dead link. Phase 2 grows this module into the full Home content and its
media manifest.
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


@dataclass(frozen=True)
class Link:
    """One navigation link: internal (a URL name), external (an https URL) or coming soon."""

    label: str
    url_name: str = ""
    external: str = ""
    soon: bool = False

    def __post_init__(self) -> None:
        targets = bool(self.url_name) + bool(self.external)
        if self.soon and targets:
            raise ValueError(f"{self.label}: a coming-soon link has no target")
        if not self.soon and targets != 1:
            raise ValueError(f"{self.label}: give exactly one of url_name or external")

    @property
    def href(self) -> str:
        """The URL to link to, or "" for a coming-soon item."""
        if self.url_name:
            return reverse(self.url_name)
        return self.external

    @property
    def is_external(self) -> bool:
        return bool(self.external)


@dataclass(frozen=True)
class FooterColumn:
    heading: str
    links: list[Link] = field(default_factory=list)


# The main nav, left to right. "Features" joins in Phase 2 once Home has that section.
NAV_LINKS = [
    Link("Engine", url_name="marketing:home"),
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

# The bare Home (Phase 1). Phase 2 replaces it with the full Cinematic sections.
HOME_HERO = {
    "badge": "Alpha · Free and open source",
    "headline": "Axcenity Engine.",
    "pitch": (
        "A 3D game engine and editor written in Rust. Build worlds, script in Luau, "
        "test with F5 and export for Windows, macOS and Linux."
    ),
    "primary": Link("Download alpha", external=RELEASES_URL),
    "secondary": Link("Read the docs", external=DOCS_URL),
}


def all_links() -> list[Link]:
    """Every link in this module, for the link checks in the tests."""
    links = [*NAV_LINKS, SIGN_IN, DOWNLOAD, HOME_HERO["primary"], HOME_HERO["secondary"]]
    for column in FOOTER_COLUMNS:
        links.extend(column.links)
    return links
