"""Rendering one snapshot page: front matter, Markdown, headings, links, code and figures.

This is a security boundary: the engine's Markdown becomes part of the Hub's pages.

- markdown-it-py runs CommonMark plus tables and strikethrough with **raw HTML
  off**, so any `<tag>` in a page is shown as text. (Should a raw-HTML token ever
  appear, it's escaped too.)
- markdown-it's own link check is switched off so that *every* link and image
  reaches `links.resolve`, the one gate: a refused link renders as its plain text,
  a refused image as its alt text, and both are reported in `problems`.
- External links get `rel="noopener"`; images must be diagrams in the manifest
  (documentation/diagrams.py), drawn at their recorded size.

On API pages (`type_links` given), a `luau` block straight under a heading is a
signature: the type names in it link to their pages (`highlight.type_names`), and
each link is an internal link the build check follows.

Heading ids are GitHub-style slugs (what the docs' own `#anchor` links use),
made unique per page: a repeat gets `-1`, `-2`… skipping any id already taken,
including the ids the page around the article uses.
"""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass

import yaml
from django.utils.html import escape
from markdown_it import MarkdownIt
from markdown_it.token import Token

from . import highlight, links
from .diagrams import Diagram

# The front matter's `status`, and the badge each shows.
STATUS_LABELS = {"partial": "Partly built", "experimental": "Experimental"}
# The headings the "On this page" rail lists.
OUTLINE_LEVELS = (2, 3)

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)


class RenderError(ValueError):
    """A page's front matter can't be read."""


@dataclass(frozen=True)
class FrontMatter:
    description: str = ""
    icon: str = ""
    status: str = ""
    samples: tuple[str, ...] = ()

    @property
    def status_label(self) -> str:
        """The badge for `status` ("" for a stable page or an unknown status)."""
        return STATUS_LABELS.get(self.status, "")


_FRONT_MATTER_LINE = re.compile(r"^(?P<key>[A-Za-z_][\w-]*):(?:[ \t]+(?P<value>.*?))?[ \t]*$")


def _front_matter_value(key: str, raw: str):
    """One value: quoted strings and [lists] are read as YAML; anything else is the text as
    written (GitBook accepts an unquoted description containing ": ", strict YAML doesn't)."""
    if raw[:1] in ("'", '"', "["):
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError as error:
            raise RenderError(f"{key}: {error}") from error
    return raw


def split_front_matter(text: str) -> tuple[FrontMatter, str]:
    """The page's front matter (description, icon, status, samples) and its body.

    One `key: value` per line, as the engine's pages write it; any other line is an error.
    """
    match = _FRONT_MATTER.match(text)
    if not match:
        return FrontMatter(), text
    data = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        entry = _FRONT_MATTER_LINE.match(line)
        if not entry:
            raise RenderError(f"front matter line isn't `key: value`: {line!r}")
        data[entry["key"]] = _front_matter_value(entry["key"], entry["value"] or "")
    samples = data.get("samples") or []
    if not isinstance(samples, list) or not all(isinstance(s, str) for s in samples):
        raise RenderError("samples must be a list of names")
    for key in ("description", "icon", "status"):
        if not isinstance(data.get(key, ""), str):
            raise RenderError(f"{key} must be text")
    meta = FrontMatter(
        description=data.get("description", "").strip(),
        icon=data.get("icon", "").strip(),
        status=data.get("status", "").strip(),
        samples=tuple(samples),
    )
    return meta, text[match.end() :]


# ---------- Heading ids ----------


def slugify(text: str) -> str:
    """A heading's GitHub-style id: lower case, punctuation dropped, spaces as hyphens
    ("The environment track: in one key" → "the-environment-track-in-one-key").
    A heading with nothing left is "section"."""
    slug = re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")
    return slug or "section"


class HeadingIds:
    """Hands out unique heading ids for one page, in the order its headings appear."""

    def __init__(self, reserved: Collection[str] = ()):
        self.taken = set(reserved)

    def add(self, text: str) -> str:
        """The id for a heading reading `text`: its slug, or the slug with the first free
        `-1`, `-2`… suffix."""
        base = candidate = slugify(text)
        number = 0
        while candidate in self.taken:
            number += 1
            candidate = f"{base}-{number}"
        self.taken.add(candidate)
        return candidate


