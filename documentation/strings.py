"""The docs site's own words (everything around the engine's pages), kept as data.

The pages themselves come from the snapshot; this is the frame: titles, labels,
the Alpha notice and the provenance line. Templates read it as `docs`.
"""

from marketing.content import ENGINE_VERSION

# <title>: "Scripting and the API · Axcenity Docs".
TITLE_SUFFIX = "Axcenity Docs"

DOCS = {
    "home": "Docs",
    "nav_label": "Documentation",
    "nav_toggle": "Browse the docs",
    "overview": "Overview",
    "breadcrumbs": "Breadcrumbs",
    "outline": "On this page",
    "previous": "Previous",
    "next": "Next",
    "pager": "Previous and next pages",
    "view_source": "View source on GitHub",
    # The code blocks' copy button (static/js/docs.js reads these from the article).
    "copy": "Copy",
    "copy_label": "Copy code",
    "copied": "Copied",
    "copy_failed": "Select and copy",
    "samples": "Try it in the editor",
    "samples_body": "Open the editor's Learn tab and pick a sample project:",
    "alpha_badge": f"Alpha · {ENGINE_VERSION}",
    "alpha_body": (
        "Axcenity is in early alpha: features, file formats and the Luau API can change "
        "between releases."
    ),
    "status_title": "Status",
    # The docs footer: where this copy of the docs came from.
    "provenance": "Copied from the engine repository at commit",
    "provenance_date": "committed",
    "provenance_link": "Browse the docs at this commit",
    # The landing page (/docs/).
    "index_eyebrow": "Documentation",
    "index_sections": "Every section",
    "index_sections_body": "The guide, chapter by chapter, then the reference and the API.",
    # The API reference (/docs/api/…).
    "api_kinds": {"property": "Properties", "event": "Events", "function": "Functions"},
    "api_globals": "Globals",
    "api_members": "Members",
    "api_name": "Name",
    "api_signature": "Type or signature",
    "api_about": "What it does",
    "api_inherited": "Inherited from",
    "api_items": "Items",
    "api_enums": "Enums",
    # The API home's panels, in order: (slug, title).
    "api_groups": (
        ("classes", "Classes"),
        ("types", "Data types"),
        ("enums", "Enums"),
        ("libraries", "Libraries"),
        ("globals", "Globals"),
    ),
    "api_filter": "Filter the API",
    "api_filter_placeholder": "Filter by name or description",
    # static/js/docs.js fills in {shown} and {total}.
    "api_filter_count": "{shown} of {total} shown",
    "api_filter_none": "Nothing in the API matches that filter.",
    # Search (/docs/search/).
    "search": "Search",
    "search_label": "Search the docs",
    "search_placeholder": "Search the docs",
    "search_title": "Search the docs",
    "search_lede": "Pages, headings and API names, such as Part, Touched or task.wait.",
    "search_results": "Results for",
    "search_count": "{count} found",
    "search_none": "Nothing in the docs matches that search. Try a shorter word or an API name.",
    "search_empty": "Type a page, heading or API name to search for.",
    "search_too_long": "That search is too long: use at most {limit} characters.",
    "search_kinds": {"page": "Page", "heading": "Section", "member": "API"},
    "search_pages": "Search result pages",
    "search_page": "Page {number} of {total}",
}
