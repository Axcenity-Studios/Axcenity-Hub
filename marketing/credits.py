"""Who made what Axcenity Engine and the Hub are built from: the lists behind /credits/.

The lists are generated, never typed. `manage.py refresh_credits` (`refresh`):

1. refuses an engine whose LICENSE, NOTICE, Cargo.toml or Cargo.lock has uncommitted
   changes, and copies LICENSE and NOTICE from its HEAD commit's objects;
2. reads every crate's name, version, licence, authors and repository from `cargo
   metadata --all-features --locked --offline` (no network), and checks them against HEAD's Cargo.lock:
   every crate it lists must be locked, and the locked crates it never resolves (behind
   a cfg no build sets) are recorded as `unbuilt`;
3. walks the Hub's uv.lock from the project's dependencies and its dev group, and reads
   each package's licence, authors and home page from its installed metadata (or
   `PACKAGE_FILLS` for one that isn't installed on this machine);
4. writes `marketing/legal/engine.json` and `hub.json`, sorted, so a re-run with nothing
   new changes nothing.

Tests compare the files with the engine's Cargo.lock (when it's checked out) and the
Hub's uv.lock, so a dependency added on either side fails the suite until this is re-run.
Nothing is written inside the engine repository.
"""

import json
import re
import subprocess
import tomllib
from collections import Counter
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

LEGAL_DIR = Path(__file__).resolve().parent / "legal"
HUB_LOCK = Path(__file__).resolve().parent.parent / "uv.lock"
ENGINE_FILES = ("LICENSE", "NOTICE")
# The engine files whose changes the copy must not miss.
ENGINE_WATCHED = (*ENGINE_FILES, "Cargo.toml", "Cargo.lock")
TAILWIND_DIR = Path(__file__).resolve().parent.parent / ".django_tailwind_cli"

# Packages uv.lock lists for another system (Windows), so their metadata isn't installed
# here: their licence, authors and home page, from their PyPI pages.
PACKAGE_FILLS = {
    "colorama": {
        "license": "BSD-3-Clause",
        "authors": ["Jonathan Hartley"],
        "url": "https://github.com/tartley/colorama",
    },
    "tzdata": {
        "license": "Apache-2.0",
        "authors": ["Python Software Foundation"],
        "url": "https://github.com/python/tzdata",
    },
}


# Trove classifiers that name exactly one SPDX licence ("BSD License" names no clause
# count and "Apache Software License" no version, so they're shown as written).
CLASSIFIER_LICENSES = {
    "MIT License": "MIT",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "ISC License (ISCL)": "ISC",
}


class CreditsError(Exception):
    """The refresh refused to run or a check failed; no file was written."""


@dataclass(frozen=True)
class Refreshed:
    commit: str
    crates: int
    packages: int
    added: list[str]
    removed: list[str]


# ---------- Licences and authors ----------


def license_label(expression: str) -> str:
    """One spelling per licence choice: "MIT/Apache-2.0", "Apache-2.0 / MIT" and
    "MIT OR Apache-2.0" are all "Apache-2.0 OR MIT". Expressions with AND, WITH or
    brackets are kept as written, spaces tidied."""
    text = " ".join(re.sub(r"\s*/\s*", " OR ", expression.strip()).split())
    if not text or re.search(r"\b(AND|WITH)\b|[()]", text):
        return text
    choices = dict.fromkeys(part.strip() for part in text.split(" OR "))
    return " OR ".join(sorted(choices, key=str.casefold))


def names(authors: list[str] | str | None) -> list[str]:
    """People and organisations without their email addresses: "Ann <a@b.c>" is "Ann"."""
    if not authors:
        return []
    if isinstance(authors, str):
        # Split at commas outside "quoted names" and <addresses>.
        authors = re.findall(r'(?:"[^"]*"|<[^>]*>|[^,"<])+', authors)
    found = []
    for author in authors:
        name = re.sub(r"<[^>]*>", "", author).strip().strip('"').strip()
        if name and "@" not in name and name not in found:
            found.append(name)
    return found


# ---------- The engine ----------


def _run(command: list[str], cwd: Path) -> bytes:
    """Run a read-only command; a failure is a CreditsError."""
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, check=False)
    except FileNotFoundError as error:
        raise CreditsError(f"{command[0]} isn't installed") from error
    if done.returncode != 0:
        message = done.stderr.decode(errors="replace").strip()
        raise CreditsError(f"{' '.join(command[:3])}: {message}")
    return done.stdout


def _git(engine: Path, *args: str) -> bytes:
    return _run(["git", "--no-optional-locks", "-C", str(engine), *args], engine)


