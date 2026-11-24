"""The Toolbox toolbox (/toolbox/): links, copy as data, its screenshots and their capture record,
the run-locally commands and the demo credentials."""

import dataclasses
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.urls import resolve, reverse
from django.utils.html import escape

from marketing import content, media
from tests.test_home import _copy, _part_main, _visible

pytestmark = pytest.mark.django_db

PAGE = content.TOOLBOX_PAGE
SCREENSHOTS = [feature.media for feature in PAGE["features"]]
# Each one in the Toolbox's light theme, shown instead whenever the site is light.
LIGHT = [item.light for item in SCREENSHOTS]
EVERY_SHOT = SCREENSHOTS + LIGHT
RECORD = json.loads((settings.BASE_DIR / content.TOOLBOX_CAPTURE_RECORD).read_text("utf-8"))
# The Toolbox's own checkout, a read-only reference repository; only on the maintainer's machine.
TOOLBOX_README = (
    Path.home() / "Documents" / "VSCode Projects" / "project-two-building-with-apis" / "README.md"
)


@pytest.fixture
def toolbox(client):
    response = client.get(reverse("marketing:toolbox"))
    assert response.status_code == 200
    return response.content.decode()


# ---------- The toolbox and its links ----------


def test_the_toolbox_page_is_at_toolbox_in_the_marketing_shell(toolbox):
    assert reverse("marketing:toolbox") == "/toolbox/"
    assert (
        toolbox.index('id="site-nav"')
        < toolbox.index('id="content"')
        < toolbox.index('id="site-footer"')
    )
    assert "<title>Axcenity Toolbox · Axcenity</title>" in toolbox
    assert f'<meta name="description" content="{escape(PAGE["description"])}">' in toolbox
    assert toolbox.count("<h1") == 1


def test_its_sections_come_in_order(toolbox):
    ids = re.findall(r'<section id="([^"]+)"', _part_main(toolbox))
    assert ids == ["overview", "discover", "library", "packs", "run"]


def test_the_nav_links_the_toolbox_and_marks_it_current(toolbox):
    nav = toolbox.split('id="site-nav"', 1)[1].split("</header>", 1)[0]
    assert re.search(r'<a href="/toolbox/" class="nav-link" aria-current="page">Toolbox</a>', nav)
    footer = toolbox.split('id="site-footer"', 1)[1]
    assert re.search(
        r'<a href="/toolbox/" class="footer-link"( aria-current="page")?>Toolbox</a>', footer
    )


def test_the_home_banner_links_the_toolbox_page(client):
    home = client.get(reverse("marketing:home")).content.decode()
    banner = home.split('id="toolbox"', 1)[1].split("</section>", 1)[0]
    assert '<a href="/toolbox/"' in banner and content.HOME_TOOLBOX["cta"].label in banner
    assert "Soon" not in banner


def test_the_github_link_is_the_toolboxs_public_repository(toolbox):
    assert content.TOOLBOX_REPO_URL == "https://github.com/pj1163928/project-two-building-with-apis"
    assert PAGE["primary"].href == content.TOOLBOX_REPO_URL
    hero = toolbox.split('id="overview"', 1)[1].split("</section>", 1)[0]
    assert f'<a href="{content.TOOLBOX_REPO_URL}" rel="noopener" class="btn btn-primary">' in hero
    # The one primary button in the page's content (the nav keeps Download).
    assert _part_main(toolbox).count("btn-primary") == 1


def test_every_href_on_the_page_goes_somewhere_real(toolbox):
    ids = set(re.findall(r' id="([^"]+)"', toolbox))
    repos = [urlsplit(url).path for url in (content.ENGINE_REPO_URL, content.TOOLBOX_REPO_URL)]
    for href in re.findall(r'href="([^"]+)"', toolbox):
        if href.startswith("/static/"):
            continue
        parts = urlsplit(href)
        if parts.scheme:
            assert parts.scheme == "https" and parts.netloc == "github.com", href
            assert any(parts.path == r or parts.path.startswith(r + "/") for r in repos), href
            continue
        if parts.path:
            resolve(parts.path)  # raises Resolver404 for a dead internal link
        if parts.fragment and parts.path in ("", "/toolbox/"):
            assert parts.fragment in ids, f"{href}: no element has that id"


# ---------- Copy is data ----------

PAGE_COPY = set(_copy(PAGE))


def test_the_visible_prose_and_labels_come_from_the_content_module(toolbox):
    visible = _visible(toolbox)
    stray = [chunk for chunk in visible.chunks if chunk not in PAGE_COPY]
    assert not stray, f"hard-coded copy: {stray}"


