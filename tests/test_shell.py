"""The marketing shell: nav, footer, links, branding, fonts, hover gate and motion."""

import mimetypes
import re
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.urls import resolve, reverse

from marketing import content

pytestmark = pytest.mark.django_db

SOURCE = (settings.BASE_DIR / "styles" / "source.css").read_text(encoding="utf-8")
SHELL_JS = (settings.BASE_DIR / "static" / "js" / "shell.js").read_text(encoding="utf-8")


@pytest.fixture
def home(client):
    response = client.get(reverse("marketing:home"))
    assert response.status_code == 200
    return response.content.decode()


def _part(html: str, start: str, end: str) -> str:
    return html.split(start, 1)[1].split(end, 1)[0]


def _nav(html):
    return _part(html, 'id="site-nav"', "</header>")


def _footer(html):
    return _part(html, 'id="site-footer"', "</footer>")


# ---------- The page and the shell ----------


def test_home_renders_inside_the_marketing_shell(home):
    assert 'data-theme="axcenity"' in home
    assert home.index('id="site-nav"') < home.index('id="content"') < home.index('id="site-footer"')
    assert "<h1" in home and "Axcenity Engine." in home


def test_a_skip_link_leads_to_the_content(home):
    assert re.search(r'<a href="#content" class="sr-only focus:not-sr-only', home)
    assert '<main id="content" tabindex="-1">' in home


def test_home_says_alpha_luau_and_the_three_desktops(home):
    hero = _part(home, 'id="hero"', "</section>")
    for phrase in ("alpha", "open-source", "Luau", "Windows, macOS and Linux"):
        assert phrase in hero, phrase


# ---------- The nav ----------


def test_nav_links_in_order(home):
    desktop = _part(_nav(home), '<nav aria-label="Main"', "</nav>")
    labels = re.findall(r'class="(?:soon )?nav-link"[^>]*>([^<]+)<', desktop)
    assert labels == ["Engine", "Features", "Toolbox", "Docs", "Community"]


def test_the_phone_menu_holds_the_same_links_and_sign_in(home):
    menu = _part(_nav(home), '<details class="nav-menu md:hidden">', "</details>")
    assert "<summary" in menu and '<span class="sr-only">Menu</span>' in menu
    labels = re.findall(r'class="(?:soon )?nav-link h-11 self-start"[^>]*>([^<]+)<', menu)
    assert labels == ["Engine", "Features", "Toolbox", "Docs", "Community", "Sign in"]
    # The desktop links hide below md, the menu above it.
    assert '<nav aria-label="Main" class="hidden md:flex' in _nav(home)


def test_the_current_page_is_marked(home):
    marked = re.findall(r'<a [^>]*aria-current="page"[^>]*>([^<]+)<', _nav(home))
    assert set(marked) == {"Engine"}  # Features links into the page, so it's never current


def test_sign_in_links_to_the_sign_in_page_until_signed_in(home, client, django_user_model):
    nav = _nav(home)
    sign_in = reverse("account_login")
    assert len(re.findall(rf'<a href="{sign_in}"[^>]*>Sign in</a>', nav)) == 2  # bar and menu
    assert "Sign in<span" not in nav  # never the "Soon" label any more

    user = django_user_model.objects.create_user("ada", "ada@example.com", "a-Long-pass-7731")
    client.force_login(user)
    nav = _nav(client.get("/").content.decode())
    profile = reverse("accounts:profile")
    assert len(re.findall(rf'<a href="{profile}"[^>]*>Account</a>', nav)) == 2
    assert sign_in not in nav


def test_coming_soon_items_are_never_links(home):
    for link in content.all_links():
        if link.soon:
            assert not re.search(rf"<a [^>]*>{re.escape(link.label)}</a>", home), link.label


def test_download_is_the_only_primary_button_in_the_nav(home):
    nav = _nav(home)
    primaries = re.findall(r'<a href="([^"]+)"[^>]*class="btn btn-primary[^"]*">([^<]+)<', nav)
    assert primaries == [(reverse("marketing:download"), "Download")]


def test_download_links_the_download_page_and_github_links_the_releases_list_not_latest():
    assert content.DOWNLOAD.href == "/download/"
    assert content.RELEASES_URL.endswith("/Axcenity-Engine/releases")
    assert all("releases/latest" not in link.href for link in content.all_links())


