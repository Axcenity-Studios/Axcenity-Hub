"""Credits: the generated crate and package lists (marketing/credits.py), the command that
refreshes them from a fake engine repository, the committed lists against both lock files,
and the /credits/ page (docs/frontend/credits.md)."""

import json
import re
import subprocess
import tomllib
from html import unescape
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils.html import escape

from marketing import content, credits
from tests.test_documentation import commit_all, fingerprint, git

ENGINE_DIR = Path(settings.AXCENITY_ENGINE_DIR)
URL = "/credits/"
MEMBER = "core 0.1.0 (path+file:///engine/crates/core)"


def _crate(
    name,
    version,
    license="MIT",
    *,
    source="registry+https://github.com/rust-lang/crates.io-index",
    **extra,
):
    return {
        "id": f"{name} {version} ({source or 'path+file:///engine/vendor/' + name})",
        "name": name,
        "version": version,
        "license": license,
        "authors": extra.pop("authors", []),
        "repository": extra.pop("repository", None),
        "homepage": extra.pop("homepage", None),
        "source": source,
    }  # fmt: skip


def _meta(*crates, unresolved=()):
    packages = [{"id": MEMBER, "name": "core", "version": "0.1.0", "source": None}, *crates]
    nodes = [{"id": p["id"]} for p in packages if p["name"] not in unresolved]
    return {"workspace_members": [MEMBER], "packages": packages, "resolve": {"nodes": nodes}}


def _lock(*entries, member=True):
    """A Cargo.lock: each entry "name version", from the registry unless it ends " path"."""
    body = ["version = 4\n"]
    if member:
        body.append('[[package]]\nname = "core"\nversion = "0.1.0"\n')
    for entry in entries:
        name, version, *path = entry.split()
        source = (
            "" if path else 'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
        )
        body.append(f'[[package]]\nname = "{name}"\nversion = "{version}"\n{source}')
    return "\n".join(body)


# ---------- Licences and authors ----------


@pytest.mark.parametrize(
    ("expression", "label"),
    [
        ("MIT/Apache-2.0", "Apache-2.0 OR MIT"),
        ("Apache-2.0 / MIT", "Apache-2.0 OR MIT"),
        ("MIT OR Apache-2.0", "Apache-2.0 OR MIT"),
        ("Zlib OR Apache-2.0 OR MIT", "Apache-2.0 OR MIT OR Zlib"),
        ("MIT OR MIT", "MIT"),
        ("  MIT  ", "MIT"),
        ("(MIT OR Apache-2.0) AND Unicode-3.0", "(MIT OR Apache-2.0) AND Unicode-3.0"),
        ("Apache-2.0 WITH LLVM-exception OR MIT", "Apache-2.0 WITH LLVM-exception OR MIT"),
        ("", ""),
    ],
)
def test_each_licence_choice_has_one_spelling(expression, label):
    assert credits.license_label(expression) == label


def test_authors_are_credited_by_name_without_their_email_addresses():
    assert credits.names(["Ann Lee <ann@example.com>", "Bo", "Bo", "<x@y.z>"]) == ["Ann Lee", "Bo"]
    assert credits.names('"Ann, Lee" <a@b.c>, Bo <b@c.d>') == ["Ann, Lee", "Bo"]
    assert credits.names("team@example.com") == []
    assert credits.names(None) == []


# ---------- The engine's crates ----------


def test_every_resolved_crate_is_credited_and_the_unbuilt_ones_are_recorded():
    meta = _meta(
        _crate("serde", "1.0.0", "MIT/Apache-2.0", authors=["Erick <e@x.y>"], repository="https://github.com/serde-rs/serde"),
        _crate("tiny", "0.1.0", "Zlib", homepage="https://tiny.example"),
        _crate("bare", "2.0.0"),
        _crate("rapier3d", "0.36.1", "Apache-2.0", source=None),
        _crate("ghost", "0.1.0"),
        unresolved={"ghost"},
    )  # fmt: skip
    lock = _lock("serde 1.0.0", "tiny 0.1.0", "bare 2.0.0", "rapier3d 0.36.1 path", "loom 0.7.3")
    crates, unbuilt = credits.engine_crates(meta, lock)
    assert [c["name"] for c in crates] == ["bare", "rapier3d", "serde", "tiny"]
    by_name = {c["name"]: c for c in crates}
    assert by_name["serde"] == {
        "name": "serde",
        "version": "1.0.0",
        "license": "Apache-2.0 OR MIT",
        "authors": ["Erick"],
        "url": "https://github.com/serde-rs/serde",
    }
    assert by_name["tiny"]["url"] == "https://tiny.example"
    assert by_name["bare"]["url"] == "https://crates.io/crates/bare"
    assert by_name["rapier3d"]["vendored"] is True
    assert "core" not in by_name and "ghost" not in by_name  # the engine's own; never built
    assert unbuilt == ["loom 0.7.3"]


