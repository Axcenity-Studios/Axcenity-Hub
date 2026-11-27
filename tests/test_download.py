"""The download page (/download/): choosing the release, its builds by system, GitHub's
failures and the cache. GitHub is mocked with `responses`, from a real release list
trimmed to the fields the Hub reads (tests/fixtures/github/releases.json)."""

import copy
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import quote

import pytest
import requests
import responses
from django.conf import settings
from django.core.cache import cache
from django.template.defaultfilters import filesizeformat
from django.test import Client
from django.urls import resolve, reverse
from django.utils.html import escape

from marketing import content, github, legal, releases, views
from tests.test_home import _copy, _part_main, _visible

FIXTURE = Path(__file__).parent / "fixtures" / "github" / "releases.json"
PAYLOAD = json.loads(FIXTURE.read_text("utf-8"))
# The ETag GitHub sent with the real list.
ETAG = 'W/"eb8f5f8eb9ba978b2f0d2d0aa269e55c5ceeaaa673fa1c61f4a21ac58fbca438"'
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
LIST_URL = github.RELEASES_API_URL
DOWNLOAD_URL = (
    "https://github.com/Axcenity-Studios/Axcenity-Engine/releases/download/v0.3.0-alpha.1/"
)

# Each way GitHub can fail: the kwargs `responses` replies with.
FAILURES = {
    "500": {"status": 500, "json": {"message": "Server Error"}},
    "503": {"status": 503, "body": "unavailable"},
    "timeout": {"body": requests.Timeout("read timed out")},
    "403 rate limit": {
        "status": 403,
        "json": {"message": "API rate limit exceeded"},
        "headers": {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1795541421"},
    },
    "429": {
        "status": 429,
        "json": {"message": "Too Many Requests"},
        "headers": {"Retry-After": "60"},
    },
}


def _payload() -> list[dict]:
    """A fresh copy of the real release list (newest first: v0.3.0-alpha.1, v0.2.0, v0.1.0)."""
    return copy.deepcopy(PAYLOAD)


# ---------- Choosing the release ----------


def test_the_newest_non_draft_release_is_chosen_and_a_prerelease_is_marked_alpha():
    newest, middle, oldest = _payload()
    # A draft newer than everything is never offered, wherever the list puts it.
    draft = {**copy.deepcopy(newest), "tag_name": "v0.4.0-alpha.1", "draft": True}
    draft["published_at"] = "2026-11-23T10:00:00Z"
    chosen = releases.select_release([oldest, draft, middle, newest])
    assert chosen is not None
    assert chosen.tag == "v0.3.0-alpha.1"
    assert chosen.prerelease and chosen.is_alpha
    assert chosen.title == newest["name"]

    # A stable release is included too when it's the newest, and isn't marked alpha.
    stable = {**copy.deepcopy(middle), "tag_name": "v0.3.1", "prerelease": False}
    stable["published_at"] = "2026-11-22T09:00:00Z"
    chosen = releases.select_release([newest, stable, oldest])
    assert chosen.tag == "v0.3.1" and not chosen.is_alpha

    # Only drafts, or nothing at all: there's no release to offer.
    assert releases.select_release([draft]) is None
    assert releases.select_release([]) is None


# ---------- GitHub's failures and the cache ----------


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
@responses.activate
def test_a_failing_github_serves_the_cached_release_then_the_plain_link(failure):
    responses.get(LIST_URL, json=_payload(), headers={"ETag": ETAG})
    assert releases.current_release(now=NOW).state == "live"

    # Two hours later the cache needs checking, and GitHub fails: the last list is served.
    responses.replace(responses.GET, LIST_URL, **failure)
    later = NOW + timedelta(hours=2)
    offer = releases.current_release(now=later)
    assert offer.state == "stale"
    assert offer.release.tag == "v0.3.0-alpha.1"
    assert offer.fetched_at == NOW

    # With nothing cached, there's no release to show: the page falls back to GitHub's link.
    cache.clear()
    offer = releases.current_release(now=later)
    assert offer.state == "unavailable" and offer.release is None
    assert len(responses.calls) == 3


@responses.activate
def test_a_304_to_the_stored_etag_reuses_the_cached_release():
    responses.get(LIST_URL, json=_payload(), headers={"ETag": ETAG})
    releases.current_release(now=NOW)

    # GitHub answers 304 only to a request carrying the ETag it gave: the list hasn't changed.
    responses.replace(
        responses.GET,
        LIST_URL,
        status=304,
        headers={"ETag": ETAG},
        match=[responses.matchers.header_matcher({"If-None-Match": ETAG})],
    )
    later = NOW + timedelta(hours=2)
    offer = releases.current_release(now=later)
    assert responses.calls[1].request.headers.get("If-None-Match") == ETAG
    assert offer.state == "live"
    assert offer.release.tag == "v0.3.0-alpha.1"
    # Confirmed unchanged just now, so it's fresh for another hour: no request half an hour on.
    assert offer.fetched_at == later
    assert releases.current_release(now=later + timedelta(minutes=30)).state == "live"
    assert len(responses.calls) == 2


@responses.activate
def test_a_list_younger_than_an_hour_is_served_without_asking_github():
    responses.get(LIST_URL, json=_payload(), headers={"ETag": ETAG})
    releases.current_release(now=NOW)
    offer = releases.current_release(now=NOW + timedelta(minutes=59))
    assert offer.state == "live" and offer.fetched_at == NOW
    assert len(responses.calls) == 1


@responses.activate
def test_the_request_names_the_hub_pins_the_api_version_and_carries_no_credentials():
    responses.get(LIST_URL, json=_payload(), headers={"ETag": ETAG})
    releases.current_release(now=NOW)
    request = responses.calls[0].request
    assert request.url == f"{LIST_URL}?per_page=10"
    assert request.headers["User-Agent"] == "axcenity-hub"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert request.headers["Accept"] == "application/vnd.github+json"
    # The first request has no ETag to send, and the list is public: no token.
    assert "If-None-Match" not in request.headers and "Authorization" not in request.headers


@responses.activate
def test_after_a_failure_github_isnt_asked_again_until_the_backoff_ends():
    responses.get(LIST_URL, status=502)
    releases.current_release(now=NOW)
    assert releases.current_release(now=NOW + timedelta(minutes=4)).state == "unavailable"
    assert len(responses.calls) == 1
    releases.current_release(now=NOW + timedelta(minutes=5))
    assert len(responses.calls) == 2


@pytest.mark.parametrize(
    ("headers", "wait"),
    [
        ({"Retry-After": "120"}, timedelta(minutes=2)),
        # Too short a wait is raised to a minute, too long a one cut to an hour.
        ({"Retry-After": "1"}, timedelta(minutes=1)),
        ({"Retry-After": "86400"}, timedelta(hours=1)),
        # A spent rate limit waits for its reset.
        (
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(NOW.timestamp()) + 600)},
            timedelta(minutes=10),
        ),
    ],
)
@responses.activate
def test_the_backoff_follows_what_github_asked_for_within_bounds(headers, wait):
    responses.get(LIST_URL, status=429, headers=headers)
    releases.current_release(now=NOW)
    releases.current_release(now=NOW + wait - timedelta(seconds=1))
    assert len(responses.calls) == 1
    releases.current_release(now=NOW + wait)
    assert len(responses.calls) == 2