def test_the_commands_render_exactly_from_the_content_module(toolbox):
    code = "".join(_visible(toolbox).code)
    expected = "".join(
        f"$ {c.line}" + (f"  # {c.note}" if c.note else "") + "\n" for c in PAGE["run"]["commands"]
    )
    assert code == expected


def test_the_toolbox_is_described_honestly(toolbox):
    text = " ".join(_visible(toolbox).chunks)
    for name in ("ambientCG", "Poly Haven", "Openverse"):
        assert name in text
    assert "your own machine" in text  # it isn't in the Hub yet
    assert "Lua " not in text and "Engine capture" not in toolbox


# ---------- Screenshots ----------


def test_each_feature_shows_its_own_toolbox_screenshot(toolbox):
    assert [m.key for m in SCREENSHOTS] == ["toolbox-discover", "toolbox-library", "toolbox-packs"]
    for feature in PAGE["features"]:
        section = toolbox.split(f'<section id="{feature.label.lower()}"', 1)[1].split(
            "</section>", 1
        )[0]
        # One picture per scheme, dark first, each of its own capture's files; one caption.
        pictures = re.findall(r'<picture class="when-(\w+)">(.*?)</picture>', section, re.S)
        assert [scheme for scheme, _ in pictures] == ["dark", "light"]
        assert section.count("<figcaption") == 1
        assert f'<figcaption class="media-cap micro">{escape(feature.media.caption)}<' in section
        sizes = escape(feature.media.display["section"].sizes)
        for (_, picture), shot in zip(pictures, [feature.media, feature.media.light], strict=True):
            types = re.findall(r'<source type="([^"]+)" srcset="[^"]+" sizes="([^"]+)">', picture)
            assert types == [("image/avif", sizes), ("image/webp", sizes)]
            assert f"/{shot.key}/{shot.key}-2560.jpg 2560w" in picture
            assert f'alt="{escape(shot.alt)}"' in picture


@pytest.mark.parametrize("item", EVERY_SHOT, ids=lambda item: item.key)
def test_screenshots_are_toolbox_captures_never_engine_ones(item):
    assert item.kind == "capture" and item.subject == "toolbox"
    assert item.caption.startswith("Toolbox screenshot")
    assert item.source_size == (2560, 1600)  # 1280×800 at 2×, the frame's own 16:10
    assert content.TOOLBOX_COMMIT[:7] in item.provenance
    assert content.TOOLBOX_CAPTURE_RECORD in item.provenance
    assert item.key in content.MEDIA  # make_media cuts it like any capture


@pytest.mark.parametrize("dark", SCREENSHOTS, ids=lambda item: item.key)
def test_each_screenshot_has_a_light_twin_of_the_same_screen(dark):
    light = dark.light
    assert light.key == f"{dark.key}-light" and light.source.endswith("-light-2560x1600.png")
    assert light.is_light_twin_of(dark)
    assert "in its dark theme" in dark.alt and "in its light theme" in light.alt
    assert "dark scheme" in dark.provenance and "light scheme" in light.provenance


def test_a_light_twin_must_match_its_capture():
    dark = SCREENSHOTS[0]
    other_caption = dataclasses.replace(LIGHT[0], key="x", caption="Toolbox screenshot · other")
    with pytest.raises(ValueError):
        dataclasses.replace(dark, light=other_caption)
    with pytest.raises(ValueError):  # a different size would frame differently
        dataclasses.replace(dark, light=dataclasses.replace(LIGHT[0], source_size=(1280, 800)))
    with pytest.raises(ValueError):  # and a twin is never itself
        dataclasses.replace(dark, light=dark)


def test_the_stylesheet_shows_the_picture_for_the_sites_scheme():
    css = (settings.BASE_DIR / "styles" / "source.css").read_text(encoding="utf-8")
    assert (
        '.media > picture.when-light, html[data-scheme="light"] .media > picture.when-dark '
        "{ display: none; }" in css
    )
    assert 'html[data-scheme="light"] .media > picture.when-light { display: block; }' in css


def test_every_image_on_the_page_is_a_screenshots_derivative(toolbox):
    files = {f"/static/{d.path}" for item in EVERY_SHOT for d in item.derivatives}
    main = _part_main(toolbox)
    for img in re.findall(r"<img [^>]+>", main):
        assert re.search(r'width="2560" height="1600"', img), img
        assert 'loading="lazy"' in img and 'decoding="async"' in img
    for src in re.findall(r'<img src="([^"]+)"', main):
        assert src in files, src
    for srcset in re.findall(r'srcset="([^"]+)"', main):
        for candidate in srcset.split(", "):
            assert candidate.split(" ")[0] in files, candidate


