"""The documentation site: the snapshot, its links, navigation, rendering and pages."""

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from urllib.parse import unquote

import pytest
from django.contrib.staticfiles import finders
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils.html import escape
from PIL import Image

from documentation import diagrams, highlight, library, links, navigation, rendering, sync

# ---------- Link rewriting ----------

PAGES = {
    "README.md",
    "learn/scripting.md",
    "learn/blocks.md",
    "reference/scripting.md",
    "api/README.md",
    "api/classes/Part.md",
}
IMAGES = {"images/scripting-client-server.png"}


@pytest.mark.parametrize(
    ("href", "url", "reported"),
    [
        # Pages: a sibling, a parent, with and without #anchor; README is its folder's URL.
        ("blocks.md", "/docs/learn/blocks/", False),
        ("../reference/scripting.md#events", "/docs/reference/scripting/#events", False),
        ("./blocks.md#wiring", "/docs/learn/blocks/#wiring", False),
        ("../README.md", "/docs/", False),
        ("../api/README.md", "/docs/api/", False),
        ("../api/classes/Part.md", "/docs/api/classes/part/", False),
        # Images: their static path.
        (
            "../images/scripting-client-server.png",
            "/static/docs/images/scripting-client-server.png",
            False,
        ),
        # Same-page anchors and external links are left as they are.
        ("#where-scripts-live", "#where-scripts-live", False),
        ("https://github.com/Axcenity-Studios", "https://github.com/Axcenity-Studios", False),
        ("mailto:team@example.com", "mailto:team@example.com", False),
        # A page link's query string is kept, before its anchor; so is an image's.
        ("blocks.md?version=2#wiring", "/docs/learn/blocks/?version=2#wiring", False),
        ("../reference/scripting.md?a=1&b=2", "/docs/reference/scripting/?a=1&b=2", False),
        (
            "../images/scripting-client-server.png?v=3",
            "/static/docs/images/scripting-client-server.png?v=3",
            False,
        ),
        # External links with query strings and fragments are never changed.
        (
            "https://github.com/Axcenity-Studios/Axcenity-Engine/issues?q=is%3Aopen+label%3Adocs#list",
            "https://github.com/Axcenity-Studios/Axcenity-Engine/issues?q=is%3Aopen+label%3Adocs#list",
            False,
        ),
        ("https://example.com/a?x=1&y=two#frag", "https://example.com/a?x=1&y=two#frag", False),
        (
            "mailto:team@example.com?subject=Docs%20bug&body=Hi#x",
            "mailto:team@example.com?subject=Docs%20bug&body=Hi#x",
            False,
        ),
        # Missing targets are reported, never kept.
        ("missing.md", "", True),
        ("../images/missing.png", "", True),
        ("blocks.md.bak", "", True),
        # Paths that climb out of the snapshot, however they're spelled.
        ("../../manage.py", "", True),
        ("../../../etc/passwd.md", "", True),
        ("%2e%2e/%2e%2e/config/settings.md", "", True),
        ("/etc/passwd", "", True),
        ("..\\..\\secret.md", "", True),
        # Schemes off the allow-list, and protocol-relative URLs.
        ("javascript:alert(1)", "", True),
        ("JavaScript:alert(1)", "", True),
        ("data:text/html;base64,PHNjcmlwdD4=", "", True),
        ("file:///etc/passwd", "", True),
        ("vbscript:msgbox", "", True),
        ("//evil.example/x", "", True),
        # Disguised schemes: percent-encoded, entity-encoded, split by whitespace or control
        # characters a browser would strip, padded, or malformed.
        ("java%73cript:alert(1)", "", True),
        ("%6A%61%76%61%73%63%72%69%70%74:alert(1)", "", True),
        ("javascript%3Aalert(1)", "", True),
        ("jav&#x61;script:alert(1)", "", True),
        ("javascript&colon;alert(1)", "", True),
        ("java\tscript:alert(1)", "", True),
        ("java\nscript:alert(1)", "", True),
        (" javascript:alert(1)", "", True),
        ("\x00javascript:alert(1)", "", True),
        ("javascript\x00:alert(1)", "", True),
        ("blocks.md\x00.png", "", True),
        ("\\\\evil.example/x", "", True),
        ("/\\evil.example/x", "", True),
        ("https:evil.example", "", True),
        ("https:/evil.example", "", True),
        ("https://", "", True),
        ("mailto:", "", True),
        ("http://example.com/plain", "http://example.com/plain", False),
    ],
)
def test_links_are_rewritten_to_hub_urls_or_reported(href, url, reported):
    result = links.resolve(href, "learn/scripting.md", PAGES, IMAGES)
    assert result.url == url
    assert bool(result.problem) == reported


# ---------- Navigation from SUMMARY.md ----------

SUMMARY = """\
# Table of contents

* [Axcenity documentation](README.md)

## Before you start

* [System requirements](reference/system-requirements.md)

## Learn: Code

* [Scripting and the API](learn/scripting.md)
* [Blocks: visual programming](learn/blocks.md)

## API reference

* [API reference](api/README.md)
  * [Classes](api/classes.md)
    * [Instance](api/classes/Instance.md)
    * [Part](api/classes/Part.md)
  * [Enums](api/enums.md)
"""