@pytest.mark.parametrize(
    "reply",
    [
        {"status": 200, "body": "<html>not json</html>"},
        {"status": 404, "json": {"message": "Not Found"}},
        {"status": 401, "json": {"message": "Bad credentials"}},
        {"body": requests.ConnectionError("refused")},
    ],
    ids=["not json", "404", "401", "connection error"],
)
@responses.activate
def test_any_other_failure_falls_back_too(reply):
    responses.get(LIST_URL, **reply)
    assert releases.current_release(now=NOW) == releases.Offer("unavailable")


@responses.activate
def test_a_list_with_nothing_to_offer_is_unavailable_and_cached():
    responses.get(LIST_URL, json=[{**PAYLOAD[0], "draft": True}], headers={"ETag": ETAG})
    assert releases.current_release(now=NOW).state == "unavailable"
    assert releases.current_release(now=NOW + timedelta(minutes=10)).state == "unavailable"
    assert len(responses.calls) == 1


def test_an_unmocked_request_fails_the_test_instead_of_being_swallowed():
    """No test reaches the network: the guard's error escapes the client's failure handling."""
    from tests.conftest import NetworkBlockedError

    with pytest.raises(NetworkBlockedError):
        releases.current_release(now=NOW)


# ---------- Reading the release ----------


def _release(payload=None) -> releases.Release:
    return releases.select_release(payload if payload is not None else _payload())


def test_the_real_release_is_read_with_its_page_files_sizes_and_digests():
    release = _release()
    assert release.page_url == PAYLOAD[0]["html_url"]
    assert release.published_at == datetime(2026, 11, 21, 19, 38, 44, tzinfo=UTC)
    assert [asset.name for asset in release.assets] == [a["name"] for a in PAYLOAD[0]["assets"]]
    for asset, raw in zip(release.assets, PAYLOAD[0]["assets"], strict=True):
        assert asset.size == raw["size"] and asset.url == raw["browser_download_url"]
        assert f"sha256:{asset.sha256}" == raw["digest"] and len(asset.sha256) == 64


@pytest.mark.parametrize(
    "digest",
    [None, "", "sha512:" + "a" * 128, "sha256:" + "A" * 64, "sha256:" + "a" * 63, 42],
    ids=["missing", "empty", "sha512", "upper case", "short", "not text"],
)
def test_a_digest_that_isnt_a_sha256_is_left_out(digest):
    payload = _payload()
    payload[0]["assets"][0]["digest"] = digest
    assert _release(payload).assets[0].sha256 == ""


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/Axcenity-Studios/Axcenity-Engine/releases/download/v1/a.exe",
        "https://evil.example/Axcenity-Studios/Axcenity-Engine/releases/download/v1/a.exe",
        "https://github.com/someone-else/Axcenity-Engine/releases/download/v1/a.exe",
        "https://github.com/Axcenity-Studios/Axcenity-Engine/releases/download/../../x/a.exe",
        "https://github.com/Axcenity-Studios/Axcenity-Engine/releases/download/v1/a.exe?x=1",
        "javascript:alert(1)",
        None,
    ],
)
def test_a_file_whose_download_isnt_the_engines_is_dropped(url):
    payload = _payload()
    payload[0]["assets"][0]["browser_download_url"] = url
    payload[0]["html_url"] = url
    release = _release(payload)
    assert len(release.assets) == len(PAYLOAD[0]["assets"]) - 1
    assert release.page_url == ""


@pytest.mark.parametrize(
    "change",
    [
        {"name": ""},
        {"name": "../a.exe"},
        {"size": -1},
        {"size": True},
        {"size": "12"},
    ],
)
def test_a_file_with_a_bad_name_or_size_is_dropped(change):
    payload = _payload()
    payload[0]["assets"][0].update(change)
    assert len(_release(payload).assets) == len(PAYLOAD[0]["assets"]) - 1


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "Not Found"},
        None,
        [None, "v1", 3],
        [{**PAYLOAD[0], "tag_name": ""}],
        [{**PAYLOAD[0], "published_at": None}],
        [{**PAYLOAD[0], "published_at": "yesterday"}],
        [{**PAYLOAD[0], "published_at": "2026-11-21T19:38:44"}],  # no time zone
        [{k: v for k, v in PAYLOAD[0].items() if k != "draft"}],
    ],
    ids=["object", "null", "junk", "no tag", "unpublished", "bad date", "naive date", "no draft"],
)
def test_malformed_lists_and_entries_offer_nothing(payload):
    assert releases.select_release(payload) is None


