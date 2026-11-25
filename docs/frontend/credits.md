# Credits (`/credits/`)

`marketing:credits` (`CreditsView`) credits everyone whose work Axcenity
Engine and the Hub are built on. It's linked from the footer's Engine
column and from under the download agreement's LICENSE and NOTICE.
`tests/test_credits.py` and `test_credits_browser.py` enforce everything
below.

## What it shows

1. **NOTICE**: the engine's NOTICE file, set as prose by
   `legal.reflow` (the same partial as the download agreement,
   `templates/marketing/legal_blocks.html`), with a link to it on GitHub
   at `content.LEGAL_COMMIT`.
2. **Crates**: every Rust crate the engine's Cargo.lock resolves, for
   every system and with every optional feature on, grouped by licence in
   `<details>` (the most used licence open). A crate that names no
   authors is credited to "Its contributors"; the patched copy under the
   engine's `vendor/` is marked.
3. **Hub**: the Python packages in `uv.lock`, in two tables ("Runs the
   site": reachable from the project's dependencies; "Builds and tests
   it": the dev group's), then the fonts and stylesheet tools, which
   `content.CREDITS_PAGE` lists by hand (Tailwind's and daisyUI's
   versions come from `hub.json`).

Copy lives in `content.CREDITS_PAGE`. The page reads only committed
files: it never runs git or cargo.

## The generated lists

`marketing/credits.py` writes, and `content.py` reads:

| File | Holds |
|---|---|
| `marketing/legal/LICENSE`, `NOTICE` | The engine's, from its HEAD commit's objects, unchanged |
| `marketing/legal/engine.json` | `commit` (that HEAD, `content.LEGAL_COMMIT`), `crates` (name, version, licence, authors, url, `vendored`) and `unbuilt` (locked crates no build resolves) |
| `marketing/legal/hub.json` | `packages` (name, version, group, licence, authors, url) and `tools` (Tailwind CSS and daisyUI versions) |

Refresh them with:

```sh
uv run python manage.py refresh_credits                # from AXCENITY_ENGINE_DIR
uv run python manage.py refresh_credits --engine PATH  # another checkout
```

Run it after the engine's NOTICE or dependencies change, and after
`uv add` or `uv lock` here. It needs git and cargo, never the network,
and writes nothing in the engine. It refuses, changing nothing, when:
- LICENSE, NOTICE, Cargo.toml or Cargo.lock has uncommitted changes in
  the engine (an edit in progress isn't the engine's NOTICE yet);
- `cargo metadata --all-features --locked --offline` lists a crate HEAD's
  Cargo.lock doesn't, or a crate or package has no licence;
- a package isn't installed here (Windows-only ones) and has no entry in
  `credits.PACKAGE_FILLS`: add its licence, authors and home page from
  PyPI.

Licences get one spelling per choice (`license_label`: "MIT/Apache-2.0"
and "MIT OR Apache-2.0" are both "Apache-2.0 OR MIT"); a package whose
License field is a whole licence text falls back to its classifiers.
Authors are names only: email addresses are dropped.

**Automatic checks.** `test_every_package_in_the_hubs_lock_file_is_credited`
always runs; `test_every_crate_in_the_engines_lock_file_is_credited` and
`test_the_copied_license_and_notice_match_the_engines` run when the
engine is checked out, against its last commit. Each fails with "run
manage.py refresh_credits" until the lists catch up, so a new dependency
can't go uncredited.

## NOTICE dividers

`legal.reflow` reads a line of only `-`, `=`, `*` or `_` (three or more)
as a divider (`Block("rule")`, drawn as `hr.dl-legal-rule`) unless it
sits right under a paragraph's only line, where it underlines a heading.
So a new credit can be added to the engine's NOTICE after a `---`, with
or without a blank line, and it sets correctly here with no change to the
Hub.

## The `.cr-*` classes

Monochrome tokens only (`styles/source.css`), hovers behind
`html[data-pointer]`. `.cr-jump` (the section chips), `.cr-section`,
`.cr-head`, `.cr-notice` (the NOTICE, scrolling inside 36rem),
`.cr-group`/`.cr-summary`/`.cr-license` (a licence's `<details>`),
`.cr-list`/`.cr-item`/`.cr-name`/`.cr-version`/`.cr-by` (crates, in
15rem columns), `.cr-table` (packages; rows stack below 40rem) and
`.cr-assets` (fonts and tools). `.dl-credits` is the line under the
agreement's full texts.
