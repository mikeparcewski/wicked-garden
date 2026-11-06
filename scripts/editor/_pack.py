#!/usr/bin/env python3
"""Shared helpers for the editor-plugin scripts (scaffold, pin, conformance, install).

An editor plugin is a ``wicked-pack.json`` spec-2 pack (DES-artifact-editor-plugins §5.2): the
manifest lists ``editors[]``, each with ONE self-contained HTML ``entry`` inside the pack and that
file's full sha256. These helpers read such a pack; none of them writes outside the pack directory.
Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

MANIFEST_NAME = "wicked-pack.json"
# The editor id and pack name shape (garden's kebab names, <= 64); `wicked`/`wicked-*` is reserved
# for the editors that ship inside studio and is refused in every pack (schema, PK061).
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_RE = re.compile(r"^wicked(?:$|-)")
KIND_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SIZES = ("inline", "pane", "full")
# §6.1's permission table, with the plain words the install sheet shows.
PERMISSIONS = {
    "artifact.read": "to read the artifact it opens",
    "artifact.write": "to change it, as new versions you can undo",
    "selection.chip": "to point at parts of it in your message box",
    "composer.draft": "to suggest what to ask the helpers (you send it)",
    "checks.read": "to see the checks and their evidence",
    "checks.contribute": "to point things out, marked as its own notes",
    "sources.read": "to see the sources attached to it",
    "media.read": "to play the recording",
    "artifact.export": "to download it",
    "ui.fullscreen": "to go full screen",
    "network.media": "to load images and fonts from the internet",
    # Granted only by this build's install consent (no steering rule allows it); never a write grant.
    "mcp.session": "to start and talk to the MCP servers you connect it to",
    # Protocol 2 `theme.set` (DES-EDITOR-PLUGIN-CONTRACT-001 §7.2): a write, versioned and undoable.
    "artifact.theme": "to change its theme, as new versions you can undo",
}
# Permissions the install consent itself grants (crew writes the build's token into EDITOR-GRANTS),
# each with the line the consent gate shows.
INSTALL_GRANTED = {"mcp.session": "This plugin can start and talk to MCP servers"}
HOST_BUNDLE_CAP = 5 * 1024 * 1024
# A manifest is a few KB; the engine's host run refuses a bigger one before it is read.
MANIFEST_CAP = 1024 * 1024
# Directories a run's worktree search never enters.
SKIP_DIRS = {"node_modules", "dist", ".git"}


class PackError(Exception):
    """A pack that cannot be read as an editor pack, with the reason."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(pack: Path, cap: int | None = None) -> dict:
    """The pack's manifest. ``cap`` (the engine's host run): a manifest bigger than it is refused unread."""
    path = pack / MANIFEST_NAME
    if not path.is_file():
        raise PackError(f"{pack} holds no {MANIFEST_NAME}")
    if cap is not None and path.stat().st_size > cap:
        raise PackError(f"{path} is over {cap} bytes")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise PackError(f"{path} is not JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise PackError(f"{path} is not a JSON object")
    return manifest


def editors_of(manifest: dict) -> list[dict]:
    editors = manifest.get("editors")
    if manifest.get("spec") != 2 or not isinstance(editors, list) or not editors:
        raise PackError("the pack declares no editors (wicked-pack.json spec 2 `editors[]`)")
    return [e for e in editors if isinstance(e, dict)]


def entry_path(pack: Path, editor: dict) -> Path:
    """The editor's entry file, resolved inside the pack (a path that escapes it is refused)."""
    entry = editor.get("entry")
    if not isinstance(entry, str) or not entry.endswith(".html") or "\x00" in entry:
        raise PackError(f"editor {editor.get('id')!r}: entry must name one .html file")
    # A plain relative POSIX path: no absolute or drive-qualified form, no backslash, no `..` or `.`
    # part — the same string is joined under a staging directory, so it must not climb out of one.
    parts = entry.split("/")
    if entry.startswith("/") or "\\" in entry or ":" in entry or any(p in ("", ".", "..") for p in parts):
        raise PackError(f"editor {editor.get('id')!r}: entry {entry!r} must be a plain relative path inside the pack")
    root = pack.resolve()
    target = (pack / entry).resolve()
    if root != target and root not in target.parents:
        raise PackError(f"editor {editor.get('id')!r}: entry {entry} is outside the pack")
    if not target.is_file():
        raise PackError(f"editor {editor.get('id')!r}: entry {entry} is missing")
    if target.stat().st_size > HOST_BUNDLE_CAP:
        raise PackError(f"editor {editor.get('id')!r}: entry {entry} is over the host's {HOST_BUNDLE_CAP}-byte cap")
    return target


def write_manifest(pack: Path, manifest: dict) -> None:
    path = pack / MANIFEST_NAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def _is_editor_pack(pack: Path, strict: bool = False) -> bool:
    """Whether ``pack`` is an editor pack. ``strict``: a manifest that cannot be read at all (too big, not JSON)
    raises instead of being skipped, so it can never hide a candidate from the exactly-one rule."""
    try:
        manifest = read_manifest(pack, cap=MANIFEST_CAP if strict else None)
    except PackError:
        if strict:
            raise
        return False
    try:
        editors_of(manifest)
        return True
    except PackError:
        return False


def find_editor_packs(tree: Path, strict: bool = False) -> list[Path]:
    """Every directory under ``tree`` holding a spec-2 ``wicked-pack.json`` with editors, in walk order,
    outside node_modules/.git/dist. Linked directories are not followed (``os.walk``'s default).

    ``strict`` (the engine's host run): a manifest that is a link raises ``PackError`` before it is opened (a
    seat-written link never makes the host read its target), and so does one that cannot be read (over the
    cap, not JSON): it can never drop out of the exactly-one rule. Other callers keep the old skipping."""
    found = []
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if MANIFEST_NAME not in filenames:
            continue
        if strict and (Path(dirpath) / MANIFEST_NAME).is_symlink():
            raise PackError(f"{Path(dirpath, MANIFEST_NAME).relative_to(tree)} is a link; an editor pack is plain files")
        if _is_editor_pack(Path(dirpath), strict):
            found.append(Path(dirpath))
    return found


def refuse_links_under(tree: Path, pack: Path) -> None:
    """Refuse a link anywhere in ``pack`` (every file and directory, not only the manifest and the entries:
    ``pack check`` also reads the pack's skills) and on the way to it from ``tree``."""
    root = Path(os.path.abspath(tree))
    top = Path(os.path.abspath(pack))
    if top != root and root not in top.parents:
        raise PackError(f"{pack} is outside the run's tree")
    cur = top
    while cur != root:
        if cur.is_symlink():
            raise PackError(f"{cur.relative_to(root)} is a link; an editor pack is plain files")
        cur = cur.parent
    for dirpath, dirnames, filenames in os.walk(top):
        for name in dirnames + filenames:
            if (Path(dirpath) / name).is_symlink():
                raise PackError(f"{(Path(dirpath) / name).relative_to(root)} is a link; an editor pack is plain files")


def refuse_links(tree: Path, pack: Path, editors: list[dict]) -> None:
    """Refuse a pack whose manifest or entry is a link, or reaches one, between ``tree`` and the file.

    The engine runs the conformance cases on the host over a tree a seat wrote: a link there could hand
    the browser (and the report's hash) a host file the seat cannot read itself. ``entry_path`` already
    refuses an entry that resolves outside the pack; this refuses any link at all on the way."""
    root = Path(os.path.abspath(tree))
    files = [pack / MANIFEST_NAME] + [pack / str(e.get("entry")) for e in editors]
    for f in files:
        path = Path(os.path.abspath(f))
        if path != root and root not in path.parents:
            raise PackError(f"{f} is outside the run's tree")
        cur = path
        while cur != root:
            if cur.is_symlink():
                raise PackError(f"{cur.relative_to(root)} is a link; an editor pack is plain files")
            cur = cur.parent
