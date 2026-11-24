"""The API reference: parsing its pages, type links, its layout, the API home and search."""

import re
from collections import Counter

import pytest
from django.conf import settings
from django.utils.html import escape

from documentation import api, highlight, library, links, rendering, search
from documentation.library import PAGE_IDS

# ---------- Parsing an API page ----------

CLASS_PAGE = """---
description: "A solid shape in the world."
---

# Part

```luau
Instance.new("Part")
```

A solid shape in the world.

It also has every member of [Instance](Instance.md).

### Properties

#### Anchored

```luau
Part.Anchored: boolean
```

If true, the part stays where it is. If false, it falls.

```lua
workspace.Bridge.Anchored = false
```

#### Content

```luau
Part.Content: string
```

Its content.

### Events

#### Touched

```luau
Part.Touched: Signal
```

Fires when another part starts touching this one. The handler gets the other part:
`part.Touched:Connect(function(otherPart) ... end)`.

### Functions

#### GetMass

```luau
Part:GetMass(): number
```

Its density times its volume: `1 x 1 x 1. Plastic` weighs 1. MeshParts weigh their shape.
"""


def parse_page(text: str, path: str, pages=("api/classes/Instance.md",)) -> api.ApiPage:
    """Parse `text` the way the site does: anchors from the rendered page's headings."""
    rendered = rendering.render(text, path, pages=pages, diagrams={}, reserved_ids=PAGE_IDS)
    return api.parse(text, path, rendered.headings, pages)


def test_a_class_page_parses_into_its_constructor_inheritance_and_members_by_kind():
    page = parse_page(CLASS_PAGE, "api/classes/Part.md")

    assert (page.kind, page.name) == ("class", "Part")
    assert page.constructor == 'Instance.new("Part")'
    assert page.inherits == "api/classes/Instance.md"

    # Members keep page order within their kind; each knows its signature and first sentence.
    assert [m.name for m in page.of_kind("property")] == ["Anchored", "Content"]
    assert [m.name for m in page.of_kind("event")] == ["Touched"]
    assert [m.name for m in page.of_kind("function")] == ["GetMass"]
    anchored, content = page.of_kind("property")
    assert anchored.signature == "Part.Anchored: boolean"
    assert anchored.summary == "If true, the part stays where it is."
    assert anchored.qualified == "Part.Anchored"
    (touched,) = page.of_kind("event")
    assert touched.summary == "Fires when another part starts touching this one."
    (get_mass,) = page.of_kind("function")
    assert get_mass.signature == "Part:GetMass(): number"
    # A full stop inside a code span doesn't end the sentence.
    assert get_mass.summary == "Its density times its volume: 1 x 1 x 1. Plastic weighs 1."

    # Anchors are the ids the rendered headings really have: "content" is taken by the
    # page around the article, so that member's heading is "content-1".
    assert [m.anchor for m in page.members] == ["anchored", "content-1", "touched", "getmass"]


# ---------- Search: ranking and query handling ----------

SEARCH_ENTRIES = (
    search.Entry(
        "page",
        "/docs/learn/parts/",
        "Working with parts",
        names=("Working with parts",),
        title="Working with parts",
        description="Move, size and colour every block.",
        order=0,
    ),
    search.Entry(
        "heading",
        "/docs/learn/parts/#touched-events",
        "Working with parts",
        label="Touched events",
        heading="Touched events",
        description="When a part is touched, its Touched event fires.",
        order=1,
    ),
    search.Entry(
        "page",
        "/docs/api/classes/part/",
        "Part",
        names=("Part",),
        title="Part",
        description="A solid shape in the world.",
        order=2,
    ),
    search.Entry(
        "member",
        "/docs/api/classes/part/#touched",
        "Part",
        label="Part.Touched",
        names=("Part.Touched", "Touched"),
        member="Part.Touched",
        description="Fires when another part starts touching this one.",
        order=3,
    ),
    search.Entry(
        "member",
        "/docs/api/classes/part/#getmass",
        "Part",
        label="Part.GetMass",
        names=("Part.GetMass", "GetMass"),
        member="Part.GetMass",
        description="Its density times its volume.",
        order=4,
    ),
    search.Entry(
        "page",
        "/docs/api/classes/meshpart/",
        "MeshPart",
        names=("MeshPart",),
        title="MeshPart",
        description="A solid 3D model imported from a file, drawn like a Part.",
        order=5,
    ),
    search.Entry(
        "member",
        "/docs/api/classes/meshpart/#touched",
        "MeshPart",
        label="MeshPart.Touched",
        names=("MeshPart.Touched", "Touched"),
        member="MeshPart.Touched",
        description="Fires when another part starts touching this one.",
        order=6,
    ),
    search.Entry(
        "member",
        "/docs/api/libraries/#wait",
        "Libraries",
        label="task.wait",
        names=("task.wait", "wait"),
        member="task.wait",
        description="Pauses this code for seconds.",
        order=7,
    ),
)