def test_the_crate_list_refuses_metadata_the_lock_file_does_not_match():
    with pytest.raises(credits.CreditsError, match="Cargo.lock doesn't"):
        credits.engine_crates(_meta(_crate("serde", "1.0.1")), _lock("serde 1.0.0"))
    with pytest.raises(credits.CreditsError, match="without a licence"):
        credits.engine_crates(_meta(_crate("serde", "1.0.0", "")), _lock("serde 1.0.0"))


# ---------- The Hub's packages ----------

HUB_LOCK = """
version = 1

[[package]]
name = "hub"
version = "0.1.0"
source = { virtual = "." }
dependencies = [{ name = "django" }, { name = "allauth", extra = ["mfa"] }]

[package.dev-dependencies]
dev = [{ name = "pytest" }]

[[package]]
name = "django"
version = "6.1"
dependencies = [{ name = "asgiref" }]

[[package]]
name = "asgiref"
version = "3.13"

[[package]]
name = "allauth"
version = "65.0"

[package.optional-dependencies]
mfa = [{ name = "fido2" }]

[[package]]
name = "fido2"
version = "2.2"

[[package]]
name = "pytest"
version = "9.2"
dependencies = [{ name = "colorama" }]

[[package]]
name = "colorama"
version = "0.4.6"
"""


class FakeMeta(dict):
    def get_all(self, key):
        value = self.get(key)
        return value if isinstance(value, list) else None


INSTALLED = {
    "django": FakeMeta(
        {"License-Expression": "BSD-3-Clause", "Author-email": "Django Software Foundation <f@d.p>",
         "Project-URL": ["Homepage, https://www.djangoproject.com/", "Source, https://github.com/django/django"]}
    ),
    "asgiref": FakeMeta({"License": "BSD-3-Clause", "Author": "Django Software Foundation"}),
    "allauth": FakeMeta({"License": "MIT", "Maintainer-email": "Raymond <r@p.n>", "Home-page": "https://allauth.org"}),
    # The whole licence text in License: the classifiers say what it is.
    "fido2": FakeMeta(
        {"License": "Copyright (c) 2018 Yubico AB\nAll rights reserved.", "Author": "Dain Nilsson",
         "Classifier": ["License :: OSI Approved :: BSD License", "License :: OSI Approved :: MIT License"]}
    ),
    "pytest": FakeMeta({"License": "MIT", "Author": "Holger Krekel, Bruno Oliveira"}),
}  # fmt: skip


def _installed(name):
    if name not in INSTALLED:
        raise credits.metadata.PackageNotFoundError(name)
    return INSTALLED[name]


def test_the_hubs_packages_are_grouped_by_what_uses_them_with_their_metadata():
    packages = {p["name"]: p for p in credits.hub_packages(HUB_LOCK, installed=_installed)}
    assert sorted(packages) == ["allauth", "asgiref", "colorama", "django", "fido2", "pytest"]
    groups = {name: p["group"] for name, p in packages.items()}
    assert groups == {
        "django": "runtime", "asgiref": "runtime", "allauth": "runtime", "fido2": "runtime",
        "pytest": "development", "colorama": "development",
    }  # fmt: skip
    assert packages["django"]["url"] == "https://github.com/django/django"
    assert packages["django"]["authors"] == ["Django Software Foundation"]
    assert packages["allauth"]["authors"] == ["Raymond"]
    assert packages["allauth"]["url"] == "https://allauth.org"
    assert packages["asgiref"]["url"] == "https://pypi.org/project/asgiref/"
    assert packages["fido2"]["license"] == "BSD License OR MIT"
    assert packages["pytest"]["authors"] == ["Holger Krekel", "Bruno Oliveira"]
    # Not installed on this system: filled from credits.PACKAGE_FILLS.
    assert packages["colorama"]["license"] == credits.PACKAGE_FILLS["colorama"]["license"]


def test_a_package_with_no_metadata_and_no_fill_stops_the_refresh():
    lock = HUB_LOCK.replace('name = "colorama"', 'name = "mystery"').replace(
        '{ name = "colorama" }', '{ name = "mystery" }'
    )
    with pytest.raises(credits.CreditsError, match="mystery"):
        credits.hub_packages(lock, installed=_installed)


