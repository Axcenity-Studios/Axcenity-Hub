# GitHub releases (`marketing/github.py`, `marketing/releases.py`)

How `/download/` gets the engine's newest release from GitHub and keeps
working when GitHub doesn't. The page itself is
[../frontend/download.md](../frontend/download.md); `tests/test_download.py`
enforces both.

`github.fetch_releases(etag, now)` is the one request: the engine's
release list (`per_page=10`), unauthenticated, with a fixed `User-Agent`,
a pinned API version, a timeout of (3.05, 5) s and `If-None-Match`. It
returns a `Fetched` ("ok", "not_modified" or "failed", with
`retry_after`) and never raises for an HTTP or network failure.

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

## New releases

Nothing on the page names a version: the release, its files and their
URLs all come from GitHub, and the build kinds match file names by
pattern (`-windows-x86_64.exe`), not by version. A newly published
release replaces the old one at the next check after the cached hour.
GitHub's list then has a new ETag, so it answers with a 200, not a 304.
A draft stays hidden until it's published. Revalidating more often than
hourly would only spend the 60 unauthenticated requests an hour.
