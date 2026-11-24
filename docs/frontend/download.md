# The download page (`/download/`)

`marketing:download` (`DownloadView`) offers the engine's newest release,
read from GitHub's REST API, with its builds grouped by system. Every
Download link on the site (the nav's button, Home's two "Download alpha"
buttons, the footer) points here. `tests/test_download.py` enforces
everything below.

## Files

| Path | Holds |
|---|---|
| `marketing/github.py` | `fetch_releases(etag, now)`: one request for the release list. Returns a `Fetched` ("ok", "not_modified" or "failed", with `retry_after`); never raises for an HTTP or network failure. `ENGINE_REPO`, `ENGINE_REPO_URL`, `RELEASES_API_URL` |
| `marketing/releases.py` | `select_release`, `group_builds`, `detect_system`, `current_release` (below), and their dataclasses: `Release`, `Asset`, `Offer`, `BuildKind`, `Build`, `SystemGroup` |
| `marketing/content.py` | `DOWNLOAD_PAGE` (every word of the page's frame), `DOWNLOAD_BUILDS` (the kinds of file a release carries, with their labels, hints, commands and icons) and `DOWNLOAD_SYSTEM_ICONS` |
| `templates/partials/icon.html` | The systems' icons (`windows`, `macos`, `linux`, `files`) and the files' (`installer`, `disk`, `app`, `package`, `archive`, `hash`, `manifest`, `key`, `history`, `file`) |
| `templates/marketing/download.html` | The page; `download/panel.html` is a system's panel, `download/build.html` one file, `download/agreement.html` the license agreement (also `download_agree.html`, its page) |
| `marketing/legal/LICENSE`, `NOTICE` | The engine's, copied in unchanged, shown in full in the agreement |
| `tests/fixtures/github/releases.json` | The real release list (v0.3.0-alpha.1, v0.2.0-alpha.1, v0.1.0-alpha.3), trimmed to the fields the Hub reads |

How the release is chosen and validated, the cache, the ETag, the
fallbacks and the backoff are in
[../architecture/github-releases.md](../architecture/github-releases.md).

## Builds by system

`group_builds(release, DOWNLOAD_BUILDS, detected)` returns the systems
in page order, Windows, macOS, Linux, then Other files, and leaves out
any system with no files. Each file goes to the first `BuildKind` that
recognises it. An editor build is `AxcenityEditor-<version><tail>`; any
other known file has an exact `name`. A file nothing recognises goes to
Other files under its own name, so every file stays reachable.

| System | Files (in order) | Main build |
|---|---|---|
| Windows | `-windows-x86_64.exe` | the setup wizard |
| macOS | `-macos-universal.dmg` | the disk image |
| Linux | `.AppImage`, `.deb`, `.rpm`, `.pkg.tar.zst`, `.tar.gz` (all `-linux-x86_64`) | the AppImage: it runs on any distribution without installing |
| Other files | the `-update.zip`, `SHA256SUMS.txt`, `axcenity-release.json`, its `.minisig`, `axcenity-history.json` | none |

The labels, hints and commands are the engine's own release notes
(`packaging/release-notes.md.tpl` in the engine repository). A command's
`{file}` becomes the file's name (`sudo apt install ./AxcenityEditor-…deb`).

## Icons

Each system and each kind of file has a line icon, in the style of the
site's other icons: 24 px grid, 1.6 stroke, `currentColor`, `aria-hidden`.
The system icons are drawn for the Hub: a four-pane window, an apple and
a penguin, not the systems' trademarked logos. They appear in each
panel's title chip and in the "Download for <system>" button.

Each file card leads with its kind's icon (`BuildKind.icon`) in a small
inset tile: installer, disk, app (AppImage), package (`.deb`, `.rpm`,
Arch), archive (`.tar.gz`, the updater zip), hash (checksums), manifest,
key (its signature), history, and file for anything unrecognised.

Every icon on the page is a **motif** (`class="motif dl-motif"`), like
Home's workflow icons ([home.md](home.md), Motifs). It draws in each time
it comes into view, with `shell.js` setting `data-on`, and one part makes
a single move:
- the panes draw in; the apple's stem rises; the penguin blinks
- the installer's arrow drops; the disk's light and the app's play
  triangle pop; the package and the archive's lid drop
- the manifest's tick rises; the key turns; the clock rewinds; the front
  sheet of Other files rises

Cards stagger by their place in the panel (`--stagger`). `.dl-motif`
keeps the icon in its container's colour. Without JavaScript, or under
reduced motion, the icons are simply drawn. On hover (behind the hover
gate), a card's icon tile turns ink.

## The visitor's system

`detect_system(user_agent, platform_hint)` reads the `Sec-CH-UA-Platform`
client hint first (Chromium sends it), then the User-Agent, and reads at
most 512 characters of either. It returns "windows", "macos", "linux" or
"" when unknown. Android, ChromeOS, iPhone and iPad all count as unknown,
although Android's User-Agent says Linux and an iPhone's says "like Mac
OS X". The response varies on both headers.

- **Known:** the hero's primary button is "Download for <system>", linking
  to that system's main build, with the file name and size under it. Other
  systems (`#builds`) is a quiet button, and the system's panel is
  outlined in ink and tagged "Your system".
- **Unknown:** the one primary button is "Choose your build" (`#builds`),
  with a line asking the visitor to pick. Nothing is highlighted.

## Sections

`#overview` holds the eyebrow, "Download Axcenity Engine." (the only
`<h1>`) and the lede, then:
- the version badge (its dot is the accent's badge use), Alpha and the
  release date
- the release's title from GitHub, and the alpha note
- the button (above) and any stale notice

`#builds` ("Every build") has a panel per system
(`download/panel.html`, built by `DownloadView._panel`):
- From 1024 px, single-build systems (Windows, macOS) share a row, and a
  system with several builds (Linux) spans the row with its builds three
  to a row (`DOWNLOAD_COLUMNS`). Panels in a row share its height.
- When a wide panel's last row isn't full, its **tip card**
  (`DOWNLOAD_PAGE["tips"]`) fills the gap, spanning one or two columns:
  - Linux: "Not sure which?", pointing at the AppImage
  - Other files: "Check your download", linking to `#verify`

  A system with no tip copy leaves the gap.
- Other files follows, then Release notes on GitHub and All releases on
  GitHub.

`#verify` has two columns from 1024 px:
- "Compare the checksum.": the hash command for each system
- `#source`, "Or build it yourself." (`DOWNLOAD_PAGE["from_source"]`):
  a terminal with clone, `cd` and `cargo run -p axcenity-editor`, the
  platform note, then Getting started and System requirements. The
  command and the note are the engine's getting-started guide, word for
  word (tested against the docs snapshot).

A line under both says where the data comes from. Without a release,
only `#overview` and its panel render.

## The license agreement

Every Download link (the button and each file's) goes through the
agreement. A link is `/download/agree/?file=<name>` with `data-download`.

- **With JavaScript:** `static/js/download.js` opens it as a modal
  `<dialog>` instead. The dialog names the file, and "Agree and download"
  stays disabled until the box is ticked. Escape, Cancel or a click on
  the backdrop closes it. A modified click (new tab) goes to the page.
  While it's open the page behind doesn't scroll
  (`html:has(.dl-dialog[open])`), and the dialog and the license pane
  keep their scrolling to themselves (`overscroll-behavior: contain`).
- **Without JavaScript:** `DownloadAgreeView` serves the same terms and
  form as a page.

Both POST the file's name (never a URL) with CSRF and `agree=yes`. The
server checks the box again (400 with an alert if it isn't ticked), then
redirects with a 303 to that file's download in the current release, so
the page stays put while the browser downloads. A file that isn't in the
current release, or no release at all, is a 404.

The terms (`DOWNLOAD_PAGE["agreement"]`) are the engine's own words: its
README's "License and trademark" section (the Apache License 2.0, your
games, forks, the pending word marks), plus a pointer to the LICENSE's
section 7 (no warranty). `test_the_terms_are_the_engines_own_words`
checks them against the engine's checkout when it's on the machine.
Change them in the engine first.

Beside the terms, a pane shows the engine's **LICENSE and NOTICE in
full**, so nobody has to leave for GitHub to read them. It sits on the
right from 1024 px and scrolls inside a frame as tall as the terms;
below that, it stacks under the form at 26rem. Its LICENSE and NOTICE tabs are radio
buttons whose labels are the chips, and `:has()` shows the chosen text,
so they work without JavaScript. The texts are copies in
`marketing/legal/` (`content.ENGINE_LICENSE`, `ENGINE_NOTICE`), taken
unchanged from the engine at `content.LEGAL_COMMIT`.

The files are hard-wrapped at about 75 columns, so they're set as prose
(`.dl-legal`) rather than shown raw. `marketing/legal.py`'s `reflow`
joins each paragraph's lines and keeps what the layout meant:
- headings: underlined, all-capitals, "1. Definitions." or APPENDIX
- numbered section titles in bold ("4. Redistribution.")
- indented definitions and (a)–(d) items
- the centred title block

A test checks that every word of each file is shown, in order.
`test_the_copied_license_and_notice_match_the_engines` fails when the
engine's copies change: copy them in again.

## The `.dl-*` classes

Monochrome tokens only (`styles/source.css`). The panels use the
Toolbox's title-bar chips (`.tb-bar`, `.tb-chip-current`).

- `.dl-system`: a system's panel, a column with 1px of padding so the
  bar keeps the outline; `[data-detected]` outlines it in ink.
  `.dl-system-name` spaces the chip's icon.
- `.dl-build`: one file card, a column. `.dl-build-head` holds the icon
  tile (`.dl-build-icon`), label and size. `.dl-build-foot` holds the
  SHA-256 and the button and is pushed to the bottom, so the buttons line
  up across a row, and across Windows and macOS, which share a row's
  height. `.dl-builds-wide` lays a full-width panel's
  files (Linux, Other files) in three columns from 1024 px.
- `.dl-tip`: a tip card on the surface colour; `.dl-motif`: an icon in
  its container's colour.
- `.dl-dialog`, `.dl-agreement`, `.dl-terms`, `.dl-agree`, `.dl-fulltext*`, `.dl-tab*`: the agreement.
- `.dl-tag`: the Alpha and Your system tags.
- `.dl-file`: a file name (mono, wraps anywhere).
- `.dl-hash`: a SHA-256 (breaks anywhere).
- `.dl-command`: a command, wrapping inside its own box.
- `.dl-notice`: the stale notice.
- `.dl-verify`: the checksum commands.

Nothing scrolls the page sideways at 360 px.
