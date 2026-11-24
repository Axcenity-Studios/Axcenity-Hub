# The documentation site (`/docs/`)

The `documentation` app serves the engine's guide and reference in the
marketing shell. The engine repository's `documentation/` folder is the
only source: the Hub serves a committed **snapshot** of it, never edits
its pages and never reads the engine or GitHub while serving.
`tests/test_documentation.py` and `tests/test_documentation_browser.py`
enforce everything here.

## Files

| Path | Holds |
|---|---|
| `documentation/content/` | The snapshot: `SUMMARY.md`, every page, `images/`, and `SOURCE.json` |
| `documentation/sync.py` | `sync()` and `tree_hash()`: copying the docs in from a commit |
| `documentation/navigation.py` | `parse_summary()`: SUMMARY.md's sections, nesting, reading order, `previous`/`next`, `trail`, `orphans` |
| `documentation/links.py` | `resolve()`: one link → its Hub URL or a reported problem; `page_slug`, `page_url`, `image_url` |
| `documentation/highlight.py` | `EditorLuauLexer` (Pygments) and `highlight()` |
| `documentation/rendering.py` | `render()`: front matter, Markdown, heading ids, links, code, tables, figures |
| `documentation/library.py` | `Library`: the snapshot as served (cached pages, `api_page`, `type_links`, `search_index`) and `check()`, the build check; `library()` |
| `documentation/api.py` | `parse()`: an API page as structure (`ApiPage`, `Member`); `page_kind()` |
| `documentation/search.py` | `build_index()`, `clean_query()`, `search()` (the ranking), `mark()` |
| `documentation/diagrams.py` | `DIAGRAMS`: the diagrams' media-manifest entries |
| `documentation/strings.py` | Every word around the pages (`DOCS`) |
| `templates/documentation/` | `layout.html`, `page.html`, `index.html`, `search.html`, `api/` and `partials/` |
| `static/js/docs.js` | The copy buttons, the sidebar's disclosure and the API home's filter (progressive) |

## Re-syncing

```sh
uv run python manage.py sync_engine_docs                 # from AXCENITY_ENGINE_DIR
uv run python manage.py sync_engine_docs --engine PATH   # another checkout
```

`AXCENITY_ENGINE_DIR` defaults to `~/Documents/VSCode Projects/Axcenity-Engine`.
Commit the changed `documentation/content/` with the code that needs it.
The sync is all or nothing:

1. It refuses uncommitted changes in the engine's `documentation/`
   (changes elsewhere in the engine don't matter), then resolves and
   verifies HEAD.
2. It reads the folder **from that commit's objects** (`git ls-tree`,
   `git cat-file`), never from the working tree. Only regular Markdown
   and raster image files (`.md`, `.png`, `.jpg`, `.webp`, `.gif`) with
   safe names are accepted. Symlinks, executables, SVG, HTML and anything
   else stop the sync.
3. It builds the new snapshot in a temporary folder beside the old one
   and writes `SOURCE.json`: repository, folder, commit, the folder's
   git tree hash, object format and commit date (never the sync's own
   time).
4. The copy must hash back to that tree (`tree_hash` recomputes git's
   object hashes: modes, name order, empty folders left out, sha1 or
   sha256). It must also pass `Library.check()`.
5. If the result is identical to the snapshot, nothing is touched.
   Otherwise two renames swap it in, and the old one is restored if the
   second fails.

Any failure leaves `documentation/content/` exactly as it was and no
temporary folders behind. `.gitattributes` marks the snapshot `-text`, so
no checkout rewrites its line endings, and a test recomputes its tree
hash against `SOURCE.json`. When the engine's checkout is on the machine,
a test also confirms that the commit exists and holds that tree.

**A new diagram** must be entered in `documentation/diagrams.py` (its
path and pixel size) before the sync will accept it. **A text fix** is
made in the engine, committed, then re-synced.