def test_a_missing_title_falls_back_to_the_tag():
    payload = _payload()
    payload[0]["name"] = None
    assert _release(payload).title == "v0.3.0-alpha.1"


# ---------- Builds by system ----------


def _names(group: releases.SystemGroup) -> list[str]:
    return [build.asset.name for build in group.builds]


def test_the_builds_are_grouped_by_system_in_page_order():
    groups = releases.group_builds(_release(), content.DOWNLOAD_BUILDS)
    stem = "AxcenityEditor-0.3.0-alpha.1"
    assert [(group.system, _names(group)) for group in groups] == [
        ("windows", [f"{stem}-windows-x86_64.exe"]),
        ("macos", [f"{stem}-macos-universal.dmg"]),
        (
            "linux",
            [
                f"{stem}-linux-x86_64.AppImage",
                f"{stem}-linux-x86_64.deb",
                f"{stem}-linux-x86_64.rpm",
                f"{stem}-linux-x86_64.pkg.tar.zst",
                f"{stem}-linux-x86_64.tar.gz",
            ],
        ),
        (
            "other",
            [
                f"{stem}-windows-x86_64-update.zip",
                "SHA256SUMS.txt",
                "axcenity-release.json",
                "axcenity-release.json.minisig",
                "axcenity-history.json",
            ],
        ),
    ]
    assert [group.primary.asset.name for group in groups[:3]] == [
        f"{stem}-windows-x86_64.exe",
        f"{stem}-macos-universal.dmg",
        f"{stem}-linux-x86_64.AppImage",
    ]
    assert groups[3].primary is None


def test_every_file_of_every_real_release_lands_in_exactly_one_group():
    for entry in PAYLOAD:
        release = releases.select_release([entry])
        groups = releases.group_builds(release, content.DOWNLOAD_BUILDS)
        grouped = [name for group in groups for name in _names(group)]
        assert sorted(grouped) == sorted(a["name"] for a in entry["assets"]), entry["tag_name"]
        # Every editor build is recognised; only unknown extras could ever be unlabelled.
        assert all(build.kind for group in groups for build in group.builds)


def test_an_unknown_file_is_still_listed_under_other_files():
    payload = _payload()
    extra = {**payload[0]["assets"][0], "name": "notes.pdf"}
    extra["browser_download_url"] = extra["browser_download_url"].rsplit("/", 1)[0] + "/notes.pdf"
    payload[0]["assets"].append(extra)
    other = releases.group_builds(_release(payload), content.DOWNLOAD_BUILDS)[-1]
    assert other.system == "other" and _names(other)[-1] == "notes.pdf"
    assert other.builds[-1].kind is None


def test_a_command_names_its_own_file():
    linux = releases.group_builds(_release(), content.DOWNLOAD_BUILDS)[2]
    deb = linux.builds[1]
    assert deb.command == f"sudo apt install ./{deb.asset.name}"


def test_a_build_kind_names_a_known_system_and_one_way_to_match():
    with pytest.raises(ValueError):
        releases.BuildKind("android", "Phone", tail=".apk")
    with pytest.raises(ValueError):
        releases.BuildKind("linux", "Both", tail=".deb", name="a.deb")
    with pytest.raises(ValueError):
        releases.BuildKind("linux", "Neither")


# ---------- The visitor's system ----------

WINDOWS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
MAC_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.1 Safari/605.1.15"
)
LINUX_UA = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0"
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)
CHROMEOS_UA = (
    "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@pytest.mark.parametrize(
    ("user_agent", "hint", "system"),
    [
        (WINDOWS_UA, "", "windows"),
        (MAC_UA, "", "macos"),
        (LINUX_UA, "", "linux"),
        (ANDROID_UA, "", ""),
        (IPHONE_UA, "", ""),
        (CHROMEOS_UA, "", ""),
        ("", "", ""),
        ("curl/8.0", "", ""),
        # The client hint wins over the User-Agent when a browser sends it.
        (WINDOWS_UA, '"macOS"', "macos"),
        (LINUX_UA, '"Linux"', "linux"),
        (ANDROID_UA, '"Android"', ""),
        (CHROMEOS_UA, '"Chrome OS"', ""),
        (WINDOWS_UA, '"<script>"', ""),
        # Only the start of an overlong header is read.
        ("x" * 600 + "Windows", "", ""),
    ],
)
def test_the_visitors_system_is_detected(user_agent, hint, system):
    assert releases.detect_system(user_agent, hint) == system


# ---------- The page ----------


@pytest.fixture(autouse=True)
def _db(request):
    """The page's tests use the client, which needs the database (sessions)."""
    if "client" in request.fixturenames:
        request.getfixturevalue("db")


def _get(client, user_agent=WINDOWS_UA, **headers):
    response = client.get(reverse("marketing:download"), HTTP_USER_AGENT=user_agent, **headers)
    assert response.status_code == 200
    return response


def _live(payload=None):
    responses.get(
        LIST_URL, json=payload if payload is not None else _payload(), headers={"ETag": ETAG}
    )


def _agree(name: str) -> str:
    """The agreement URL a Download link goes to for one file."""
    return f"{reverse('marketing:download_agree')}?file={quote(name)}"


def _primaries(html: str) -> list[tuple[str, str]]:
    """(href, label) of each primary button in <main>, its icon's markup left out."""
    main = _part_main(html)
    found = re.findall(r'<a href="([^"]+)"[^>]*class="btn btn-primary">(.*?)</a>', main, re.S)
    return [(unescape(href), re.sub(r"<[^>]+>", "", label).strip()) for href, label in found]


def test_the_download_page_is_at_download_in_the_marketing_shell():
    assert reverse("marketing:download") == "/download/"
    assert resolve("/download/").func.view_class is views.DownloadView


