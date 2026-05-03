"""Append-only JSONL log rotation for audit + dispatch logs (#505).

Both ``gate-ingest-audit.jsonl`` and ``dispatch-log.jsonl`` are append-only
and were unbounded — a long-running crew project could accumulate hundreds
of MB and slow ``read_entries`` / audit tailers. This module adds cheap
size-based rotation:

  1. Before writing each record, caller invokes
     :func:`rotate_if_needed` with the target path.
  2. If the file exists and its size >= ``max_size_bytes`` (default 10MB,
     overridable per-call and via ``WG_LOG_RETENTION_MAX_MB`` env var),
     the file is moved to
     ``<path.parent>/<archive_dir>/<path.name>.<timestamp>.jsonl.gz``
     (compressed with gzip) and the original path is cleared.
  3. Next caller writes into a fresh empty file.

Design choices / constraints (R-series):
  - R4 (no swallowed errors): every failure path writes a stderr WARN
    and returns without raising. A rotation I/O failure MUST NOT block
    the audit / dispatch append that triggered it — that would be a
    security regression (audit-write gated by rotation).
  - R5 (no unbounded ops): the rotation itself is bounded — one stat(),
    one rename (cheap, same-filesystem), one gzip pass. We do NOT
    re-read to re-compress if rename fails; we fall back to skip-rotate.
  - Cross-platform: uses ``pathlib`` and ``shutil``, never shell.
  - Idempotent on timestamp collision: uses ISO-8601 with microseconds +
    a short ``secrets`` suffix to tolerate rapid consecutive rotations.

Stdlib-only.
"""

from __future__ import annotations

import gzip
import os
import secrets
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Default rotation threshold: 10MB per file. Chosen so one phase in a
# busy project (many gate-result ingestions) comfortably fits without
# rotation, but a multi-month project eventually archives.
DEFAULT_MAX_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB

# Archive subdirectory name — co-located with the active log so tailers
# that already `ls phases/{phase}/` see the archive without extra paths.
DEFAULT_ARCHIVE_DIR: str = "archive"

# Env var override (in MB). Tolerated failure: malformed value falls
# back to the default with a stderr WARN so an op cannot accidentally
# wedge rotation by setting WG_LOG_RETENTION_MAX_MB=notanumber.
_ENV_OVERRIDE: str = "WG_LOG_RETENTION_MAX_MB"


def _effective_max_bytes(max_size_bytes: Optional[int]) -> int:
    """Resolve the effective rotation threshold.

    Priority: explicit argument > env var > default. Negative / zero
    values are clamped to the default so a mistake never disables
    rotation silently.
    """
    if max_size_bytes is not None:
        if max_size_bytes > 0:
            return max_size_bytes
        return DEFAULT_MAX_SIZE_BYTES

    raw = os.environ.get(_ENV_OVERRIDE, "").strip()
    if not raw:
        return DEFAULT_MAX_SIZE_BYTES
    try:
        mb = float(raw)
    except ValueError:
        sys.stderr.write(
            f"[wicked-garden:log-retention] {_ENV_OVERRIDE}={raw!r} is not "
            f"a number; falling back to {DEFAULT_MAX_SIZE_BYTES // (1024 * 1024)}MB.\n"
        )
        return DEFAULT_MAX_SIZE_BYTES
    if mb <= 0:
        sys.stderr.write(
            f"[wicked-garden:log-retention] {_ENV_OVERRIDE}={raw!r} must be "
            f"positive; falling back to {DEFAULT_MAX_SIZE_BYTES // (1024 * 1024)}MB.\n"
        )
        return DEFAULT_MAX_SIZE_BYTES
    return int(mb * 1024 * 1024)


def _timestamp_suffix() -> str:
    """Generate an archive filename suffix.

    Shape: ``YYYYMMDDTHHMMSSffffff-<4hex>`` — ISO-compact + short random
    tail so two rotations triggered within the same microsecond (plausible
    on fast SSDs) do not collide.
    """
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return f"{now}-{secrets.token_hex(2)}"


def _archive_destination(path: Path, archive_dir: str) -> Path:
    """Compute the archive path for ``path`` under ``archive_dir``.

    ``path.name`` retains its original stem (e.g., ``dispatch-log``) so
    tailers can glob ``archive/dispatch-log.*.jsonl.gz`` to reconstruct
    history.
    """
    stem = path.stem  # e.g., "dispatch-log" from "dispatch-log.jsonl"
    suffix = path.suffix or ".jsonl"
    archive_name = f"{stem}.{_timestamp_suffix()}{suffix}.gz"
    return path.parent / archive_dir / archive_name