# ---------- The command, against a fake engine ----------

NOTICE = (
    "Fake Engine\nCopyright 2026 Someone\n\nThird-party code\n----------------\nA.\n\n---\nB.\n"
)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """A git repository shaped like the engine, and Cargo's metadata for it (no cargo run)."""
    repo = tmp_path / "engine"
    repo.mkdir()
    (repo / "LICENSE").write_text("Apache License\n")
    (repo / "NOTICE").write_text(NOTICE)
    (repo / "Cargo.toml").write_text("[workspace]\n")
    (repo / "Cargo.lock").write_text(_lock("serde 1.0.0", "rapier3d 0.36.1 path"))
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    commit_all(repo, "Engine")
    meta = _meta(_crate("serde", "1.0.0"), _crate("rapier3d", "0.36.1", "Apache-2.0", source=None))
    monkeypatch.setattr(credits, "cargo_metadata", lambda path: meta)
    monkeypatch.setattr(credits, "tailwind_versions", lambda: {"tailwindcss": "4.3.5"})
    return repo


def test_refresh_copies_the_engine_at_head_writes_both_lists_and_changes_nothing_when_rerun(
    engine, tmp_path
):
    out = tmp_path / "legal"
    out.mkdir()
    before = fingerprint(engine)
    result = credits.refresh(engine, legal_dir=out)
    assert (out / "NOTICE").read_text() == NOTICE
    assert (out / "LICENSE").read_text() == "Apache License\n"
    data = json.loads((out / "engine.json").read_text())
    assert data["commit"] == git(engine, "rev-parse", "HEAD") == result.commit
    assert [c["name"] for c in data["crates"]] == ["rapier3d", "serde"]
    assert data["unbuilt"] == []
    hub = json.loads((out / "hub.json").read_text())
    assert hub["tools"] == {"tailwindcss": "4.3.5"}
    assert {p["name"] for p in hub["packages"]} == _hub_locked_names()
    assert result.added == ["rapier3d 0.36.1", "serde 1.0.0"] and result.removed == []
    # Nothing is written in the engine, and a re-run rewrites nothing.
    assert fingerprint(engine) == before
    written = fingerprint(out)
    again = credits.refresh(engine, legal_dir=out)
    assert fingerprint(out) == written and again.added == again.removed == []


def test_refresh_refuses_an_engine_with_uncommitted_credits_and_writes_nothing(engine, tmp_path):
    out = tmp_path / "legal"
    out.mkdir()
    (engine / "NOTICE").write_text(NOTICE + "\n---\nAn entry still being written.\n")
    with pytest.raises(credits.CreditsError, match="commit these in the engine first"):
        credits.refresh(engine, legal_dir=out)
    assert list(out.iterdir()) == []
    (engine / "crates").mkdir()
    with pytest.raises(credits.CreditsError, match="not the top"):
        credits.refresh(engine / "crates", legal_dir=out)


def test_the_command_reports_the_refresh_and_refuses_with_nothing_changed(
    engine, tmp_path, monkeypatch, capsys
):
    out = tmp_path / "legal"
    out.mkdir()
    monkeypatch.setattr(credits, "LEGAL_DIR", out)
    call_command("refresh_credits", "--engine", str(engine))
    printed = capsys.readouterr().out
    assert "New crates (2): rapier3d 0.36.1, serde 1.0.0" in printed
    assert f"Credits at engine {git(engine, 'rev-parse', 'HEAD')[:12]}: 2 crates" in printed
    (engine / "Cargo.lock").write_text(_lock("serde 1.0.1"))
    with pytest.raises(CommandError, match="Nothing changed: commit these"):
        call_command("refresh_credits", "--engine", str(engine))


# ---------- The committed lists ----------


def _hub_locked() -> set[tuple[str, str]]:
    lock = tomllib.loads((settings.BASE_DIR / "uv.lock").read_text())
    return {
        (p["name"], p["version"])
        for p in lock["package"]
        if p.get("source", {}).get("virtual") != "."
    }


def _hub_locked_names() -> set[str]:
    return {name for name, _ in _hub_locked()}


def test_every_package_in_the_hubs_lock_file_is_credited():
    """Fails after `uv add` or `uv lock` until `manage.py refresh_credits` is run."""
    listed = {(p["name"], p["version"]) for p in content.HUB_CREDITS["packages"]}
    assert listed == _hub_locked(), "run manage.py refresh_credits"
    assert {p["group"] for p in content.HUB_CREDITS["packages"]} == {"runtime", "development"}