def test_summary_gives_sections_nesting_reading_order_neighbours_and_orphans():
    nav = navigation.parse_summary(SUMMARY)

    # Sections in order; the README sits before the first one, untitled.
    assert [section.title for section in nav.sections] == [
        "",
        "Before you start",
        "Learn: Code",
        "API reference",
    ]
    learn = nav.sections[2]
    assert [(e.title, e.path) for e in learn.entries] == [
        ("Scripting and the API", "learn/scripting.md"),
        ("Blocks: visual programming", "learn/blocks.md"),
    ]
    # Nesting follows the indents.
    (api,) = nav.sections[3].entries
    assert api.path == "api/README.md"
    assert [child.title for child in api.children] == ["Classes", "Enums"]
    assert [leaf.title for leaf in api.children[0].children] == ["Instance", "Part"]
    assert api.children[1].children == ()

    # Reading order is the file's, depth first.
    assert nav.order == (
        "README.md",
        "reference/system-requirements.md",
        "learn/scripting.md",
        "learn/blocks.md",
        "api/README.md",
        "api/classes.md",
        "api/classes/Instance.md",
        "api/classes/Part.md",
        "api/enums.md",
    )

    # Previous and next follow it, across sections and in and out of nesting.
    assert nav.previous("README.md") is None
    assert nav.next("README.md").path == "reference/system-requirements.md"
    assert nav.previous("learn/scripting.md").path == "reference/system-requirements.md"
    assert nav.next("learn/blocks.md").path == "api/README.md"
    assert nav.next("api/README.md").path == "api/classes.md"
    assert nav.next("api/classes/Part.md").path == "api/enums.md"
    assert nav.previous("api/enums.md").title == "Part"
    assert nav.next("api/enums.md") is None
    assert nav.next("learn/unlisted.md") is None

    # A page the table of contents doesn't list is an orphan.
    assert nav.orphans([*nav.order, "learn/secret.md", "api/types/Ray.md"]) == [
        "api/types/Ray.md",
        "learn/secret.md",
    ]
    assert nav.orphans(nav.order) == []


def test_summary_keeps_an_empty_section_and_lifts_entries_with_nothing_to_nest_under():
    nav = navigation.parse_summary(
        "# Table of contents\n\n"
        "## Empty\n\n"
        "## Only nested\n\n"
        "    * [Deep](learn/deep.md)\n"
        "  * [Shallower](learn/shallower.md)\n"
        "      * [Under shallower](learn/under.md)\n\n"
        "## After\n\n"
        "* [Last](learn/last.md)\n"
    )
    assert [(s.title, len(s.entries)) for s in nav.sections] == [
        ("Empty", 0),
        ("Only nested", 2),
        ("After", 1),
    ]
    deep, shallower = nav.sections[1].entries
    assert (deep.title, deep.children) == ("Deep", ())
    assert [child.title for child in shallower.children] == ["Under shallower"]
    assert nav.order == ("learn/deep.md", "learn/shallower.md", "learn/under.md", "learn/last.md")
    assert nav.previous("learn/last.md").path == "learn/under.md"
    assert navigation.parse_summary("").sections == ()
    assert navigation.parse_summary("## Lonely\n").order == ()


def test_trail_gives_a_pages_section_and_the_entries_down_to_it():
    nav = navigation.parse_summary(SUMMARY)
    section, entries = nav.trail("api/classes/Part.md")
    assert section.title == "API reference"
    assert [e.title for e in entries] == ["API reference", "Classes", "Part"]
    section, entries = nav.trail("README.md")
    assert (section.title, [e.title for e in entries]) == ("", ["Axcenity documentation"])
    assert nav.trail("learn/unlisted.md") is None


# ---------- sync_engine_docs, against a fake engine repository ----------

# Git run in isolation: no global or system config, hooks or signing, a fixed identity.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Engine",
    "GIT_AUTHOR_EMAIL": "engine@example.invalid",
    "GIT_COMMITTER_NAME": "Engine",
    "GIT_COMMITTER_EMAIL": "engine@example.invalid",
    "GIT_AUTHOR_DATE": "2026-11-20T10:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-11-20T10:00:00+00:00",
}
FAKE_DOCS = {
    "SUMMARY.md": "# Table of contents\n\n* [Home](README.md)\n\n## Learn\n\n"
    "* [Start](learn/start.md)\n",
    "README.md": "---\ndescription: The fake docs.\n---\n\n# Home\n\nSee [Start](learn/start.md).\n",
    "learn/start.md": "---\ndescription: Start here.\n---\n\n# Start\n\n"
    "![A diagram.](../images/diagram.png)\n",
}