@responses.activate
def test_the_page_shows_the_release_its_version_date_and_alpha_mark(client):
    _live()
    html = _get(client).content.decode()
    assert "<title>Download · Axcenity</title>" in html
    assert (
        f'<meta name="description" content="{escape(content.DOWNLOAD_PAGE["description"])}">'
        in html
    )
    overview = html.split('id="overview"', 1)[1].split("</section>", 1)[0]
    assert "v0.3.0-alpha.1" in overview and 'class="badge-dot"' in overview
    assert '<span class="dl-tag micro">Alpha</span>' in overview
    assert '<time datetime="2026-11-21T19:38:44+00:00">21 November 2026</time>' in overview
    assert escape(PAYLOAD[0]["name"]) in overview
    assert content.DOWNLOAD_PAGE["alpha_note"] in overview
    assert html.count("<h1") == 1


@responses.activate
def test_a_stable_release_isnt_marked_alpha(client):
    payload = _payload()
    payload[0]["prerelease"] = False
    _live(payload)
    html = _get(client).content.decode()
    assert '<span class="dl-tag micro">Alpha</span>' not in html
    assert content.DOWNLOAD_PAGE["alpha_note"] not in html


@pytest.mark.parametrize(
    ("user_agent", "system", "suffix"),
    [
        (WINDOWS_UA, "Windows", "-windows-x86_64.exe"),
        (MAC_UA, "macOS", "-macos-universal.dmg"),
        (LINUX_UA, "Linux", "-linux-x86_64.AppImage"),
    ],
)
@responses.activate
def test_the_visitors_system_is_highlighted_and_every_build_stays_reachable(
    client, user_agent, system, suffix
):
    _live()
    html = _get(client, user_agent).content.decode()
    name = f"AxcenityEditor-0.3.0-alpha.1{suffix}"
    assert _primaries(html) == [(_agree(name), f"Download for {system}")]
    detected = re.findall(r'aria-labelledby="system-(\w+)" data-detected', html)
    assert detected == [{"Windows": "windows", "macOS": "macos", "Linux": "linux"}[system]]
    assert html.count(">Your system<") == 1
    for raw in PAYLOAD[0]["assets"]:
        assert f'href="{escape(_agree(raw["name"]))}" data-download' in html, raw["name"]


@pytest.mark.parametrize("user_agent", [ANDROID_UA, IPHONE_UA, ""])
@responses.activate
def test_an_unknown_system_highlights_nothing_and_points_to_every_build(client, user_agent):
    _live()
    html = _get(client, user_agent).content.decode()
    assert _primaries(html) == [("/download/#builds", "Choose your build")]
    assert "data-detected" not in html and ">Your system<" not in html
    assert content.DOWNLOAD_PAGE["unknown_system"].replace("'", "&#x27;") in html
    assert 'id="builds"' in html


@responses.activate
def test_the_client_hint_picks_the_build(client):
    _live()
    html = _get(client, WINDOWS_UA, HTTP_SEC_CH_UA_PLATFORM='"macOS"').content.decode()
    assert _primaries(html)[0][1] == "Download for macOS"


@responses.activate
def test_the_page_varies_on_the_headers_it_reads(client):
    _live()
    vary = _get(client)["Vary"]
    assert "User-Agent" in vary and "Sec-CH-UA-Platform" in vary


@responses.activate
def test_every_build_shows_its_name_size_and_sha256(client):
    _live()
    html = _get(client).content.decode()
    for raw in PAYLOAD[0]["assets"]:
        assert escape(raw["name"]) in html
        assert f'<code class="dl-hash">{raw["digest"].removeprefix("sha256:")}</code>' in html
        assert filesizeformat(raw["size"]) in html
    assert content.DOWNLOAD_PAGE["no_digest"] not in html
    for kind in content.DOWNLOAD_BUILDS:
        assert escape(kind.label) in html


@responses.activate
def test_a_file_without_a_digest_says_where_to_find_one(client):
    payload = _payload()
    del payload[0]["assets"][7]["digest"]
    _live(payload)
    html = _get(client).content.decode()
    assert html.count(escape(content.DOWNLOAD_PAGE["no_digest"])) == 1


@responses.activate
def test_install_commands_name_the_real_files(client):
    _live()
    html = _get(client).content.decode()
    stem = "AxcenityEditor-0.3.0-alpha.1-linux-x86_64"
    for command in (
        f"chmod +x {stem}.AppImage",
        f"sudo apt install ./{stem}.deb",
        f"sudo dnf install ./{stem}.rpm",
        f"sudo pacman -U {stem}.pkg.tar.zst",
        "minisign -Vm axcenity-release.json -p axcenity-release.pub",
    ):
        assert f'<code class="dl-command">{command}</code>' in html


@responses.activate
def test_the_release_page_and_every_release_are_linked(client):
    _live()
    html = _get(client).content.decode()
    assert f'href="{PAYLOAD[0]["html_url"]}"' in html
    assert f'href="{content.RELEASES_URL}"' in html


@responses.activate
def test_text_from_github_is_escaped(client):
    payload = _payload()
    payload[0]["name"] = '<script>alert("x")</script>'
    payload[0]["tag_name"] = "<b>v1</b>"
    _live(payload)
    html = _get(client).content.decode()
    assert "<script>alert" not in html and "<b>v1</b>" not in html
    assert "&lt;script&gt;alert" in html


@responses.activate
def test_a_failing_github_shows_the_cached_release_with_its_date(client):
    _live()
    fetched_at = (datetime.now(UTC) - timedelta(hours=2)).replace(microsecond=0)
    releases.current_release(now=fetched_at)
    responses.replace(responses.GET, LIST_URL, status=503)
    html = _get(client).content.decode()
    assert content.DOWNLOAD_PAGE["stale"].replace("'", "&#x27;") in html
    assert f'datetime="{fetched_at.isoformat(timespec="seconds")}' in html
    assert _primaries(html)[0][1] == "Download for Windows"
    assert len(responses.calls) == 2


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
@responses.activate
def test_with_nothing_cached_a_failing_github_shows_the_plain_link_not_an_error(client, failure):
    responses.get(LIST_URL, **failure)
    html = _get(client).content.decode()
    unavailable = content.DOWNLOAD_PAGE["unavailable"]
    assert escape(unavailable["title"]) in html
    assert _primaries(html) == [(content.RELEASES_URL, unavailable["link"].label)]
    assert 'id="builds"' not in html