def ranked(raw: str) -> list[tuple[str, int]]:
    return [(r.entry.url, r.rank) for r in search.search(SEARCH_ENTRIES, raw).results]


def test_search_ranks_exact_names_then_titles_headings_members_and_descriptions():
    # 1 exact name, 2 title, 3 heading, 4 member name, 5 description; within a rank, a
    # field starting with the query first, then reading order. Each URL once, at its best.
    assert ranked("Part") == [
        ("/docs/api/classes/part/", 1),
        ("/docs/learn/parts/", 2),
        ("/docs/api/classes/meshpart/", 2),
        ("/docs/api/classes/part/#touched", 4),
        ("/docs/api/classes/part/#getmass", 4),
        ("/docs/api/classes/meshpart/#touched", 4),
        ("/docs/learn/parts/#touched-events", 5),
    ]
    # A member's short name is an exact name too; ties keep reading order (Part first).
    assert ranked("Touched") == [
        ("/docs/api/classes/part/#touched", 1),
        ("/docs/api/classes/meshpart/#touched", 1),
        ("/docs/learn/parts/#touched-events", 3),
    ]
    # Case doesn't matter, and `:` reads as `.` in a qualified name.
    assert ranked("PART")[0] == ("/docs/api/classes/part/", 1)
    assert ranked("task:wait") == [("/docs/api/libraries/#wait", 1)]

    # The query is trimmed and its whitespace collapsed; every word must appear.
    outcome = search.search(SEARCH_ENTRIES, "  part \t touched \n")
    assert (outcome.query, outcome.problem) == ("part touched", "")
    assert [(r.entry.url, r.rank) for r in outcome.results] == [
        ("/docs/api/classes/part/#touched", 4),
        ("/docs/api/classes/meshpart/#touched", 4),
        ("/docs/learn/parts/#touched-events", 5),
    ]

    # Empty, whitespace-only and over-long queries return no results and say why.
    for raw, problem in (
        ("", search.EMPTY),
        (" \t\n ", search.EMPTY),
        ("x" * (search.MAX_QUERY + 1), search.TOO_LONG),
    ):
        outcome = search.search(SEARCH_ENTRIES, raw)
        assert (outcome.problem, outcome.results) == (problem, ())
    at_limit = search.search(SEARCH_ENTRIES, "x" * search.MAX_QUERY)
    assert (at_limit.problem, at_limit.results) == ("", ())


# ---------- The other API page shapes ----------


