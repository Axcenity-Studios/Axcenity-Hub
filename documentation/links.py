"""Rewriting the snapshot's links into Hub URLs.

The engine's pages link to each other with relative Markdown paths
(`../learn/blocks.md#events`) and to their diagrams with relative image paths
(`../images/x.png`). `resolve` turns each into the URL the Hub serves it at, or
reports why it can't: a target that isn't in the snapshot, a path that climbs
out of it, or a scheme that isn't on the allow-list. A reported link is never
emitted as a link.

This is a security boundary: the pages are rendered into the site, so a link
must never smuggle in a script URL or reach a file outside the snapshot. Every
check runs on the link as written *and* on its percent- and entity-decoded
forms, and anything a browser would quietly repair (whitespace, control
characters, backslashes, a scheme without its slashes) is refused outright.
"""

import html
import posixpath
import re
from collections.abc import Collection
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from django.templatetags.static import static
from django.urls import reverse

# Schemes a page may link out to, and how each must be spelled.
WEB_SCHEMES = ("https", "http")
MAIL_SCHEME = "mailto"
# Where the snapshot's images are served from (config/settings.py STATICFILES_DIRS).
IMAGES_FOLDER = "images/"
STATIC_PREFIX = "docs/"

_SCHEME = re.compile(r"^([a-z][a-z0-9+.\-]*):", re.I)
# Anything a browser strips from or chokes on inside a URL, so it could hide a scheme.
_UNSAFE_CHARACTERS = re.compile(r"[\x00-\x20\x7f\\]")


@dataclass(frozen=True)
class Resolved:
    """Where one link goes: its `url`, or the `problem` that stopped it (then `url` is "").

    For a link into the snapshot, `target` is the page or image's snapshot path (the
    current page for a same-page anchor) and `fragment` its anchor, so the anchor can be
    checked against the target's headings.
    """

    url: str
    problem: str = ""
    target: str = ""
    fragment: str = ""


def _refused(problem: str) -> Resolved:
    return Resolved("", problem)


def page_slug(path: str) -> str:
    """The URL path of a snapshot page: lower-cased, without `.md`; a README is its folder.

    `learn/Blocks.md` → `learn/blocks`, `api/README.md` → `api`, `README.md` → "".
    """
    stem = path.removesuffix(".md")
    folder, _, name = stem.rpartition("/")
    if name.lower() == "readme":
        stem = folder
    return stem.lower()


def page_url(path: str) -> str:
    """The Hub URL of a snapshot page (see `page_slug`)."""
    slug = page_slug(path)
    if not slug:
        return reverse("documentation:index")
    return reverse("documentation:page", args=[slug])


def image_url(path: str) -> str:
    """The static URL of a snapshot image (`images/x.png`)."""
    return static(STATIC_PREFIX + path)


def _decodings(href: str) -> list[str]:
    """`href` as written and as a browser might read it: entity- and percent-decoded,
    repeatedly, until nothing changes."""
    forms = [href]
    current = href
    for _ in range(5):
        decoded = unquote(html.unescape(current))
        if decoded == current:
            break
        forms.append(decoded)
        current = decoded
    return forms


def _external(href: str, scheme: str) -> Resolved:
    """An allow-listed external link, kept exactly as written, or refused if malformed."""
    if scheme in WEB_SCHEMES:
        parts = urlsplit(href)
        if not href.lower().startswith(f"{scheme}://") or not parts.hostname:
            return _refused(f"{href!r}: a web link is written scheme://host")
        return Resolved(href)
    if len(href) <= len(MAIL_SCHEME) + 1:
        return _refused(f"{href!r}: a mailto link needs an address")
    return Resolved(href)


def resolve(href: str, page: str, pages: Collection[str], images: Collection[str]) -> Resolved:
    """Resolve `href`, written on the snapshot page `page`, to a Hub URL.

    - A relative page link (`../learn/blocks.md?x=1#events`) becomes the page's Hub URL,
      keeping its query and anchor; a relative image link becomes its static URL.
    - A same-page anchor (`#events`) and an `https`, `http` or `mailto` link are kept as
      written.
    - Anything else is refused with a `problem`: a target that isn't in `pages` or
      `images`, a path that leaves the snapshot, an absolute or protocol-relative path,
      a scheme off the allow-list (however it's encoded), or characters a browser would
      strip or rewrite.
    """
    if not href:
        return _refused("an empty link")
    unsafe = f"{href!r}: whitespace, control characters or backslashes"
    if _UNSAFE_CHARACTERS.search(href):
        return _refused(unsafe)

    written = _SCHEME.match(href)
    if written and written.group(1).lower() in (*WEB_SCHEMES, MAIL_SCHEME):
        # Kept byte for byte: its encoded query (`%20`) is the link's own business.
        return _external(href, written.group(1).lower())

    # Everything else is read the way a browser might decode it before deciding.
    forms = _decodings(href)
    if any(_UNSAFE_CHARACTERS.search(form) for form in forms):
        return _refused(unsafe)
    for form in forms:
        hidden = _SCHEME.match(form)
        if hidden:
            return _refused(f"{href!r}: the scheme {hidden.group(1)!r} isn't allowed")
        if ":" in form.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]:
            return _refused(f"{href!r}: looks like a scheme")

    if href.startswith("#"):
        return Resolved(href, target=page, fragment=unquote(href[1:]))
    if any(form.startswith("/") for form in forms):
        return _refused(f"{href!r}: absolute and protocol-relative paths aren't allowed")

    parts = urlsplit(href)
    path = forms[-1].split("#", 1)[0].split("?", 1)[0]
    target = posixpath.normpath(posixpath.join(posixpath.dirname(page), path))
    if target == ".." or target.startswith(("../", "/")):
        return _refused(f"{href!r}: climbs out of the snapshot")

    suffix = (f"?{parts.query}" if parts.query else "") + (
        f"#{parts.fragment}" if parts.fragment else ""
    )
    fragment = unquote(parts.fragment)
    if target in pages:
        return Resolved(page_url(target) + suffix, target=target, fragment=fragment)
    if target in images and target.startswith(IMAGES_FOLDER):
        return Resolved(image_url(target) + suffix, target=target)
    return _refused(f"{href!r}: {target} isn't in the snapshot")
