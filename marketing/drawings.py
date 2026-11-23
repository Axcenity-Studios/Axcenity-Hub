"""Drawn media for the marketing pages: geometry and code tokens, computed in Python.

The drawings are illustrative stand-ins (see the media manifest in content.py);
the templates in templates/marketing/media/ turn this data into SVG and HTML,
coloured only by the axcenity tokens.
"""

import math
import re
from dataclasses import dataclass
from functools import cache


@dataclass(frozen=True)
class Stroke:
    """One SVG path and how strongly to draw it (0–1)."""

    d: str
    opacity: float


@dataclass(frozen=True)
class TerrainDrawing:
    view_box: str
    grid: tuple[Stroke, ...]
    trees: tuple[Stroke, ...]


def _height(x: float, z: float) -> float:
    """Rolling hills: the same periodic field the prototype's reel used."""
    return 1.6 * (math.sin(x * 0.55 + z * 0.35) * 1.1 + math.cos(z * 0.45 - x * 0.25) * 0.8 + 1)


@cache
def terrain_wireframe(
    width: int = 800, height: int = 500, columns: int = 30, rows: int = 22
) -> TerrainDrawing:
    """A perspective wireframe of hills with trees scattered over them.

    Deterministic, so the same drawing is served every time. Points are
    projected from a camera 5.5 units up, looking down the +z axis; rows
    fade with distance.
    """
    camera_height, focal = 5.5, min(width, height * 1.6) * 0.55
    x0, x1, z0, z1 = -7.0, 7.0, 2.0, 15.0

    def project(x: float, z: float) -> tuple[float, float]:
        y = _height(x, z)
        return width / 2 + x / z * focal, height * 0.18 + (camera_height - y) / z * focal * 0.55

    def path(points: list[tuple[float, float]]) -> str:
        return "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in points)

    xs = [x0 + (x1 - x0) * i / columns for i in range(columns + 1)]
    zs = [z0 + (z1 - z0) * j / rows for j in range(rows + 1)]
    grid = [
        Stroke(path([project(x, z) for x in xs]), round(0.9 - j / rows * 0.7, 2))
        for j, z in enumerate(zs)
    ]
    grid += [Stroke(path([project(x, z) for z in zs]), 0.45) for x in xs]

    trees = []
    for i in range(46):
        x = ((i * 7919) % 1000) / 1000 * 10 - 5
        z = 3 + ((i * 4241) % 1000) / 1000 * 10
        sx, sy = project(x, z)
        r = 44 / z
        trees.append(
            Stroke(
                f"M{sx:.1f} {sy - r * 2.2:.1f} L{sx - r * 0.7:.1f} {sy:.1f} "
                f"L{sx + r * 0.7:.1f} {sy:.1f} Z",
                round(0.95 - z / 20, 2),
            )
        )
    # Far trees first, so near ones draw over them.
    trees.sort(key=lambda stroke: stroke.opacity)
    return TerrainDrawing(f"0 0 {width} {height}", tuple(grid), tuple(trees))


LUAU_KEYWORDS = frozenset(
    "and break do else elseif end false for function if in local nil not or repeat return "
    "then true until while continue".split()
)
_TOKEN = re.compile(r'(?P<c>--.*$)|(?P<s>"[^"]*")|(?P<w>[A-Za-z_]\w*)|(?P<o>.)', re.M)


def luau_lines(source: str) -> list[list[tuple[str, str]]]:
    """Split Luau source into lines of (kind, text) tokens for monochrome highlighting.

    Kinds: "k" keyword, "c" comment, "s" string, "t" anything else. Neighbouring
    plain tokens are merged, so the joined text of every line is exactly the
    source line.
    """
    lines = []
    for line in source.split("\n"):
        tokens: list[tuple[str, str]] = []
        for match in _TOKEN.finditer(line):
            kind, text = match.lastgroup, match.group()
            if kind == "w":
                kind = "k" if text in LUAU_KEYWORDS else "t"
            elif kind == "o":
                kind = "t"
            if tokens and kind == "t" and tokens[-1][0] == "t":
                tokens[-1] = ("t", tokens[-1][1] + text)
            else:
                tokens.append((kind, text))
        lines.append(tokens)
    return lines