def git(repo, *args) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], env=GIT_ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit_all(repo, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def engine(tmp_path):
    """A git repository shaped like the engine: documentation/ plus code it must ignore."""
    repo = tmp_path / "engine"
    docs = repo / "documentation"
    for name, text in FAKE_DOCS.items():
        (docs / name).parent.mkdir(parents=True, exist_ok=True)
        (docs / name).write_text(text)
    (docs / "images").mkdir()
    Image.new("RGB", (40, 20), "#336699").save(docs / "images" / "diagram.png")
    (repo / "crates").mkdir()
    (repo / "crates" / "main.rs").write_text("fn main() {}\n")
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    commit_all(repo, "Docs")
    return repo


def fingerprint(root) -> dict[str, tuple[str, int]]:
    """Every file under `root` (git's own included): its content hash and modification time."""
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_sync_copies_the_docs_at_a_commit_records_it_and_changes_nothing_when_rerun(
    engine, tmp_path
):
    dest = tmp_path / "hub" / "documentation" / "content"
    engine_before = fingerprint(engine)

    result = sync.sync(engine, dest)

    # Markdown and images are copied byte for byte; nothing outside documentation/ is.
    copied = {path for path in fingerprint(dest) if path != "SOURCE.json"}
    assert copied == {"SUMMARY.md", "README.md", "learn/start.md", "images/diagram.png"}
    for path in copied:
        assert (dest / path).read_bytes() == (engine / "documentation" / path).read_bytes()

    # SOURCE.json records the commit, its documentation/ tree and when it was committed.
    head = git(engine, "rev-parse", "HEAD")
    source = json.loads((dest / "SOURCE.json").read_text())
    assert source["commit"] == head == result.commit
    assert source["tree"] == git(engine, "rev-parse", "HEAD:documentation") == result.tree
    committed = datetime.fromisoformat(source["committed"])
    assert committed == datetime(2026, 11, 20, 10, tzinfo=UTC)
    assert source["repository"] == sync.ENGINE_REPO_URL
    # The snapshot's files hash to that tree, so it can be checked without the engine.
    assert sync.tree_hash(dest) == source["tree"]
    assert result.changed

    # The engine repository is never written to, git's own files included.
    assert fingerprint(engine) == engine_before

    # A second run with no engine changes touches nothing.
    snapshot = fingerprint(dest)
    again = sync.sync(engine, dest)
    assert not again.changed
    assert fingerprint(dest) == snapshot
    assert fingerprint(engine) == engine_before


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_tree_hash_is_gits_own_with_modes_sorting_symlinks_and_empty_folders(
    tmp_path, object_format
):
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", f"--object-format={object_format}", str(repo))
    files = {
        "a-b": "dash",
        "a.b": "dot",
        "a/inner.md": "folder a sorts as 'a/', between 'a.b' and 'a0'",
        "a0": "zero",
        "b c.md": "a space",
        "ñandú.md": "unicode",
        "deep/er/est.md": "nested",
        "run.sh": "#!/bin/sh\n",
    }
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    (repo / "run.sh").chmod(0o755)
    (repo / "link").symlink_to("a.b")
    (repo / "empty").mkdir()
    (repo / "deep" / "hollow" / "inside").mkdir(parents=True)
    commit_all(repo, "Shapes")

    expected = git(repo, "rev-parse", "HEAD^{tree}")
    assert git(repo, "ls-tree", "HEAD", "run.sh").startswith("100755")
    assert git(repo, "ls-tree", "HEAD", "link").startswith("120000")
    assert sync.tree_hash(repo, algorithm=object_format, exclude=frozenset({".git"})) == expected
    assert sync.tree_hash(repo / "deep", algorithm=object_format) == git(
        repo, "rev-parse", "HEAD:deep"
    )


def leftovers(dest) -> list[str]:
    """Anything beside the snapshot: a sync's temporary or backup folders."""
    return sorted(p.name for p in dest.parent.iterdir() if p != dest)


@pytest.fixture
def synced(engine, tmp_path):
    dest = tmp_path / "hub" / "content"
    sync.sync(engine, dest)
    return dest


def test_a_failed_check_leaves_the_snapshot_untouched_and_nothing_behind(engine, synced):
    (engine / "documentation" / "learn" / "start.md").write_text("# Changed\n")
    commit_all(engine, "Change")
    before = fingerprint(synced)
    with pytest.raises(sync.SyncError, match="fails its checks"):
        sync.sync(engine, synced, validate=lambda root: ["learn/start.md: a broken link"])
    assert fingerprint(synced) == before
    assert leftovers(synced) == []


def test_a_copy_that_doesnt_hash_to_the_commits_tree_is_refused(engine, synced, monkeypatch):
    (engine / "documentation" / "learn" / "start.md").write_text("# Changed\n")
    commit_all(engine, "Change")
    before = fingerprint(synced)
    monkeypatch.setattr(sync, "tree_hash", lambda root, **kw: "0" * 40)
    with pytest.raises(sync.SyncError, match="hashes to"):
        sync.sync(engine, synced)
    assert fingerprint(synced) == before
    assert leftovers(synced) == []


def test_a_failed_swap_puts_the_old_snapshot_back(engine, synced, monkeypatch):
    (engine / "documentation" / "learn" / "start.md").write_text("# Changed\n")
    commit_all(engine, "Change")
    before = fingerprint(synced)
    real_rename, calls = type(synced).rename, []

    def rename(self, target):
        calls.append(self.name)
        if len(calls) == 2:  # the new snapshot moving into place
            raise OSError("disk full")
        return real_rename(self, target)

    monkeypatch.setattr(type(synced), "rename", rename)
    with pytest.raises(OSError, match="disk full"):
        sync.sync(engine, synced)
    monkeypatch.undo()
    assert fingerprint(synced) == before
    assert leftovers(synced) == []


@pytest.mark.parametrize(
    "change",
    ["edit", "untracked"],
)
def test_uncommitted_changes_to_the_docs_are_refused(engine, synced, change):
    docs = engine / "documentation"
    if change == "edit":
        (docs / "README.md").write_text("# Uncommitted\n")
    else:
        (docs / "learn" / "new.md").write_text("# New\n")
    before = fingerprint(synced)
    with pytest.raises(sync.SyncError, match="uncommitted changes"):
        sync.sync(engine, synced)
    assert fingerprint(synced) == before


def test_uncommitted_changes_outside_the_docs_dont_matter(engine, synced):
    (engine / "crates" / "main.rs").write_text("fn main() { todo!() }\n")
    assert not sync.sync(engine, synced).changed


@pytest.mark.parametrize(
    ("name", "make", "problem"),
    [
        ("tool.sh", lambda p: (p.write_text("echo\n"), p.chmod(0o755)), "regular files"),
        ("alias.md", lambda p: p.symlink_to("README.md"), "regular files"),
        ("images/logo.svg", lambda p: p.write_text("<svg onload='x()'/>"), "Markdown and images"),
        ("page.html", lambda p: p.write_text("<script></script>"), "Markdown and images"),
        ("SOURCE.json", lambda p: p.write_text("{}"), "Markdown and images"),
    ],
)
def test_only_regular_markdown_and_image_files_are_copied(engine, synced, name, make, problem):
    make(engine / "documentation" / name)
    commit_all(engine, f"Add {name}")
    before = fingerprint(synced)
    with pytest.raises(sync.SyncError, match=problem):
        sync.sync(engine, synced)
    assert fingerprint(synced) == before
    assert leftovers(synced) == []


def test_an_engine_without_the_docs_folder_is_refused(engine, tmp_path):
    with pytest.raises(sync.SyncError, match="handbook/ isn't in commit"):
        sync.sync(engine, tmp_path / "content", folder="handbook")
    assert not (tmp_path / "content").exists()


def test_a_snapshot_inside_the_engine_is_refused(engine):
    with pytest.raises(sync.SyncError, match="must not overlap"):
        sync.sync(engine, engine / "documentation" / "copy")
    assert not (engine / "documentation" / "copy").exists()


def test_a_new_commit_is_mirrored_deletions_included(engine, synced):
    docs = engine / "documentation"
    (docs / "learn" / "start.md").unlink()
    (docs / "learn" / "next.md").write_text("# Next\n")
    commit = commit_all(engine, "Rename")
    result = sync.sync(engine, synced)
    assert result.changed and result.commit == commit
    assert not (synced / "learn" / "start.md").exists()
    assert (synced / "learn" / "next.md").read_text() == "# Next\n"
    assert json.loads((synced / "SOURCE.json").read_text())["commit"] == commit
    assert sync.tree_hash(synced) == git(engine, "rev-parse", "HEAD:documentation")
    assert leftovers(synced) == []


def test_sync_is_deterministic(engine, tmp_path):
    one, two = tmp_path / "one" / "content", tmp_path / "two" / "content"
    sync.sync(engine, one)
    sync.sync(engine, two)
    assert {k: v[0] for k, v in fingerprint(one).items()} == {
        k: v[0] for k, v in fingerprint(two).items()
    }


# ---------- Luau highlighting: the editor's own test cases (lua_syntax.rs) ----------

KIND_NAMES = {
    "keyword": "Keyword",
    "literal": "Literal",
    "builtin": "Builtin",
    "number": "Number",
    "string": "String",
    "comment": "Comment",
}


def colored(code: str) -> list[tuple[str, str]]:
    """The pieces of `code` that aren't plain, as (the editor's kind, text)."""
    return [
        (KIND_NAMES[highlight.KINDS[kind]], text)
        for _, kind, text in highlight.editor_tokens(code)
        if kind in highlight.KINDS
    ]


def test_keywords_strings_numbers_and_comments_are_told_apart():
    code = (
        "local pad = workspace.Pad -- the pad\n"
        "if pad.Anchored == false then print(\"hi\", 'x', 1.5e-3, 0xFF) end"
    )
    assert colored(code) == [
        ("Keyword", "local"),
        ("Builtin", "workspace"),
        ("Comment", "-- the pad"),
        ("Keyword", "if"),
        ("Literal", "false"),
        ("Keyword", "then"),
        ("Builtin", "print"),
        ("String", '"hi"'),
        ("String", "'x'"),
        ("Number", "1.5e-3"),
        ("Number", "0xFF"),
        ("Keyword", "end"),
    ]


def test_long_strings_and_comments_span_lines():
    code = "--[[ one\ntwo ]] x = [==[ a ]] b ]==] y = 'it\\'s' --[=[ never closed"
    assert colored(code) == [
        ("Comment", "--[[ one\ntwo ]]"),
        ("String", "[==[ a ]] b ]==]"),
        ("String", "'it\\'s'"),
        ("Comment", "--[=[ never closed"),
    ]
    # An unclosed quote stops at the end of its line.
    assert colored('s = "open\nend') == [("String", '"open'), ("Keyword", "end")]


def test_names_after_a_dot_or_colon_are_not_globals():
    assert colored("x.print(game:workspace())") == [("Builtin", "game")]
    # Part of a longer name isn't a keyword either.
    assert len(colored("endless = 1 notable = 2 local_x = 3")) == 3


def test_pieces_cover_all_the_code():
    code = '-- ünïcode ✓\nlocal é = "日本\\é" ±1 [[ß]] \'x\\'
    pieces = list(highlight.editor_tokens(code))
    end = 0
    for start, _, text in pieces:
        assert start == end
        end += len(text)
    assert end == len(code)


def test_the_editors_keyword_and_builtin_lists_are_the_ones_used():
    """The Luau sets are the editor's (marketing/drawings.py copies lua_syntax.rs)."""
    assert len(highlight.LUAU_KEYWORDS) == 19 and len(highlight.LUAU_BUILTINS) == 34


def test_highlight_renders_luau_as_escaped_spans_and_other_languages_plain():
    html = highlight.highlight('print("<b>") -- & done\n', "luau")
    assert html == (
        '<span class="luau-builtin">print</span>('
        '<span class="luau-string">&quot;&lt;b&gt;&quot;</span>) '
        '<span class="luau-comment">-- &amp; done</span>'
    )
    assert highlight.highlight("local x", "lua").startswith('<span class="luau-keyword">')
    assert highlight.highlight("<div> local", "css") == "&lt;div&gt; local"
    assert highlight.highlight("uv sync\n", "sh") == "uv sync"


# ---------- Rendering: a security boundary ----------

RENDER_PAGES = {"learn/scripting.md", "learn/blocks.md", "README.md"}


def render(body: str, path: str = "learn/scripting.md", **kwargs) -> rendering.Rendered:
    return rendering.render(body, path, pages=RENDER_PAGES, diagrams=diagrams.DIAGRAMS, **kwargs)


def test_raw_html_is_shown_as_text_never_run():
    html = render(
        '# T\n\n<script>alert(1)</script>\n\nText <img src=x onerror="alert(1)"> and '
        '<a href="javascript:x">a</a>.\n\n<div onclick="x()">block</div>\n'
    ).html
    assert "<script" not in html and "<img src=x" not in html and "<div" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "onerror" not in html.replace("onerror=&quot;", "")


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "java%73cript:alert(1)",
        "jav&#x61;script:alert(1)",
        "data:text/html,x",
        "../../manage.py",
        "missing.md",
        "//evil.example",
    ],
)
def test_a_refused_link_renders_as_its_text_and_is_reported(href):
    rendered = render(f"# T\n\nSee [the place]({href}) now.\n")
    assert "<a " not in rendered.html
    assert "See the place now." in rendered.html
    assert len(rendered.problems) == 1


