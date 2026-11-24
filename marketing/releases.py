"""The engine's releases for /download/: which release to offer, its builds by system,
the visitor's system, and the cache that keeps GitHub's failures off the page.

GitHub's release list is untrusted input: every field is checked before use, and a file
whose download URL isn't one of the engine's release downloads is dropped.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from django.core.cache import cache

from marketing import github

CACHE_KEY = "marketing:releases:engine"
RETRY_KEY = "marketing:releases:engine:retry-at"
# A list younger than this is served without asking GitHub.
FRESH_FOR = timedelta(hours=1)
# How long the last list is kept as the fallback when GitHub fails.
KEEP_FOR = timedelta(days=7)
# After a failure, GitHub isn't asked again for its Retry-After (or rate-limit reset), or
# for DEFAULT_BACKOFF when it didn't say, within these bounds: a GitHub outage must not cost
# every page view a timeout, nor spend the hourly allowance.
DEFAULT_BACKOFF = timedelta(minutes=5)
MIN_BACKOFF = timedelta(minutes=1)
MAX_BACKOFF = timedelta(hours=1)

# Where the engine's files and release pages live on GitHub.
DOWNLOAD_PATH = f"/{github.ENGINE_REPO}/releases/download/"
RELEASE_PAGE_PATH = f"/{github.ENGINE_REPO}/releases/tag/"
SHA256 = re.compile(r"sha256:([0-9a-f]{64})")
# The systems /download/ groups builds under, in page order; "other" holds every other file.
SYSTEMS = ("windows", "macos", "linux", "other")
# The longest header value read when detecting the visitor's system.
MAX_HEADER = 512


@dataclass(frozen=True)
class Asset:
    """One file attached to a release."""

    name: str
    size: int
    url: str
    # The SHA-256 GitHub computed for the file, as 64 lower-case hex digits, or "".
    sha256: str = ""


@dataclass(frozen=True)
class Release:
    """The release /download/ offers."""

    tag: str
    title: str
    published_at: datetime
    prerelease: bool
    page_url: str
    assets: tuple[Asset, ...] = ()

    @property
    def is_alpha(self) -> bool:
        """Prereleases are marked alpha."""
        return self.prerelease


@dataclass(frozen=True)
class Offer:
    """What /download/ can show right now.

    `state` is "live" (fresh from GitHub, or confirmed unchanged within the hour), "stale"
    (GitHub failed, so this is the last list it gave, from `fetched_at`) or "unavailable"
    (nothing to show: the page links to GitHub Releases instead).
    """

    state: str
    release: Release | None = None
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class BuildKind:
    """A kind of file the engine's releases carry, recognised by its name.

    An editor build is `AxcenityEditor-<version><tail>` (`-windows-x86_64.exe`); any other
    known file has an exact `name` (`SHA256SUMS.txt`). `command` may contain `{file}`, the
    file's name. The `primary` kind is the one button offered for its system. `icon` names
    a line icon in templates/partials/icon.html.
    """

    system: str
    label: str
    hint: str = ""
    command: str = ""
    tail: str = ""
    name: str = ""
    primary: bool = False
    icon: str = "file"

    def __post_init__(self) -> None:
        if self.system not in SYSTEMS:
            raise ValueError(f"{self.label}: unknown system {self.system!r}")
        if bool(self.tail) == bool(self.name):
            raise ValueError(f"{self.label}: give exactly one of tail or name")

    def matches(self, filename: str) -> bool:
        if self.name:
            return filename == self.name
        return filename.startswith("AxcenityEditor-") and filename.endswith(self.tail)


@dataclass(frozen=True)
class Build:
    """A release file with what it is (None for a file no kind recognises)."""

    asset: Asset
    kind: BuildKind | None = None

    @property
    def command(self) -> str:
        return self.kind.command.replace("{file}", self.asset.name) if self.kind else ""

    @property
    def icon(self) -> str:
        """The kind's icon; a file no kind recognises is a plain file."""
        return self.kind.icon if self.kind else "file"


@dataclass(frozen=True)
class SystemGroup:
    """One system's builds, in the order of the kinds that matched them."""

    system: str
    builds: tuple[Build, ...]
    detected: bool = False

    @property
    def primary(self) -> Build | None:
        """The build to offer first: its primary kind's, else the first."""
        if self.system == "other":
            return None
        chosen = [build for build in self.builds if build.kind and build.kind.primary]
        return (chosen or list(self.builds) or [None])[0]


# ---------- Reading GitHub's list ----------


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _github_url(value: object, path_prefix: str) -> str:
    """`value` when it's an https URL on github.com under `path_prefix`, else ""."""
    if not isinstance(value, str):
        return ""
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.netloc != "github.com" or parts.query or parts.fragment:
        return ""
    if not parts.path.startswith(path_prefix) or ".." in parts.path:
        return ""
    return value


def _parse_asset(entry: object) -> Asset | None:
    """One file, or None when its name, size or download URL can't be trusted."""
    if not isinstance(entry, dict):
        return None
    name, size = entry.get("name"), entry.get("size")
    url = _github_url(entry.get("browser_download_url"), DOWNLOAD_PATH)
    if not (isinstance(name, str) and name and "/" not in name and url):
        return None
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        return None
    digest = entry.get("digest")
    match = SHA256.fullmatch(digest) if isinstance(digest, str) else None
    return Asset(name=name, size=size, url=url, sha256=match.group(1) if match else "")