def test_nav_is_transparent_until_the_page_scrolls():
    nav = re.search(r"\n#site-nav \{([^}]*)\}", SOURCE).group(1)
    assert "position: fixed;" in nav and "background: transparent;" in nav
    assert "html[data-scrolled] #site-nav, #site-nav:has(.nav-menu[open]) {" in SOURCE
    assert "if (window.scrollY > 40) root.dataset.scrolled" in SHELL_JS
    assert "{ passive: true }" in SHELL_JS


def test_nothing_scrolls_sideways():
    assert "body { overflow-x: clip; }" in SOURCE


# ---------- The footer ----------


def test_footer_has_four_columns(home):
    footer = _footer(home)
    assert "md:grid-cols-[2fr_1fr_1fr_1fr]" in footer
    headings = re.findall(r'<h2 class="micro mb-3 text-fg-weak">([^<]+)</h2>', footer)
    assert headings == ["Engine", "Learn", "Community"]
    assert content.FOOTER_SIGNATURE in footer and "Alpha software" in footer


# ---------- Links ----------


@pytest.mark.parametrize("link", content.all_links(), ids=lambda link: link.label)
def test_every_content_link_resolves_or_is_well_formed(link):
    if link.soon:
        assert link.href == ""
    elif link.url_name:
        assert link.href.startswith("/")
    else:
        parts = urlsplit(link.href)
        assert parts.scheme == "https" and parts.netloc == "github.com", link.href
        repos = [urlsplit(url).path for url in (content.ENGINE_REPO_URL, content.TOOLBOX_REPO_URL)]
        assert any(parts.path == r or parts.path.startswith(r + "/") for r in repos), link.href
        assert " " not in link.href


def test_a_fragment_belongs_to_an_internal_link():
    assert content.Link("Features", url_name="marketing:home", fragment="features").href == (
        "/#features"
    )
    with pytest.raises(ValueError):
        content.Link("Out", external=content.RELEASES_URL, fragment="top")
    with pytest.raises(ValueError):
        content.Link("Out", external=content.RELEASES_URL, args=("learn",))
    with pytest.raises(ValueError):
        content.Link("Out", external=content.RELEASES_URL, section="documentation")


def test_an_internal_link_takes_url_args():
    assert content.GETTING_STARTED.href == "/docs/learn/getting-started/"


def test_a_link_must_have_exactly_one_target():
    with pytest.raises(ValueError):
        content.Link("Nowhere")
    with pytest.raises(ValueError):
        content.Link("Both", url_name="marketing:home", external="https://example.com")
    with pytest.raises(ValueError):
        content.Link("Soon but linked", url_name="marketing:home", soon=True)


def test_every_href_on_the_page_goes_somewhere_real(home):
    ids = set(re.findall(r' id="([^"]+)"', home))
    for href in re.findall(r'href="([^"]+)"', home):
        if href.startswith("/static/"):
            continue
        if href.startswith("https://"):
            assert href.startswith("https://github.com/Axcenity-Studios/"), href
            continue
        parts = urlsplit(href)
        if parts.path:
            resolve(parts.path)  # raises Resolver404 for a dead internal link
        if parts.fragment:
            assert parts.fragment in ids, f"{href}: no element has that id"


# ---------- Branding and fonts ----------


def test_branding_loads_from_static_files(home):
    assert re.search(
        r'<link rel="icon" type="image/png" sizes="32x32" href="[^"]*favicon-32\.png"', home
    )
    assert re.search(
        r'<img src="/static/brand/wordmark-white\.png" alt="Axcenity"[^>]*class="logo-img', home
    )
    for asset in ("brand/favicon-32.png", "brand/wordmark-white.png", "brand/mark-white.png"):
        assert finders.find(asset), f"{asset} is not in static files"


def test_every_font_in_the_stylesheet_is_a_static_file():
    fonts = re.findall(r'url\("\.\./fonts/([^"]+)"\)', SOURCE)
    families = set(re.findall(r'font-family: "([^"]+)"; src:', SOURCE))
    assert families == {"Inter", "JetBrains Mono", "Plus Jakarta Sans"}
    for font in fonts:
        assert finders.find(f"fonts/{font}"), f"fonts/{font} is missing"


def test_each_font_family_ships_its_ofl_licence():
    for licence in ("Inter-OFL.txt", "JetBrainsMono-OFL.txt", "PlusJakartaSans-OFL.txt"):
        path = finders.find(f"fonts/{licence}")
        assert path, licence
        with open(path, encoding="utf-8") as f:
            assert "SIL Open Font License" in f.read()