def test_libraries_globals_and_enums_parse_into_their_members():
    libraries = parse_page(
        "# Libraries\n\nTables.\n\n## task\n\nPauses scripts.\n\n### Functions\n\n#### wait\n\n"
        "```luau\ntask.wait(seconds: number?): number\n```\n\nPauses this code. Returns.\n",
        "api/libraries.md",
    )
    assert [(m.kind, m.qualified) for m in libraries.members] == [
        ("library", "task"),
        ("function", "task.wait"),
    ]
    wait = libraries.members[1]
    assert (wait.anchor, wait.short_signature) == ("wait", "(seconds: number?): number")
    assert wait.summary == "Pauses this code."

    globals_ = parse_page(
        "# Globals\n\n## game\n\n```luau\ngame: DataModel\n```\n\nThe root.\n\n"
        "## Enum\n\nEvery enum.\n",
        "api/globals.md",
    )
    assert [(m.kind, m.name, m.short_signature) for m in globals_.members] == [
        ("global", "game", "DataModel"),
        ("global", "Enum", ""),
    ]

    enums = parse_page(
        "# Enums\n\n## Enum.Material\n\nThe choices of `Enum.Material`.\n\n"
        "Items: `Plastic`, `Neon`\n",
        "api/enums.md",
    )
    (material,) = enums.members
    assert (material.qualified, material.anchor) == ("Enum.Material", "enummaterial")
    assert material.items == ("Plastic", "Neon")
    assert material.summary_html == "The choices of <code>Enum.Material</code>."


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("# Part\n\n## Stray\n", "isn't where the engine puts one"),
        ("# Part\n\n### Callbacks\n\n#### Run\n", "isn't Properties, Events or Functions"),
        ("# Part\n\n#### Loose\n", "isn't where the engine puts one"),
        ("# Part\n\nIt also has every member of [Thing](Thing.md).\n", "isn't in the snapshot"),
    ],
)
def test_a_page_in_another_shape_is_an_error(text, problem):
    with pytest.raises(api.ApiError, match=problem):
        parse_page(text, "api/classes/Part.md")


def test_only_api_pages_have_a_kind():
    assert api.page_kind("api/classes/Part.md") == "class"
    assert api.page_kind("api/types/Vector3.md") == "type"
    assert api.page_kind("api/enums.md") == "enums"
    for plain in ("api/README.md", "api/classes.md", "api/types.md", "learn/scripting.md"):
        assert api.page_kind(plain) is None


# ---------- Type links ----------


@pytest.mark.parametrize(
    ("code", "names"),
    [
        ("Part:UnionAsync(parts: {Instance}): UnionOperation", ["Instance", "UnionOperation"]),
        ('Part.Material: EnumMaterial | "Plastic"', ["EnumMaterial"]),
        ('Instance.new("Part")', []),  # an owner and a string, never a type
        ("Model.PrimaryPart: Part?", ["Part"]),
        ("-- Part in a comment\nPart.Size: Vector3", ["Vector3"]),
    ],
)
def test_type_names_are_the_types_a_signature_uses(code, names):
    known = {"Part", "Instance", "UnionOperation", "EnumMaterial", "Vector3"}
    assert highlight.type_names(code, known) == names


def test_linked_signatures_keep_their_colours_and_escape():
    html = highlight.highlight(
        'Part.Shape: EnumPartType | "Block"', "luau", {"EnumPartType": "/docs/api/enums/#e"}
    )
    assert html == (
        'Part.Shape: <a class="api-type" href="/docs/api/enums/#e">EnumPartType</a> | '
        '<span class="luau-string">&quot;Block&quot;</span>'
    )


# ---------- The real snapshot's API pages ----------

LIBRARY = library.library()
API_PATHS = [path for path in LIBRARY.navigation.order if api.page_kind(path)]


def test_summary_lists_every_api_page_and_each_parses():
    kinds = Counter(api.page_kind(path) for path in API_PATHS)
    assert kinds == {"class": 144, "type": 46, "enums": 1, "libraries": 1, "globals": 1}
    # Some pages have no members of their own (ReplicatedStorage has Instance's; DataRow
    # is read by column name), so they show their intro and no table.
    members = Counter(m.kind for path in API_PATHS for m in LIBRARY.api_page(path).members)
    assert members == {
        "property": 1714,
        "function": 485,
        "event": 121,
        "enum": 53,
        "global": 5,
        "library": 1,
    }


