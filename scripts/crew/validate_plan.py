#!/usr/bin/env python3
"""Validate a facilitator process-plan JSON file.

Usage:
    validate_plan.py <path-to-plan.json>
    validate_plan.py --selftest

Exit 0 on valid, exit 1 on invalid or selftest failure.
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

# Resolver import is best-effort — validate_plan is used in CI where the
# repo layout is guaranteed, but the import is guarded so a malformed
# agents/ tree surfaces a readable warning instead of a hard crash.
try:
    from crew.specialist_resolver import build_resolver, resolve_role
    _RESOLVER_AVAILABLE = True
except Exception:  # pragma: no cover - import-time safety net
    _RESOLVER_AVAILABLE = False
    build_resolver = None  # type: ignore[assignment]
    resolve_role = None  # type: ignore[assignment]

# Plugin root for resolver lookups. Mirrors the convention used in
# hooks/scripts/*: prefer the env var, fall back to the repo tree above
# this file. Kept module-level so tests can patch it if needed.
_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# Close-match cutoff chosen by difflib's default (0.6). Issue #573 asks
# for suggestions on unknown roles; three is enough to narrow without
# drowning the reader in look-alikes.
_CLOSE_MATCHES_N = 3
_CLOSE_MATCHES_CUTOFF = 0.6

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

# Issue #583: warning code for the test-strategy-missing gap. Plans that
# declare ``test_required: true`` on any task but omit the ``test-strategy``
# phase silently bypass the wicked-testing integration path — dispatches
# to ``wicked-testing:plan`` / ``wicked-testing:authoring`` never fire.
_WARN_TEST_STRATEGY_MISSING = "test-strategy-missing"
_TEST_STRATEGY_PHASE_NAME = "test-strategy"

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
    """Return a 'See: <doc> § <anchor>' hint for a given violation, or an
    empty string for file-level failures where the schema doc isn't the
    right reference (missing file, invalid JSON, non-object root).

    Copilot #569 review: don't mislead the user by citing the schema doc
    on errors whose fix is the file path or the JSON itself.
    """
    head = violation.split(" — ", 1)[0]
    # Strip index / dotted suffix so "tasks[0].metadata" → "tasks".
    section = head.split(".", 1)[0].split("[", 1)[0]
    if section not in _SECTION_ANCHORS:
        return ""
    return f"See: {SCHEMA_DOC} {_SECTION_ANCHORS[section]}"


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

    # Issue #573: every pick must resolve via the agent-frontmatter
    # resolver. Build the resolver once and re-use it across entries.
    resolver = None
    if _RESOLVER_AVAILABLE:
        try:
            resolver = build_resolver(_PLUGIN_ROOT)  # type: ignore[misc]
        except Exception:  # pragma: no cover - defensive
            resolver = None

    for i, entry in enumerate(specialists):
        if not isinstance(entry, dict):
            violations.append(f"specialists[{i}] — must be a dict")
            continue
        name = entry.get("name")
        if not name or not str(name).strip():
            violations.append(f"specialists[{i}].name — must be a non-empty string")
        if not entry.get("why") or not str(entry["why"]).strip():
            violations.append(f"specialists[{i}].why — must be a non-empty string")

        # Resolver check — applied only when the name is present and the
        # resolver loaded successfully. Unknown picks become blocking
        # errors with difflib suggestions so the facilitator can
        # self-correct a typo without re-running the rubric.
        if name and str(name).strip() and resolver is not None:
            role_name = str(name).strip()
            domain, subagent_type = resolve_role(role_name, resolver)  # type: ignore[misc]
            if domain is None or subagent_type is None:
                suggestions = difflib.get_close_matches(
                    role_name,
                    list(resolver.get("role_to_subagent", {}).keys()),
                    n=_CLOSE_MATCHES_N,
                    cutoff=_CLOSE_MATCHES_CUTOFF,
                )
                if suggestions:
                    hint = ", ".join(suggestions)
                    violations.append(
                        f"specialists[{i}].name — unknown specialist "
                        f"'{role_name}'; did you mean: {hint}?"
                    )
                else:
                    violations.append(
                        f"specialists[{i}].name — unknown specialist "
                        f"'{role_name}'; no close matches found in "
                        f"agents/**/*.md"
                    )

        # Expanded-form (Issue #573): validators accept picks emitted as
        # either a bare string (via ``name``) or the full triple
        # {name, domain, subagent_type}. When domain/subagent_type are
        # present, they must agree with the resolver — silent drift
        # between the expanded form and the agent frontmatter would
        # reintroduce the original engagement-tracker bug.
        if (
            isinstance(entry.get("domain"), str)
            or isinstance(entry.get("subagent_type"), str)
        ) and resolver is not None and name:
            role_name = str(name).strip()
            expected_domain, expected_subagent = resolve_role(role_name, resolver)  # type: ignore[misc]
            if expected_domain is not None and expected_subagent is not None:
                declared_domain = entry.get("domain")
                declared_subagent = entry.get("subagent_type")
                if (
                    isinstance(declared_domain, str)
                    and declared_domain != expected_domain
                ):
                    violations.append(
                        f"specialists[{i}].domain — '{declared_domain}' does "
                        f"not match resolved domain '{expected_domain}' for "
                        f"role '{role_name}'"
                    )
                if (
                    isinstance(declared_subagent, str)
                    and declared_subagent != expected_subagent
                ):
                    violations.append(
                        f"specialists[{i}].subagent_type — "
                        f"'{declared_subagent}' does not match resolved "
                        f"subagent_type '{expected_subagent}' for role "
                        f"'{role_name}'"
                    )


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


def _check_test_strategy_present(plan: dict) -> list:
    """Issue #583: warn when ``test_required: true`` tasks exist but the
    plan omits the ``test-strategy`` phase.

    Returns a list of structured warning dicts (never raises). Empty list
    when either no task opts into testing or a ``test-strategy`` phase is
    present. The warning is advisory — plans still validate — but it
    surfaces the qe integration bypass that used to go silent when the
    facilitator collapsed test-strategy into build for "crisp bugfixes."

    Each warning dict has:
      - ``code``: stable identifier (``test-strategy-missing``)
      - ``severity``: ``"warn"``
      - ``message``: human-readable explanation naming the offending task ids
    """
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        return []

    test_required_ids: list = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        meta = task.get("metadata")
        if not isinstance(meta, dict):
            continue
        if meta.get("test_required") is True:
            task_id = task.get("id")
            if task_id and str(task_id).strip():
                test_required_ids.append(str(task_id).strip())

    if not test_required_ids:
        return []

    phases = plan.get("phases")
    if isinstance(phases, list):
        for entry in phases:
            if isinstance(entry, dict) and entry.get("name") == _TEST_STRATEGY_PHASE_NAME:
                return []

    id_list = ", ".join(test_required_ids)
    message = (
        f"test_required=true on task(s) [{id_list}] but no test-strategy "
        f"phase in plan; wicked-testing specialists will not be dispatched"
    )
    return [
        {
            "code": _WARN_TEST_STRATEGY_MISSING,
            "severity": "warn",
            "message": message,
        }
    ]


def validate(plan: dict) -> list:
    """Return a list of violation strings (empty means valid)."""
    violations = []
    _check_top_level(plan, violations)
    _check_factors(plan, violations)
    _check_specialists(plan, violations)
    _check_phases(plan, violations)
    _check_tasks(plan, violations)
    return violations


def warnings(plan: dict) -> list:
    """Return a list of non-blocking warning dicts (Issue #583).

    Warnings are distinct from violations: they do NOT fail validation but
    surface advisory gaps (test-strategy missing, etc.). Kept as a separate
    function so callers that only care about reject/accept can ignore them.
    """
    out: list = []
    out.extend(_check_test_strategy_present(plan))
    return out


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
            pointer = _schema_pointer_for(v)
            if pointer:
                sys.stderr.write(f"  {pointer}\n")
        sys.exit(1)

    # Issue #583: emit non-blocking warnings after a clean validation so
    # the qe-integration-bypass gap surfaces in CI without failing the run.
    try:
        plan_text = path.read_text(encoding="utf-8")
        plan_obj = json.loads(plan_text)
        if isinstance(plan_obj, dict):
            for warn in warnings(plan_obj):
                sys.stderr.write(
                    f"WARN: {path} — [{warn['code']}] {warn['message']}\n"
                )
    except (OSError, json.JSONDecodeError):
        # Unreachable in practice — validate_file would have failed above —
        # but defense-in-depth: warnings must never turn a pass into a fail.
        # R4-suppressed by design: warnings are advisory; never block the pass
        # path when the warning-extraction itself cannot parse the plan.
        return

    sys.exit(0)


if __name__ == "__main__":
    main()