# ---------- The rendered page ----------


@dataclass(frozen=True)
class Heading:
    level: int
    id: str
    text: str


@dataclass(frozen=True)
class InternalLink:
    """A link into the snapshot: the target page (or image) and the anchor it asks for."""

    target: str
    fragment: str


@dataclass(frozen=True)
class Rendered:
    title: str
    html: str
    # The start of `html`, before the first heading (an API page's constructor and intro).
    lead: str
    meta: FrontMatter
    headings: tuple[Heading, ...]
    links: tuple[InternalLink, ...]
    images: tuple[str, ...]
    problems: tuple[str, ...]

    @property
    def body(self) -> str:
        """`html` from the first heading on."""
        return self.html[len(self.lead) :]

    @property
    def outline(self) -> tuple[Heading, ...]:
        """The h2 and h3 headings, for "On this page"."""
        return tuple(h for h in self.headings if h.level in OUTLINE_LEVELS)

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(h.id for h in self.headings)


def plain_text(children: list[Token] | None) -> str:
    """An inline token's words: its text and code spans, without markup."""
    return "".join(
        child.content for child in children or () if child.type in ("text", "code_inline")
    ).strip()


def _markdown() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    # Every link reaches links.resolve, which is stricter; nothing is dropped unreported.
    md.validateLink = lambda url: True
    rules = md.add_render_rule
    rules("heading_close", _render_heading_close)
    rules("link_open", _render_link_open)
    rules("link_close", _render_link_close)
    rules("image", _render_image)
    rules("paragraph_open", _render_paragraph_open)
    rules("paragraph_close", _render_paragraph_close)
    rules("fence", _render_fence)
    rules("code_block", _render_fence)
    rules("table_open", _render_table_open)
    rules("table_close", lambda self, tokens, idx, options, env: "</table></div>\n")
    rules("html_block", lambda self, tokens, idx, options, env: escape(tokens[idx].content))
    rules("html_inline", lambda self, tokens, idx, options, env: escape(tokens[idx].content))
    return md


def _render_heading_close(self, tokens, idx, options, env):
    anchor = tokens[idx].meta.get("anchor")
    if not anchor:
        return self.renderToken(tokens, idx, options, env)
    ident, text = anchor
    return (
        f'<a class="doc-anchor" href="#{escape(ident)}" aria-label="Link to {escape(text)}">'
        f'<span aria-hidden="true">#</span></a></{tokens[idx].tag}>\n'
    )


def _render_link_open(self, tokens, idx, options, env):
    if tokens[idx].meta.get("refused"):
        return ""
    return self.renderToken(tokens, idx, options, env)


def _render_link_close(self, tokens, idx, options, env):
    if tokens[idx].meta.get("refused"):
        return ""
    return self.renderToken(tokens, idx, options, env)


def _render_image(self, tokens, idx, options, env):
    token = tokens[idx]
    alt = escape(token.meta.get("alt", ""))
    diagram: Diagram | None = token.meta.get("diagram")
    if diagram is None:
        return alt  # refused: its words stay, the picture doesn't
    width, height = diagram.source_size
    img = (
        f'<img src="{escape(token.attrGet("src"))}" alt="{alt}" width="{width}" '
        f'height="{height}" loading="lazy" decoding="async">'
    )
    if not token.meta.get("figure"):
        return img
    return (
        f'{img}<figcaption class="doc-caption"><span class="doc-caption-label micro">'
        f"{escape(diagram.label)}</span> "
        f'<span aria-hidden="true">{alt}</span></figcaption>'
    )


def _render_paragraph_open(self, tokens, idx, options, env):
    if tokens[idx].meta.get("figure"):
        return '<figure class="doc-figure">'
    return self.renderToken(tokens, idx, options, env)


def _render_paragraph_close(self, tokens, idx, options, env):
    if tokens[idx].meta.get("figure"):
        return "</figure>\n"
    return self.renderToken(tokens, idx, options, env)


def _render_fence(self, tokens, idx, options, env):
    token = tokens[idx]
    language = (token.info or "").strip().split(" ")[0].lower()
    label = "Luau code" if language in highlight.LUAU_LANGUAGES else "Code"
    data = f' data-language="{escape(language)}"' if language else ""
    return (
        f'<div class="doc-code"{data}><pre tabindex="0" aria-label="{label}"><code>'
        f"{highlight.highlight(token.content, language, token.meta.get('type_links'))}"
        "</code></pre></div>\n"
    )