## The build check (`Library.check`)

Every page renders with a title (its `#` heading) and a front-matter
`description`. SUMMARY.md and the pages agree: no orphans, nothing
listed that's missing, nothing listed twice, and no two paths sharing a
lower-cased URL, and none takes `/docs/search/`. Every API page parses
(`api.ApiError` otherwise). Every link and image resolves, every `#anchor` names a
heading on its target page, every `status` is known, and every image is
a manifest diagram at its recorded size.

## URLs

A page's URL is its snapshot path, lower-cased, without `.md`
(`learn/scripting.md` → `/docs/learn/scripting/`). A `README.md` is its
folder: `/docs/` and `/docs/api/`. Views look the path up in the
snapshot's own index, so a URL can only ever name a page. Unknown paths
are 404s, and a mixed-case URL 301s to its page.

## Rendering: a security boundary

- markdown-it-py: CommonMark plus tables and strikethrough, **raw HTML
  off** (a `<tag>` shows as text; a raw-HTML token, should one appear,
  is escaped too).
- markdown-it's own link check is off, so that every link and image
  (autolinks included) reaches `links.resolve`, the one gate:
  - It keeps `#anchor`, and `https://host`, `http://host` and `mailto:`
    links byte for byte (`rel="noopener"` is added).
  - It rewrites relative page links (`../learn/blocks.md?x=1#events` →
    `/docs/learn/blocks/?x=1#events`) and image links (→
    `/static/docs/images/…`).
  - It refuses everything else: missing targets, paths that leave the
    snapshot, absolute and protocol-relative paths, other schemes, and
    whitespace, control characters or backslashes. Schemes are checked
    on every entity- and percent-decoded form of the link as well.
  - A refused link renders as its text, a refused image as its alt
    text, and each one is a problem the build check reports.
