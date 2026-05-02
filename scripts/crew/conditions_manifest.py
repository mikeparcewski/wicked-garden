#!/usr/bin/env python3
"""
Conditions manifest helpers — atomic, crash-safe mutations (issue #477).

Writing `conditions-manifest.json` is a multi-step operation: the caller
typically lands a resolution artifact on disk (e.g. a design addendum or
a patched file), then flips the matching condition entry to
``verified=True``. If the process dies between those two writes, the
addendum is on disk but the manifest still reports the condition
uncleared. This module centralizes the correct ordering — write the
resolution reference first, fsync, update the manifest, fsync — so a
crash between the two steps leaves the system in a state that a
recovery pass can reconcile deterministically.

Public helpers:
    - ``mark_cleared(manifest_path, condition_id, resolution_ref)``:
      clear one condition atomically. Returns the updated manifest dict.
    - ``mark_resolved(project_dir, phase, condition_id, applied_rule,
      resolution_ref)``: per-condition resolution sidecar for the
      classify-don't-retry path (issue #717). Does NOT flip the condition
      to ``verified=True`` — that decision still belongs to the user via
      ``crew:approve``. The sidecar records *who* (rule id) resolved
      *what* (resolution_ref) at *when* (timestamp) for the audit trail.
    - ``recover(manifest_path, resolutions_dir)``: scan the resolutions
      directory on disk and fill in manifest entries where the resolution
      artifact landed but the flip never completed.

Schema additions for issue #717 (additive, backward-compatible):
    Each condition entry MAY include the following optional fields. Old
    manifests without them still load and behave identically — the only
    consumer that reads them is ``crew:resolve``.

        classification: "mechanical" | "judgment" | "escalation"
        applied_rule:    string id from finding-classification.json

All writes go through :func:`atomic_write_json` which writes to a
``<path>.tmp`` file, ``fsync``s it, and then ``os.replace``s the
temporary file over the target. On POSIX ``os.replace`` is atomic; on
Windows it is atomic as of Python 3.3.

The helpers are fail-open in the sense that they raise
``FileNotFoundError`` / ``ValueError`` on hard input problems (missing
manifest, missing condition id) rather than swallow them — crash safety
cannot rescue a caller who is pointing at the wrong file. But they do
not raise on partial state on disk; partial state is exactly what
:func:`recover` exists to fix.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# The resolution-reference file written by ``mark_cleared`` BEFORE the
# manifest flip. Recovery keys off the presence of this sidecar.
RESOLUTION_SIDECAR_SUFFIX = ".resolution.json"


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, data: Any) -> None:
    """Write ``data`` as JSON to ``path`` atomically with fsync.

    Sequence:
        1. Serialize JSON to ``<path>.tmp``.
        2. ``fsync`` the temp file descriptor (durability on POSIX).
        3. ``os.replace`` the temp file over ``path`` (atomic rename).
        4. ``fsync`` the parent directory if possible (POSIX only —
           silently skipped on Windows, where directory fsync is not
           supported).

    Args:
        path: Destination file path (will be created or overwritten).
        data: JSON-serializable value.

    Raises:
        OSError: If the write, rename, or fsync fails.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, indent=2, sort_keys=False)

    # Write + fsync the temp file.
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            # Fsync can fail on filesystems that don't support it (e.g.
            # some FUSE mounts). The atomic rename below still provides
            # ordering correctness for recovery — durability is the only
            # thing we lose. Swallow and proceed.
            pass  # fail open: durability best-effort on non-fsync FS

    os.replace(tmp_path, path)

    # Best-effort parent directory fsync. Not available on Windows
    # (opening a directory for reading is not permitted); swallow any
    # failure since durability is best-effort on non-POSIX platforms.
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except (OSError, AttributeError):
        pass  # fail open: directory fsync unsupported (Windows / FUSE)


def _resolution_sidecar_path(manifest_path: Path, condition_id: str) -> Path:
    """Return the sidecar path that records a resolution reference.

    Sidecar lives next to the manifest so recovery is a single-directory
    scan. Filename shape: ``<manifest-stem>.<condition-id>.resolution.json``.
    """
    stem = manifest_path.stem  # "conditions-manifest"
    safe_id = condition_id.replace("/", "_").replace("\\", "_")
    return manifest_path.parent / f"{stem}.{safe_id}{RESOLUTION_SIDECAR_SUFFIX}"


def _load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load a manifest file, raising FileNotFoundError if missing."""
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"conditions-manifest.json not found at {manifest_path}"
        )
    with open(manifest_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _find_condition_index(
    manifest: Dict[str, Any], condition_id: str
) -> int:
    """Return the index of ``condition_id`` in ``manifest['conditions']``.

    Raises:
        ValueError: if no matching condition is found.
    """
    conditions: List[Dict[str, Any]] = manifest.get("conditions") or []
    for idx, cond in enumerate(conditions):
        if cond.get("id") == condition_id:
            return idx
    raise ValueError(
        f"condition id '{condition_id}' not found in manifest "
        f"(available: {[c.get('id') for c in conditions]})"
    )


def mark_cleared(
    manifest_path: Path,
    condition_id: str,
    resolution_ref: str,
    *,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Clear one condition atomically.

    Write ordering (crash-safe):

        1. Write resolution sidecar to disk + fsync.
        2. Load manifest, flip condition to ``verified=True``.
        3. Atomically replace the manifest file + fsync.

    If the process crashes between step 1 and step 3, the sidecar is on
    disk but the manifest still reports the condition as unverified.
    :func:`recover` finds such orphans on startup and finishes step 3.

    Args:
        manifest_path: Path to ``conditions-manifest.json``.
        condition_id: ID of the condition to clear (e.g. ``"CONDITION-1"``).
        resolution_ref: Path or URI to the artifact that resolves this
            condition (e.g. a design addendum, a test result, a commit
            SHA). Stored verbatim in the manifest and sidecar.
        note: Optional free-text note explaining the resolution.

    Returns:
        The updated manifest dict.

    Raises:
        FileNotFoundError: if ``manifest_path`` does not exist.
        ValueError: if ``condition_id`` is not present in the manifest.
    """
    manifest_path = Path(manifest_path)
    manifest = _load_manifest(manifest_path)
    idx = _find_condition_index(manifest, condition_id)

    timestamp = _utc_now_iso()
    sidecar = {
        "condition_id": condition_id,
        "resolution_ref": resolution_ref,
        "note": note,
        "written_at": timestamp,
    }

    # Step 1: resolution sidecar lands first. A crash after this point
    # leaves a "claim" on disk that recovery can act on.
    sidecar_path = _resolution_sidecar_path(manifest_path, condition_id)
    atomic_write_json(sidecar_path, sidecar)

    # Step 2: mutate the manifest in memory.
    condition = manifest["conditions"][idx]
    condition["verified"] = True
    condition["resolution"] = resolution_ref
    condition["verified_at"] = timestamp
    if note is not None:
        condition["resolution_note"] = note

    # Step 3: atomic manifest replace.
    atomic_write_json(manifest_path, manifest)

    return manifest