@pytest.mark.django_db
def test_every_api_page_has_its_member_table_and_every_anchor_resolves(client):
    failures = []
    for path in API_PATHS:
        reference = LIBRARY.api_page(path)
        html = client.get(LIBRARY.page(path).url).content.decode()
        ids = set(re.findall(r'\sid="([^"]+)"', html))
        for member in reference.members:
            if member.anchor not in ids:
                failures.append(f"{path}: #{member.anchor} isn't on the page")
            if reference.kind != "enums" and member.kind != "library":
                row = f'<a href="#{member.anchor}" class="api-name"><code>{escape(member.name)}'
                if row not in html:
                    failures.append(f"{path}: no summary row for {member.qualified}")
        if reference.kind == "enums":
            assert html.count('class="api-chips"') == len(reference.members)
    assert failures == []


@pytest.mark.django_db
def test_type_names_in_signatures_link_to_their_pages_wherever_one_exists(client):
    names = LIBRARY.type_links
    failures = []
    for path in API_PATHS:
        html = client.get(LIBRARY.page(path).url).content.decode()
        for member in LIBRARY.api_page(path).members:
            for name in highlight.type_names(member.signature, names):
                target, fragment = names[name]
                url = links.page_url(target) + (f"#{fragment}" if fragment else "")
                if f'<a class="api-type" href="{url}">' not in html:
                    failures.append(f"{path}: {member.qualified} doesn't link {name}")
    assert failures == []
    assert names["EnumMaterial"] == ("api/enums.md", "enummaterial")
    assert names["Part"] == ("api/classes/Part.md", "")


@pytest.fixture
def part_html(client, db):
    return client.get("/docs/api/classes/part/").content.decode()


def test_a_class_page_shows_its_constructor_tables_inherited_group_and_rail(part_html):
    summary = part_html.split('class="api-summary"', 1)[1].split('class="doc-prose api-details"')[0]
    # The constructor and intro come first, then a table per kind in the engine's words.
    lead = part_html.split('class="doc-prose api-lead"', 1)[1].split('class="api-summary"')[0]
    assert '<span class="luau-builtin">Instance</span>.new' in lead
    assert "A solid shape in the world." in lead
    tables = re.findall(r'aria-label="(Properties|Events|Functions)"', summary)
    assert tables[:3] == ["Properties", "Events", "Functions"]
    assert '<code class="api-sig"><a class="api-type" href="/docs/api/enums/#enummaterial">' in (
        summary
    )
    # Instance's members, collapsed, linking to Instance's own anchors.
    inherited = summary.split('<details class="api-inherited">', 1)[1].split("</details>")[0]
    assert "Inherited from Instance" in inherited
    assert '<a href="/docs/api/classes/instance/#name" class="api-name">' in inherited
    # The rail lists the members by kind.
    rail = part_html.split('id="docs-outline"', 1)[1].split("</nav>")[0]
    assert re.findall(r'api-rail-title micro">(\w+)<', rail) == [
        "Properties",
        "Events",
        "Functions",
    ]
    assert '<a href="#touched">Touched</a>' in rail


@pytest.mark.django_db
def test_instance_inherits_nothing(client):
    html = client.get("/docs/api/classes/instance/").content.decode()
    assert "api-inherited" not in html


# ---------- The API home ----------


@pytest.mark.django_db
def test_the_api_home_lists_every_entry_without_javascript(client):
    html = client.get("/docs/api/").content.decode()
    groups = re.findall(r'<section id="api-(\w+)" class="panel api-panel"', html)
    assert groups == ["classes", "types", "enums", "libraries", "globals"]
    expected = {
        "classes": [p.name for p in LIBRARY.api_pages("class")],
        "types": [p.name for p in LIBRARY.api_pages("type")],
        "enums": [m.qualified for m in LIBRARY.api_page("api/enums.md").members],
        "libraries": [m.name for m in LIBRARY.api_page("api/libraries.md").of_kind("library")],
        "globals": [m.name for m in LIBRARY.api_page("api/globals.md").members],
    }
    for group, names in expected.items():
        section = html.split(f'<section id="api-{group}"', 1)[1].split("</section>")[0]
        listed = re.findall(r'class="api-name"><code>([^<]+)</code>', section)
        assert listed == names, group
        assert section.count("data-filter=") == len(names)
    assert len(expected["classes"]) == 144 and len(expected["types"]) == 46
    # The filter is progressive: hidden in the markup, shown by docs.js.
    assert re.search(r'<div class="api-filter" data-api-filter hidden', html)
    assert "[data-api-filter]" in (settings.BASE_DIR / "static/js/docs.js").read_text()