def _parse_release(entry: object) -> Release | None:
    """One entry of the list as a Release, or None when it's a draft or malformed."""
    if not isinstance(entry, dict) or entry.get("draft") is not False:
        return None
    tag, title = entry.get("tag_name"), entry.get("name")
    published_at = _parse_time(entry.get("published_at"))
    if not (isinstance(tag, str) and tag and published_at):
        return None
    assets = entry.get("assets")
    return Release(
        tag=tag,
        title=title if isinstance(title, str) and title else tag,
        published_at=published_at,
        prerelease=entry.get("prerelease") is True,
        page_url=_github_url(entry.get("html_url"), RELEASE_PAGE_PATH),
        assets=tuple(
            asset
            for item in (assets if isinstance(assets, list) else [])
            if (asset := _parse_asset(item))
        ),
    )


def select_release(payload: object) -> Release | None:
    """Pick the newest published, non-draft release from GitHub's release list.

    "Newest" is the latest `published_at`, whatever order the list is in. Prereleases are
    included (and marked alpha); drafts and malformed entries are skipped. None when no
    release qualifies.
    """
    if not isinstance(payload, list):
        return None
    candidates = [release for entry in payload if (release := _parse_release(entry))]
    return max(candidates, key=lambda release: release.published_at, default=None)


def find_asset(release: Release | None, name: object) -> Asset | None:
    """The release's file called exactly `name`, or None (no release, or no such file).

    This is how a download request names its file: by name only, so the URL it ends up at
    is always the one GitHub gave for this release, never one from the request.
    """
    if release is None or not isinstance(name, str):
        return None
    return next((asset for asset in release.assets if asset.name == name), None)


# ---------- Builds by system ----------


def group_builds(release: Release, kinds: list[BuildKind], detected: str = "") -> list[SystemGroup]:
    """The release's files grouped by system, in `SYSTEMS` order, empty systems left out.

    Each file goes to the first kind that recognises it (in `kinds` order), and a file no
    kind recognises goes to "other", so every file stays reachable. The `detected` system's
    group is marked.
    """
    builds: dict[str, list[tuple[int, Build]]] = {system: [] for system in SYSTEMS}
    for asset in release.assets:
        index, kind = next(
            ((i, kind) for i, kind in enumerate(kinds) if kind.matches(asset.name)),
            (len(kinds), None),
        )
        builds[kind.system if kind else "other"].append((index, Build(asset, kind)))
    return [
        SystemGroup(
            system,
            tuple(build for _, build in sorted(found, key=lambda pair: pair[0])),
            detected=system == detected,
        )
        for system, found in builds.items()
        if found
    ]


def detect_system(user_agent: str = "", platform_hint: str = "") -> str:
    """The visitor's desktop system ("windows", "macos", "linux"), or "" when unknown.

    `platform_hint` is the `Sec-CH-UA-Platform` client hint (`"Windows"`, quoted), which
    Chromium browsers send; it wins when present. Otherwise the User-Agent decides. Phones,
    tablets and ChromeOS are "" (the engine has no build for them), even though Android's
    User-Agent says Linux and an iPhone's says "like Mac OS X".
    """
    hint = platform_hint[:MAX_HEADER].strip().strip('"').lower()
    if hint:
        return {"windows": "windows", "macos": "macos", "linux": "linux"}.get(hint, "")
    agent = user_agent[:MAX_HEADER]
    if any(word in agent for word in ("Android", "CrOS", "iPhone", "iPad", "iPod")):
        return ""
    if "Windows" in agent:
        return "windows"
    if "Macintosh" in agent or "Mac OS X" in agent:
        return "macos"
    if "Linux" in agent or "X11" in agent:
        return "linux"
    return ""


# ---------- The cache and GitHub's failures ----------


def _back_off(now: datetime, retry_after: int | None) -> None:
    wait = timedelta(seconds=retry_after) if retry_after is not None else DEFAULT_BACKOFF
    wait = min(max(wait, MIN_BACKOFF), MAX_BACKOFF)
    cache.set(RETRY_KEY, now + wait, wait.total_seconds())


def _live(release: Release | None, fetched_at: datetime) -> Offer:
    """GitHub's current answer: a release to offer, or (a list with none) nothing."""
    return Offer("live", release, fetched_at) if release else Offer("unavailable")


def _fallback(cached: dict | None) -> Offer:
    if cached and cached["release"]:
        return Offer("stale", cached["release"], cached["fetched_at"])
    return Offer("unavailable")


def current_release(now: datetime | None = None) -> Offer:
    """The release to offer, from the cache or GitHub, falling back when GitHub fails.

    A list fetched (or confirmed unchanged) within the last hour is served without asking
    GitHub. Otherwise GitHub is asked again, sending the cached list's ETag; a 304 keeps
    the cached list, fresh for another hour. If GitHub fails (a timeout, a 5xx, a 403 or
    429 rate limit, anything but a 200 or 304), the last list it gave is served as "stale",
    and with none cached the offer is "unavailable"; GitHub isn't asked again until its
    backoff ends. Never raises for a GitHub failure.
    """
    now = now or datetime.now(UTC)
    cached = cache.get(CACHE_KEY)
    if cached and now - cached["fetched_at"] < FRESH_FOR:
        return _live(cached["release"], cached["fetched_at"])
    retry_at = cache.get(RETRY_KEY)
    if retry_at and now < retry_at:
        return _fallback(cached)

    fetched = github.fetch_releases(etag=cached["etag"] if cached else "", now=now)
    if fetched.status == "not_modified" and cached:
        # Unchanged since the cached list: keep it, fresh for another hour.
        cache.set(CACHE_KEY, {**cached, "fetched_at": now}, KEEP_FOR.total_seconds())
        return _live(cached["release"], now)
    if fetched.status == "ok":
        release = select_release(fetched.payload)
        cache.set(
            CACHE_KEY,
            {"release": release, "etag": fetched.etag, "fetched_at": now},
            KEEP_FOR.total_seconds(),
        )
        return _live(release, now)
    _back_off(now, fetched.retry_after)
    return _fallback(cached)