def test_autolinks_go_through_the_same_gate():
    rendered = render("# T\n\n<https://github.com/x> and <javascript:alert(1)>\n")
    assert '<a href="https://github.com/x" rel="noopener">' in rendered.html
    assert "and javascript:alert(1)</p>" in rendered.html  # its words, not a link
    assert 'href="javascript' not in rendered.html and len(rendered.problems) == 1


def test_internal_and_external_links_are_rewritten_and_marked():
    rendered = render(
        "# T\n\n[Blocks](blocks.md#wiring), [Home](../README.md), [GH](https://github.com/a)\n"
    )
    assert '<a href="/docs/learn/blocks/#wiring">Blocks</a>' in rendered.html
    assert '<a href="/docs/">Home</a>' in rendered.html
    assert '<a href="https://github.com/a" rel="noopener">GH</a>' in rendered.html
    assert rendering.InternalLink("learn/blocks.md", "wiring") in rendered.links


def test_an_image_must_be_a_manifest_diagram():
    ok = render("# T\n\n![A client-server diagram.](../images/scripting-client-server.png)\n")
    assert '<figure class="doc-figure">' in ok.html
    assert 'src="/static/docs/images/scripting-client-server.png"' in ok.html
    assert 'width="1200" height="620"' in ok.html and 'loading="lazy"' in ok.html
    assert ">Diagram</span>" in ok.html and "A client-server diagram." in ok.html
    for src in (
        "../images/missing.png",
        "https://evil.example/x.png",
        "../../static/brand/logo.png",
    ):
        refused = render(f"# T\n\n![Words stay.]({src})\n")
        assert "<img" not in refused.html and "Words stay." in refused.html
        assert refused.problems


