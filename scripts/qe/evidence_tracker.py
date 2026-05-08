#!/usr/bin/env python3
"""evidence_tracker.py — Track produces-contracts per archetype phase.

Each archetype declares a ``produces`` contract in
``.claude-plugin/archetypes.json`` (e.g. build → ``shipped-code`` +
``test-report``; migrate → ``shape-change`` + ``rollback-proof``).
This module records when each produces item is met and provides
``produces_satisfied()`` for archetype playbooks to check before
advancing past their final phase.

The tracker is doctrine-light: it records what the archetype claims
to have produced, with a path to the artifact. It does not validate
the artifact's content. Validation is the archetype's job (build's
test phase runs tests; migrate's cutover phase runs rollback drill;
review's assess phase applies the rubric). The tracker just answers:
"have all produces items been claimed?"

Stdlib-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _evidence_path(project_dir: Path) -> Path:
    return Path(project_dir) / "audit" / "evidence.json"


def _load_archetype_produces(archetype: str) -> List[str]:
    """Read produces[] from the catalog. Returns [] when unavailable."""
    try:
        from pathlib import Path as _Path
        catalog_path = (
            _Path(__file__).resolve().parents[2]
            / ".claude-plugin" / "archetypes.json"
        )
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        return list(
            catalog.get("archetypes", {}).get(archetype, {}).get("produces", [])
        )
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def initialize_for_archetype(
    project_dir: Path,
    archetype: str,
) -> Path:
    """Initialise the evidence tracker for an archetype run. Pre-populates
    each declared produces item with verified=False. Idempotent: re-init
    over an existing tracker preserves prior verifications by name."""
    project_dir = Path(project_dir)
    path = _evidence_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    declared = _load_archetype_produces(archetype)

    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}

    by_name = {item.get("name"): item
               for item in (existing.get("produces") or [])
               if item.get("name")}

    produces = []
    for name in declared:
        if name in by_name:
            produces.append(by_name[name])
        else:
            produces.append({
                "name": name,
                "verified": False,
                "claimed_at": None,
                "artifact_path": None,
                "claimed_by": None,
                "note": None,
            })

    tracker = {
        "archetype": archetype,
        "created_at": existing.get("created_at") or _utc_now(),
        "updated_at": _utc_now(),
        "produces": produces,
    }
    path.write_text(json.dumps(tracker, indent=2))
    return path


def claim_produces(
    project_dir: Path,
    name: str,
    *,
    artifact_path: str,
    claimed_by: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a produces item satisfied. ``artifact_path`` is a file path,
    URL, or commit reference. ``claimed_by`` is the agent / task / user.

    Raises:
      FileNotFoundError if no tracker exists.
      ValueError if ``name`` is not in the tracker (typo guard).
    """
    if not artifact_path or not artifact_path.strip():
        raise ValueError("artifact_path is required")
    if not claimed_by or not claimed_by.strip():
        raise ValueError("claimed_by is required")

    project_dir = Path(project_dir)
    path = _evidence_path(project_dir)
    if not path.exists():
        raise FileNotFoundError(f"No evidence tracker at {path}")

    tracker = json.loads(path.read_text(encoding="utf-8"))
    produces = tracker.get("produces") or []

    for item in produces:
        if item.get("name") == name:
            item["verified"] = True
            item["claimed_at"] = _utc_now()
            item["artifact_path"] = artifact_path
            item["claimed_by"] = claimed_by
            if note:
                item["note"] = note
            tracker["updated_at"] = _utc_now()
            path.write_text(json.dumps(tracker, indent=2))
            return item

    known = [p.get("name") for p in produces]
    raise ValueError(
        f"Produces item '{name}' not declared for this archetype. "
        f"Declared: {known}"
    )


def status(project_dir: Path) -> Dict[str, Any]:
    project_dir = Path(project_dir)
    path = _evidence_path(project_dir)
    empty = {"exists": False, "total": 0, "verified": 0, "pending": 0,
             "produces": []}
    if not path.exists():
        return empty
    try:
        tracker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    produces = tracker.get("produces") or []
    verified = sum(1 for p in produces if p.get("verified"))
    return {
        "exists": True,
        "archetype": tracker.get("archetype"),
        "total": len(produces),
        "verified": verified,
        "pending": len(produces) - verified,
        "produces": produces,
        "created_at": tracker.get("created_at"),
        "updated_at": tracker.get("updated_at"),
    }


def produces_satisfied(project_dir: Path) -> bool:
    """True iff every declared produces item is verified, OR no tracker
    exists. The latter case is intentional — archetype playbooks may
    skip evidence tracking for low-rigor work."""
    s = status(project_dir)
    if not s["exists"]:
        return True
    return s["pending"] == 0


__all__ = [
    "initialize_for_archetype", "claim_produces", "status",
    "produces_satisfied",
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="v11 evidence tracker tool.")
    sub = parser.add_subparsers(dest="action", required=True)

    init = sub.add_parser("init")
    init.add_argument("project_dir")
    init.add_argument("--archetype", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("project_dir")
    claim.add_argument("--name", required=True)
    claim.add_argument("--artifact", required=True)
    claim.add_argument("--claimed-by", required=True)
    claim.add_argument("--note", default=None)

    stat = sub.add_parser("status")
    stat.add_argument("project_dir")

    args = parser.parse_args()

    if args.action == "init":
        path = initialize_for_archetype(Path(args.project_dir), args.archetype)
        print(json.dumps({"ok": True, "path": str(path)}))
    elif args.action == "claim":
        try:
            item = claim_produces(
                Path(args.project_dir), args.name,
                artifact_path=args.artifact, claimed_by=args.claimed_by,
                note=args.note,
            )
            print(json.dumps({"ok": True, "produces_item": item}))
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            sys.exit(1)
    elif args.action == "status":
        print(json.dumps(status(Path(args.project_dir)), indent=2))
