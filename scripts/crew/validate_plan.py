#!/usr/bin/env python3
"""Validate a facilitator process-plan JSON file.

Usage:
    validate_plan.py <path-to-plan.json>
    validate_plan.py --selftest

Exit 0 on valid, exit 1 on invalid or selftest failure.
"""

import argparse
import json
import sys
from pathlib import Path

VALID_RIGOR_TIERS = {"minimal", "standard", "full"}
VALID_FACTOR_READINGS = {"LOW", "MEDIUM", "HIGH"}
VALID_EVENT_TYPES = {
    "task", "coding-task", "gate-finding",
    "phase-transition", "procedure-trigger", "subtask",
}
REQUIRED_TOP_LEVEL_KEYS = {
    "project_slug", "summary", "factors", "specialists",
    "phases", "rigor_tier", "complexity", "tasks",
}
REQUIRED_FACTOR_KEYS = {
    "reversibility", "blast_radius", "compliance_scope",
    "user_facing_impact", "novelty", "scope_effort",
    "state_complexity", "operational_risk", "coordination_cost",
}
REQUIRED_TASK_METADATA_KEYS = {
    "chain_id", "event_type", "source_agent", "phase", "rigor_tier",
}

# Issue #563: every violation cites this doc so callers don't have to grep
# to find the authoritative schema.
SCHEMA_DOC = "skills/propose-process/refs/output-schema.md"

# Per-section anchors within SCHEMA_DOC. Key is the violation-message prefix
# (the text before ' — ', with [] / . suffixes stripped).
_SECTION_ANCHORS = {
    "top-level": "§ Required vs. optional fields",
    "factors": "§ Schema — factors block",
    "specialists": "§ Schema — specialists",
    "phases": "§ Schema — phases",
    "tasks": "§ Schema — tasks",
    "rigor_tier": "§ rigor_tier enum (minimal|standard|full)",
    "complexity": "§ complexity bounds (0..7)",
}


def _schema_pointer_for(violation: str) -> str:
    """Return a 'See: <doc> § <anchor>' hint for a given violation message."""
    head = violation.split(" — ", 1)[0]
    # Strip index / dotted suffix so "tasks[0].metadata" → "tasks".
    section = head.split(".", 1)[0].split("[", 1)[0]
    anchor = _SECTION_ANCHORS.get(section, "")
    return f"See: {SCHEMA_DOC}" + (f" {anchor}" if anchor else "")


def _check_top_level(plan: dict, violations: list) -> None:
    missing = REQUIRED_TOP_LEVEL_KEYS - plan.keys()
    for key in sorted(missing):
        violations.append(f"top-level — missing required key '{key}'")

    if "rigor_tier" in plan and plan["rigor_tier"] not in VALID_RIGOR_TIERS:
        violations.append(
            f"rigor_tier — '{plan['rigor_tier']}' is not one of {sorted(VALID_RIGOR_TIERS)}"
        )

    if "complexity" in plan:
        c = plan["complexity"]
        if not isinstance(c, int) or not (0 <= c <= 7):
            violations.append(f"complexity — must be an integer in [0, 7], got {c!r}")


def _check_factors(plan: dict, violations: list) -> None:
    if "factors" not in plan:
        return
    factors = plan["factors"]
    if not isinstance(factors, dict):
        violations.append("factors — must be a dict")
        return

    actual_keys = set(factors.keys())
    missing = REQUIRED_FACTOR_KEYS - actual_keys
    extra = actual_keys - REQUIRED_FACTOR_KEYS
    for key in sorted(missing):
        violations.append(f"factors — missing required factor key '{key}'")
    for key in sorted(extra):
        violations.append(f"factors — unexpected factor key '{key}'")

    for key, value in factors.items():
        if key not in REQUIRED_FACTOR_KEYS:
            continue
        if not isinstance(value, dict):
            violations.append(f"factors.{key} — must be a dict")
            continue
        reading = value.get("reading")
        if reading not in VALID_FACTOR_READINGS:
            violations.append(
                f"factors.{key}.reading — '{reading}' is not one of {sorted(VALID_FACTOR_READINGS)}"
            )
        why = value.get("why")
        if not why or not str(why).strip():
            violations.append(f"factors.{key}.why — must be a non-empty string")


def _check_specialists(plan: dict, violations: list) -> None:
    if "specialists" not in plan:
        return
    specialists = plan["specialists"]
    if not isinstance(specialists, list) or len(specialists) == 0:
        violations.append("specialists — must be a non-empty list")
        return
    for i, entry in enumerate(specialists):
        if not isinstance(entry, dict):
            violations.append(f"specialists[{i}] — must be a dict")
            continue
        if not entry.get("name") or not str(entry["name"]).strip():
            violations.append(f"specialists[{i}].name — must be a non-empty string")
        if not entry.get("why") or not str(entry["why"]).strip():
            violations.append(f"specialists[{i}].why — must be a non-empty string")


def _check_phases(plan: dict, violations: list) -> None:
    if "phases" not in plan:
        return
    phases = plan["phases"]
    if not isinstance(phases, list) or len(phases) == 0:
        violations.append("phases — must be a non-empty list")
        return
    for i, entry in enumerate(phases):
        if not isinstance(entry, dict):
            violations.append(f"phases[{i}] — must be a dict")
            continue
        if not entry.get("name") or not str(entry["name"]).strip():
            violations.append(f"phases[{i}].name — must be a non-empty string")
        if not entry.get("why") or not str(entry["why"]).strip():
            violations.append(f"phases[{i}].why — must be a non-empty string")
        if not isinstance(entry.get("primary"), list):
            violations.append(f"phases[{i}].primary — must be a list of strings")


