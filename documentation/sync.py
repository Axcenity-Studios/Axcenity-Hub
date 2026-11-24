"""Copying the engine's documentation into the Hub's committed snapshot.

The engine repository is read-only to the Hub, and the snapshot must be exactly
the docs at a commit anyone can check. So `sync`:

1. refuses an engine whose `documentation/` folder has uncommitted changes, and
   resolves and verifies its HEAD commit;
2. reads the folder's files *from that commit's objects* (`git ls-tree`, `git
   cat-file`), never from the working tree, accepting only regular Markdown and
   image files with safe paths;
3. builds the replacement in a temporary folder beside the snapshot, writes
   `SOURCE.json` (repository, commit, its `documentation/` tree hash, object format
   and commit date), and checks it: the files must hash to that very tree
   (`tree_hash`), and the caller's `validate` (the docs' own link and navigation
   checks) must find no problems;
4. leaves the snapshot alone when the result is identical (a re-run changes
   nothing, not even modification times), and otherwise swaps it in with two
   renames, restoring the old one if the second fails.

A failure at any step raises `SyncError`, removes the temporary folder and leaves
the snapshot as it was. Nothing is ever written inside the engine repository.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ENGINE_REPO_URL = "https://github.com/Axcenity-Studios/Axcenity-Engine"
SOURCE_FILE = "SOURCE.json"
# What the snapshot may contain: Markdown, and raster images (SVG can carry script).
ALLOWED_SUFFIXES = frozenset({".md", ".png", ".jpg", ".jpeg", ".webp", ".gif"})
# A path component the snapshot will write: no dot-only names, separators or control characters.
_SAFE_NAME = re.compile(r"^(?!\.{1,2}$)[^\x00-\x1f\x7f/\\:]+$")


class SyncError(Exception):
    """The sync refused to run or its result failed a check; the snapshot is unchanged."""


@dataclass(frozen=True)
class SyncResult:
    """What a sync did: the commit and tree it copied, whether the snapshot changed, and
    how many files it holds (without SOURCE.json)."""

    commit: str
    tree: str
    changed: bool
    files: int


# ---------- Git's object hashes ----------


def _object_hash(kind: bytes, data: bytes, algorithm: str) -> bytes:
    return hashlib.new(algorithm, kind + b" %d\0" % len(data) + data).digest()


def _tree_entries(folder: Path, algorithm: str, exclude: frozenset[str]) -> bytes | None:
    """The body of `folder`'s tree object, or None if it holds no files (git keeps no
    empty trees)."""
    entries = []
    for path in folder.iterdir():
        if path.name in exclude:
            continue
        name = os.fsencode(path.name)
        if path.is_symlink():
            mode, digest = (
                b"120000",
                _object_hash(b"blob", os.fsencode(os.readlink(path)), algorithm),
            )
        elif path.is_dir():
            body = _tree_entries(path, algorithm, frozenset())
            if body is None:
                continue
            mode, digest = b"40000", _object_hash(b"tree", body, algorithm)
            entries.append((name + b"/", mode, name, digest))
            continue
        elif path.is_file():
            executable = path.stat().st_mode & 0o111
            mode = b"100755" if executable else b"100644"
            digest = _object_hash(b"blob", path.read_bytes(), algorithm)
        else:
            raise SyncError(f"{path}: not a file, folder or symlink")
        entries.append((name, mode, name, digest))
    if not entries:
        return None
    # Git sorts by name bytes, comparing a tree's name as if it ended in "/".
    entries.sort(key=lambda entry: entry[0])
    return b"".join(mode + b" " + name + b"\0" + digest for _, mode, name, digest in entries)


def tree_hash(root: Path, *, algorithm: str = "sha1", exclude: frozenset[str] | None = None) -> str:
    """The hash git gives the tree of the files under `root`, as hex.

    Follows git's object format: blobs and trees are hashed with their `blob <size>\\0`
    or `tree <size>\\0` header; entries are `<mode> <name>\\0<raw hash>`, with mode
    100644 for a file, 100755 for an executable one, 120000 for a symlink (its target is
    the blob) and 40000 for a folder; entries sort by name bytes with folders compared as
    `name/`; and folders holding no files are left out. `algorithm` is the repository's
    object format ("sha1" or "sha256"). Top-level names in `exclude` (by default the
    snapshot's SOURCE.json) are skipped.
    """
    skip = frozenset({SOURCE_FILE}) if exclude is None else exclude
    body = _tree_entries(root, algorithm, skip) or b""
    return _object_hash(b"tree", body, algorithm).hex()


# ---------- Reading the engine ----------


def _git(engine: Path, *args: str, stdin: bytes | None = None) -> bytes:
    """Run a read-only git command in `engine` (no optional locks, so not even the index
    is refreshed) and return its output; a failure is a SyncError."""
    completed = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(engine), *args],
        input=stdin,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode(errors="replace").strip()
        raise SyncError(f"git {' '.join(args)}: {message}")
    return completed.stdout


def _read_blobs(engine: Path, objects: list[str]) -> list[bytes]:
    """The contents of `objects`, in order, through one `git cat-file --batch`."""
    output = _git(engine, "cat-file", "--batch", stdin="".join(f"{o}\n" for o in objects).encode())
    blobs, at = [], 0
    for expected in objects:
        header_end = output.index(b"\n", at)
        name, kind, size = output[at:header_end].decode().split()
        if name != expected or kind != "blob":
            raise SyncError(f"{expected}: expected a blob, git gave {kind}")
        start = header_end + 1
        blobs.append(output[start : start + int(size)])
        at = start + int(size) + 1
    return blobs


def _listing(engine: Path, commit: str, folder: str) -> list[tuple[str, str]]:
    """(path inside `folder`, object) for every file in `folder` at `commit`, refusing
    anything that isn't a regular Markdown or image file with a safe path."""
    output = _git(engine, "ls-tree", "-r", "-z", "--full-tree", commit, "--", f"{folder}/")
    files = []
    for record in filter(None, output.split(b"\0")):
        meta, _, raw_path = record.partition(b"\t")
        mode, kind, obj = meta.decode().split()
        path = raw_path.decode("utf-8", errors="strict").removeprefix(f"{folder}/")
        if kind != "blob" or mode != "100644":
            raise SyncError(f"{path}: only regular files are copied (git mode {mode} {kind})")
        if not all(_SAFE_NAME.match(part) for part in path.split("/")):
            raise SyncError(f"{path!r}: not a safe path")
        if Path(path).suffix.lower() not in ALLOWED_SUFFIXES:
            raise SyncError(f"{path}: only Markdown and images are copied")
        if path == SOURCE_FILE:
            raise SyncError(f"{path}: that name is the snapshot's own record")
        files.append((path, obj))
    if not files:
        raise SyncError(f"{folder}/ is empty at {commit}")
    return sorted(files)


def _source(engine: Path, folder: str, repository: str) -> dict[str, str]:
    """The engine's HEAD commit, verified, with its `folder` tree, object format and date;
    refuses uncommitted changes in `folder`."""
    top = Path(_git(engine, "rev-parse", "--show-toplevel").decode().strip())
    if top.resolve() != engine.resolve():
        raise SyncError(f"{engine} is not the top of its git repository ({top})")
    dirty = _git(engine, "status", "--porcelain", "--untracked-files=all", "--", folder)
    if dirty.strip():
        raise SyncError(f"{folder}/ has uncommitted changes:\n{dirty.decode().rstrip()}")
    commit = _git(engine, "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}")
    commit = commit.decode().strip()
    _git(engine, "cat-file", "-e", f"{commit}^{{commit}}")  # the object really exists
    try:
        tree = _git(engine, "rev-parse", "--verify", f"{commit}^{{tree}}:{folder}")
    except SyncError:
        raise SyncError(f"{folder}/ isn't in commit {commit}") from None
    return {
        "repository": repository,
        "folder": folder,
        "commit": commit,
        "tree": tree.decode().strip(),
        "object_format": _git(engine, "rev-parse", "--show-object-format").decode().strip(),
        "committed": _git(engine, "show", "-s", "--format=%cI", commit).decode().strip(),
    }


# ---------- Building and swapping the snapshot ----------


def _files_of(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def _same_snapshot(a: Path, b: Path) -> bool:
    """Whether two snapshots hold the same files with the same bytes (and no extra folders)."""
    folders = lambda root: {p.relative_to(root) for p in root.rglob("*") if p.is_dir()}  # noqa: E731
    return _files_of(a) == _files_of(b) and folders(a) == folders(b)


def _swap(new: Path, dest: Path) -> None:
    """Put `new` at `dest`: two renames on one filesystem, with the old snapshot restored if
    the second fails."""
    if not dest.exists():
        new.rename(dest)
        return
    backup = Path(tempfile.mkdtemp(prefix=f".{dest.name}.old-", dir=dest.parent))
    backup.rmdir()
    dest.rename(backup)
    try:
        new.rename(dest)
    except BaseException:
        backup.rename(dest)
        raise
    shutil.rmtree(backup)


def sync(
    engine: Path,
    dest: Path,
    *,
    folder: str = "documentation",
    repository: str = ENGINE_REPO_URL,
    validate: Callable[[Path], list[str]] | None = None,
) -> SyncResult:
    """Replace the snapshot at `dest` with `engine`'s `folder` at its HEAD commit.

    `validate(root)` runs on the finished replacement before it's swapped in; any problem
    it returns aborts the sync. See the module docstring for every check.
    """
    engine, dest = Path(engine).resolve(), Path(dest).absolute()
    if dest.resolve().is_relative_to(engine) or engine.is_relative_to(dest.resolve()):
        raise SyncError(f"the snapshot ({dest}) and the engine ({engine}) must not overlap")

    source = _source(engine, folder, repository)
    files = _listing(engine, source["commit"], folder)
    blobs = _read_blobs(engine, [obj for _, obj in files])

    dest.parent.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix=f".{dest.name}.sync-", dir=dest.parent))
    try:
        for (path, _), data in zip(files, blobs, strict=True):
            target = build / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o644)
        record = json.dumps(source, indent=2, sort_keys=True) + "\n"
        (build / SOURCE_FILE).write_text(record, encoding="utf-8")

        built = tree_hash(build, algorithm=source["object_format"])
        if built != source["tree"]:
            raise SyncError(f"the copy hashes to {built}, not {folder}'s tree {source['tree']}")
        problems = validate(build) if validate else []
        if problems:
            raise SyncError("the new snapshot fails its checks:\n" + "\n".join(problems))

        changed = not (dest.exists() and _same_snapshot(build, dest))
        if changed:
            _swap(build, dest)
        return SyncResult(source["commit"], source["tree"], changed, len(files))
    finally:
        if build.exists():
            shutil.rmtree(build)