@responses.activate
def test_the_nav_marks_download_as_the_current_page(client):
    _live()
    nav = _get(client).content.decode().split('id="site-nav"', 1)[1].split("</header>", 1)[0]
    assert re.search(r'href="/download/" class="btn btn-primary btn-sm" aria-current="page"', nav)


@responses.activate
def test_the_visible_prose_comes_from_the_content_module_or_the_release(client):
    _live()
    html = _get(client).content.decode()
    release = _release()
    allowed = set(_copy(content.DOWNLOAD_PAGE)) | set(_copy(content.DOWNLOAD_BUILDS))
    allowed |= {release.tag, release.title, "21 November 2026"}
    for group in releases.group_builds(release, content.DOWNLOAD_BUILDS):
        for build in group.builds:
            size = " ".join(filesizeformat(build.asset.size).split())
            allowed |= {build.asset.name, size, build.asset.sha256, build.command}
            allowed.add(f"{build.asset.name} · {size}")
    allowed.add("Download for Windows")
    allowed.add(f"{content.DOWNLOAD_PAGE['released']}")
    allowed |= {system for system, _ in content.DOWNLOAD_PAGE["verify"]["commands"]}
    allowed |= {command for _, command in content.DOWNLOAD_PAGE["verify"]["commands"]}
    stray = [chunk for chunk in _visible(html).chunks if chunk not in allowed]
    assert not stray, f"hard-coded copy: {stray}"


def test_the_copy_is_honest_about_the_alpha():
    text = " ".join(_copy(content.DOWNLOAD_PAGE))
    assert "Alpha" in text and "Windows, macOS and Linux" in text
    assert "Lua " not in text


# ---------- Icons ----------

ICONS = (settings.BASE_DIR / "templates" / "partials" / "icon.html").read_text("utf-8")


def _drawn(name: str) -> bool:
    return f'name == "{name}"' in ICONS


def test_every_system_and_kind_of_file_has_an_icon_the_partial_draws():
    assert set(content.DOWNLOAD_SYSTEM_ICONS) == set(releases.SYSTEMS)
    for icon in content.DOWNLOAD_SYSTEM_ICONS.values():
        assert _drawn(icon), icon
    for kind in content.DOWNLOAD_BUILDS:
        assert kind.icon != "file" and _drawn(kind.icon), kind.label
    # A file no kind recognises still gets one.
    assert _drawn("file")
    asset = releases.Asset("notes.pdf", 1, "https://github.com/x")
    assert releases.Build(asset).icon == "file"


def _icon_paths(name: str) -> str:
    """The first path or shape the partial draws for an icon, to find it in a page."""
    body = ICONS.split(f'name == "{name}" %}}', 1)[1]
    return re.search(r"<(?:path|rect|circle) [^>]*>", body).group(0)


@pytest.mark.parametrize(
    ("user_agent", "icon"), [(WINDOWS_UA, "windows"), (MAC_UA, "macos"), (LINUX_UA, "linux")]
)
@responses.activate
def test_the_primary_button_and_each_panel_carry_their_systems_icon(client, user_agent, icon):
    _live()
    main = _part_main(_get(client, user_agent).content.decode())
    button = re.search(r'class="btn btn-primary">(.*?)</a>', main, re.S).group(1)
    assert _icon_paths(icon) in button and 'aria-hidden="true"' in button
    for system, name in content.DOWNLOAD_SYSTEM_ICONS.items():
        heading = re.search(rf'<h3 id="system-{system}"[^>]*>(.*?)</h3>', main, re.S).group(1)
        assert _icon_paths(name) in heading, system


@responses.activate
def test_each_file_shows_its_kinds_icon(client):
    _live()
    main = _part_main(_get(client).content.decode())
    cards = re.findall(r'<li class="dl-build" style="--stagger: \d+">(.*?)</li>', main, re.S)
    assert len(cards) == len(PAYLOAD[0]["assets"])
    for card in cards:
        name = re.search(r'<span class="sr-only"> ([^<]+)</span>', card).group(1)
        kind = next(k for k in content.DOWNLOAD_BUILDS if k.matches(name))
        assert _icon_paths(kind.icon) in card, name
        # The SHA-256 and the button sit together in the card's foot, which lines them up.
        foot = card.split('<div class="dl-build-foot">', 1)[1]
        assert "dl-hash" in foot and "btn btn-quiet btn-sm" in foot


# ---------- New releases ----------


def _next_release() -> dict:
    """The real newest release as a later one would look: v0.4.0-alpha.1, published after it."""
    text = json.dumps(PAYLOAD[0]).replace("0.3.0-alpha.1", "0.4.0-alpha.1")
    entry = json.loads(text)
    entry["published_at"] = "2026-12-05T18:00:00Z"
    return entry


@responses.activate
def test_a_newly_published_release_replaces_the_old_one_once_the_hour_is_up(client):
    _live()
    releases.current_release(now=NOW)
    # GitHub's list changed, so it answers the stored ETag with a 200 and a new one.
    responses.replace(
        responses.GET, LIST_URL, json=[_next_release(), *_payload()], headers={"ETag": 'W/"new"'}
    )
    assert releases.current_release(now=NOW + timedelta(minutes=30)).release.tag == (
        "v0.3.0-alpha.1"
    )
    offer = releases.current_release(now=NOW + timedelta(hours=1))
    assert offer.state == "live" and offer.release.tag == "v0.4.0-alpha.1"
    assert responses.calls[1].request.headers.get("If-None-Match") == ETAG
    # The build kinds match by file pattern, not version, so the new files group the same way.
    groups = releases.group_builds(offer.release, content.DOWNLOAD_BUILDS)
    assert [g.system for g in groups] == ["windows", "macos", "linux", "other"]
    assert all(build.kind for g in groups for build in g.builds)
    assert groups[0].primary.asset.name == "AxcenityEditor-0.4.0-alpha.1-windows-x86_64.exe"


