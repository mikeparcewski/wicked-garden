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
import math
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
TOPIC_SEG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
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
ICON_CAP = 32 * 1024
SAMPLES_CAP = 256 * 1024
# A manifest is a few KB; the engine's host run refuses a bigger one before it is read.
MANIFEST_CAP = 1024 * 1024
# Directories a run's worktree search never enters.
SKIP_DIRS = {"node_modules", "dist", ".git"}


def valid_topic_pattern(topic: object) -> bool:
    """Whether ``topic`` is a valid run-plugin observe topic pattern (CONTRACT-CS7 §C2):
    at most 120 chars; dot-separated; starts with ``wicked.run.`` (at least one segment after ``run``);
    every segment after ``wicked`` is ``^[a-z][a-z0-9_-]{0,40}$`` or ``*``, or ``**`` as the last segment only."""
    if not isinstance(topic, str) or not topic or len(topic) > 120:
        return False
    parts = topic.split(".")
    if len(parts) < 3 or parts[0] != "wicked" or parts[1] != "run":
        return False
    for i, seg in enumerate(parts[2:], start=2):
        if seg == "**":
            if i != len(parts) - 1:
                return False
        elif seg == "*":
            continue
        elif not TOPIC_SEG_RE.fullmatch(seg):
            return False
    return True


def valid_core_event(item: object) -> bool:
    """The sample shape studio's run conformance page reads, before run/sequence normalization."""
    def finite_number(value: object) -> bool:
        try:
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        except OverflowError:
            return False

    return (
        isinstance(item, dict)
        and isinstance(item.get("type"), str) and bool(item["type"].strip())
        and isinstance(item.get("session"), str) and bool(item["session"].strip())
        and all(finite_number(item.get(k)) for k in ("seq", "ts"))
    )


def topic_matches(pattern: str, topic: str) -> bool:
    """Whether ``pattern`` (a valid §C2 pattern) matches ``topic`` (a concrete dot-separated run topic)."""
    if not valid_topic_pattern(pattern) or not isinstance(topic, str) or not topic:
        return False
    p_parts = pattern.split(".")
    t_parts = topic.split(".")
    if len(t_parts) < 3 or t_parts[0] != "wicked" or t_parts[1] != "run":
        return False
    if p_parts[-1] == "**":
        prefix = p_parts[:-1]
        if len(t_parts) < len(p_parts):
            return False
        return all(p == "*" or p == t for p, t in zip(prefix, t_parts[: len(prefix)]))
    if len(p_parts) != len(t_parts):
        return False
    return all(p == "*" or p == t for p, t in zip(p_parts, t_parts))


class PackError(Exception):
    """A pack that cannot be read as an editor pack, with the reason."""


def _no_constant(name: str):
    raise ValueError(f"{name} is not a JSON number")


def _finite(text: str) -> float:
    value = float(text)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{text} is not a finite number")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(pack: Path, cap: int | None = None, finite: bool = False) -> dict:
    """The pack's manifest. The engine's host run passes ``cap`` (a manifest bigger than it is refused unread) and
    ``finite`` (NaN, Infinity or an overflowing number is refused: its report must stay valid JSON); other callers
    read as before."""
    path = pack / MANIFEST_NAME
    if not path.is_file():
        raise PackError(f"{pack} holds no {MANIFEST_NAME}")
    if cap is not None and path.stat().st_size > cap:
        raise PackError(f"{path} is over {cap} bytes")
    try:
        text = path.read_text(encoding="utf-8")
        manifest = json.loads(text, parse_constant=_no_constant, parse_float=_finite) if finite else json.loads(text)
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


def plugins_of(manifest: dict) -> list[dict]:
    plugins = manifest.get("plugins")
    if manifest.get("spec") != 2 or not isinstance(plugins, list) or not plugins:
        raise PackError("the pack declares no plugins (wicked-pack.json spec 2 `plugins[]`)")
    return [p for p in plugins if isinstance(p, dict)]


def pack_entries_of(manifest: dict) -> tuple[list[dict], list[dict]]:
    if manifest.get("spec") != 2:
        raise PackError("the pack declares no editors or plugins (wicked-pack.json spec 2 `editors[]` or `plugins[]`)")
    raw_ed = manifest.get("editors")
    raw_pl = manifest.get("plugins")
    editors = [e for e in raw_ed if isinstance(e, dict)] if isinstance(raw_ed, list) else []
    plugins = [p for p in raw_pl if isinstance(p, dict)] if isinstance(raw_pl, list) else []
    if not editors and not plugins:
        raise PackError("the pack declares no editors or plugins (wicked-pack.json spec 2 `editors[]` or `plugins[]`)")
    return editors, plugins


def asset_path(pack: Path, rel: object, *, label: str, suffix: str, cap: int) -> Path:
    """Resolve a plain relative path inside ``pack`` with the required suffix and size cap."""
    if not isinstance(rel, str) or not rel.endswith(suffix) or "\x00" in rel:
        raise PackError(f"{label} must name one {suffix} file")
    parts = rel.split("/")
    if rel.startswith("/") or "\\" in rel or ":" in rel or any(p in ("", ".", "..") for p in parts):
        raise PackError(f"{label} {rel!r} must be a plain relative path inside the pack")
    root = pack.resolve()
    target = (pack / rel).resolve()
    if root != target and root not in target.parents:
        raise PackError(f"{label} {rel} is outside the pack")
    if not target.is_file():
        raise PackError(f"{label} {rel} is missing")
    if target.stat().st_size > cap:
        raise PackError(f"{label} {rel} is over the host's {cap}-byte cap")
    return target