- **Front matter:** one `key: value` per line (GitBook accepts an
  unquoted description containing `: `; strict YAML doesn't). Quoted
  values and `[lists]` are read as YAML; any other line shape is an
  error. Reads `description`, `icon` (parsed, not shown: the Hub has no
  icons for GitBook's names), `status` and `samples`.
- **Headings:** the first `#` is the title and leaves the body. Every
  other heading gets a GitHub-style id (`slugify`: lower case,
  punctuation dropped, spaces as hyphens, which is what the docs'
  anchors use) and a `#` permalink. `HeadingIds` makes ids unique in
  order: a repeat takes the first free `-1`, `-2`… The ids the page
  around the article uses (`library.PAGE_IDS`) are taken from the
  start, so no heading can repeat them.
- **Code:** fenced `luau` and `lua` blocks are highlighted by
  `EditorLuauLexer`. It splits code exactly as the editor's script tab
  does (`crates/editor-kit/src/lua_syntax.rs`): its keywords, literals
  and 34 builtins (never after `.` or `:`, as in
  `marketing/drawings.py`), numbers, line-bounded quoted strings, and
  long-bracket strings and comments. Pygments' stock Luau lexer marks
  other words. Its tests are the editor's own cases. The pieces use the
  `.luau-*` rules ([theme.md](theme.md)) on `inset`. Other languages are
  escaped plain text. Each block is `.doc-code > pre[tabindex=0]`, and
  scrolls in its own box.
- **Tables** are wrapped in `.doc-table[role=region][tabindex=0]` and
  scroll in their own box. **Diagrams** standing alone in a paragraph
  become a `<figure>`: the PNG at its pixel size (`width`/`height`,
  lazy), then a "Diagram" label and the page's alt text.

## Layout

`layout.html` extends the marketing shell. `<title>` is
"Page · Axcenity Docs" and the meta description is the front matter's.

- **From 1024 px:** the sidebar (sticky, scrolling on its own) and the
  article (at most 46rem, about 70ch). **From 1280 px:** the "On this
  page" rail as well. Three columns at 1024 px would squeeze code and
  tables to about 450 px, so the rail waits.
- **Sidebar** (`partials/sidebar.html`, `nav_items.html` recursive): the
  search form, Overview (the README), then one `<details>` per guide
  section; only the current page's section and groups start open. The
  API reference is set apart below a rule (`views._api_section`): Overview,
  Classes, Data types, Enums, Libraries, Globals with page counts, and only
  the current class or type under its group. The current page is
  `aria-current` with an ink bar; `docs.js` scrolls it into view.
- **Below 1024 px** the same `<details>` is a disclosure at the top
  ("Browse the docs"). The script right after it closes it before first
  paint. Without JavaScript it stays open; with it, it follows the
  breakpoint.
- **Header** (`partials/header.html`): breadcrumbs (Docs / section /
  parents; a section named like its first page isn't repeated), the
  title, the description as the lede, the status badge ("Partly built"
  or "Experimental"), the Alpha badge (the hero's `badge-pill` and its
  accent dot), View source on GitHub (the file at the snapshot's
  commit), the Alpha sentence, and "Try it in the editor" with each
  sample's name.
- **After the article:** previous and next in reading order, then the
  docs footer: the commit (linked to the folder at that commit) and its
  date.
- **Landing** (`index.html`): the README as the article, then one panel
  per titled section listing its pages and their children, with
  descriptions (API reference shows Classes, Data types, Enums,
  Libraries and Globals, not every class).
- Without JavaScript the docs work in full. `docs.js` adds a Copy button
  to each `.doc-code`. It writes `code.textContent` to the clipboard and
  says "Copied"; its words come from the `.docs` element's `data-copy*`
  attributes.

## The nav and the rest of the site

Docs in the nav is `Link(url_name="documentation:index",
section="documentation")`, so it's `aria-current` on every `/docs/`
page. Home's "Read the docs", the footer's Docs and Getting started
(`content.GETTING_STARTED`) and the closing section point here. GitHub
stays one click away: each page's View source link and the footer's
GitHub link.

## The API reference (`/docs/api/…`)

`api.parse` reads the generated pages' fixed shape (see its docstring).
Anchors are the rendered headings' own ids, never recomputed. Kinds keep the
engine's words: Properties, Events, Functions. `views.API_TEMPLATES` picks:

- **Class, type, libraries, globals** (`api/members.html`): header, the lead
  (constructor and intro, `Rendered.lead`), a summary table per kind (name to
  its anchor, type or signature, first sentence), "Inherited from Instance"
  collapsed, then every member in full (`Rendered.body`). The rail lists the
  members by kind. Pages with no members (DataRow) show only their intro.
- **Enums** (`api/enums.html`): an anchored heading per enum, items as chips.
- **API home** (`api/home.html`): the README, then a panel each for Classes,
  Data types, Enums, Libraries and Globals. The filter is `hidden` in the
  markup; `docs.js` shows it and hides names (and empty panels) lacking any
  typed word, so without JavaScript everything is listed.
- **Type links:** a `luau` block right under a heading on an API page is a
  signature; its class, type and `EnumX` names (`highlight.type_names`, never
  an owner, member, string or comment) link to their pages, checked by build.

## Search (`/docs/search/?q=`)

`partials/search_form.html`: one field with its icon and an icon submit
button inside, its ring drawn inside (`:focus-within`) so the sidebar's
scroll box can't crop it. It tops the sidebar column; the results page
drops that one for a large one under its title (`search_in_article`). The index (`Library.search_index`, built
once per process) holds every page, guide heading and API member.
`clean_query` trims and collapses whitespace; empty or over 100 characters is a
message, never an error. Ranking: an exact name (title or full name before a
member's short name; `:` reads as `.`), then the words in a title, heading,
member name, description; within a rank, prefix matches then reading order.
One result per URL, 20 a page (Django's paginator; a bad page number falls
back), matched words in `<mark>`.
