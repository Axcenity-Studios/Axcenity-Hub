"""The engine docs' diagrams: their entries in the site's media manifest.

Each is a PNG drawn for the engine's documentation (`documentation/images/` in the
engine repository), copied into the snapshot by `sync_engine_docs` and served as
it is from `/static/docs/images/`: they're already web-sized, and recompressing
them as JPEG or AVIF would blur their text. Like every item in the manifest
(marketing/content.py) each records its kind, provenance, source pixel size and
display sizes, and the tests hold it to the same rules: the file's real size
matches, and it's never drawn wider than half its pixel width, so 2× screens
never upscale it.

On a page, a diagram is captioned "Diagram" plus the alt text the page gives it
(two pages show the same diagram with different words).
"""

from dataclasses import dataclass

from marketing.content import Display

KIND = "illustrative"
LABEL = "Diagram"
# The article's widest drawing: 600 CSS px, half the diagrams' 1200 px.
MAX_DISPLAY_WIDTH = 600
_GUTTERS = 32  # the page's 16 px gutters below 640 px


@dataclass(frozen=True)
class Diagram:
    """One diagram: its snapshot path and recorded pixel size."""

    path: str
    source_size: tuple[int, int]
    kind: str = KIND
    label: str = LABEL

    @property
    def key(self) -> str:
        return self.path.rsplit("/", 1)[-1].removesuffix(".png")

    @property
    def provenance(self) -> str:
        return (
            f"Axcenity-Engine documentation/{self.path}: drawn for the engine's documentation, "
            "copied unchanged by sync_engine_docs at the commit in documentation/content/"
            "SOURCE.json"
        )

    @property
    def display(self) -> dict[str, Display]:
        """Its drawn size: the article's width below 632 px, then at most 600 px."""
        width, height = self.source_size
        narrowest = MAX_DISPLAY_WIDTH + _GUTTERS - 1

        def scaled(w: int) -> tuple[int, int]:
            return (w, round(w * height / width))

        return {
            "article": Display(
                f"(min-width: {narrowest + 1}px) {MAX_DISPLAY_WIDTH}px, calc(100vw - {_GUTTERS}px)",
                {
                    f"360–{narrowest} px": scaled(narrowest - _GUTTERS),
                    f"{narrowest + 1} px and up": scaled(MAX_DISPLAY_WIDTH),
                },
            )
        }


DIAGRAMS = {
    item.path: item
    for item in (
        Diagram("images/building-transforms.png", (1200, 620)),
        Diagram("images/editor-layout.png", (1200, 680)),
        Diagram("images/engine-architecture.png", (1200, 640)),
        Diagram("images/home-overview.png", (1200, 640)),
        Diagram("images/instance-hierarchy.png", (1200, 640)),
        Diagram("images/scripting-client-server.png", (1200, 620)),
        Diagram("images/ui-layout-udim2.png", (1200, 620)),
    )
}