@responses.activate
def test_the_page_offers_the_new_release(client):
    responses.get(LIST_URL, json=[_next_release(), *_payload()], headers={"ETag": ETAG})
    html = _get(client).content.decode()
    assert _primaries(html) == [
        (_agree("AxcenityEditor-0.4.0-alpha.1-windows-x86_64.exe"), "Download for Windows")
    ]
    assert "v0.4.0-alpha.1" in html and "0.3.0-alpha.1-" not in html


@responses.activate
def test_a_draft_stays_hidden_until_it_is_published():
    draft = {**_next_release(), "draft": True}
    responses.get(LIST_URL, json=[draft, *_payload()], headers={"ETag": ETAG})
    assert releases.current_release(now=NOW).release.tag == "v0.3.0-alpha.1"


# ---------- Filling the layout ----------


def _tips(html: str) -> list[str]:
    return re.findall(r'<li class="dl-build dl-tip[^"]*"', _part_main(html))


@pytest.mark.parametrize(
    ("linux_builds", "tip"),
    [
        (5, '<li class="dl-build dl-tip"'),  # 3 + 2: one cell left
        (4, '<li class="dl-build dl-tip lg:col-span-2"'),  # 3 + 1: two cells left
        (3, None),  # a full row: nothing to fill
    ],
)
@responses.activate
def test_a_tip_card_fills_the_gap_in_the_linux_panels_last_row(client, linux_builds, tip):
    payload = _payload()
    linux = [a for a in payload[0]["assets"] if "-linux-" in a["name"]]
    for extra in linux[linux_builds:]:
        payload[0]["assets"].remove(extra)
    _live(payload)
    html = _get(client).content.decode()
    linux_panel = html.split('id="system-linux"', 1)[1].split("</section>", 1)[0]
    found = _tips(f'<main id="content">{linux_panel}</main>')
    assert found == ([tip] if tip else [])
    if tip:
        assert escape(content.DOWNLOAD_PAGE["tips"]["linux"]["title"]) in linux_panel


@responses.activate
def test_other_files_tip_links_to_checking_the_download(client):
    _live()
    html = _get(client).content.decode()
    other = html.split('id="system-other"', 1)[1].split("</section>", 1)[0]
    assert content.DOWNLOAD_PAGE["tips"]["other"]["title"] in other
    assert 'href="/download/#verify"' in other and 'id="verify"' in html
    # Windows and macOS have one build each: they share a row and need no tip.
    assert len(_tips(html)) == 2


@responses.activate
def test_the_from_source_steps_are_the_engines_own(client):
    _live()
    html = _get(client).content.decode()
    guide = (settings.DOCS_SNAPSHOT_DIR / "learn" / "getting-started.md").read_text("utf-8")
    source = content.DOWNLOAD_PAGE["from_source"]
    assert "cargo run -p axcenity-editor" in source["commands"] and (
        "cargo run -p axcenity-editor" in guide
    )
    assert source["note"] in guide
    assert source["commands"][0] == f"git clone {content.ENGINE_REPO_URL}.git"
    terminal = html.split('<pre class="tb-terminal"', 1)[1].split("</pre>", 1)[0]
    for command in source["commands"]:
        assert f"{escape(command)}\n" in terminal
    for link in source["links"]:
        assert f'href="{link.href}"' in html
    assert reverse("documentation:page", args=("reference/system-requirements",))


@responses.activate
def test_the_download_icons_are_decorative_motifs(client):
    _live()
    main = _part_main(_get(client).content.decode())
    motifs = re.findall(r'<svg class="motif dl-motif"[^>]*>', main)
    # The button's, one per panel (4), one per file (12) and one per tip (2).
    assert len(motifs) == 1 + 4 + 12 + 2
    assert all('aria-hidden="true"' in svg and 'focusable="false"' in svg for svg in motifs)
    # Every icon has a part that draws in or moves.
    for name in {
        *content.DOWNLOAD_SYSTEM_ICONS.values(),
        *(k.icon for k in content.DOWNLOAD_BUILDS),
    }:
        body = ICONS.split(f'name == "{name}" %}}', 1)[1].split("{% ", 1)[0]
        assert 'class="m-' in body, name


# ---------- The license agreement ----------

AGREEMENT = content.DOWNLOAD_PAGE["agreement"]
AGREE_URL = "/download/agree/"
EXE = "AxcenityEditor-0.3.0-alpha.1-windows-x86_64.exe"
ENGINE_DIR = Path.home() / "Documents" / "VSCode Projects" / "Axcenity-Engine"


@responses.activate
def test_every_download_link_goes_through_the_agreement(client):
    _live()
    main = _part_main(_get(client).content.decode())
    links = re.findall(r'<a href="([^"]+)" data-download data-file="([^"]+)"', main)
    # The button, then one per file.
    assert len(links) == 1 + len(PAYLOAD[0]["assets"])
    for href, name in links:
        assert unescape(href) == _agree(unescape(name))
    # No link on the page reaches a file without the agreement.
    assert "/releases/download/" not in main