def cargo_metadata(engine: Path) -> dict:
    """The engine's packages as Cargo resolves them from its lock file, offline, with every
    feature on, so a crate only an optional feature pulls in (a profiler) is credited too."""
    output = _run(
        ["cargo", "metadata", "--format-version", "1", "--all-features", "--locked", "--offline"],
        engine,
    )
    return json.loads(output)


def _locked(lock_text: str) -> set[tuple[str, str]]:
    """The (name, version) of every package in a Cargo.lock that isn't the engine's own
    (a registry or git source, or a vendored copy under vendor/)."""
    return {
        (package["name"], package["version"])
        for package in tomllib.loads(lock_text).get("package", [])
        if "source" in package
    }


def engine_crates(meta: dict, lock_text: str) -> tuple[list[dict], list[str]]:
    """The engine's third-party crates, from `cargo metadata`, checked against Cargo.lock,
    and the locked crates Cargo resolves for no build ("name version"), which aren't in
    the engine (a lock file also keeps crates behind cfgs nothing sets, such as loom).

    A crate under vendor/ (a patched copy, used through [patch.crates-io]) is marked
    `vendored`; its crates.io release has no `source` in Cargo.lock, so it's matched by
    name and version from Cargo metadata instead."""
    members = set(meta["workspace_members"])
    used = {node["id"] for node in meta["resolve"]["nodes"]}
    crates = []
    for package in meta["packages"]:
        if package["id"] in members or package["id"] not in used:
            continue
        source = package.get("source") or ""
        vendored = not source
        crates.append(
            {
                "name": package["name"],
                "version": package["version"],
                "license": license_label(package.get("license") or ""),
                "authors": names(package.get("authors")),
                "url": package.get("repository")
                or package.get("homepage")
                or f"https://crates.io/crates/{package['name']}",
                **({"vendored": True} if vendored else {}),
            }
        )
    crates.sort(key=lambda crate: (crate["name"].casefold(), crate["version"]))
    registry = {(c["name"], c["version"]) for c in crates if not c.get("vendored")}
    locked = _locked(lock_text)
    extra = sorted(f"{n} {v}" for n, v in registry - locked)
    if extra:
        raise CreditsError(f"cargo metadata lists crates Cargo.lock doesn't: {extra[:5]}")
    unlicensed = [c["name"] for c in crates if not c["license"]]
    if unlicensed:
        raise CreditsError(f"crates without a licence in their metadata: {unlicensed}")
    # Locked but never resolved for any build (e.g. only under cfg(loom)): not in the engine.
    unbuilt = sorted((f"{n} {v}" for n, v in locked - registry), key=str.casefold)
    return crates, unbuilt