def test_plus_jakarta_source_is_pinned():
    sources = (settings.BASE_DIR / "static" / "fonts" / "SOURCES.md").read_text(encoding="utf-8")
    assert "8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5" in sources
    assert "89b3fb38aa0d275d7a731d0d817a4f1622b316b4d7fbdedcf02ee9099ff68bc8" in sources


def test_fonts_are_preloaded_and_display_fonts_never_swap_in_late(home):
    head = home.split("</head>", 1)[0]
    for font in (
        "JetBrainsMono-Regular",
        "Inter-Regular",
        "Inter-SemiBold",
        "PlusJakartaSans-Variable",
    ):
        assert re.search(
            rf'<link rel="preload" href="[^"]*fonts/{font}\.ttf" as="font" type="font/ttf" crossorigin>',
            head,
        ), font
    assert head.index('rel="preload"') < head.index("tailwind.css")
    for line in SOURCE.splitlines():
        if line.startswith(
            (
                '@font-face { font-family: "JetBrains Mono"',
                '@font-face { font-family: "Plus Jakarta Sans"',
            )
        ):
            assert "font-display: block;" in line, line


def test_fonts_are_served_as_fonts():
    assert mimetypes.guess_type("static/fonts/JetBrainsMono-Regular.ttf")[0] == "font/ttf"


# ---------- Hover gate, focus and motion ----------


def _selectors_with_hover(css: str) -> list[str]:
    selectors = []
    for rule in re.findall(r"([^{}]+)\{", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        selectors += [s.strip() for s in rule.split(",") if ":hover" in s]
    return selectors


def test_every_hover_style_waits_for_real_pointer_movement():
    """After a click the next page loads under a still cursor; nothing may flip on arrival."""
    hovers = _selectors_with_hover(SOURCE)
    assert hovers
    for selector in hovers:
        assert selector.startswith("html[data-pointer] "), selector
    assert 'addEventListener("pointermove", onMove' in SHELL_JS
    assert 'root.dataset.pointer = ""' in SHELL_JS


def test_one_easing_for_snaps_and_reveals():
    assert "--ease-expo: cubic-bezier(0.16, 1, 0.3, 1);" in SOURCE
    assert "cubic-bezier(" not in SOURCE.replace("--ease-expo: cubic-bezier(0.16, 1, 0.3, 1);", "")


def test_motion_primitives_are_ported():
    assert (
        ".spotlight::before {" in SOURCE
        and "html[data-pointer] .spotlight[data-spot]::before" in SOURCE
    )
    assert 'closest(".spotlight")' in SHELL_JS
    assert "html[data-pointer] .lift:hover { z-index: 2; transform: translateY(-4px);" in SOURCE
    assert ".blur-up { animation: blur-up 0.5s var(--ease-expo) backwards;" in SOURCE
    assert "@keyframes blur-up { from {" in SOURCE


def test_reduced_motion_stops_everything():
    reduced = _part(SOURCE, "@media (prefers-reduced-motion: reduce) {", "\n}")
    assert (
        "*, *::before, *::after { animation: none !important; transition: none !important; "
        "scroll-behavior: auto !important; }" in reduced
    )
    assert ".spotlight::before { display: none; }" in reduced
    assert "reduce.matches" in SHELL_JS  # the spotlight is never lit


def test_every_animation_names_real_keyframes():
    keyframes = set(re.findall(r"@keyframes ([\w-]+)", SOURCE))
    used = set(re.findall(r"animation: ([\w-]+) ", SOURCE)) - {"none"}
    assert used and used <= keyframes


# ---------- Versioned static ----------


def test_the_stylesheet_and_script_carry_a_version(home, tmp_path, settings):
    head = home.split("</head>", 1)[0]
    assert re.search(r'<link rel="stylesheet" href="/static/css/tailwind\.css(\?v=\d+)?">', head)
    assert re.search(r'<script src="/static/js/shell\.js\?v=\d+" defer></script>', head)


def test_versioned_static_follows_the_file_and_skips_missing_ones(tmp_path, settings):
    import os

    from marketing.templatetags.shell_tags import versioned_static

    folder = tmp_path / "static"
    (folder / "js").mkdir(parents=True)
    script = folder / "js" / "probe.js"
    script.write_text("//", encoding="utf-8")
    os.utime(script, (1_700_000_000, 1_700_000_000))
    settings.STATICFILES_DIRS = [folder]
    assert versioned_static("js/probe.js") == "/static/js/probe.js?v=1700000000"
    assert versioned_static("js/missing.js") == "/static/js/missing.js"