def recover(
    manifest_path: Path,
) -> List[str]:
    """Reconcile orphan sidecars against the manifest.

    Scans for ``<manifest-stem>.<id>.resolution.json`` sidecars in the
    manifest's directory. For each sidecar whose condition is still
    marked ``verified=False`` in the manifest, flips the condition using
    the sidecar's ``resolution_ref`` and ``written_at`` values.

    Idempotent — running recovery twice on the same on-disk state is a
    no-op the second time.

    Args:
        manifest_path: Path to ``conditions-manifest.json``.

    Returns:
        List of condition IDs that were reconciled during this call.
        Empty list when nothing needed reconciling.

    Raises:
        FileNotFoundError: if ``manifest_path`` does not exist.
    """
    manifest_path = Path(manifest_path)
    manifest = _load_manifest(manifest_path)

    stem = manifest_path.stem
    directory = manifest_path.parent
    prefix = f"{stem}."
    suffix = RESOLUTION_SIDECAR_SUFFIX

    reconciled: List[str] = []
    mutated = False

    for sidecar_path in sorted(directory.glob(f"{stem}.*{suffix}")):
        name = sidecar_path.name
        if not (name.startswith(prefix) and name.endswith(suffix)):
            continue
        condition_id = name[len(prefix): -len(suffix)]
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Corrupt sidecar — skip. Don't let one bad file block the
            # rest of recovery.
            continue

        try:
            idx = _find_condition_index(manifest, condition_id)
        except ValueError:
            # Sidecar points at a condition that no longer exists in the
            # manifest (e.g. manifest was regenerated). Leave sidecar
            # alone so a human can investigate.
            continue

        condition = manifest["conditions"][idx]
        if condition.get("verified"):
            # Already cleared — nothing to do.
            continue

        condition["verified"] = True
        condition["resolution"] = sidecar.get("resolution_ref")
        condition["verified_at"] = sidecar.get("written_at") or _utc_now_iso()
        if sidecar.get("note") is not None:
            condition["resolution_note"] = sidecar.get("note")
        reconciled.append(condition_id)
        mutated = True

    if mutated:
        atomic_write_json(manifest_path, manifest)

    return reconciled


def mark_resolved(
    project_dir: Path,
    phase: str,
    condition_id: str,
    *,
    applied_rule: str,
    resolution_ref: str,
    note: Optional[str] = None,
) -> Path:
    """Write a resolution sidecar for the classify-don't-retry path (#717).

    Distinct from :func:`mark_cleared`:

        - ``mark_cleared`` flips ``verified=True`` on the manifest entry.
          It is the verification step run AFTER the user has approved a
          resolution.
        - ``mark_resolved`` writes ONLY the resolution sidecar — the
          condition stays ``verified=False`` until the user approves via
          ``crew:approve``. The verdict on ``gate-result.json`` is never
          touched. This preserves the honest CONDITIONAL signal end-to-end.

    The sidecar lives at the canonical path
    ``phases/{phase}/conditions-manifest.{condition_id}.resolution.json``
    so :func:`recover` would still pick it up, but production callers
    don't run recover on resolve outputs — the manifest flip is gated on
    the user, not on disk state.

    Args:
        project_dir: Project root (parent of ``phases/``).
        phase: Phase name (e.g. ``"design"``).
        condition_id: ID of the condition being resolved.
        applied_rule: ID of the classification rule that matched the
            finding (from ``finding-classification.json``).
        resolution_ref: Path or URI to the resolution artifact (e.g. a
            patch path, a commit SHA, a regenerated AC document).
        note: Optional free-text note explaining the resolution.

    Returns:
        Absolute path to the sidecar file just written.

    Raises:
        OSError: If the sidecar write fails. Callers should treat this
            as a hard failure — there is nothing to recover from.
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / "phases" / phase / "conditions-manifest.json"
    sidecar_path = _resolution_sidecar_path(manifest_path, condition_id)

    timestamp = _utc_now_iso()
    sidecar = {
        "condition_id": condition_id,
        "applied_rule": applied_rule,
        "resolution_ref": resolution_ref,
        "note": note,
        "written_at": timestamp,
        "verdict_unchanged": True,  # explicit assertion for auditors
    }
    atomic_write_json(sidecar_path, sidecar)
    return sidecar_path


__all__ = [
    "RESOLUTION_SIDECAR_SUFFIX",
    "atomic_write_json",
    "mark_cleared",
    "mark_resolved",
    "recover",
]