def _render_table_open(self, tokens, idx, options, env):
    return '<div class="doc-table" role="region" tabindex="0" aria-label="Table"><table>\n'


_MD = _markdown()


def parse_body(body: str) -> list[Token]:
    """The Markdown `body` (front matter already split off) as markdown-it block tokens,
    parsed exactly as `render` parses it."""
    return _MD.parse(body)


def render(
    text: str,
    path: str,
    *,
    pages: Collection[str],
    diagrams: Mapping[str, Diagram],
    reserved_ids: Collection[str] = (),
    type_links: Mapping[str, tuple[str, str]] | None = None,
) -> Rendered:
    """Render the snapshot page at `path` (its full text, front matter included).

    `pages` are the snapshot's page paths, for link checks; `diagrams` the images a page
    may show; `reserved_ids` the ids the page around the article already uses. The first
    h1 becomes the title (taken out of the body: the page header shows it).
    `type_links` (type name → its page's snapshot path and anchor) links the type names
    in an API page's signatures.
    """
    meta, body = split_front_matter(text)
    tokens = _MD.parse(body)
    ids = HeadingIds(reserved_ids)
    title, headings, internal, images, problems = "", [], [], [], []
    drop: set[int] = set()

    def report(problem: str) -> None:
        problems.append(f"{path}: {problem}")

    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            level, text_ = int(token.tag[1]), plain_text(tokens[index + 1].children)
            if level == 1 and not title:
                title = text_
                drop.update({index, index + 1, index + 2})
                continue
            ident = ids.add(text_)
            token.attrSet("id", ident)
            tokens[index + 2].meta["anchor"] = (ident, text_)
            headings.append(Heading(level, ident, text_))
        elif (
            token.type == "fence"
            and type_links
            and index
            and tokens[index - 1].type == "heading_close"
        ):
            if token.info.strip().lower() != "luau":
                continue
            urls = {}
            for name in highlight.type_names(token.content, type_links):
                target, fragment = type_links[name]
                urls[name] = links.page_url(target) + (f"#{fragment}" if fragment else "")
                internal.append(InternalLink(target, fragment))
            token.meta["type_links"] = urls
        elif token.type == "paragraph_open":
            children = tokens[index + 1].children or []
            if len(children) == 1 and children[0].type == "image":
                token.meta["figure"] = tokens[index + 2].meta["figure"] = True
                children[0].meta["figure"] = True
        elif token.type == "inline":
            refusing = False
            for child in token.children or []:
                if child.type == "link_open":
                    resolved = links.resolve(child.attrGet("href") or "", path, pages, diagrams)
                    if resolved.problem:
                        report(resolved.problem)
                        child.meta["refused"] = refusing = True
                        continue
                    child.attrSet("href", resolved.url)
                    if resolved.target:
                        internal.append(InternalLink(resolved.target, resolved.fragment))
                    else:
                        child.attrSet("rel", "noopener")
                elif child.type == "link_close" and refusing:
                    child.meta["refused"], refusing = True, False
                elif child.type == "image":
                    child.meta["alt"] = plain_text(child.children)
                    src = child.attrGet("src") or ""
                    resolved = links.resolve(src, path, (), diagrams)
                    if resolved.problem or resolved.target not in diagrams:
                        report(resolved.problem or f"{src!r}: not a diagram in the manifest")
                        continue
                    child.attrSet("src", resolved.url)
                    child.meta["diagram"] = diagrams[resolved.target]
                    images.append(resolved.target)

    kept = [token for index, token in enumerate(tokens) if index not in drop]
    first_heading = next(
        (at for at, token in enumerate(kept) if token.type == "heading_open"), len(kept)
    )
    lead = _MD.renderer.render(kept[:first_heading], _MD.options, {})
    html = lead + _MD.renderer.render(kept[first_heading:], _MD.options, {})
    return Rendered(
        title=title,
        html=html,
        lead=lead,
        meta=meta,
        headings=tuple(headings),
        links=tuple(internal),
        images=tuple(images),
        problems=tuple(problems),
    )
