#!/usr/bin/env python3
"""migrate_v6_projects.py — Detect + (optionally) migrate v6-v10 crew
projects to v11 archetype-mode.

The v6-v10 universal-pipeline machinery was deleted wholesale in
v11.0.0. Any existing project state on disk references concepts the
v11 phase_manager no longer understands — `process-plan.json`, the
9-phase universal plan, gate-result.json files, conditions-manifest,
reeval-log, etc. The v11 phase_manager loads those records but the
plan / gate / addendum machinery is gone.

This script:
  1. Detects v6-v10 projects in the wicked-crew DomainStore.
  2. Optionally migrates each one to v11 by mapping the v6 phase
     plan to the closest v11 archetype + stamping
     phase_plan_mode="archetype" on the project state.

The mapping is best-effort — many v6 plans don't fit cleanly into
a single v11 archetype. The default mapping uses the v6 phase
list to pick the v11 archetype that best matches:

  v6 plan contains 'cutover' or 'expand' / 'backfill' → migrate
  v6 plan = ['triage', 'investigate', ...]            → incident
  v6 plan = ['canary', 'ramp', 'full', ...]           → ship
  v6 plan = ['scope', 'assess', 'findings', ...]      → review
  v6 plan = ['elicit', 'structure', ...]              → specify
  v6 plan = ['frame', 'diverge', 'converge']          → explore
  v6 plan = ['brief', 'options', 'score', 'record']   → decide
  default                                             → build

The script defaults to dry-run. Use --apply to actually mutate state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS))


_PHASE_HINTS_TO_ARCHETYPE: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    # First match wins. Most-specific patterns first.
    (("expand", "backfill", "cutover", "contract"), "migrate"),
    (("cutover",), "migrate"),
    (("canary", "ramp", "full", "soak"), "ship"),
    (("triage", "investigate", "mitigate"), "incident"),
    (("scope", "assess", "findings", "remediate-or-accept"), "review"),
    (("scope", "assess", "findings"), "review"),
    (("elicit", "structure", "validate"), "specify"),
    (("frame", "diverge", "converge"), "explore"),
    (("brief", "options", "score", "record"), "decide"),
    # Universal-pipeline plans land here:
    (("clarify", "design", "build", "test", "review"), "build"),
)


def _classify_phase_plan(phase_plan: List[str]) -> str:
    """Pick the v11 archetype that best matches a v6 phase plan."""
    if not phase_plan:
        return "build"
    plan_set = set(phase_plan)
    for phases_required, archetype in _PHASE_HINTS_TO_ARCHETYPE:
        if all(p in plan_set for p in phases_required):
            return archetype
    return "build"  # safe default


def _map_to_v11_phases(archetype: str) -> List[str]:
    """Read .claude-plugin/archetypes.json for the canonical phase list."""
    catalog_path = (
        Path(__file__).resolve().parents[2]
        / ".claude-plugin" / "archetypes.json"
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    return list(
        catalog.get("archetypes", {}).get(archetype, {}).get("phases", [])
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_v6_projects() -> List[Dict]:
    """Return a list of projects whose state looks like v6-v10 universal-
    pipeline output (i.e. phase_plan_mode != 'archetype' AND non-empty
    phase_plan)."""
    try:
        from _domain_store import DomainStore
    except ImportError:
        return []

    sm = DomainStore("projects")
    try:
        all_records = sm.list("projects")
    except Exception:
        all_records = []

    legacy = []
    for rec in (all_records or []):
        if not isinstance(rec, dict):
            continue
        extras = rec.get("extras") or {}
        mode = extras.get("phase_plan_mode")
        plan = rec.get("phase_plan") or []
        if mode == "archetype":
            continue  # already v11
        if not plan:
            continue  # no phase plan to migrate
        legacy.append(rec)
    return legacy


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate_one(project_record: Dict, *, dry_run: bool = True) -> Dict:
    """Translate a single v6 project to v11 archetype-mode.

    Returns a dict describing the migration: {name, from_phases,
    chosen_archetype, to_phases, applied}.
    """
    name = project_record.get("name") or project_record.get("id")
    from_phases = list(project_record.get("phase_plan") or [])
    archetype = _classify_phase_plan(from_phases)
    to_phases = _map_to_v11_phases(archetype)

    result = {
        "name": name,
        "from_phases": from_phases,
        "chosen_archetype": archetype,
        "to_phases": to_phases,
        "applied": False,
    }

    if dry_run:
        return result

    # Apply: mutate state via the v11 phase_manager API
    try:
        from _domain_store import DomainStore
    except ImportError:
        return result

    sm = DomainStore("projects")
    record = dict(project_record)
    record["phase_plan"] = to_phases
    extras = dict(record.get("extras") or {})
    extras["phase_plan_mode"] = "archetype"
    extras["v11_archetype"] = archetype
    extras["v11_migrated_at"] = _utc_now()
    extras["v11_migration_source"] = {
        "from_phases": from_phases,
        "chosen_archetype": archetype,
    }
    record["extras"] = extras
    sm.update("projects", name, record)
    result["applied"] = True
    return result


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Detect + migrate v6-v10 crew projects to v11 archetype-mode."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually mutate state. Without this flag, prints what would happen.")
    parser.add_argument("--name", default=None,
                        help="Migrate only the project with this name.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    legacy = detect_v6_projects()
    if args.name:
        legacy = [p for p in legacy if p.get("name") == args.name]

    if not legacy:
        if args.json:
            print(json.dumps({"status": "CLEAN", "migratable": []}))
        else:
            print("CLEAN: no v6-v10 projects detected.")
        return

    results = [
        migrate_one(p, dry_run=not args.apply) for p in legacy
    ]

    if args.json:
        print(json.dumps({
            "status": "MIGRATABLE_FOUND" if not args.apply else "APPLIED",
            "count": len(results),
            "results": results,
        }, indent=2, default=str))
    else:
        print(
            f"{'APPLIED' if args.apply else 'DRY-RUN'}: "
            f"{len(results)} v6-v10 project(s) "
            f"{'migrated' if args.apply else 'detected'}"
        )
        for r in results:
            arrow = "→"
            print(
                f"  {r['name']}: {' → '.join(r['from_phases'][:5])}"
                f"{'...' if len(r['from_phases']) > 5 else ''} "
                f"{arrow} archetype={r['chosen_archetype']} "
                f"({' → '.join(r['to_phases'])})"
            )
        if not args.apply:
            print(
                "\nRe-run with --apply to perform the migration. "
                "The legacy phase_plan is recorded in extras.v11_migration_source."
            )


if __name__ == "__main__":
    _cli()