@responses.activate
def test_the_agreement_page_shows_the_terms_and_the_form(client):
    _live()
    response = client.get(AGREE_URL, {"file": EXE})
    assert response.status_code == 200
    html = response.content.decode()
    assert reverse("marketing:download_agree") == AGREE_URL
    assert "<title>License agreement · Axcenity</title>" in html
    assert html.count("<h1") == 1
    assert f"{EXE} · 187.9" in html
    for term in AGREEMENT["terms"]:
        assert escape(term["body"]) in html, term["title"]
    form = html.split('<form method="post" action="/download/agree/"', 1)[1].split("</form>", 1)[0]
    assert 'name="csrfmiddlewaretoken"' in form
    assert f'<input type="hidden" name="file" value="{EXE}">' in form
    assert '<input type="checkbox" name="agree" value="yes" required>' in form
    _assert_full_text(html)


def _assert_full_text(html: str) -> None:
    """The engine's LICENSE and NOTICE in full beside the terms, set as prose, as tabs that
    need no script."""
    pane = html.split('<div class="dl-fulltext"', 1)[1]
    for key, text in (("license", content.ENGINE_LICENSE), ("notice", content.ENGINE_NOTICE)):
        body = pane.split(f'data-fulltext="{key}"', 1)[1].split("\n        </div>", 1)[0]
        # Every word of the file, in order: nothing dropped by the reflow or the template.
        shown = unescape(re.sub(r"<[^>]+>", " ", body.split(">", 1)[1])).split()
        assert shown == _words(text), key
    assert "<pre" not in pane
    assert (
        '<h3 class="dl-legal-heading">TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION</h3>'
        in pane
    )
    assert "<p><strong>7. Disclaimer of Warranty.</strong> Unless required" in pane
    assert '<h3 class="dl-legal-heading">Third-party code</h3>' in pane
    assert pane.count('<hr class="dl-legal-rule">') == content.ENGINE_NOTICE.count("\n---\n")
    # Under the texts, the way to every crate and package.
    assert f'<a href="{reverse("marketing:credits")}" class="dl-credits-link">Credits</a>' in pane
    assert (
        '<input type="radio" name="fulltext" id="fulltext-license" class="dl-tab-input sr-only" checked>'
        in pane
    )
    assert '<label for="fulltext-notice" class="tb-chip dl-tab">NOTICE</label>' in pane
    # Nothing sends the visitor to GitHub to read the terms.
    assert "/blob/main/LICENSE" not in html


@responses.activate
def test_agreeing_redirects_to_the_files_download_on_github(client):
    _live()
    response = client.post(AGREE_URL, {"file": EXE, "agree": "yes"})
    assert response.status_code == 303
    assert response["Location"] == f"{DOWNLOAD_URL}{EXE}"


@pytest.mark.parametrize("agree", [None, "", "on", "no", "YES"])
@responses.activate
def test_without_ticking_the_box_there_is_no_download(client, agree):
    _live()
    data = {"file": EXE} | ({"agree": agree} if agree is not None else {})
    response = client.post(AGREE_URL, data)
    assert response.status_code == 400
    assert "Location" not in response
    html = response.content.decode()
    assert AGREEMENT["required"] in html and 'role="alert"' in html
    assert 'aria-invalid="true"' in html


@pytest.mark.parametrize(
    "name",
    [
        None,
        "",
        "notes.pdf",
        f"{DOWNLOAD_URL}{EXE}",
        "https://evil.example/AxcenityEditor.exe",
        f"../{EXE}",
        EXE.upper(),
    ],
)
@responses.activate
def test_only_a_file_in_the_current_release_can_be_agreed_to(client, name):
    _live()
    query = {"file": name} if name is not None else {}
    assert client.get(AGREE_URL, query).status_code == 404
    assert client.post(AGREE_URL, {**query, "agree": "yes"}).status_code == 404


@responses.activate
def test_with_no_release_to_offer_the_agreement_is_a_404(client):
    responses.get(LIST_URL, status=503)
    assert client.get(AGREE_URL, {"file": EXE}).status_code == 404


@responses.activate
def test_agreeing_requires_a_csrf_token(db):
    _live()
    response = Client(enforce_csrf_checks=True).post(AGREE_URL, {"file": EXE, "agree": "yes"})
    assert response.status_code == 403
    assert "Location" not in response


@responses.activate
def test_the_download_page_carries_the_agreement_as_a_dialog(client):
    _live()
    html = _get(client).content.decode()
    dialog = html.split('<dialog class="dl-dialog"', 1)[1].split("</dialog>", 1)[0]
    assert 'aria-labelledby="agreement-title" data-agreement' in dialog
    assert '<form method="post" action="/download/agree/"' in dialog
    assert 'name="csrfmiddlewaretoken"' in dialog
    assert '<input type="hidden" name="file" value="">' in dialog
    assert "required" in dialog and "data-agreement-cancel" in dialog
    assert re.search(r'<script src="/static/js/download\.js\?v=[^"]+" defer>', html)


def test_download_js_gates_every_link_and_keeps_modified_clicks_as_pages():
    js = (settings.BASE_DIR / "static" / "js" / "download.js").read_text("utf-8")
    assert 'event.target.closest("a[data-download]")' in js
    assert "event.preventDefault();" in js and "dialog.showModal();" in js
    assert "if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;" in js
    assert "submit.disabled = !box.checked;" in js and "box.checked = false;" in js
    assert 'typeof dialog.showModal !== "function"' in js


