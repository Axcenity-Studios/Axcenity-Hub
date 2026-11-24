"""The committed snapshot of the engine docs, as the site serves it.

`Library(root)` reads a snapshot folder: `SOURCE.json` (where it came from),
`SUMMARY.md` (the table of contents), every other `.md` file as a page and the
diagrams under `images/`. Pages are rendered on first use and kept. Nothing here
reads the engine repository or the network: the snapshot is the only source.

`check()` is the build check that `sync_engine_docs` runs on a new snapshot before
swapping it in, and the tests run on the committed one: every page renders with
a title and description, every link and image resolves, every `#anchor` names a
heading on its page, SUMMARY.md and the pages agree (no orphans, nothing missing),
no two pages share a URL, every status is known, and every image is a manifest
diagram at its recorded size.
"""

import dataclasses
import functools
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from PIL import Image

from . import links, navigation, rendering
from .diagrams import DIAGRAMS, Diagram
from .sync import SOURCE_FILE

SUMMARY_FILE = "SUMMARY.md"
# Ids the docs pages use around the article (templates/documentation/ and the shells), which a
# heading id must never repeat; the landing page adds one `docs-panel-<n>` per section
# (`Library.reserved_ids`). A test checks this covers every id outside the article.
PAGE_IDS = frozenset(
    {"content", "site-nav", "site-footer", "theme-toggle"}
    | {"docs-nav", "docs-article", "docs-title", "docs-source", "docs-outline"}
    | {"docs-sections", "docs-sections-title"}
)


@dataclass(frozen=True)
class Page:
    """One rendered page and where it sits."""

    path: str
    url: str
    rendered: rendering.Rendered
    source_url: str
    section: str
    trail: tuple[navigation.Entry, ...]
    previous: navigation.Entry | None
    next: navigation.Entry | None

    @property
    def title(self) -> str:
        return self.rendered.title

    @property
    def description(self) -> str:
        return self.rendered.meta.description


class Library:
    """A snapshot folder: its provenance, table of contents, pages and diagrams."""

    def __init__(self, root: Path, diagrams: dict[str, Diagram] | None = None):
        self.root = Path(root)
        self.diagrams = DIAGRAMS if diagrams is None else diagrams
        self.source: dict[str, str] = json.loads((self.root / SOURCE_FILE).read_text("utf-8"))
        self.navigation = navigation.parse_summary((self.root / SUMMARY_FILE).read_text("utf-8"))
        files = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        self.paths = tuple(f for f in files if f.endswith(".md") and f != SUMMARY_FILE)
        self.images = tuple(f for f in files if f.startswith(links.IMAGES_FOLDER))
        self._by_slug = {links.page_slug(path): path for path in self.paths}
        self._pages: dict[str, Page] = {}

    @property
    def reserved_ids(self) -> frozenset[str]:
        """The ids no heading may take: the page's own, and the landing page's panels."""
        panels = range(1, len(self.navigation.sections) + 1)
        return PAGE_IDS | {f"docs-panel-{number}" for number in panels}

    # ---------- Lookups ----------

    def path_for(self, slug: str) -> str | None:
        """The snapshot path served at the URL path `slug` ("" for the docs' README)."""
        return self._by_slug.get(slug)

    def source_url(self, path: str) -> str:
        """The page's file on GitHub, at the snapshot's commit."""
        repository, commit = self.source["repository"], self.source["commit"]
        return f"{repository}/blob/{commit}/{quote(self.source['folder'])}/{quote(path)}"

    def title_of(self, path: str) -> str:
        """The page's title (its h1), or its table-of-contents title if it has none."""
        return self.page(path).title

    def page(self, path: str) -> Page:
        """The rendered page at the snapshot path `path` (KeyError if there's none)."""
        if path not in self._pages:
            if path not in self.paths:
                raise KeyError(path)
            text = (self.root / path).read_text("utf-8")
            rendered = rendering.render(
                text,
                path,
                pages=self.paths,
                diagrams={k: v for k, v in self.diagrams.items() if k in self.images},
                reserved_ids=self.reserved_ids,
            )
            place = self.navigation.trail(path)
            section, trail = (place[0].title, place[1]) if place else ("", ())
            if not rendered.title and trail:
                rendered = dataclasses.replace(rendered, title=trail[-1].title)
            self._pages[path] = Page(
                path=path,
                url=links.page_url(path),
                rendered=rendered,
                source_url=self.source_url(path),
                section=section,
                trail=trail,
                previous=self.navigation.previous(path),
                next=self.navigation.next(path),
            )
        return self._pages[path]

    # ---------- The build check ----------

    def check(self) -> list[str]:
        """Every problem in the snapshot (empty when it's fit to serve); see the module."""
        problems: list[str] = []
        listed = self.navigation.order
        problems += [
            f"{p}: not listed in {SUMMARY_FILE} (an orphan)"
            for p in self.navigation.orphans(self.paths)
        ]
        problems += [
            f"{SUMMARY_FILE}: lists {p}, which isn't in the snapshot"
            for p in listed
            if p not in self.paths
        ]
        problems += [f"{SUMMARY_FILE}: lists {p} twice" for p in set(listed) if listed.count(p) > 1]
        if len(self._by_slug) != len(self.paths):
            problems.append("two pages share a URL (their paths differ only in case)")

        rendered: dict[str, rendering.Rendered] = {}
        for path in self.paths:
            try:
                page = self.page(path)
            except rendering.RenderError as error:
                problems.append(f"{path}: {error}")
                continue
            rendered[path] = page.rendered
            problems += page.rendered.problems
            if not page.title:
                problems.append(f"{path}: no title (no # heading)")
            if not page.description:
                problems.append(f"{path}: no description in its front matter")
            status = page.rendered.meta.status
            if status and status not in rendering.STATUS_LABELS:
                problems.append(f"{path}: unknown status {status!r}")

        for path, page in rendered.items():
            for link in page.links:
                target = rendered.get(link.target)
                if link.fragment and target and link.fragment not in target.ids:
                    problems.append(f"{path}: #{link.fragment} isn't a heading on {link.target}")

        for image in self.images:
            diagram = self.diagrams.get(image)
            if diagram is None:
                problems.append(f"{image}: not in the diagram manifest (documentation/diagrams.py)")
                continue
            with Image.open(self.root / image) as picture:
                if picture.size != diagram.source_size:
                    problems.append(
                        f"{image}: the manifest says {diagram.source_size}, the file is "
                        f"{picture.size}"
                    )
        return problems


def check_snapshot(root: Path) -> list[str]:
    """The build check on the snapshot at `root` (what `sync_engine_docs` runs)."""
    try:
        return Library(root).check()
    except (OSError, ValueError, KeyError) as error:
        return [f"the snapshot can't be read: {error}"]


@functools.cache
def library() -> Library:
    """The committed snapshot (settings.DOCS_SNAPSHOT_DIR), loaded once per process."""
    return Library(settings.DOCS_SNAPSHOT_DIR)
