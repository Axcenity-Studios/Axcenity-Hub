"""One request to GitHub's REST API for the engine's release list.

No token: the list is public, and unauthenticated reads allow 60 requests an hour per IP,
which the hourly cache in marketing/releases.py keeps well under. Every outcome comes back
as a `Fetched`; this module never raises for an HTTP or network failure.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import requests

# The engine's canonical repository (its README's older account redirects here).
ENGINE_REPO = "Axcenity-Studios/Axcenity-Engine"
ENGINE_REPO_URL = f"https://github.com/{ENGINE_REPO}"
RELEASES_API_URL = f"https://api.github.com/repos/{ENGINE_REPO}/releases"
# GitHub rejects requests without a User-Agent; the API version is pinned.
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "axcenity-hub",
    "X-GitHub-Api-Version": "2022-11-28",
}
# (connect, read) seconds: a page view waits at most this long for GitHub.
TIMEOUT = (3.05, 5)
PER_PAGE = 10


@dataclass(frozen=True)
class Fetched:
    """What one request returned.

    `status` is "ok" (a 200 with a JSON body in `payload`), "not_modified" (a 304 to the
    ETag sent) or "failed" (anything else: a timeout, a connection error, a 4xx or 5xx, a
    body that isn't JSON). `retry_after` is how many seconds GitHub asked us to wait, when
    it said (Retry-After, or the rate-limit reset when none remain).
    """

    status: str
    payload: object = None
    etag: str = ""
    retry_after: int | None = None


def _retry_after(response: requests.Response, now: datetime) -> int | None:
    header = response.headers.get("Retry-After", "")
    if header.isdigit():
        return int(header)
    reset = response.headers.get("X-RateLimit-Reset", "")
    if response.headers.get("X-RateLimit-Remaining") == "0" and reset.isdigit():
        return max(0, int(reset) - int(now.timestamp()))
    return None


def fetch_releases(etag: str = "", now: datetime | None = None) -> Fetched:
    """Ask GitHub for the engine's newest releases, conditionally when `etag` is given.

    Sends `If-None-Match: <etag>` so an unchanged list comes back as a 304 with no body.
    Never raises for a network or HTTP failure: those return status "failed".
    """
    now = now or datetime.now(UTC)
    headers = {**HEADERS, **({"If-None-Match": etag} if etag else {})}
    try:
        response = requests.get(
            RELEASES_API_URL, params={"per_page": PER_PAGE}, headers=headers, timeout=TIMEOUT
        )
    except requests.RequestException:
        return Fetched("failed")
    if response.status_code == 304:
        return Fetched("not_modified", etag=response.headers.get("ETag", etag))
    if response.status_code != 200:
        return Fetched("failed", retry_after=_retry_after(response, now))
    try:
        payload = response.json()
    except ValueError:
        return Fetched("failed")
    return Fetched("ok", payload=payload, etag=response.headers.get("ETag", ""))
