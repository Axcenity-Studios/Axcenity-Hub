"""Searching the docs: an in-memory index of the snapshot, and ranked matching.

`build_index(library)` makes one `Entry` per page, per heading of a guide page and
per API member (properties, events, functions, enums, libraries, globals), in
reading order. It's built from the committed snapshot only, once per process
(`Library.search_index`).

`search(entries, raw)` cleans the query (`clean_query`: whitespace trimmed and
collapsed, at most `MAX_QUERY` characters, nothing to search for when it's empty)
and ranks every entry it matches:

1. an exact name: a page's title or an API member's full or short name (`Part`,
   `task.wait`, `Touched`), ignoring case, with `:` read as `.`; a full name ranks
   before a short one, so `TweenService` finds its page before `DataModel.TweenService`;
2. then every query word in a page's title,
3. in a heading,
4. in a member's name,
5. in a description (a page's, or a member's first sentence).

Within a rank, a field that starts with the query comes first, then reading order:
`Touched` finds Part's before MeshPart's because Part comes first in SUMMARY.md.
Each URL appears once, at its best rank.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import rendering

if TYPE_CHECKING:
    from .library import Library

# The longest query searched; a longer one gets a message instead.
MAX_QUERY = 100
# Results per page of /docs/search/.
PER_PAGE = 20
# A snippet's length before it's cut with "…".
SNIPPET = 180

EMPTY = "empty"
TOO_LONG = "too_long"


@dataclass(frozen=True)
class Entry:
    """One thing search can find: a page, a heading on a guide page, or an API member.

    `names` are the names it matches exactly; `title`, `heading`, `member` and
    `description` are the fields ranked after that (empty where they don't apply).
    """

    kind: str
    url: str
    page: str
    label: str = ""
    names: tuple[str, ...] = ()
    title: str = ""
    heading: str = ""
    member: str = ""
    description: str = ""
    snippet: str = ""
    order: int = 0


@dataclass(frozen=True)
class Result:
    entry: Entry
    rank: int


@dataclass(frozen=True)
class Outcome:
    """A search's cleaned `query`, its `problem` ("" or EMPTY or TOO_LONG) and results."""

    query: str
    problem: str
    results: tuple[Result, ...]


def clean_query(raw: str) -> tuple[str, str]:
    """The query as searched (trimmed, inner whitespace collapsed) and its problem: EMPTY
    when nothing is left, TOO_LONG when it's over MAX_QUERY characters, else ""."""
    query = " ".join(raw.split())
    if not query:
        return "", EMPTY
    if len(query) > MAX_QUERY:
        return query, TOO_LONG
    return query, ""


def _name(text: str) -> str:
    """A name as compared: lower case, `:` read as `.` (`Part:GetMass` is `part.getmass`)."""
    return text.lower().replace(":", ".")


def _rank(entry: Entry, query: str, words: list[str]) -> tuple[int, int, int] | None:
    """(rank, 0 if the field starts with the query else 1, reading order), or None."""
    name = _name(query)
    names = [_name(n) for n in entry.names]
    if name in names:
        # A full name (a title, `Part.Touched`) before a member's short name (`Touched`).
        return (1, 0 if name == names[0] else 1, entry.order)
    plain, named = (query, words), (name, [_name(word) for word in words])
    fields = (
        (entry.title.lower(), plain),
        (entry.heading.lower(), plain),
        (_name(entry.member), named),
        (entry.description.lower(), plain),
    )
    for rank, (field, (whole, parts)) in enumerate(fields, start=2):
        if field and all(part in field for part in parts):
            return (rank, 0 if field.startswith(whole) else 1, entry.order)
    return None


def search(entries: Sequence[Entry], raw: str) -> Outcome:
    """Every entry `raw` matches, best first (see the module for the ranking)."""
    query, problem = clean_query(raw)
    if problem:
        return Outcome(query, problem, ())
    lowered = query.lower()
    words = lowered.split()
    best: dict[str, tuple[tuple[int, int, int], Entry]] = {}
    for entry in entries:
        key = _rank(entry, lowered, words)
        if key is not None and (entry.url not in best or key < best[entry.url][0]):
            best[entry.url] = (key, entry)
    ordered = sorted(best.values(), key=lambda found: found[0])
    return Outcome(query, "", tuple(Result(entry, key[0]) for key, entry in ordered))


def mark(text: str, query: str) -> list[tuple[str, bool]]:
    """`text` split into (piece, matched) pieces, where matched pieces are the query's
    words (ignoring case), for highlighting a snippet."""
    words = sorted({w for w in query.lower().split() if w}, key=len, reverse=True)
    lower, pieces, at = text.lower(), [], 0
    while words and at < len(text):
        found = min(
            ((lower.find(w, at), w) for w in words if lower.find(w, at) >= 0),
            default=None,
        )
        if found is None:
            break
        start, word = found
        if start > at:
            pieces.append((text[at:start], False))
        pieces.append((text[start : start + len(word)], True))
        at = start + len(word)
    if at < len(text):
        pieces.append((text[at:], False))
    return pieces


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= SNIPPET:
        return text
    return text[:SNIPPET].rsplit(" ", 1)[0] + " …"


def _sections(text: str, headings) -> list[tuple[object, str]]:
    """Each heading of a page (the rendered ones, in order) with its first paragraph."""
    _, body = rendering.split_front_matter(text)
    tokens = rendering.parse_body(body)
    found, waiting, titled = [], None, False
    remaining = iter(headings)
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            if token.tag == "h1" and not titled:
                titled = True
                continue
            heading = next(remaining, None)
            if heading is None:
                break
            waiting = [heading, ""]
            found.append(waiting)
        elif token.type == "inline" and index and tokens[index - 1].type == "paragraph_open":
            if waiting is not None and not waiting[1]:
                waiting[1] = rendering.plain_text(token.children)
    return [(heading, first) for heading, first in found]


def build_index(lib: "Library") -> tuple[Entry, ...]:
    """Every page, guide heading and API member of the snapshot, in reading order."""
    listed = [p for p in lib.navigation.order if p in lib.paths]
    paths = listed + [p for p in lib.paths if p not in listed]
    entries: list[Entry] = []

    def add(**fields) -> None:
        entries.append(Entry(order=len(entries), **fields))

    for path in paths:
        page = lib.page(path)
        add(
            kind="page",
            url=page.url,
            page=page.title,
            names=(page.title,),
            title=page.title,
            description=page.description,
            snippet=_snippet(page.description),
        )
        reference = lib.api_page(path)
        if reference is not None:
            for member in reference.members:
                about = " ".join((member.summary, *member.items))
                add(
                    kind="member",
                    url=f"{page.url}#{member.anchor}",
                    page=page.title,
                    label=member.qualified,
                    names=(member.qualified, member.name),
                    member=member.qualified,
                    description=about,
                    snippet=_snippet(member.summary or member.signature),
                )
            continue
        text = (lib.root / path).read_text("utf-8")
        for heading, first in _sections(text, page.rendered.headings):
            add(
                kind="heading",
                url=f"{page.url}#{heading.id}",
                page=page.title,
                label=heading.text,
                heading=heading.text,
                description=first,
                snippet=_snippet(first or page.description),
            )
    return tuple(entries)