# ---------- The capture record: the screenshots are committed static sources ----------


@pytest.mark.parametrize("item", EVERY_SHOT, ids=lambda item: item.key)
def test_each_screenshot_matches_its_capture_record(item):
    """The committed file is the one captured: tests only read it, nothing regenerates it."""
    screen = next(s for s in RECORD["screens"].values() if s["file"] == item.source)
    assert screen["scheme"] == ("light" if item in LIGHT else "dark")
    data = (media.SOURCES_DIR / item.source).read_bytes()
    assert hashlib.sha256(data).hexdigest() == screen["sha256"]
    assert screen["url"].startswith("/") and screen["captured_at"].startswith("2026-")
    # What it showed, with the live provider thumbnails it showed them with.
    assert screen["shown"]
    for shown in screen["shown"]:
        assert shown["title"]
        assert urlsplit(shown["src"]).scheme == "https", shown


def test_the_capture_record_names_the_toolbox_source_state():
    source = RECORD["source"]
    assert source["repository"] == content.TOOLBOX_REPO_URL
    assert source["commit"] == content.TOOLBOX_COMMIT
    assert "git archive" in source["working_tree"]
    capture = RECORD["capture"]
    assert capture["viewport"] == {"width": 1280, "height": 800}
    assert capture["device_scale_factor"] == 2
    assert capture["signed_in_as"] == "demo_mira"
    screens = RECORD["screens"]
    assert set(screens) == {
        f"{s}{v}" for s in ("discover", "library", "packs") for v in ("", "-light")
    }
    assert screens["discover"]["shelves"]  # the live provider shelves it showed
    # Both themes showed the same results and thumbnails, so the twins match.
    for name in ("discover", "library", "packs"):
        dark, light = screens[name], screens[f"{name}-light"]
        assert dark["url"] == light["url"] and dark["shelves"] == light["shelves"]
        assert dark["shown"] == light["shown"]


def test_the_demo_accounts_had_no_privileges_when_captured():
    users = RECORD["source"]["demo_accounts"]["users"]
    assert {u["username"] for u in users} == {"demo_mira", "demo_otto", "demo_juno"}
    for user in users:
        assert user["is_staff"] is False and user["is_superuser"] is False
        assert user["groups"] == 0 and user["permissions"] == 0


# ---------- Running it locally ----------


def test_the_demo_credentials_are_marked_demo_local_and_unprivileged(toolbox):
    demo = PAGE["run"]["demo"]
    box = toolbox.split('class="tb-demo"', 1)[1].split("</div>", 1)[0]
    assert demo["title"] == "Demo credentials" and demo["title"] in box
    assert "local copy only" in demo["body"]
    assert "no staff or admin rights" in demo["privileges"]
    assert "Never run seed_demo" in demo["privileges"]
    assert escape(demo["privileges"]) in box and demo["password"] in box
    # Only the README's public demo password: never the README's personal test account.
    assert "test_user" not in toolbox


def test_the_commands_use_uv_only():
    lines = [c.line for c in PAGE["run"]["commands"]]
    assert lines[0] == f"git clone {content.TOOLBOX_REPO_URL}"
    assert lines[1] == "cd " + urlsplit(content.TOOLBOX_REPO_URL).path.rsplit("/", 1)[1]
    assert all(line.startswith(("uv sync", "uv run ")) for line in lines[2:])
    assert not any(word in " ".join(lines) for word in ("pip ", "npm", "node "))


def _sh_blocks(section: str) -> list[str]:
    """The command lines of a README section's ```sh blocks, without their # comments."""
    lines = []
    for block in re.findall(r"```sh\n(.*?)```", section, re.S):
        lines += [line.split("#", 1)[0].strip() for line in block.splitlines() if line.strip()]
    return lines


@pytest.mark.skipif(
    not TOOLBOX_README.exists(), reason="the Toolbox repository isn't checked out here"
)
def test_the_commands_match_the_toolbox_readme():
    readme = TOOLBOX_README.read_text(encoding="utf-8")
    setup = readme.split("\n## Setup\n", 1)[1].split("\n## ", 1)[0]
    running = readme.split("\n## Running the site\n", 1)[1].split("\n## ", 1)[0]
    expected = _sh_blocks(setup) + _sh_blocks(running)[:1]
    lines = [c.line for c in PAGE["run"]["commands"]]
    assert expected[0] == "git clone <this repository>"
    assert lines[1:] == expected[1:]
    assert PAGE["run"]["open_url"] in running
    assert f"`demo_mira` | `{PAGE['run']['demo']['password']}`" in readme
