"""The generated API reference, read as structure: classes, members, enums, libraries, globals.

The engine generates `documentation/api/` from its own API description, so every page
has the same shape, and `parse` reads it back:

- A class or data type page (`api/classes/Part.md`, `api/types/Vector3.md`): the `#`
  title, an optional `luau` constructor block (`Instance.new("Part")`), the intro (with
  "It also has every member of [Instance](Instance.md)." for an Instance class), then
  `### Properties`, `### Events` and `### Functions`, each a list of `#### Member`
  headings, each followed by its `luau` signature and its description.
- `api/libraries.md`: a `## library` (such as `task`) per library, then the same
  `###` kinds and `####` members.
- `api/globals.md`: a `## name` per global, with its signature and description.
- `api/enums.md`: a `## Enum.Name` per enum, its description and an `Items:` line.

Anchors are never computed here: `parse` takes the rendered page's headings
(`rendering.Rendered.headings`) and pairs them with the Markdown's headings in order,
so a member's anchor is the id its heading really has on the page.
"""

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from django.utils.html import escape
from markdown_it.token import Token

from . import links, rendering
from .rendering import Heading


class ApiError(ValueError):
    """An API page doesn't have the shape the engine generates."""


# The `###` headings of a class, type or library, and the kind of member each lists.
KINDS = {"Properties": "property", "Events": "event", "Functions": "function"}


@dataclass(frozen=True)
class Member:
    """One entry of the reference: a property, event, function, library, global or enum."""

    kind: str
    name: str
    owner: str
    anchor: str
    signature: str = ""
    summary: str = ""
    summary_html: str = ""
    items: tuple[str, ...] = ()

    @property
    def qualified(self) -> str:
        """Its full name: `Part.Touched`, `task.wait`, `Enum.Material`, `game`."""
        return f"{self.owner}.{self.name}" if self.owner else self.name

    @property
    def short_signature(self) -> str:
        """The signature without its name, for a summary table: a property's or event's
        type (`boolean`), a function's parameters and result (`(seconds: number?): number`).
        A signature that doesn't start with the member's name is kept whole."""
        for prefix in (f"{self.owner}.{self.name}", f"{self.owner}:{self.name}", self.name):
            if self.signature.startswith(prefix) and (self.owner or prefix == self.name):
                rest = self.signature[len(prefix) :].strip()
                return rest[1:].strip() if rest.startswith(":") else rest
        return self.signature


@dataclass(frozen=True)
class ApiPage:
    """An API page as structure. `kind` is "class", "type", "libraries", "globals" or
    "enums"; `inherits` is the snapshot path of the page whose members it also has."""

    path: str
    kind: str
    name: str
    constructor: str = ""
    inherits: str = ""
    members: tuple[Member, ...] = ()

    def of_kind(self, kind: str) -> tuple[Member, ...]:
        """Its members of one kind, in page order."""
        return tuple(member for member in self.members if member.kind == kind)


def page_kind(path: str) -> str | None:
    """The kind of API page at the snapshot path `path`, or None for any other page
    (the API's README and its Classes and Data types index tables are plain pages)."""
    folder, _, name = path.rpartition("/")
    if folder in ("api/classes", "api/types") and name.endswith(".md"):
        return "class" if folder == "api/classes" else "type"
    return _SINGLE_PAGES.get(path)


_SINGLE_PAGES = {
    "api/enums.md": "enums",
    "api/libraries.md": "libraries",
    "api/globals.md": "globals",
}
# Where a sentence ends inside a run of text (never inside a code span).
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_INHERITS = "every member of"
_ITEMS = "Items:"


def first_sentence(children: Sequence[Token]) -> tuple[str, str]:
    """A paragraph's first sentence as plain text and as HTML (code spans as `<code>`,
    links as their words). A full stop inside a code span never ends it."""
    plain: list[str] = []
    html: list[str] = []
    for child in children:
        if child.type == "code_inline":
            plain.append(child.content)
            html.append(f"<code>{escape(child.content)}</code>")
        elif child.type in ("text", "softbreak", "hardbreak"):
            text = child.content if child.type == "text" else " "
            end = _SENTENCE_END.search(text)
            if end:
                text = text[: end.end()]
            plain.append(text)
            html.append(str(escape(text)))
            if end:
                break
    return "".join(plain).strip(), "".join(html).strip()