def test_the_first_h1_is_the_title_and_leaves_the_body():
    rendered = render("# The title\n\nBody.\n\n## Part\n")
    assert rendered.title == "The title"
    assert "<h1" not in rendered.html


def test_code_blocks_are_highlighted_escaped_and_scroll_in_their_own_box():
    html = render('# T\n\n```luau\nprint("<b>")\n```\n\n```sh\nuv sync && <x>\n```\n').html
    assert (
        '<div class="doc-code" data-language="luau"><pre tabindex="0" aria-label="Luau code">'
        in html
    )
    assert '<span class="luau-builtin">print</span>' in html
    assert "uv sync &amp;&amp; &lt;x&gt;" in html


def test_tables_scroll_inside_a_labelled_region():
    html = render("# T\n\n| A | B |\n|---|---|\n| 1 | 2 |\n").html
    assert '<div class="doc-table" role="region" tabindex="0" aria-label="Table"><table>' in html


# ---------- Heading ids ----------


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Collaborate: editing together", "collaborate-editing-together"),
        (
            "The environment track: the weather and the time of day in one key",
            "the-environment-track-the-weather-and-the-time-of-day-in-one-key",
        ),
        ("Ground clutter and stains", "ground-clutter-and-stains"),
        ("`Part.Touched`", "parttouched"),
        ("Size & scale (studs)", "size--scale-studs"),
        ("Ñandú über", "ñandú-über"),
        ("!!!", "section"),
    ],
)
def test_heading_ids_are_github_style_slugs(text, slug):
    assert rendering.slugify(text) == slug