def entry_path(pack: Path, editor: dict, kind: str = "editor") -> Path:
    """The editor's or plugin's entry file, resolved inside the pack (a path that escapes it is refused)."""
    return asset_path(pack, editor.get("entry"), label=f"{kind} {editor.get('id')!r}: entry",
                      suffix=".html", cap=HOST_BUNDLE_CAP)


def plugin_extra_paths(pack: Path, plugin: dict) -> list[tuple[str, Path]]:
    """Resolved ``(rel, path)`` pairs for optional files a run plugin declares (``samples``, ``visuals.icon``)."""
    out: list[tuple[str, Path]] = []
    pid = plugin.get("id")
    samples = plugin.get("samples")
    if samples is not None:
        p = asset_path(pack, samples, label=f"plugin {pid!r}: samples", suffix=".ndjson", cap=SAMPLES_CAP)
        out.append((str(samples), p))
    visuals = plugin.get("visuals")
    if isinstance(visuals, dict) and visuals.get("icon") is not None:
        icon = visuals.get("icon")
        p = asset_path(pack, icon, label=f"plugin {pid!r}: visuals.icon", suffix=".svg", cap=ICON_CAP)
        out.append((str(icon), p))
    return out


def write_manifest(pack: Path, manifest: dict) -> None:
    path = pack / MANIFEST_NAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def _is_editor_pack(pack: Path, strict: bool = False) -> bool:
    """Whether ``pack`` is an editor or run-plugin pack. ``strict``: a manifest that cannot be read at all (too big,
    not JSON) raises instead of being skipped, so it can never hide a candidate from the exactly-one rule."""
    try:
        manifest = read_manifest(pack, cap=MANIFEST_CAP if strict else None, finite=strict)
    except PackError:
        if strict:
            raise
        return False
    try:
        pack_entries_of(manifest)
        return True
    except PackError:
        return False


def _strict_walk(top: Path):
    """``os.walk`` (top-down, sorted, SKIP_DIRS pruned, links not followed) that RAISES on any directory or entry
    it cannot read or classify, instead of skipping it: an unreadable corner could hide a second pack."""
    def unreadable(path, exc: OSError) -> PackError:
        return PackError(f"{path} cannot be read ({exc.strerror or exc}), so the tree cannot be shown to hold "
                         "exactly one editor pack")
    stack = [str(top)]
    while stack:
        here = stack.pop()
        dirs, files = [], []
        try:
            with os.scandir(here) as it:
                for entry in it:
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                    except OSError as exc:
                        raise unreadable(entry.path, exc) from exc
                    (dirs if is_dir else files).append(entry.name)
        except OSError as exc:
            raise unreadable(here, exc) from exc
        dirs = sorted(d for d in dirs if d not in SKIP_DIRS)
        yield here, dirs, files
        stack.extend(os.path.join(here, d) for d in reversed(dirs))


def find_editor_packs(tree: Path, strict: bool = False) -> list[Path]:
    """Every directory under ``tree`` holding a spec-2 ``wicked-pack.json`` with editors, in walk order,
    outside node_modules/.git/dist. Linked directories are not followed.

    ``strict`` (the engine's host run): any directory or entry that cannot be read raises ``PackError`` (it could
    hide a second pack); a manifest that is a link raises before it is opened (a seat-written link never makes the
    host read its target), and so does one that cannot be read (over the cap, not JSON): nothing can drop out of
    the exactly-one rule. Other callers keep the old skipping walk."""
    found = []
    walk = _strict_walk(tree) if strict else os.walk(tree)
    for dirpath, dirnames, filenames in walk:
        if not strict:
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if MANIFEST_NAME not in filenames:
            continue
        try:
            if strict and (Path(dirpath) / MANIFEST_NAME).is_symlink():
                raise PackError(f"{Path(dirpath, MANIFEST_NAME).relative_to(tree)} is a link; an editor pack is plain files")
            candidate = _is_editor_pack(Path(dirpath), strict)
        except OSError as exc:
            if not strict:
                continue
            raise PackError(f"{dirpath} cannot be read ({exc.strerror}), so the tree cannot be shown to hold exactly one "
                            "editor pack") from exc
        if candidate:
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


def refuse_links(tree: Path, pack: Path, editors: list[dict], plugins: list[dict] | None = None) -> None:
    """Refuse a pack whose manifest or entry is a link, or reaches one, between ``tree`` and the file.

    The engine runs the conformance cases on the host over a tree a seat wrote: a link there could hand
    the browser (and the report's hash) a host file the seat cannot read itself. ``entry_path`` already
    refuses an entry that resolves outside the pack; this refuses any link at all on the way."""
    root = Path(os.path.abspath(tree))
    files = [pack / MANIFEST_NAME] + [pack / str(e.get("entry")) for e in editors]
    for p in plugins or []:
        files.append(pack / str(p.get("entry")))
        if p.get("samples") is not None:
            files.append(pack / str(p.get("samples")))
        vis = p.get("visuals")
        if isinstance(vis, dict) and vis.get("icon") is not None:
            files.append(pack / str(vis.get("icon")))
    for f in files:
        path = Path(os.path.abspath(f))
        if path != root and root not in path.parents:
            raise PackError(f"{f} is outside the run's tree")
        cur = path
        while cur != root:
            if cur.is_symlink():
                raise PackError(f"{cur.relative_to(root)} is a link; an editor pack is plain files")
            cur = cur.parent