@dataclass
class _Building:
    kind: str
    name: str
    owner: str
    anchor: str
    signature: str = ""
    summary: tuple[str, str] = ("", "")
    items: list[str] = field(default_factory=list)

    def freeze(self) -> Member:
        return Member(
            kind=self.kind,
            name=self.name,
            owner=self.owner,
            anchor=self.anchor,
            signature=self.signature,
            summary=self.summary[0],
            summary_html=self.summary[1],
            items=tuple(self.items),
        )


def parse(text: str, path: str, headings: Sequence[Heading], pages: Collection[str]) -> ApiPage:
    """Read the API page at `path` (its full text) into its structure.

    `headings` are the rendered page's headings (title excluded), in order; `pages` the
    snapshot's page paths, for the inheritance link. Raises ApiError on a shape the
    engine doesn't generate.
    """
    kind = page_kind(path)
    if kind is None:
        raise ApiError(f"{path}: not an API page")
    _, body = rendering.split_front_matter(text)
    tokens = rendering.parse_body(body)
    rendered = iter(headings)
    title, constructor, inherits = "", "", ""
    owner, member_kind = "", ""
    members: list[_Building] = []
    current: _Building | None = None
    intro = True

    def fail(problem: str) -> ApiError:
        return ApiError(f"{path}: {problem}")

    for index, token in enumerate(tokens):
        previous = tokens[index - 1].type if index else ""
        if token.type == "heading_open":
            level, words = int(token.tag[1]), rendering.plain_text(tokens[index + 1].children)
            if level == 1 and not title:
                title = words
                owner = title if kind in ("class", "type") else ""
                continue
            heading = next(rendered, None)
            if heading is None or (heading.level, heading.text) != (level, words):
                raise fail(f"the heading {words!r} doesn't match the rendered page's headings")
            intro, current = False, None
            if level == 2 and kind == "enums":
                if not words.startswith("Enum."):
                    raise fail(f"an enum heading is Enum.Name, not {words!r}")
                current = _Building("enum", words.removeprefix("Enum."), "Enum", heading.id)
            elif level == 2 and kind == "globals":
                current = _Building("global", words, "", heading.id)
            elif level == 2 and kind == "libraries":
                current = _Building("library", words, "", heading.id)
                owner, member_kind = words, ""
            elif level == 3 and kind in ("class", "type", "libraries"):
                if words not in KINDS:
                    raise fail(f"{words!r} isn't Properties, Events or Functions")
                member_kind = KINDS[words]
            elif level == 4 and member_kind:
                current = _Building(member_kind, words, owner, heading.id)
            else:
                raise fail(f"the heading {words!r} (h{level}) isn't where the engine puts one")
            if current is not None:
                members.append(current)
        elif token.type == "fence" and previous == "heading_close":
            if token.info.strip().lower() != "luau":
                continue
            if current is not None and not current.signature:
                current.signature = token.content.strip()
            elif intro and title and not constructor:
                constructor = token.content.strip()
        elif token.type == "inline" and previous == "paragraph_open":
            children = token.children or []
            words = rendering.plain_text(children)
            if current is not None:
                if current.kind == "enum" and words.startswith(_ITEMS):
                    current.items = [c.content for c in children if c.type == "code_inline"]
                elif not current.summary[0]:
                    current.summary = first_sentence(children)
            elif intro and _INHERITS in words:
                href = next((c.attrGet("href") for c in children if c.type == "link_open"), "")
                resolved = links.resolve(href or "", path, pages, ())
                if not resolved.target or resolved.problem:
                    raise fail(f"it inherits from {href!r}, which isn't in the snapshot")
                inherits = resolved.target

    if not title:
        raise fail("no # title")
    if next(rendered, None) is not None:
        raise fail("the rendered page has headings the Markdown doesn't")
    return ApiPage(
        path=path,
        kind=kind,
        name=title,
        constructor=constructor,
        inherits=inherits,
        members=tuple(member.freeze() for member in members),
    )