# ---------- Search: the page ----------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "first"),
    [
        ("Part", "/docs/api/classes/part/"),
        ("Touched", "/docs/api/classes/part/#touched"),
        ("TweenService", "/docs/api/types/tweenservice/"),
        ("Enum.Material", "/docs/api/enums/#enummaterial"),
        ("task.wait", "/docs/api/libraries/#wait"),
    ],
)
def test_search_finds_the_expected_first_result(client, query, first):
    html = client.get("/docs/search/", {"q": query}).content.decode()
    assert re.findall(r'<a href="([^"]+)" class="search-link">', html)[0] == first


@pytest.mark.django_db
def test_search_paginates_twenty_a_page_and_survives_a_bad_page(client):
    total = len(search.search(LIBRARY.search_index, "part").results)
    assert total > 40
    pages = -(-total // search.PER_PAGE)
    first = client.get("/docs/search/", {"q": "part"}).content.decode()
    assert first.count('class="search-result"') == search.PER_PAGE
    assert f"{total} found" in first and f"Page 1 of {pages}" in first
    assert 'href="?q=part&amp;page=2" rel="next"' in first
    for page, label in (("2", "Page 2 of"), ("abc", "Page 1 of"), ("9999", f"Page {pages} of")):
        response = client.get("/docs/search/", {"q": "part", "page": page})
        assert response.status_code == 200 and label in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("", "Type a page, heading or API name to search for."),
        ("   ", "Type a page, heading or API name to search for."),
        ("x" * 101, "That search is too long: use at most 100 characters."),
        ("zzzzqqq", "Nothing in the docs matches that search."),
    ],
)
def test_empty_long_and_unmatched_searches_show_a_message(client, query, message):
    response = client.get("/docs/search/", {"q": query})
    html = response.content.decode()
    assert response.status_code == 200
    assert message in html and 'class="search-result"' not in html
    assert "<title>Search the docs · Axcenity Docs</title>" in html


@pytest.mark.django_db
def test_search_escapes_the_query_and_marks_matches(client):
    html = client.get("/docs/search/", {"q": '<script>"x"</script>'}).content.decode()
    assert '<script>"x"' not in html and "&lt;script&gt;" in html
    html = client.get("/docs/search/", {"q": "touched"}).content.decode()
    assert "<mark>" in html


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/docs/", "/docs/learn/scripting/", "/docs/api/classes/part/"])
def test_every_docs_page_has_the_search_form(client, url):
    html = client.get(url).content.decode()
    form = html.split('<form id="docs-search"', 1)[1].split("</form>")[0]
    assert 'action="/docs/search/" method="get"' in form and 'name="q"' in form
    # Outside the phone disclosure, so it's always in reach.
    assert html.index('id="docs-search"') < html.index('id="docs-nav"')


def test_a_page_may_not_take_the_search_url(tmp_path):
    (tmp_path / "SOURCE.json").write_text('{"repository": "r", "commit": "c", "folder": "d"}')
    (tmp_path / "SUMMARY.md").write_text("# Contents\n\n* [Home](README.md)\n* [S](search.md)\n")
    (tmp_path / "README.md").write_text("---\ndescription: Home.\n---\n\n# Home\n")
    (tmp_path / "search.md").write_text("---\ndescription: S.\n---\n\n# S\n")
    problems = library.Library(tmp_path, diagrams={}).check()
    assert problems == ["search.md: takes the URL /docs/search/, which the docs use"]


def test_the_search_index_covers_pages_headings_and_members():
    kinds = Counter(entry.kind for entry in LIBRARY.search_index)
    members = sum(len(LIBRARY.api_page(path).members) for path in API_PATHS)
    assert kinds["page"] == len(LIBRARY.paths) and kinds["member"] == members
    assert kinds["heading"] > 100
    assert len({entry.url for entry in LIBRARY.search_index}) == len(LIBRARY.search_index)