def rotate_if_needed(
    path: Path,
    max_size_bytes: Optional[int] = None,
    archive_dir: str = DEFAULT_ARCHIVE_DIR,
) -> Optional[Path]:
    """Rotate ``path`` when its size >= ``max_size_bytes``.

    Args:
        path: Active log file. Must be a plain file (not a symlink, not
            a directory). Non-existent path is a no-op.
        max_size_bytes: Rotation threshold. ``None`` falls back to
            :data:`DEFAULT_MAX_SIZE_BYTES` (or the env-var override).
            Explicit callers pass a per-log override.
        archive_dir: Subdirectory under ``path.parent`` to receive the
            compressed archive.

    Returns:
        The archive path when rotation fired, or ``None`` when the file
        was below threshold / missing / the rotation failed. Never
        raises.

    Failure modes (all fail-open; stderr WARN + return ``None``):
      - ``path`` is not a plain file (e.g., symlink, directory)
      - ``stat()`` fails with ``OSError``
      - ``archive_dir.mkdir(parents=True, exist_ok=True)`` fails
      - The gzip compress + write + unlink sequence partially fails
        (the original log is left in place so append continues; the
         next call may retry rotation)
    """
    threshold = _effective_max_bytes(max_size_bytes)

    try:
        if not path.exists():
            return None
        # Guard against weird filesystem states — we only rotate a
        # regular file. Symlinks are not rotated: the caller's append
        # target could be a symlink to a shared log, and rewriting it
        # is the operator's responsibility.
        if not path.is_file():
            return None
        size = path.stat().st_size
    except OSError as exc:
        sys.stderr.write(
            f"[wicked-garden:log-retention] stat() failed on {path}: {exc}. "
            "Skipping rotation; next append will retry.\n"
        )
        return None

    if size < threshold:
        return None

    dest = _archive_destination(path, archive_dir)

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(
            f"[wicked-garden:log-retention] archive dir create failed "
            f"({dest.parent}): {exc}. Skipping rotation.\n"
        )
        return None

    # Compress the active file into ``dest``, then truncate the original.
    # We copy-then-truncate rather than rename-then-compress so if gzip
    # fails mid-stream the original log is still intact (append continues).
    try:
        with path.open("rb") as src_fp, gzip.open(dest, "wb") as gz_fp:
            shutil.copyfileobj(src_fp, gz_fp)
    except OSError as exc:
        sys.stderr.write(
            f"[wicked-garden:log-retention] gzip write failed "
            f"(src={path}, dest={dest}): {exc}. Original log preserved.\n"
        )
        # Clean up a partial archive so the next rotation doesn't trip
        # over it. Swallowed error: removal failure is informational only.
        try:
            if dest.exists():
                dest.unlink()
        except OSError:  # pragma: no cover — defensive
            pass  # Partial archive remains; next rotation picks a new timestamp
        return None

    # Truncate the active log in place. Using O_TRUNC keeps the inode so
    # any open file descriptor (rare — our appends are short-lived) sees
    # a clean file.
    try:
        with path.open("w", encoding="utf-8"):
            pass  # open+close with "w" truncates atomically on POSIX
    except OSError as exc:
        sys.stderr.write(
            f"[wicked-garden:log-retention] log truncate failed ({path}): "
            f"{exc}. Archive at {dest} is preserved; next append may "
            "re-rotate.\n"
        )
        return None

    # Wave-2 Tranche A audit-marker emit (#746 W3).  log_retention is
    # EXEMPT from full bus-cutover per docs/v9/wave-2-cutover-plan.md
    # §W3 — rotation is a maintenance side-effect that doesn't change
    # any source of truth (the reconciler reads active logs, not
    # archives).  This optional summary marker gives operators a
    # forensics anchor: "did the log rotate before or after the bug?"
    # Fail-open: bus unavailable must NOT fail rotation (the disk
    # operations have already completed by this point).
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_root = str(_Path(__file__).resolve().parents[1])
        if _scripts_root not in _sys.path:
            _sys.path.insert(0, _scripts_root)
        from _bus import emit_event  # type: ignore[import]
        # chain_id is best-effort: log files don't carry a project
        # identifier inherently.  Use the parent-directory name as a
        # weak grouping key so per-project rotations are distinguishable.
        rotation_scope = path.parent.parent.name or "unknown-scope"
        emit_event(
            "wicked.log.rotated",
            {
                "log_path": str(path),
                "archive_path": str(dest),
                "size_bytes": size,
                "threshold_bytes": threshold,
            },
            chain_id=f"{rotation_scope}.root",
        )
    except Exception:  # noqa: BLE001 — fail-open per Decision #8
        pass  # bus unavailable — rotation disk operations already completed

    return dest


__all__ = [
    "DEFAULT_ARCHIVE_DIR",
    "DEFAULT_MAX_SIZE_BYTES",
    "rotate_if_needed",
]
