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
}