def test_heading_ids_never_collide_and_are_the_same_every_time():
    def ids():
        made = rendering.HeadingIds(reserved={"content", "overview"})
        return [
            made.add(t) for t in ("Events", "Events", "Events-1", "Events", "Content", "Overview")
        ]

    first = ids()
    assert first == ["events", "events-1", "events-1-1", "events-2", "content-1", "overview-1"]
    assert len(set(first)) == len(first)
    assert ids() == first


def test_every_heading_gets_a_unique_id_and_a_permalink():
    rendered = render("# T\n\n## Events\n\n### Events\n\n## Events\n\n#### Deep\n")
    assert [h.id for h in rendered.headings] == ["events", "events-1", "events-2", "deep"]
    assert '<h2 id="events">Events<a class="doc-anchor" href="#events"' in rendered.html
    assert [h.text for h in rendered.outline] == ["Events", "Events", "Events"]


# ---------- Front matter ----------


def test_front_matter_reads_the_engines_shapes():
    meta, body = rendering.split_front_matter(
        "---\ndescription: Projects: templates, folders.\nicon: cube\n"
        "samples: [script, events]\nstatus: partial\n---\n\n# Title\n"
    )
    assert meta.description == "Projects: templates, folders."
    assert (meta.icon, meta.samples, meta.status_label) == (
        "cube",
        ("script", "events"),
        "Partly built",
    )
    assert body == "\n# Title\n"
    quoted, _ = rendering.split_front_matter('---\ndescription: "A solid: shape."\n---\n')
    assert quoted.description == "A solid: shape."
    assert rendering.split_front_matter("# No front matter\n")[0] == rendering.FrontMatter()


@pytest.mark.parametrize(
    "front",
    ["not a key line", "samples: [unclosed", "samples: 3", 'description: ["a list"]'],
)
def test_bad_front_matter_is_an_error(front):
    with pytest.raises(rendering.RenderError):
        rendering.split_front_matter(f"---\n{front}\n---\n# T\n")


# ---------- The committed snapshot ----------

LIBRARY = library.library()
PAGE_PATHS = LIBRARY.navigation.order


def test_the_committed_snapshot_passes_the_build_check():
    """Every page renders with a title and description; every link, image and #anchor
    resolves; SUMMARY.md and the pages agree; every image is a manifest diagram."""
    assert LIBRARY.check() == []


def test_the_snapshot_is_exactly_its_recorded_engine_tree():
    source = LIBRARY.source
    assert set(source) == {"repository", "folder", "commit", "tree", "object_format", "committed"}
    assert source["repository"] == sync.ENGINE_REPO_URL and source["folder"] == "documentation"
    assert sync.tree_hash(LIBRARY.root, algorithm=source["object_format"]) == source["tree"]


def test_the_recorded_commit_exists_in_the_engine_and_holds_that_tree(settings):
    engine = settings.AXCENITY_ENGINE_DIR
    if not (engine / ".git").exists():
        pytest.skip("the engine checkout isn't on this machine")
    source = LIBRARY.source
    assert git(engine, "cat-file", "-t", source["commit"]) == "commit"
    assert git(engine, "rev-parse", f"{source['commit']}:documentation") == source["tree"]


def test_gitattributes_keeps_the_snapshots_bytes_exact():
    attributes = (LIBRARY.root.parent.parent / ".gitattributes").read_text()
    assert "documentation/content/** -text" in attributes


def test_every_snapshot_image_is_a_diagram_in_the_manifest():
    assert set(LIBRARY.images) == set(diagrams.DIAGRAMS)
    for path, diagram in diagrams.DIAGRAMS.items():
        assert diagram.kind == "illustrative" and diagram.label == "Diagram"
        assert path in diagram.provenance
        with Image.open(LIBRARY.root / path) as picture:
            assert picture.size == diagram.source_size
        # Never drawn wider than half its pixels, so 2× screens never upscale it.
        for slot, display in diagram.display.items():
            assert display.sizes, slot
            for where, (width, height) in display.breakpoints.items():
                assert width * 2 <= diagram.source_size[0], (path, where)
                assert height * 2 <= diagram.source_size[1], (path, where)
        assert finders.find(f"docs/{path}"), f"{path} isn't served as a static file"


# ---------- Pages ----------


@pytest.mark.django_db
def test_every_listed_page_serves_its_title_and_description(client):
    failures = []
    for path in PAGE_PATHS:
        page = LIBRARY.page(path)
        response = client.get(page.url)
        html = response.content.decode()
        if response.status_code != 200:
            failures.append(f"{page.url}: {response.status_code}")
            continue
        if f"<title>{escape(page.title)} · Axcenity Docs</title>" not in html:
            failures.append(f"{page.url}: title")
        if f'<meta name="description" content="{escape(page.description)}">' not in html:
            failures.append(f"{page.url}: description")
    assert failures == []
    assert len(PAGE_PATHS) == len(LIBRARY.paths) == 236


def _hrefs(html: str) -> list[str]:
    return re.findall(r'<a [^>]*href="([^"]*)"', html)


def _ids(html: str) -> list[str]:
    return re.findall(r'\sid="([^"]+)"', html)