def _plain(markdown: str) -> str:
    """Markdown as read: links as their text, no emphasis or code marks, one space between words."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown).replace("**", "").replace("`", "")
    return " ".join(text.split())


@pytest.mark.skipif(not ENGINE_DIR.exists(), reason="the engine's checkout isn't on this machine")
def test_the_terms_are_the_engines_own_words():
    readme = _plain((ENGINE_DIR / "README.md").read_text("utf-8"))
    licence = " ".join((ENGINE_DIR / "LICENSE").read_text("utf-8").split())
    for term in AGREEMENT["terms"][:4]:
        for sentence in re.split(r"(?<=\.) ", term["body"]):
            assert sentence in readme, sentence
    assert "Apache License Version 2.0" in licence
    assert 'on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND' in licence
    assert "reasonable and customary use in describing the origin of the Work" in licence


@responses.activate
def test_the_dialog_carries_the_full_license_and_notice(client):
    _live()
    html = _get(client).content.decode()
    _assert_full_text(html.split('<dialog class="dl-dialog"', 1)[1].split("</dialog>", 1)[0])


def test_the_full_texts_are_the_apache_license_and_the_engines_notice():
    assert content.ENGINE_LICENSE.lstrip().startswith("Apache License")
    assert "Version 2.0, January 2004" in content.ENGINE_LICENSE
    assert "6. Trademarks." in content.ENGINE_LICENSE
    assert content.ENGINE_NOTICE.startswith("Axcenity Engine\nCopyright 2026")


@pytest.mark.skipif(not ENGINE_DIR.exists(), reason="the engine's checkout isn't on this machine")
def test_the_copied_license_and_notice_match_the_engines():
    # The engine's last commit, not its working tree: an edit in progress there isn't
    # the engine's NOTICE yet.
    for name, text in (("LICENSE", content.ENGINE_LICENSE), ("NOTICE", content.ENGINE_NOTICE)):
        committed = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(ENGINE_DIR), "show", f"HEAD:{name}"],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
        assert committed == text, f"{name} changed in the engine: run manage.py refresh_credits"


# ---------- The legal texts as prose ----------


def _words(text: str) -> list[str]:
    """A plain-text file's words in order, its heading underlines left out."""
    return [word for word in text.split() if not re.fullmatch(r"[-=]{3,}", word)]


def _block_words(blocks) -> list[str]:
    return [w for b in blocks for part in (b.lead, b.text, *b.lines) for w in part.split()]


@pytest.mark.parametrize(
    "text", [content.ENGINE_LICENSE, content.ENGINE_NOTICE], ids=["LICENSE", "NOTICE"]
)
def test_reflowing_keeps_every_word_in_order(text):
    assert _block_words(legal.reflow(text)) == _words(text)


def test_the_license_reflows_into_headings_sections_and_sub_items():
    blocks = legal.reflow(content.ENGINE_LICENSE)
    title = blocks[0]
    assert title.kind == "lines" and title.centred
    assert title.lines == (
        "Apache License",
        "Version 2.0, January 2004",
        "http://www.apache.org/licenses/",
    )
    headings = [b.text for b in blocks if b.kind == "heading"]
    assert headings == [
        "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
        "1. Definitions.",
        "END OF TERMS AND CONDITIONS",
        "APPENDIX: How to apply the Apache License to your work.",
    ]
    leads = [b.lead for b in blocks if b.lead]
    assert leads[0] == "2. Grant of Copyright License." and leads[-1].startswith("9. ")
    assert len(leads) == 8
    # Definitions and (a)–(d) are indented; the hard wraps are gone.
    assert all(b.level == 1 for b in blocks if b.text.startswith(('"License"', "(a)", "(d)")))
    assert all("\n" not in b.text and "  " not in b.text for b in blocks)


def test_the_notice_reflows_its_underlined_headings():
    """The engine's NOTICE as copied, whatever sections it has now: the expectations are
    read from the file's own lines, so a credit added or dropped there needs no change here."""
    text = content.ENGINE_NOTICE
    lines = [line.strip() for line in text.splitlines()]
    blocks = legal.reflow(text)
    # The title block: the file's opening lines, up to the first blank one.
    assert blocks[0].lines == tuple(lines[: lines.index("")])
    assert not blocks[0].centred
    # A heading is a paragraph's only line, underlined with dashes or equals signs.
    underlined = [
        lines[i]
        for i in range(1, len(lines) - 1)
        if lines[i] and not lines[i - 1] and re.fullmatch(r"[-=]{3,}", lines[i + 1])
    ]
    assert underlined, "the NOTICE has no headings left"
    assert [b.text for b in blocks if b.kind == "heading"] == underlined
    # Each lone "---" between two credited works is a divider, never a word or a heading.
    rules = [i for i, b in enumerate(blocks) if b.kind == "rule"]
    assert len(rules) == text.count("\n---\n")
    assert all(blocks[i + 1].kind in ("paragraph", "lines") for i in rules)


def test_reflow_handles_the_edges():
    assert legal.reflow("") == []
    first = "A body line long enough to have been hard-wrapped at eighty columns,"
    text = f"Title\n-----\n\n{first}\r\n   and its   continuation.\r\n\nShort\nlines"
    assert legal.reflow(text) == [
        legal.Block("heading", text="Title"),
        legal.Block("paragraph", text=f"{first} and its continuation."),
        legal.Block("lines", lines=("Short", "lines")),
    ]


def test_reflow_divides_entries_at_a_line_of_dashes_but_keeps_underlines():
    """New credits can be added to the NOTICE in any of these layouts and still set right:
    a "---" between entries (alone, or running into the next entry), "***" or "___", and a
    long rule; a rule under a paragraph's only line still underlines it as a heading."""
    long_line = "Permission is hereby granted, free of charge, to any person obtaining a"
    text = (
        f"First work\n----------\n{long_line}\ncopy.\n\n"
        "---\n\n"
        f"---\n{long_line}\nsecond.\n\n"
        f"{long_line}\ncontinued.\n***\n"
        "Third work\n==========\n\n"
        "___\n"
    )
    blocks = legal.reflow(text)
    assert [b.kind for b in blocks] == [
        "heading", "paragraph", "rule", "rule", "paragraph", "paragraph", "rule",
        "heading", "rule",
    ]  # fmt: skip
    assert blocks[0].text == "First work" and blocks[7].text == "Third work"
    assert blocks[4].text == f"{long_line} second."
    # Words are unchanged and in order; the rules carry none.
    assert _block_words(blocks) == [w for w in text.split() if not re.fullmatch(r"[-=*_]{3,}", w)]
