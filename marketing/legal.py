"""Plain-text legal files (the engine's LICENSE and NOTICE) as blocks to set as prose.

The files are hard-wrapped at about 75 columns with space indentation, which wraps badly
in a narrow pane. `reflow` joins each paragraph's lines so the browser can wrap them,
and keeps what the layout means: headings, numbered section titles, indented sub-items,
short centred lines and the dividers between entries. It never drops or reorders a word
(tested).
"""

import re
from dataclasses import dataclass

# A paragraph whose every line is at most this long keeps its line breaks (a title block,
# an address); anything longer was wrapped to fit 80 columns and is joined.
SHORT_LINE = 50
# A first line indented at least this far, in a paragraph that keeps its breaks, was centred.
CENTRED = 20
# "2. Grant of Copyright License." at the start of a paragraph: the section's title.
SECTION_LEAD = re.compile(r"(\d+\. [A-Z][^.]{0,60}\.)(?: |$)")
NUMBERED_HEADING = re.compile(r"\d+\. [A-Z][\w ]*\.")
UNDERLINE = re.compile(r"[-=]{3,}")
# A line of only dashes, equals signs, asterisks or underscores: a heading's underline when
# it sits right under a paragraph's one line, otherwise a divider between entries ("---").
RULE = re.compile(r"[-=*_]{3,}")


@dataclass(frozen=True)
class Block:
    """One block of a legal text.

    `kind` is "heading", "lines" (line breaks kept), "paragraph" or "rule" (a divider,
    with no text). `lead` is a numbered
    section's title, set in bold before `text`. `level` is 1 for an indented sub-item or
    definition, else 0; `centred` marks a centred title block.
    """

    kind: str
    text: str = ""
    lines: tuple[str, ...] = ()
    lead: str = ""
    level: int = 0
    centred: bool = False


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_heading(lines: list[str]) -> bool:
    text = lines[0].strip()
    if len(lines) != 1:
        return False
    letters = [c for c in text if c.isalpha()]
    return bool(
        (letters and all(c.isupper() for c in letters))
        or NUMBERED_HEADING.fullmatch(text)
        or text.startswith("APPENDIX:")
    )


def _split(lines: list[str]) -> list[list[str]]:
    """A paragraph's lines cut at its dividers (each an empty list) and after an underlined
    heading that runs straight into its first paragraph. A rule line right under a
    paragraph's single line underlines it; anywhere else it divides two entries."""
    parts: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not RULE.fullmatch(line.strip()):
            if len(current) == 2 and UNDERLINE.fullmatch(current[1].strip()):
                parts.append(current)
                current = []
            current.append(line)
        elif len(current) == 1 and UNDERLINE.fullmatch(line.strip()):
            current.append(line)
        else:
            if current:
                parts.append(current)
            parts.append([])
            current = []
    if current:
        parts.append(current)
    return parts


def reflow(text: str) -> list[Block]:
    """Split a plain-text legal file into blocks whose lines the browser may rewrap.

    Paragraphs are separated by blank lines; a line of only dashes (or =, *, _) that
    doesn't underline a heading is a divider. A paragraph underlined with dashes, or a
    single all-capitals, numbered ("1. Definitions.") or APPENDIX line, is a heading. A
    paragraph of short lines keeps its breaks (centred when indented far). Any other is
    joined into one line, its numbered section title split off as `lead`, and indented a
    level when its first line is indented more than the file's shallowest paragraph.
    """
    chunks = [
        [line for line in chunk.split("\n") if line.strip()]
        for chunk in re.split(r"\n[ \t]*\n", text.replace("\r\n", "\n"))
    ]
    paragraphs = [part for lines in chunks for part in _split(lines)]
    base = min((_indent(lines[0]) for lines in paragraphs if lines), default=0)
    blocks = []
    for lines in paragraphs:
        if not lines:
            blocks.append(Block("rule"))
            continue
        indent = _indent(lines[0])
        if len(lines) == 2 and UNDERLINE.fullmatch(lines[1].strip()):
            blocks.append(Block("heading", text=lines[0].strip()))
        elif _is_heading(lines):
            blocks.append(Block("heading", text=lines[0].strip()))
        elif len(lines) > 1 and max(len(line.strip()) for line in lines) <= SHORT_LINE:
            blocks.append(
                Block(
                    "lines",
                    lines=tuple(line.strip() for line in lines),
                    centred=indent - base >= CENTRED,
                )
            )
        else:
            # One space between words, as the browser shows it.
            joined = " ".join(" ".join(lines).split())
            match = SECTION_LEAD.match(joined)
            lead = match.group(1) if match else ""
            blocks.append(
                Block(
                    "paragraph",
                    text=joined[len(lead) :].strip(),
                    lead=lead,
                    level=1 if indent - base >= 3 else 0,
                )
            )
    return blocks