@pytest.mark.django_db
def test_every_internal_link_anchor_and_image_on_every_page_resolves(client):
    """Walks the served HTML: every /docs/ link is a page (and its #anchor an id there),
    every same-page #anchor is an id, every image is a static file, and nothing in the
    article leaves for anywhere but https or mailto."""
    pages = {path: client.get(LIBRARY.page(path).url).content.decode() for path in PAGE_PATHS}
    ids = {LIBRARY.page(path).url: set(_ids(html)) for path, html in pages.items()}
    failures = []
    for path, html in pages.items():
        url = LIBRARY.page(path).url
        assert len(_ids(html)) == len(set(_ids(html))), f"{url}: an id repeats"
        article = html.split('id="docs-article"', 1)[1].split('class="docs-provenance', 1)[0]
        for href in _hrefs(article):
            target, _, fragment = href.partition("#")
            target = target.split("?", 1)[0] or url
            if target.startswith("/docs/"):
                if target not in ids:
                    failures.append(f"{url}: {href} isn't a page")
                elif fragment and unquote(fragment) not in ids[target]:
                    failures.append(f"{url}: {href} has no such anchor")
            elif not target.startswith(("https://", "mailto:")):
                failures.append(f"{url}: {href} leaves the site unsafely")
        for src in re.findall(r'<img [^>]*src="([^"]+)"', article):
            if not finders.find(src.removeprefix("/static/")):
                failures.append(f"{url}: image {src} isn't served")
    assert failures == []


@pytest.mark.django_db
def test_pages_never_read_the_engine_repository(client, settings, tmp_path, monkeypatch):
    settings.AXCENITY_ENGINE_DIR = tmp_path / "nowhere"

    def no_subprocess(*args, **kwargs):
        raise AssertionError("a page ran a subprocess")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    library.library.cache_clear()
    try:
        for url in ("/docs/", "/docs/learn/scripting/", "/docs/api/classes/part/"):
            assert client.get(url).status_code == 200
    finally:
        library.library.cache_clear()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url", ["/docs/nope/", "/docs/readme/", "/docs/learn/", "/docs/../config/"]
)
def test_unknown_paths_are_404(client, url):
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_a_mixed_case_url_redirects_to_its_page(client):
    response = client.get("/docs/API/Classes/Part/")
    assert response.status_code == 301 and response["Location"] == "/docs/api/classes/part/"


@pytest.fixture
def scripting(client, db):
    return client.get("/docs/learn/scripting/").content.decode()


def test_the_sidebar_marks_the_current_page_and_opens_only_its_section(scripting):
    sidebar = scripting.split('id="docs-nav"', 1)[1].split("</nav>", 1)[0]
    assert '<a href="/docs/learn/scripting/" class="docs-link" aria-current="page">' in sidebar
    assert sidebar.count('aria-current="page"') == 1
    assert sidebar.count('<details class="docs-group" open>') == 1
    open_group = sidebar.split('<details class="docs-group" open>', 1)[1].split("</details>")[0]
    assert "Learn: Code" in open_group
    # Every section is there, every page linked.
    for section in LIBRARY.navigation.sections:
        assert escape(section.title) in sidebar
    assert sidebar.count('class="docs-link') == len(PAGE_PATHS)


def test_the_layout_needs_no_javascript(scripting):
    """The sidebar and its groups are <details> (open without a script), the article and
    rail are plain HTML; the copy button is added by docs.js only."""
    assert '<details id="docs-nav" class="docs-nav" open>' in scripting
    assert 'class="doc-copy' not in scripting
    assert "js/docs.js" in scripting


def test_breadcrumbs_title_lede_and_neighbours(scripting):
    crumbs = scripting.split('class="docs-crumbs"', 1)[1].split("</nav>", 1)[0]
    assert '<a href="/docs/">Docs</a>' in crumbs and "<span>Learn: Code</span>" in crumbs
    assert '<span aria-current="page">Scripting and the API</span>' in crumbs
    assert '<h1 id="docs-title"' in scripting
    page = LIBRARY.page("learn/scripting.md")
    assert escape(page.description) in scripting.split('class="docs-lede', 1)[1][:400]
    assert f'href="{LIBRARY.page(page.previous.path).url}" rel="prev"' in scripting
    assert '<a href="/docs/learn/blocks/" rel="next"' in scripting


@pytest.mark.django_db
def test_a_nested_pages_breadcrumbs_dont_repeat_its_section(client):
    html = client.get("/docs/api/classes/part/").content.decode()
    crumbs = html.split('class="docs-crumbs"', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r">([^<>]+)</(?:a|span)>", crumbs) == [
        "Docs",
        "API reference",
        "Classes",
        "Part",
    ]


def test_on_this_page_lists_the_h2_and_h3_headings(scripting):
    page = LIBRARY.page("learn/scripting.md")
    rail = scripting.split('id="docs-outline"', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'href="#([^"]+)"', rail) == [h.id for h in page.rendered.outline]
    for heading in page.rendered.outline:
        assert f'id="{heading.id}"' in scripting
        assert f'class="doc-anchor" href="#{heading.id}"' in scripting


@pytest.mark.django_db
def test_every_page_shows_the_alpha_notice_and_its_source_at_the_snapshot_commit(client):
    commit = LIBRARY.source["commit"]
    for path in PAGE_PATHS:
        page = LIBRARY.page(path)
        html = client.get(page.url).content.decode()
        assert "Alpha · v0.3.0-alpha.1" in html and 'class="badge-dot"' in html, path
        source = f"{sync.ENGINE_REPO_URL}/blob/{commit}/documentation/{path}"
        assert f'<a id="docs-source" href="{source}" rel="noopener"' in html, path
        # Provenance in the docs footer: the commit and its date.
        footer = html.split('class="docs-provenance', 1)[1]
        assert commit[:12] in footer and f'datetime="{LIBRARY.source["committed"]}"' in footer


