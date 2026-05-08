#!/usr/bin/env python3
"""conditions_manifest.py — Track CONDITIONAL findings to resolution.

When the ``review`` archetype emits a CONDITIONAL verdict, each
condition gets a row in ``{project_dir}/audit/conditions.json``. The
``build`` (or ``migrate`` etc.) archetype that picks up the work
calls ``mark_condition_resolved()`` as it satisfies each one. The
manifest is the contract between archetypes — review can hand work
forward without losing the open items.

Restored in v11 from the deleted v6 ``conditions_manifest.py``.
Slimmed and decoupled from the v6 universal pipeline. No longer wired
into any phase_manager gate; the archetype playbooks decide when to
call this module.

Stdlib-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _manifest_path(project_dir: Path) -> Path:
    return Path(project_dir) / "audit" / "conditions.json"


# ---------------------------------------------------------------------------
# Initialise / load
# ---------------------------------------------------------------------------

def init_manifest(
    project_dir: Path,
    *,
    archetype: str,
    phase: str,
    conditions: List[Dict[str, Any]],
) -> Path:
    """Initialise the conditions manifest from a CONDITIONAL verdict.

    Each condition dict must have at least an ``id`` and a
    ``description`` / ``reason``. Severity is optional.

    The manifest carries metadata about the verdict that produced these
    conditions so future readers can trace back. Idempotent: re-init
    over an existing manifest merges new conditions in without
    overwriting resolved ones (matched by id).
    """
    project_dir = Path(project_dir)
    path = _manifest_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}

    by_id = {c.get("id"): c for c in (existing.get("conditions") or []) if c.get("id")}

    new_conditions = []
    for c in conditions:
        cid = c.get("id")
        if not cid:
            continue
        if cid in by_id:
            # Preserve any prior resolution metadata
            merged = dict(by_id[cid])
            merged.update({k: v for k, v in c.items() if k != "id"})
            new_conditions.append(merged)
        else:
            new_conditions.append({
                "id": cid,
                "description": c.get("description") or c.get("reason"),
                "severity": c.get("severity"),
                "verified": bool(c.get("verified", False)),
                "satisfied_by": c.get("satisfied_by"),
                "verification_evidence": c.get("verification_evidence"),
                "resolved_at": c.get("resolved_at"),
                "resolution_note": c.get("resolution_note"),
            })

    manifest = {
        "archetype": archetype,
        "phase": phase,
        "created_at": existing.get("created_at") or _utc_now(),
        "updated_at": _utc_now(),
        "conditions": new_conditions,
    }
    path.write_text(json.dumps(manifest, indent=2))
    return path


def load_manifest(project_dir: Path) -> Optional[Dict[str, Any]]:
    """Return the manifest dict or None when absent / unreadable."""
    path = _manifest_path(Path(project_dir))
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def mark_condition_resolved(
    project_dir: Path,
    condition_id: str,
    *,
    satisfied_by: str,
    verification_evidence: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a single condition resolved. Returns the updated condition.

    Required arguments encode the audit trail:
      - satisfied_by: task id, agent name, commit sha, or PR url.
      - verification_evidence: path or URL to the artifact proving
        the condition is met.
      - note (optional): free-form resolution annotation.

    Raises:
      FileNotFoundError if no manifest exists.
      ValueError if condition_id is not in the manifest, or required
        audit fields are empty / whitespace.
    """
    if not satisfied_by or not satisfied_by.strip():
        raise ValueError("satisfied_by is required (task / agent / commit / PR)")
    if not verification_evidence or not verification_evidence.strip():
        raise ValueError("verification_evidence is required (path or URL)")

    project_dir = Path(project_dir)
    path = _manifest_path(project_dir)
    if not path.exists():
        raise FileNotFoundError(f"No conditions manifest at {path}")

    manifest = json.loads(path.read_text(encoding="utf-8"))
    conditions = manifest.get("conditions") or []

    for c in conditions:
        if c.get("id") == condition_id:
            c["verified"] = True
            c["satisfied_by"] = satisfied_by
            c["verification_evidence"] = verification_evidence
            c["resolved_at"] = _utc_now()
            if note:
                c["resolution_note"] = note
            manifest["updated_at"] = _utc_now()
            path.write_text(json.dumps(manifest, indent=2))
            return c

    known = [c.get("id") for c in conditions]
    raise ValueError(
        f"Condition '{condition_id}' not found in {path}. Known ids: {known}"
    )


def status(project_dir: Path) -> Dict[str, Any]:
    """Return resolution counts + the per-condition list, or an empty
    shape when no manifest exists."""
    manifest = load_manifest(project_dir)
    empty = {"total": 0, "verified": 0, "pending": 0,
             "conditions": [], "exists": False}
    if not manifest:
        return empty
    conditions = manifest.get("conditions") or []
    verified = sum(1 for c in conditions if c.get("verified"))
    return {
        "exists": True,
        "archetype": manifest.get("archetype"),
        "phase": manifest.get("phase"),
        "total": len(conditions),
        "verified": verified,
        "pending": len(conditions) - verified,
        "conditions": conditions,
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
    }


def all_resolved(project_dir: Path) -> bool:
    """True iff all conditions in the manifest are verified, OR no
    manifest exists (no conditions to resolve)."""
    s = status(project_dir)
    if not s["exists"]:
        return True
    return s["pending"] == 0


__all__ = [
    "init_manifest", "load_manifest", "mark_condition_resolved",
    "status", "all_resolved",
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="v11 conditions manifest tool.")
    sub = parser.add_subparsers(dest="action", required=True)

    init = sub.add_parser("init")
    init.add_argument("project_dir")
    init.add_argument("--archetype", required=True)
    init.add_argument("--phase", required=True)
    init.add_argument("--from-verdict", required=True,
                      help="Path to a verdict JSON whose conditions[] feeds the manifest.")

    mark = sub.add_parser("mark")
    mark.add_argument("project_dir")
    mark.add_argument("--id", required=True)
    mark.add_argument("--satisfied-by", required=True)
    mark.add_argument("--evidence", required=True)
    mark.add_argument("--note", default=None)

    stat = sub.add_parser("status")
    stat.add_argument("project_dir")

    args = parser.parse_args()

    if args.action == "init":
        with open(args.from_verdict, "r", encoding="utf-8") as fh:
            verdict = json.load(fh)
        conditions = verdict.get("conditions") or []
        path = init_manifest(
            Path(args.project_dir),
            archetype=args.archetype, phase=args.phase,
            conditions=conditions,
        )
        print(json.dumps({"ok": True, "path": str(path),
                          "count": len(conditions)}))
    elif args.action == "mark":
        try:
            updated = mark_condition_resolved(
                Path(args.project_dir), args.id,
                satisfied_by=args.satisfied_by,
                verification_evidence=args.evidence,
                note=args.note,
            )
            print(json.dumps({"ok": True, "condition": updated}))
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            sys.exit(1)
    elif args.action == "status":
        s = status(Path(args.project_dir))
        print(json.dumps(s, indent=2))