@pytest.mark.skipif(not ENGINE_DIR.exists(), reason="the engine's checkout isn't on this machine")
def test_every_crate_in_the_engines_lock_file_is_credited():
    """Against the engine's last commit: fails when its dependencies change until
    `manage.py refresh_credits` is run."""
    lock = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(ENGINE_DIR), "show", "HEAD:Cargo.lock"],
        capture_output=True,
        check=True,
    ).stdout.decode()
    crates = content.ENGINE_CREDITS["crates"]
    listed = {(c["name"], c["version"]) for c in crates if not c.get("vendored")}
    unbuilt = {tuple(entry.split(" ", 1)) for entry in content.ENGINE_CREDITS["unbuilt"]}
    assert listed | unbuilt == credits._locked(lock), "run manage.py refresh_credits"
    for crate in crates:
        if crate.get("vendored"):
            assert (ENGINE_DIR / "vendor" / crate["name"]).is_dir(), crate["name"]


def test_every_credited_crate_and_package_has_a_licence_and_a_link():
    entries = [*content.ENGINE_CREDITS["crates"], *content.HUB_CREDITS["packages"]]
    assert len(content.ENGINE_CREDITS["crates"]) > 700
    for entry in entries:
        assert entry["license"], entry["name"]
        assert re.fullmatch(r"https?://[^\s\"'<>]+", entry["url"]), entry
        assert all("@" not in author for author in entry["authors"]), entry["name"]
    assert re.fullmatch(r"[0-9a-f]{40}", content.LEGAL_COMMIT)


# ---------- The page ----------


def _section(html: str, key: str) -> str:
    return html.split(f'data-credits="{key}"', 1)[1].split("</section>", 1)[0]


def test_the_credits_page_lists_every_crate_package_and_font(client):
    response = client.get(URL)
    assert response.status_code == 200
    assert reverse("marketing:credits") == URL
    html = response.content.decode()
    assert "<title>Credits · Axcenity</title>" in html
    assert html.count("<h1") == 1
    crates = _section(html, "crates")
    for crate in content.ENGINE_CREDITS["crates"]:
        link = f'<a href="{escape(crate["url"])}" rel="noopener" class="cr-name">{escape(crate["name"])}</a>'
        assert f'{link} <span class="cr-version">{escape(crate["version"])}</span>' in crates, crate
        for author in crate["authors"]:
            assert escape(author) in crates
    groups = credits.by_license(content.ENGINE_CREDITS["crates"])
    assert crates.count('<details class="cr-group"') == len(groups)
    assert crates.count('<details class="cr-group" open>') == 1  # the most used licence
    assert f'<span class="cr-license">{escape(groups[0]["license"])}</span>' in crates
    assert "Patched copy in the engine&#x27;s vendor/" in crates
    hub = _section(html, "hub")
    for package in content.HUB_CREDITS["packages"]:
        assert (
            f'<a href="{escape(package["url"])}" rel="noopener">{escape(package["name"])}</a>'
            in hub
        )
    for asset in content.CREDITS_PAGE["sections"]["hub"]["assets"]:
        assert f'rel="noopener" class="cr-name">{escape(asset["name"])}</a>' in hub
    for title in ("Runs the site", "Builds and tests it", "Fonts and styles"):
        assert title in hub
    assert f"commit {content.LEGAL_COMMIT[:12]}" in html


def test_the_credits_page_shows_the_engines_notice_word_for_word_with_its_dividers(client):
    html = client.get(URL).content.decode()
    notice = _section(html, "notice").split("\n    </div>", 1)[0]
    shown = unescape(re.sub(r"<[^>]+>", " ", notice.split(">", 1)[1])).split()
    words = [w for w in content.ENGINE_NOTICE.split() if not re.fullmatch(r"[-=]{3,}", w)]
    assert shown == words
    assert notice.count('<hr class="dl-legal-rule">') == content.ENGINE_NOTICE.count("\n---\n")
    source = (
        f"https://github.com/Axcenity-Studios/Axcenity-Engine/blob/{content.LEGAL_COMMIT}/NOTICE"
    )
    assert f'href="{source}"' in html


def test_the_credits_page_is_linked_from_the_footer_and_never_runs_a_subprocess(
    client, monkeypatch
):
    def no_subprocess(*args, **kwargs):
        raise AssertionError("a page ran a subprocess")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    for path in ("/", URL):
        html = client.get(path).content.decode()
        footer = html.split('id="site-footer"', 1)[1]
        assert f'href="{URL}"' in footer
    assert 'aria-current="page">Credits</a>' in client.get(URL).content.decode()
