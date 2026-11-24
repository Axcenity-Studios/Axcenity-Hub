"""The docs' table of contents, read from the snapshot's `SUMMARY.md` (GitBook's format).

`SUMMARY.md` is a `# Table of contents` heading, then entries (`* [Title](path.md)`),
grouped under `## Section` headings and nested by indents. The entries before the
first section have no section title (the docs' README). Reading order is the file's
order, depth first; previous and next follow it.

The parser is forgiving about shape: a section with no entries is kept (empty), and
an indented entry with nothing above it to nest under becomes a top-level entry of
its section. Neither case breaks the reading order.
"""

import re
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field

_ENTRY = re.compile(r"^(?P<indent>[ \t]*)[*+-][ \t]+\[(?P<title>.+?)\]\((?P<path>[^)\s]+)\)\s*$")
_SECTION = re.compile(r"^##[ \t]+(?P<title>.+?)\s*#*\s*$")


@dataclass(frozen=True)
class Entry:
    """One page in the table of contents, with the pages nested under it."""

    title: str
    path: str
    children: tuple["Entry", ...] = ()

    def walk(self) -> Iterator["Entry"]:
        """This entry, then every entry under it, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class Section:
    """A `## Section` and its entries ("" for the entries before the first section)."""

    title: str
    entries: tuple[Entry, ...]

    def walk(self) -> Iterator[Entry]:
        for entry in self.entries:
            yield from entry.walk()


@dataclass(frozen=True)
class Navigation:
    """The parsed table of contents: its sections, and lookups by snapshot path."""

    sections: tuple[Section, ...]

    def walk(self) -> Iterator[tuple[Section, Entry]]:
        """Every entry with its section, in reading order."""
        for section in self.sections:
            for entry in section.walk():
                yield section, entry

    @property
    def order(self) -> tuple[str, ...]:
        """Every listed path, in reading order."""
        return tuple(entry.path for _, entry in self.walk())

    def _neighbour(self, path: str, step: int) -> Entry | None:
        entries = [entry for _, entry in self.walk()]
        for index, entry in enumerate(entries):
            if entry.path == path:
                other = index + step
                return entries[other] if 0 <= other < len(entries) else None
        return None

    def previous(self, path: str) -> Entry | None:
        """The entry read before `path`, or None at the start or for an unlisted page."""
        return self._neighbour(path, -1)

    def next(self, path: str) -> Entry | None:
        """The entry read after `path`, or None at the end or for an unlisted page."""
        return self._neighbour(path, 1)

    def trail(self, path: str) -> tuple[Section, tuple[Entry, ...]] | None:
        """Where `path` sits: its section and the entries from the top down to it (itself
        last), or None if it isn't listed."""

        def search(entries: tuple[Entry, ...], above: tuple[Entry, ...]):
            for entry in entries:
                here = (*above, entry)
                if entry.path == path:
                    return here
                found = search(entry.children, here)
                if found:
                    return found
            return None

        for section in self.sections:
            found = search(section.entries, ())
            if found:
                return section, found
        return None

    def orphans(self, pages: Collection[str]) -> list[str]:
        """The pages in `pages` that the table of contents doesn't list, sorted."""
        listed = set(self.order)
        return sorted(page for page in pages if page not in listed)


@dataclass
class _Building:
    title: str
    path: str
    indent: int
    children: list["_Building"] = field(default_factory=list)

    def freeze(self) -> Entry:
        return Entry(self.title, self.path, tuple(child.freeze() for child in self.children))


def parse_summary(text: str) -> Navigation:
    """Read a `SUMMARY.md` into its sections and nested entries.

    Lines that are neither a `## Section` nor an entry (the `#` title, blank lines,
    prose) are skipped. An entry nests under the nearest entry above it with a smaller
    indent (a tab counts as four spaces); with none, it's top level in its section.
    """
    sections: list[tuple[str, list[_Building]]] = [("", [])]
    stack: list[_Building] = []
    for line in text.splitlines():
        if heading := _SECTION.match(line):
            sections.append((heading.group("title"), []))
            stack = []
            continue
        if not (match := _ENTRY.match(line)):
            continue
        indent = len(match.group("indent").replace("\t", "    "))
        entry = _Building(match.group("title").strip(), match.group("path"), indent)
        while stack and stack[-1].indent >= indent:
            stack.pop()
        (stack[-1].children if stack else sections[-1][1]).append(entry)
        stack.append(entry)

    # The untitled lead section exists only if something comes before the first heading.
    if not sections[0][1]:
        sections.pop(0)
    return Navigation(
        tuple(Section(title, tuple(e.freeze() for e in entries)) for title, entries in sections)
    )
