"""The engine documentation, rendered from the committed snapshot.

Views look pages up in the snapshot's own index (`Library.path_for`): a URL can
only ever name a page the snapshot has, never a file path. Unknown paths are 404s.
The API reference's pages get their own layouts (`api_context`); search runs over
the snapshot's in-memory index (documentation/search.py).
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.core.paginator import Paginator
from django.http import Http404, HttpResponsePermanentRedirect
from django.views.generic import TemplateView

from marketing.views import MarketingPageMixin

from . import api, highlight, links, navigation, search
from .library import Library, Page, library
from .strings import DOCS, TITLE_SUFFIX

README = "README.md"
API_README = "api/README.md"
# The template for each kind of API page (api.page_kind); other pages use page.html.
API_TEMPLATES = {
    "class": "documentation/api/members.html",
    "type": "documentation/api/members.html",
    "libraries": "documentation/api/members.html",
    "globals": "documentation/api/members.html",
    "enums": "documentation/api/enums.html",
}
# How many of an enum's items the API home shows before "…".
ENUM_PREVIEW = 6


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

    def docs_context(self, lib: Library, page: Page | None, title: str = "") -> dict:
        source = lib.source
        return {
            "docs": DOCS,
            "page": page,
            "full_title": f"{page.title if page else title} · {TITLE_SUFFIX}",
            "sidebar": sidebar(lib.navigation, page.path if page else ""),
            "source": source,
            "committed": datetime.fromisoformat(source["committed"]),
            "commit_url": f"{source['repository']}/tree/{source['commit']}/{source['folder']}",
            "search_query": "",
            "search_limit": search.MAX_QUERY,
            "pager": [
                (DOCS[label], entry.title, links.page_url(entry.path), rel)
                for label, entry, rel in (
                    ("previous", page.previous if page else None, "prev"),
                    ("next", page.next if page else None, "next"),
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

    def get_template_names(self):
        if self.page.path == API_README:
            return ["documentation/api/home.html"]
        return [API_TEMPLATES.get(api.page_kind(self.page.path), self.template_name)]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lib = library()
        context.update(self.docs_context(lib, self.page))
        context["breadcrumbs"] = _breadcrumbs(self.page)
        if self.page.path == API_README:
            context.update(api_home_context(lib))
        elif api.page_kind(self.page.path):
            context.update(api_context(lib, lib.api_page(self.page.path)))
        return context


# ---------- The API reference ----------


@dataclass
class Row:
    """One member in a summary table: its name, linked type or signature, first sentence."""

    member: api.Member
    url: str
    signature: str


@dataclass
class MemberTable:
    """A summary table: one kind of member (or one library's, or the globals)."""

    title: str
    anchor: str
    rows: list[Row]


@dataclass
class Inherited:
    """The members a class has from another page (Instance), linked to that page."""

    title: str
    url: str
    tables: list[MemberTable]

    @property
    def count(self) -> int:
        return sum(len(table.rows) for table in self.tables)


def _type_urls(lib: Library) -> dict[str, str]:
    return {
        name: links.page_url(path) + (f"#{fragment}" if fragment else "")
        for name, (path, fragment) in lib.type_links.items()
    }


def member_tables(page: api.ApiPage, urls: dict[str, str], base: str = "") -> list[MemberTable]:
    """The page's summary tables: Properties, Events and Functions for a class, type or
    library (one set per library), or the globals. Links are to `base` + `#anchor`."""

    def rows(members) -> list[Row]:
        return [
            Row(m, f"{base}#{m.anchor}", highlight.highlight(m.short_signature, "luau", urls))
            for m in members
        ]

    def by_kind(members, prefix: str = "") -> list[MemberTable]:
        tables = []
        for kind, title in DOCS["api_kinds"].items():
            chosen = [m for m in members if m.kind == kind]
            if chosen:
                tables.append(MemberTable(f"{prefix}{title}", "", rows(chosen)))
        return tables

    if page.kind == "globals":
        return [MemberTable(DOCS["api_globals"], "", rows(page.members))]
    if page.kind == "libraries":
        tables = []
        for library_ in page.of_kind("library"):
            owned = [m for m in page.members if m.owner == library_.name]
            for table in by_kind(owned, f"{library_.name} · "):
                table.anchor = library_.anchor
                tables.append(table)
        return tables
    return by_kind(page.members)


def api_context(lib: Library, page: api.ApiPage) -> dict:
    """What an API page shows beyond the article: summary tables, the inherited group,
    and the rail of members by kind."""
    urls = _type_urls(lib)
    tables = member_tables(page, urls)
    inherited = None
    if page.inherits:
        parent = lib.api_page(page.inherits)
        url = links.page_url(page.inherits)
        inherited = Inherited(parent.name, url, member_tables(parent, urls, base=url))
    if page.kind == "enums":
        rail = [(DOCS["api_enums"], [(m.qualified, f"#{m.anchor}") for m in page.members])]
    else:
        rail = [(t.title, [(r.member.name, r.url) for r in t.rows]) for t in tables]
    return {"api": page, "tables": tables, "inherited": inherited, "rail": rail}


@dataclass
class HomeEntry:
    """One name on the API home: where it goes, its one line, and what the filter reads."""

    name: str
    url: str
    about: str

    @property
    def filter_text(self) -> str:
        return f"{self.name} {self.about}".lower()


def api_home_context(lib: Library) -> dict:
    """The API home's panels: every class, data type, enum, library and global."""
    enums = lib.api_page("api/enums.md")
    libraries = lib.api_page("api/libraries.md")
    globals_ = lib.api_page("api/globals.md")

    def pages(kind: str) -> list[HomeEntry]:
        return [
            HomeEntry(p.name, links.page_url(p.path), lib.page(p.path).description)
            for p in lib.api_pages(kind)
        ]

    def members(page: api.ApiPage | None, kind: str) -> list[HomeEntry]:
        if page is None:
            return []
        base = links.page_url(page.path)
        entries = []
        for m in page.of_kind(kind):
            about = m.summary
            if m.items:
                shown = ", ".join(m.items[:ENUM_PREVIEW])
                about = shown + (", …" if len(m.items) > ENUM_PREVIEW else "")
            entries.append(HomeEntry(m.qualified, f"{base}#{m.anchor}", about))
        return entries

    found = {
        "classes": pages("class"),
        "types": pages("type"),
        "enums": members(enums, "enum"),
        "libraries": members(libraries, "library"),
        "globals": members(globals_, "global"),
    }
    groups = [(slug, title, found[slug]) for slug, title in DOCS["api_groups"]]
    return {
        "groups": groups,
        "api_total": sum(len(entries) for _, _, entries in groups),
        "rail": [(DOCS["api_members"], [(title, f"#api-{slug}") for slug, title, _ in groups])],
    }


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


class DocsSearchView(DocsMixin, TemplateView):
    """Search the docs at /docs/search/?q=: pages, headings and API members, 20 a page."""

    template_name = "documentation/search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lib = library()
        outcome = search.search(lib.search_index, self.request.GET.get("q", ""))
        results = Paginator(outcome.results, search.PER_PAGE).get_page(self.request.GET.get("page"))
        context.update(self.docs_context(lib, None, DOCS["search_title"]))
        context.update(
            {
                "outcome": outcome,
                "results": results,
                "marked": [(r, search.mark(r.entry.snippet, outcome.query)) for r in results],
                "search_query": outcome.query[: search.MAX_QUERY],
                "problem": (
                    DOCS["search_too_long"].format(limit=search.MAX_QUERY)
                    if outcome.problem == search.TOO_LONG
                    else DOCS["search_empty"]
                    if outcome.problem == search.EMPTY
                    else ""
                ),
                "breadcrumbs": [(DOCS["home"], links.page_url(README))],
                "count_label": DOCS["search_count"].format(count=results.paginator.count),
                "page_label": DOCS["search_page"].format(
                    number=results.number, total=results.paginator.num_pages
                ),
            }
        )
        return context