def _check_tasks(plan: dict, violations: list) -> None:
    if "tasks" not in plan:
        return
    tasks = plan["tasks"]
    if not isinstance(tasks, list) or len(tasks) == 0:
        violations.append("tasks — must be a non-empty list")
        return
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            violations.append(f"tasks[{i}] — must be a dict")
            continue
        for field in ("id", "title", "phase"):
            if not task.get(field) or not str(task[field]).strip():
                violations.append(f"tasks[{i}].{field} — must be a non-empty string")
        meta = task.get("metadata")
        if not isinstance(meta, dict):
            violations.append(f"tasks[{i}].metadata — must be a dict")
            continue
        for key in sorted(REQUIRED_TASK_METADATA_KEYS):
            if key not in meta:
                violations.append(f"tasks[{i}].metadata — missing required key '{key}'")
        if "rigor_tier" in meta and meta["rigor_tier"] not in VALID_RIGOR_TIERS:
            violations.append(
                f"tasks[{i}].metadata.rigor_tier — '{meta['rigor_tier']}' is not one of {sorted(VALID_RIGOR_TIERS)}"
            )
        if "event_type" in meta and meta["event_type"] not in VALID_EVENT_TYPES:
            violations.append(
                f"tasks[{i}].metadata.event_type — '{meta['event_type']}' is not one of {sorted(VALID_EVENT_TYPES)}"
            )


def validate(plan: dict) -> list:
    """Return a list of violation strings (empty means valid)."""
    violations = []
    _check_top_level(plan, violations)
    _check_factors(plan, violations)
    _check_specialists(plan, violations)
    _check_phases(plan, violations)
    _check_tasks(plan, violations)
    return violations


def validate_file(path: Path) -> list:
    """Load JSON from path and validate. Returns violations list."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read file — {exc}"]
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON — {exc}"]
    if not isinstance(plan, dict):
        return ["top-level — must be a JSON object, not an array or scalar"]
    return validate(plan)


# ---------------------------------------------------------------------------
# Self-test fixtures
# ---------------------------------------------------------------------------

_VALID_FIXTURE = {
    "project_slug": "test-project",
    "summary": "A valid test plan.",
    "rigor_tier": "standard",
    "complexity": 3,
    "factors": {
        key: {"reading": "LOW", "why": "because reasons"}
        for key in REQUIRED_FACTOR_KEYS
    },
    "specialists": [{"name": "backend-engineer", "why": "writes the code"}],
    "phases": [{"name": "build", "why": "do the work", "primary": ["backend-engineer"]}],
    "tasks": [
        {
            "id": "t1",
            "title": "Implement feature",
            "phase": "build",
            "blockedBy": [],
            "metadata": {
                "chain_id": "test-project.root",
                "event_type": "coding-task",
                "source_agent": "facilitator",
                "phase": "build",
                "rigor_tier": "standard",
            },
        }
    ],
}

_INVALID_FIXTURES = [
    # (description, mutator_fn) — every entry must produce >= 1 violation.
    ("missing top-level key", lambda p: {k: v for k, v in p.items() if k != "summary"}),
    ("bad rigor_tier", lambda p: {**p, "rigor_tier": "turbo"}),
    ("bad factor reading", lambda p: {
        **p,
        "factors": {**p["factors"], "reversibility": {"reading": "MAYBE", "why": "idk"}},
    }),
    ("missing task metadata key", lambda p: {
        **p,
        "tasks": [{**p["tasks"][0], "metadata": {k: v for k, v in p["tasks"][0]["metadata"].items() if k != "chain_id"}}],
    }),
    ("factors keyset missing a key", lambda p: {
        **p,
        "factors": {k: v for k, v in p["factors"].items() if k != "novelty"},
    }),
    ("specialists empty list", lambda p: {**p, "specialists": []}),
    ("bad event_type", lambda p: {
        **p,
        "tasks": [{**p["tasks"][0], "metadata": {**p["tasks"][0]["metadata"], "event_type": "garbage"}}],
    }),
]


def _run_selftest() -> None:
    import copy

    failures = []

    # Valid fixture must pass
    result = validate(copy.deepcopy(_VALID_FIXTURE))
    if result:
        failures.append(f"valid fixture produced violations: {result}")

    # Invalid fixtures must each produce at least one violation
    for desc, mutator in _INVALID_FIXTURES:
        mutated = mutator(copy.deepcopy(_VALID_FIXTURE))
        result = validate(mutated)
        if not result:
            failures.append(f"invalid fixture '{desc}' produced no violations (expected >=1)")

    if failures:
        for msg in failures:
            sys.stderr.write(f"selftest FAIL: {msg}\n")
        sys.exit(1)

    sys.stdout.write("selftest PASS\n")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a facilitator process-plan JSON file.")
    parser.add_argument("plan_path", nargs="?", help="Path to the plan JSON file")
    parser.add_argument("--selftest", action="store_true", help="Run built-in smoke tests and exit")
    args = parser.parse_args()

    if args.selftest:
        _run_selftest()

    if not args.plan_path:
        parser.print_usage(sys.stderr)
        sys.stderr.write("ERROR: plan_path is required\n")
        sys.exit(1)

    path = Path(args.plan_path)
    violations = validate_file(path)

    if violations:
        for v in violations:
            sys.stderr.write(f"ERROR: {path} — {v}\n")
            sys.stderr.write(f"  {_schema_pointer_for(v)}\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
