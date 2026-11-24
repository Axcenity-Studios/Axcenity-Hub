"""The engine documentation, rendered from the committed snapshot.

Views look pages up in the snapshot's own index (`Library.path_for`): a URL can
only ever name a page the snapshot has, never a file path. Unknown paths are 404s.
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.http import Http404, HttpResponsePermanentRedirect
from django.views.generic import TemplateView

from marketing.views import MarketingPageMixin

from . import links, navigation
from .library import Library, Page, library
from .strings import DOCS, TITLE_SUFFIX

README = "README.md"


@dataclass
class NavItem:
    """One sidebar link, marked current or open (an ancestor of the current page)."""

    title: str
    url: str
    current: bool
    open: bool
    children: list["NavItem"] = field(default_factory=list)


@dataclass
class NavSection:
    title: str
    open: bool
    items: list[NavItem]


def _nav_item(entry: navigation.Entry, current: str) -> NavItem:
    children = [_nav_item(child, current) for child in entry.children]
    is_current = entry.path == current
    return NavItem(
        title=entry.title,
        url=links.page_url(entry.path),
        current=is_current,
        open=is_current or any(child.current or child.open for child in children),
        children=children,
    )


def sidebar(nav: navigation.Navigation, current: str) -> list[NavSection]:
    """The table of contents as the sidebar shows it: the current page's section open."""
    sections = []
    for section in nav.sections:
        items = [_nav_item(entry, current) for entry in section.entries]
        is_open = any(item.current or item.open for item in items)
        sections.append(NavSection(section.title, is_open, items))
    return sections


def _breadcrumbs(page: Page) -> list[tuple[str, str]]:
    """(title, url) from the docs home down to the page's parent; "" url for a section."""
    crumbs = [(DOCS["home"], links.page_url(README))]
    # A section named like its first page ("API reference") isn't said twice.
    if page.section and (not page.trail or page.trail[0].title != page.section):
        crumbs.append((page.section, ""))
    crumbs += [(entry.title, links.page_url(entry.path)) for entry in page.trail[:-1]]
    return crumbs


class DocsMixin(MarketingPageMixin):
    """What every docs page shows around the article."""

    def docs_context(self, lib: Library, page: Page) -> dict:
        source = lib.source
        return {
            "docs": DOCS,
            "page": page,
            "full_title": f"{page.title} · {TITLE_SUFFIX}",
            "sidebar": sidebar(lib.navigation, page.path),
            "source": source,
            "committed": datetime.fromisoformat(source["committed"]),
            "commit_url": f"{source['repository']}/tree/{source['commit']}/{source['folder']}",
            "pager": [
                (DOCS[label], entry.title, links.page_url(entry.path), rel)
                for label, entry, rel in (
                    ("previous", page.previous, "prev"),
                    ("next", page.next, "next"),
                )
                if entry
            ],
        }


class DocsPageView(DocsMixin, TemplateView):
    """One page of the engine docs at /docs/<path>/."""

    template_name = "documentation/page.html"

    def get(self, request, *args, path: str = "", **kwargs):
        lib = library()
        found = lib.path_for(path)
        if found is None and path != path.lower() and lib.path_for(path.lower()):
            return HttpResponsePermanentRedirect(links.page_url(lib.path_for(path.lower())))
        if found is None or found == README:
            raise Http404("No such page in the documentation.")
        self.page = lib.page(found)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.docs_context(library(), self.page))
        context["breadcrumbs"] = _breadcrumbs(self.page)
        return context


@dataclass
class Panel:
    """A section of the landing page: its pages (two levels deep) with their descriptions."""

    title: str
    pages: list[tuple[Page, list[Page]]]


class DocsIndexView(DocsMixin, TemplateView):
    """The docs' landing page at /docs/: the README, then a panel per section."""

    template_name = "documentation/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lib = library()
        page = lib.page(README)
        context.update(self.docs_context(lib, page))
        context["panels"] = [
            Panel(
                section.title,
                [
                    (lib.page(entry.path), [lib.page(child.path) for child in entry.children])
                    for entry in section.entries
                ],
            )
            for section in lib.navigation.sections
            if section.title
        ]
        return context
