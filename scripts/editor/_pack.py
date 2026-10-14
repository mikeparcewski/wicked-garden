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


class PackError(Exception):
    """A pack that cannot be read as an editor pack, with the reason."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(pack: Path) -> dict:
    path = pack / MANIFEST_NAME
    if not path.is_file():
        raise PackError(f"{pack} holds no {MANIFEST_NAME}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
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
    if not isinstance(entry, str) or not entry.endswith(".html"):
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
