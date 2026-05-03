#!/usr/bin/env python3
"""migrate_qe_evaluator_name.py — One-shot migration: rewrite legacy qe-evaluator
references in reeval-log.jsonl and amendments.jsonl to the canonical gate-adjudicator name.

Usage:
    python migrate_qe_evaluator_name.py [--dry-run] [--project-dir PATH]

    --dry-run       Print what would change; no writes, no .bak files.
    --project-dir   Limit scan to one crew project directory.
                    Omit to scan all projects under ~/.something-wicked/wicked-garden/projects/.

Exit 0 if all files processed successfully (or nothing to do).
Exit 1 if any file was skipped due to an I/O error.

Idempotency: a file with no legacy entries is skipped immediately (BEFORE any .bak write).
Second run on an already-migrated tree exits 0 with SKIP notices per file.

Stdlib-only. No external dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants (R3 — no magic values)
# ---------------------------------------------------------------------------

_LEGACY_REVIEWER = "qe-evaluator"
_CANONICAL_REVIEWER = "gate-adjudicator"
_LEGACY_FQ_REVIEWER = "wicked-garden:crew:qe-evaluator"
_CANONICAL_FQ_REVIEWER = "wicked-garden:crew:gate-adjudicator"
_LEGACY_TRIGGER_PREFIX = "qe-evaluator:"
_CANONICAL_TRIGGER_PREFIX = "gate-adjudicator:"

_DEFAULT_PROJECTS_ROOT = (
    Path.home() / ".something-wicked" / "wicked-garden" / "projects"
)
_TARGET_GLOB_PATTERNS = [
    "phases/*/reeval-log.jsonl",
    "phases/*/amendments.jsonl",
]


# ---------------------------------------------------------------------------
# Field rewrite helpers
# ---------------------------------------------------------------------------

def _rewrite_reviewer(value: str) -> str:
    """Return canonical reviewer name; pass-through if already canonical or unknown."""
    if value == _LEGACY_REVIEWER:
        return _CANONICAL_REVIEWER
    if value == _LEGACY_FQ_REVIEWER:
        return _CANONICAL_FQ_REVIEWER
    return value


def _rewrite_trigger(value: str) -> str:
    """Return canonical trigger string; pass-through if already canonical or not a qe trigger."""
    if value.startswith(_LEGACY_TRIGGER_PREFIX):
        return _CANONICAL_TRIGGER_PREFIX + value[len(_LEGACY_TRIGGER_PREFIX):]
    return value


def _rewrite_manifest_path(value: str) -> str:
    """Replace qe-evaluator substrings in manifest_path values."""
    if _LEGACY_REVIEWER in value:
        return value.replace(_LEGACY_REVIEWER, _CANONICAL_REVIEWER)
    return value


def _has_legacy_entry(record: dict) -> bool:
    """Return True if a parsed JSON record contains any legacy qe-evaluator reference."""
    reviewer = record.get("reviewer", "")
    if reviewer == _LEGACY_REVIEWER or reviewer == _LEGACY_FQ_REVIEWER:
        return True
    trigger = record.get("trigger", "")
    if isinstance(trigger, str) and trigger.startswith(_LEGACY_TRIGGER_PREFIX):
        return True
    manifest = record.get("manifest_path", "")
    if isinstance(manifest, str) and _LEGACY_REVIEWER in manifest:
        return True
    return False


def _rewrite_record(record: dict) -> dict:
    """Return a copy of the record with all legacy names replaced by canonical names."""
    out = dict(record)
    if "reviewer" in out:
        out["reviewer"] = _rewrite_reviewer(out["reviewer"])
    if "trigger" in out and isinstance(out["trigger"], str):
        out["trigger"] = _rewrite_trigger(out["trigger"])
    if "manifest_path" in out and isinstance(out["manifest_path"], str):
        out["manifest_path"] = _rewrite_manifest_path(out["manifest_path"])
    return out


# ---------------------------------------------------------------------------
# File-level migration
# ---------------------------------------------------------------------------

def _file_has_legacy(path: Path) -> bool:
    """Quick check: return True if the file contains any legacy entry (JSON-parsed, not raw substring)."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rec = json.loads(stripped)
            if isinstance(rec, dict) and _has_legacy_entry(rec):
                return True
        except json.JSONDecodeError:
            continue
    return False


def _migrate_file(
    path: Path,
    *,
    dry_run: bool,
) -> Tuple[str, Optional[str]]:
    """Migrate a single JSONL file in-place.

    Returns:
        (status, error_message)
        status is one of: "SKIP", "DRY_RUN", "MIGRATED", "ERROR"
        error_message is set only when status == "ERROR"
    """
    # Step 1: Check for legacy entries (idempotency fast-path, BEFORE .bak write)
    if not _file_has_legacy(path):
        return ("SKIP", None)

    if dry_run:
        return ("DRY_RUN", None)

    # Step 2: Read file and parse lines
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ("ERROR", f"cannot read {path}: {exc}")

    new_lines: List[str] = []
    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.strip()
        if not stripped:
            new_lines.append(raw_line)
            continue
        try:
            rec = json.loads(stripped)
            if isinstance(rec, dict):
                rec = _rewrite_record(rec)
                new_line = json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n"
                new_lines.append(new_line)
            else:
                new_lines.append(raw_line)
        except json.JSONDecodeError:
            # Corrupt line — skip with warn (same fail-open as _read_jsonl)
            sys.stderr.write(f"  WARN: corrupt line in {path} — preserved as-is\n")
            new_lines.append(raw_line)

    # Step 3: Write .bak (idempotency check already passed — safe to write)
    bak_path = path.with_suffix(path.suffix + ".bak")
    try:
        bak_path.write_bytes(path.read_bytes())
    except OSError as exc:
        return ("ERROR", f"cannot write .bak for {path}: {exc}")

    # Step 4: Write .tmp in same directory (same filesystem for atomic rename)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text("".join(new_lines), encoding="utf-8")
    except OSError as exc:
        # Clean up .tmp if it was created
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass  # intentional: best-effort cleanup; original error is returned below
        return ("ERROR", f"cannot write .tmp for {path}: {exc}")

    # Step 5: Atomic rename .tmp -> original
    try:
        os.replace(tmp_path, path)
    except OSError as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass  # intentional: best-effort cleanup; original error is returned below
        return ("ERROR", f"os.replace failed for {path}: {exc}")

    return ("MIGRATED", None)