@pytest.mark.django_db
def test_status_badges_come_from_the_front_matter(client):
    partial = [p for p in PAGE_PATHS if LIBRARY.page(p).rendered.meta.status]
    assert partial, "the snapshot has no page with a status"
    for path in partial:
        html = client.get(LIBRARY.page(path).url).content.decode()
        assert (
            '<span class="docs-status micro"><span class="sr-only">Status: </span>Partly built</span>'
            in html
        )
    stable = client.get("/docs/learn/scripting/").content.decode()
    assert "docs-status" not in stable


def test_samples_show_as_try_it_in_the_editor(scripting):
    samples = scripting.split('class="docs-samples', 1)[1].split("</aside>", 1)[0]
    assert "Try it in the editor" in samples
    for name in LIBRARY.page("learn/scripting.md").rendered.meta.samples:
        assert f"<code>{name}</code>" in samples


@pytest.mark.django_db
def test_diagrams_are_captioned_diagram_with_their_alt_text(client):
    html = client.get("/docs/learn/scripting/").content.decode()
    figure = html.split('<figure class="doc-figure">', 1)[1].split("</figure>", 1)[0]
    assert '<span class="doc-caption-label micro">Diagram</span>' in figure
    assert "Client-server scripting model" in figure
    assert 'width="1200" height="620"' in figure


@pytest.mark.django_db
def test_the_landing_page_shows_the_readme_and_a_panel_per_section(client):
    html = client.get("/docs/").content.decode()
    assert "<title>Axcenity Engine documentation · Axcenity Docs</title>" in html
    titled = [s for s in LIBRARY.navigation.sections if s.title]
    panels = re.findall(r'<section class="panel docs-panel"[^>]*>\s*<h3[^>]*>([^<]+)</h3>', html)
    assert panels == [escape(s.title) for s in titled]
    # Two levels of each section: the API's top pages, not its every class.
    assert 'href="/docs/api/classes/"' in html.split('id="docs-sections"', 1)[1]
    assert 'href="/docs/api/classes/part/"' not in html.split('id="docs-sections"', 1)[1]


# ---------- Site links ----------


@pytest.mark.django_db
def test_the_nav_marks_docs_current_on_every_docs_page(client):
    for url in ("/docs/", "/docs/learn/scripting/"):
        nav = client.get(url).content.decode().split('id="site-nav"', 1)[1].split("</header>")[0]
        assert '<a href="/docs/" class="nav-link" aria-current="page">Docs</a>' in nav
    home = client.get("/").content.decode().split('id="site-nav"', 1)[1].split("</header>")[0]
    assert '<a href="/docs/" class="nav-link">Docs</a>' in home


@pytest.mark.django_db
def test_the_home_and_footer_send_readers_to_the_docs(client):
    home = client.get("/").content.decode()
    assert '<a href="/docs/" class="btn btn-quiet">Read the docs</a>' in home
    footer = home.split('id="site-footer"', 1)[1]
    assert '<a href="/docs/" class="footer-link">Docs</a>' in footer
    assert (
        '<a href="/docs/learn/getting-started/" class="footer-link">Getting started</a>' in footer
    )
    assert "github.com/Axcenity-Studios/Axcenity-Engine/tree/main/documentation" not in home


# ---------- sync_engine_docs, the command ----------


def test_the_command_refuses_a_snapshot_that_fails_the_build_check(engine, tmp_path):
    """The fake docs' diagram isn't in the manifest, so the check stops the sync."""
    dest = tmp_path / "content"
    with override_settings(DOCS_SNAPSHOT_DIR=dest):
        with pytest.raises(CommandError, match="not in the diagram manifest"):
            call_command("sync_engine_docs", engine=engine)
    assert not dest.exists()


def test_the_command_syncs_and_then_reports_nothing_changed(engine, tmp_path, capsys):
    docs = engine / "documentation"
    (docs / "images" / "diagram.png").unlink()
    (docs / "learn" / "start.md").write_text("---\ndescription: Start here.\n---\n\n# Start\n")
    commit = commit_all(engine, "No diagram")
    dest = tmp_path / "content"
    with override_settings(DOCS_SNAPSHOT_DIR=dest):
        call_command("sync_engine_docs", engine=engine)
        call_command("sync_engine_docs", engine=engine)
    output = capsys.readouterr().out
    assert f"Synced 3 files from {commit[:12]}" in output
    assert f"Already current at {commit[:12]}: nothing changed." in output
    library.library.cache_clear()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url", "path"),
    [
        ("/docs/", "README.md"),
        ("/docs/learn/scripting/", "learn/scripting.md"),
        ("/docs/api/classes/part/", "api/classes/Part.md"),
    ],
)
def test_every_id_around_the_article_is_reserved_from_headings(client, url, path):
    """A heading can never take an id the page's own chrome uses."""
    html = client.get(url).content.decode()
    headings = {heading.id for heading in LIBRARY.page(path).rendered.headings}
    chrome = set(_ids(html)) - headings
    assert chrome <= LIBRARY.reserved_ids, sorted(chrome - LIBRARY.reserved_ids)
    assert not headings & LIBRARY.reserved_ids
