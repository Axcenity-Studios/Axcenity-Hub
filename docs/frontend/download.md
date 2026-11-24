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
| `marketing/content.py` | `DOWNLOAD_PAGE` (every word of the page's frame) and `DOWNLOAD_BUILDS` (the kinds of file a release carries, with their labels, hints and commands) |
| `templates/marketing/download.html` | The page; `download/build.html` is one file |
| `tests/fixtures/github/releases.json` | The real release list (v0.3.0-alpha.1, v0.2.0-alpha.1, v0.1.0-alpha.3), trimmed to the fields the Hub reads |

## Choosing the release

`select_release(payload)` takes the release with the latest
`published_at` that isn't a draft, whatever order GitHub lists them in.
Prereleases count (every engine release so far is one) and are marked
**Alpha** (`Release.is_alpha`); a stable release counts too and isn't
marked. The list endpoint is used, never `/releases/latest`: that one
skips prereleases, so it 404s today.

GitHub's reply is untrusted input. An entry is skipped when it's a draft,
has no tag, or has a `published_at` that isn't an ISO time with a zone.
A file is dropped unless:
- its name is text with no `/`
- its size is a whole number of bytes
- its download URL is `https://github.com/Axcenity-Studios/Axcenity-Engine/releases/download/…`
  with no query, no fragment and no `..`

The release's page link follows the same rule under `/releases/tag/`.
A digest is shown only as `sha256:` and 64 lower-case hex digits; any
other file says to use `SHA256SUMS.txt`. Templates escape everything.

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

## The cache and GitHub's failures

`current_release(now=None)` returns an `Offer`: its `state`, the
`release` and `fetched_at`. It keeps GitHub's answer in Django's cache
(`CACHE_KEY`) along with the list's ETag:

1. If the list was fetched or confirmed less than `FRESH_FOR` (an hour)
   ago, it's served with no request ("live").
2. Otherwise GitHub is asked again, with `If-None-Match: <the stored
   ETag>`. A **304** keeps the cached list and makes it fresh for another
   hour. A **200** replaces it.
3. A **failure** serves the cached list as "stale", with its
   `fetched_at`; with nothing cached, the state is "unavailable". Failures
   are a timeout, a connection error, a 5xx, a 403 or 429 rate limit, any
   other status, or a body that isn't JSON.
4. After a failure, GitHub isn't asked again until a backoff ends
   (`RETRY_KEY`). The wait is `Retry-After`, or the rate limit's reset
   when no requests remain, otherwise 5 minutes, kept between 1 minute
   and 1 hour. During an outage, page views don't each wait out a timeout
   or spend the 60 requests an hour GitHub allows without a token.

The list is kept for `KEEP_FOR` (7 days) as the fallback. A list with no
release to offer is cached too, and is "unavailable".

The page never fails because GitHub did. "Stale" adds a notice: "GitHub
didn't answer just now, so this is the release list as of <date, time>
UTC." "Unavailable" replaces the release with a panel, "The builds are on
GitHub.", whose one primary button is Open GitHub Releases.

**Production:** local-memory caching is per process, so each worker
keeps its own list and backoff. A shared cache (Phase 8) makes them one.

## Sections

`#overview` holds the eyebrow, "Download Axcenity Engine." (the only
`<h1>`) and the lede, then:
- the version badge (its dot is the accent's badge use), Alpha and the
  release date
- the release's title from GitHub, and the alpha note
- the button (above) and any stale notice

`#builds` ("Every build") has a panel per system (three columns from
1024 px, each sized to its own content), then Other files, then
Release notes on GitHub and All releases on GitHub. `#verify` ("Compare the checksum.")
lists the hash command for each system, and a line says where the data
comes from. Without a release, only `#overview` and its panel render.

## The `.dl-*` classes

Monochrome tokens only (`styles/source.css`). The panels use the
Toolbox's title-bar chips (`.tb-bar`, `.tb-chip-current`).

- `.dl-system`: a system's panel, with 1px of padding so the bar keeps
  the outline; `[data-detected]` outlines it in ink.
- `.dl-build`: one file. `.dl-builds-wide` lays Other files in three
  columns from 1024 px.
- `.dl-tag`: the Alpha and Your system tags.
- `.dl-file`: a file name (mono, wraps anywhere).
- `.dl-hash`: a SHA-256 (breaks anywhere).
- `.dl-command`: a command, scrolling inside its own box.
- `.dl-notice`: the stale notice.
- `.dl-verify`: the checksum commands.

Nothing scrolls the page sideways at 360 px.