# ---------------------------------------------------------------------------
# Project scanning
# ---------------------------------------------------------------------------

def _find_target_files(project_dir: Path) -> List[Path]:
    """Return all reeval-log.jsonl and amendments.jsonl under a project dir."""
    found: List[Path] = []
    for pattern in _TARGET_GLOB_PATTERNS:
        found.extend(project_dir.glob(pattern))
    return sorted(found)


def _scan_and_migrate(
    projects_root: Optional[Path],
    project_dir: Optional[Path],
    *,
    dry_run: bool,
) -> int:
    """Run migration over the given scope.

    Returns exit code: 0 (all ok) or 1 (at least one I/O error).
    """
    if project_dir is not None:
        target_files = _find_target_files(project_dir)
        scan_root = project_dir
    elif projects_root is not None and projects_root.exists():
        target_files = []
        # Scan all project directories one level deep
        for child in sorted(projects_root.iterdir()):
            if child.is_dir():
                target_files.extend(_find_target_files(child))
        scan_root = projects_root
    else:
        # No projects found — nothing to do
        print("No projects found to scan.")
        return 0

    if not target_files:
        print(f"No target files found under {scan_root}.")
        return 0

    scanned = 0
    migrated = 0
    skipped = 0
    errors = 0

    for path in target_files:
        scanned += 1
        status, err_msg = _migrate_file(path, dry_run=dry_run)
        rel = path
        if status == "SKIP":
            print(f"  SKIP (already migrated): {rel}")
            skipped += 1
        elif status == "DRY_RUN":
            print(f"  DRY_RUN (would migrate): {rel}")
            migrated += 1
        elif status == "MIGRATED":
            print(f"  MIGRATED: {rel}")
            migrated += 1
        elif status == "ERROR":
            print(f"  ERROR: {rel} — {err_msg}", file=sys.stderr)
            errors += 1

    dry_label = " (dry-run)" if dry_run else ""
    print(
        f"\nSummary{dry_label}: {scanned} scanned, "
        f"{migrated} migrated, {skipped} skipped (already clean), "
        f"{errors} error(s)."
    )

    # Wave-2 Tranche A audit-marker emit (#746 W4).  Same shape as
    # adopt_legacy.py's wicked.crew.legacy_adopted: this script is
    # EXEMPT from full bus-cutover (one-shot operator migration), but
    # emits a summary marker so future forensics can identify projects
    # that went through the qe-evaluator → gate-adjudicator rename.
    # Only fires on actual application (not dry-run) AND when migrations
    # happened.  Fail-open: bus unavailable must NOT fail the migration.
    if not dry_run and migrated > 0:
        try:
            import sys as _sys
            from pathlib import Path as _Path
            _scripts_root = str(_Path(__file__).resolve().parents[1])
            if _scripts_root not in _sys.path:
                _sys.path.insert(0, _scripts_root)
            from _bus import emit_event  # type: ignore[import]
            # Scope identifier for chain_id: when targeting a single
            # project_dir, use its basename; when scanning a projects_root,
            # use the root's basename + "all-projects" sentinel so the
            # marker is distinguishable from a single-project run.
            scope_id = (
                project_dir.name if project_dir is not None
                else f"{(projects_root.name if projects_root else 'unknown')}-all-projects"
            )
            emit_event(
                "wicked.crew.qe_evaluator_migrated",
                {
                    "project_id": scope_id,
                    "scope": "single-project" if project_dir else "all-projects",
                    "scanned": scanned,
                    "migrated": migrated,
                    "skipped": skipped,
                    "errors": errors,
                },
                chain_id=f"{scope_id}.root",
            )
        except Exception:  # noqa: BLE001 — fail-open per Decision #8
            pass  # bus unavailable — migration disk writes already completed

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """Entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy qe-evaluator names to gate-adjudicator in JSONL files."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change; make no writes and create no .bak files.",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Limit scan to one crew project directory.",
    )
    args = parser.parse_args(argv)

    projects_root: Optional[Path] = None
    if args.project_dir is None:
        projects_root = _DEFAULT_PROJECTS_ROOT
        print(f"Scanning all projects under: {projects_root}")
    else:
        print(f"Scanning project: {args.project_dir}")

    if args.dry_run:
        print("DRY RUN — no files will be modified.")

    return _scan_and_migrate(
        projects_root=projects_root,
        project_dir=args.project_dir,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