def engine_head(engine: Path) -> str:
    """The engine's HEAD commit; refuses uncommitted changes to the files the copy reads."""
    top = Path(_git(engine, "rev-parse", "--show-toplevel").decode().strip())
    if top.resolve() != engine.resolve():
        raise CreditsError(f"{engine} is not the top of its git repository ({top})")
    dirty = _git(engine, "status", "--porcelain", "--", *ENGINE_WATCHED).decode().rstrip()
    if dirty:
        raise CreditsError(f"commit these in the engine first:\n{dirty}")
    return _git(engine, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()


# ---------- The Hub ----------


def _license_of(meta) -> str:
    """A package's licence: its SPDX expression, a short License field, or its classifiers
    (some packages put the whole licence text in License)."""
    expression = meta.get("License-Expression")
    if expression:
        return license_label(expression)
    field = (meta.get("License") or "").strip()
    if field and "\n" not in field and len(field) <= 40 and not field.startswith("Copyright"):
        return license_label(field)
    classifiers = [
        CLASSIFIER_LICENSES.get(name, name)
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::") and c.count("::") >= 2
        for name in [c.rsplit("::", 1)[1].strip()]
    ]
    return " OR ".join(dict.fromkeys(classifiers))


def _url_of(meta) -> str:
    urls = {}
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        urls[label.strip().casefold()] = url.strip()
    for label in ("source", "source code", "repository", "github", "homepage", "home"):
        if urls.get(label):
            return urls[label]
    return meta.get("Home-page") or ""


def _closure(lock: dict, roots: list[dict]) -> set[str]:
    """Every package reachable from `roots` (uv.lock dependency entries), extras included."""
    packages = {package["name"]: package for package in lock["package"]}
    seen: set[str] = set()
    todo = list(roots)
    while todo:
        entry = todo.pop()
        name = entry["name"]
        package = packages[name]
        extras = [
            dep
            for extra in entry.get("extra", [])
            for dep in package.get("optional-dependencies", {}).get(extra, [])
        ]
        if name in seen and not extras:
            continue
        seen.add(name)
        todo += package.get("dependencies", []) + extras
    return seen


def hub_packages(lock_text: str, installed=metadata.metadata) -> list[dict]:
    """The Hub's Python packages from uv.lock, each with its group ("runtime" or
    "development") and its licence, authors and home page."""
    lock = tomllib.loads(lock_text)
    project = next(p for p in lock["package"] if p.get("source", {}).get("virtual") == ".")
    runtime = _closure(lock, project.get("dependencies", []))
    development = _closure(
        lock, [d for group in project.get("dev-dependencies", {}).values() for d in group]
    )
    found, unknown = [], []
    for package in lock["package"]:
        name = package["name"]
        if package is project:
            continue
        try:
            meta = installed(name)
        except metadata.PackageNotFoundError:
            meta = None
        if meta is not None:
            authors = names(meta.get("Author") or meta.get("Author-email"))
            if not authors:
                authors = names(meta.get("Maintainer") or meta.get("Maintainer-email"))
            facts = {"license": _license_of(meta), "authors": authors, "url": _url_of(meta)}
        elif name in PACKAGE_FILLS:
            facts = dict(PACKAGE_FILLS[name])
        else:
            unknown.append(name)
            continue
        if not facts["url"]:
            facts["url"] = f"https://pypi.org/project/{name}/"
        group = "runtime" if name in runtime else "development" if name in development else ""
        found.append({"name": name, "version": package["version"], "group": group, **facts})
    if unknown:
        raise CreditsError(
            f"not installed here and not in credits.PACKAGE_FILLS: {unknown}. Add each one's "
            "licence, authors and home page from its PyPI page."
        )
    unlicensed = [p["name"] for p in found if not p["license"]]
    if unlicensed:
        raise CreditsError(f"packages without a licence in their metadata: {unlicensed}")
    return sorted(found, key=lambda package: package["name"])


def tailwind_versions(folder: Path = TAILWIND_DIR) -> dict[str, str]:
    """The Tailwind CSS and daisyUI versions django-tailwind-cli downloaded, or {}."""
    versions = {}
    binaries = sorted(folder.glob("tailwindcss-*")) if folder.is_dir() else []
    if binaries:
        versions["tailwindcss"] = binaries[-1].name.rsplit("-", 1)[-1].removesuffix(".exe")
    daisy = folder / "daisyui.version"
    if daisy.is_file():
        versions["daisyui"] = daisy.read_text().strip()
    return versions


# ---------- Writing and reading ----------


def _write(path: Path, data) -> bool:
    text = data if isinstance(data, str) else json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def refresh(engine: Path, legal_dir: Path | None = None, hub_lock: Path | None = None) -> Refreshed:
    """Copy the engine's LICENSE and NOTICE and regenerate both lists (see the module).
    Every check runs before the first file is written."""
    legal_dir = legal_dir or LEGAL_DIR
    hub_lock = hub_lock or HUB_LOCK
    commit = engine_head(engine)
    texts = {name: _git(engine, "show", f"{commit}:{name}").decode() for name in ENGINE_FILES}
    lock_text = _git(engine, "show", f"{commit}:Cargo.lock").decode()
    crates, unbuilt = engine_crates(cargo_metadata(engine), lock_text)
    packages = hub_packages(hub_lock.read_text(encoding="utf-8"))
    old = load(legal_dir / "engine.json").get("crates", [])
    before = {f"{c['name']} {c['version']}" for c in old}
    after = {f"{c['name']} {c['version']}" for c in crates}
    for name, text in texts.items():
        _write(legal_dir / name, text)
    _write(legal_dir / "engine.json", {"commit": commit, "crates": crates, "unbuilt": unbuilt})
    hub = {"packages": packages}
    tools = tailwind_versions() or load(legal_dir / "hub.json").get("tools", {})
    if tools:
        hub["tools"] = tools
    _write(legal_dir / "hub.json", hub)
    return Refreshed(
        commit, len(crates), len(packages), sorted(after - before), sorted(before - after)
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def by_license(entries: list[dict]) -> list[dict]:
    """Entries grouped under their licence, the most used licence first."""
    counts = Counter(entry["license"] for entry in entries)
    order = sorted(counts, key=lambda label: (-counts[label], label.casefold()))
    return [
        {"license": label, "entries": [e for e in entries if e["license"] == label]}
        for label in order
    ]
