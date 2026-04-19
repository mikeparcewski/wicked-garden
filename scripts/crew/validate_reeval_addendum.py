#!/usr/bin/env python3
"""Validate a re-evaluation addendum JSONL file or single JSON record (D2, D8).

Each line in a JSONL file (or a single stdin record) must conform to the
re-eval addendum schema defined in autonomy-and-checks-model.md §5.

Schema version 1.1.0 adds optional archetype fields (AC-4, AC-5).
1.0 records remain fully valid under this validator (backward-compat, AC-13).

Usage:
    validate_reeval_addendum.py <path-to-reeval-log.jsonl>
    validate_reeval_addendum.py --stdin            # read single record from stdin
    validate_reeval_addendum.py --selftest

Exit 0 on valid.
Exit 1 on any validation error — prints a descriptive message to stderr.

Stdlib-only.  No external dependencies.
"""

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema constants (per autonomy-and-checks-model.md §5)
# ---------------------------------------------------------------------------

REQUIRED_TOP_KEYS = frozenset({
    "chain_id",
    "triggered_at",
    "trigger",
    "prior_rigor_tier",
    "new_rigor_tier",
    "mutations",
    "mutations_applied",
    "mutations_deferred",
    "validator_version",
})

# v1.0 known triggers; v1.1.0 extends with qe-evaluator prefix (checked separately).
VALID_TRIGGERS = frozenset({"phase-end", "task-completion"})

# v1.1.0: qe-evaluator triggers use a prefix convention "qe-evaluator:<gate>".
QE_EVALUATOR_TRIGGER_PREFIX = "qe-evaluator:"

# v1.1.0: archetype enum (AC-5).
VALID_ARCHETYPES = frozenset({
    "code-repo",
    "docs-only",
    "skill-agent-authoring",
    "config-infra",
    "multi-repo",
    "testing-only",
    "schema-migration",
})

# v1.1.0: allowed manifest_path prefixes for qe-evaluator triggers (MINOR-1).
ALLOWED_QE_MANIFEST_PREFIXES = ("phases/testability/", "phases/evidence-quality/")
DISALLOWED_QE_MANIFEST_PREFIXES = ("phases/clarify/", "phases/design/")

VALID_RIGOR_TIERS = frozenset({"minimal", "standard", "full"})
VALID_MUTATION_OPS = frozenset({"prune", "augment", "re_tier"})

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_mutation(mut: object, label: str) -> "list[str]":
    """Validate a single mutation object.  Returns list of error strings."""
    errors: list[str] = []
    if not isinstance(mut, dict):
        errors.append(f"{label}: must be a JSON object, got {type(mut).__name__}")
        return errors
    op = mut.get("op")
    if op not in VALID_MUTATION_OPS:
        errors.append(
            f"{label}.op: '{op}' is not one of {sorted(VALID_MUTATION_OPS)}"
        )
    why = mut.get("why")
    if not why or not str(why).strip():
        errors.append(f"{label}.why: required, must be a non-empty string")
    if op == "re_tier":
        tier = mut.get("new_rigor_tier")
        if tier not in VALID_RIGOR_TIERS:
            errors.append(
                f"{label}.new_rigor_tier: '{tier}' is not one of {sorted(VALID_RIGOR_TIERS)}"
            )
    return errors


def _is_subset(candidate: list, superset: list) -> bool:
    """Return True if every item in candidate appears in superset (by JSON equality)."""
    # Serialise to canonical JSON strings for comparison
    sup_strs = {json.dumps(item, sort_keys=True) for item in superset}
    for item in candidate:
        if json.dumps(item, sort_keys=True) not in sup_strs:
            return False
    return True


def validate_record(record: object, line_num: "int | None" = None) -> "list[str]":
    """Validate a single addendum record dict.

    Args:
        record:   Parsed JSON object (expected to be a dict).
        line_num: 1-based line number for error messages; None for stdin records.

    Returns:
        List of human-readable error strings.  Empty means valid.
    """
    prefix = f"line {line_num}" if line_num is not None else "record"
    errors: list[str] = []

    if not isinstance(record, dict):
        errors.append(f"{prefix}: must be a JSON object, got {type(record).__name__}")
        return errors

    # Required keys
    missing = REQUIRED_TOP_KEYS - record.keys()
    for key in sorted(missing):
        errors.append(f"{prefix}: missing required key '{key}'")

    # trigger enum — v1.1.0 extends with qe-evaluator:<gate> prefix convention.
    trigger = record.get("trigger")
    if trigger is not None:
        is_qe_trigger = isinstance(trigger, str) and trigger.startswith(
            QE_EVALUATOR_TRIGGER_PREFIX
        )
        if not is_qe_trigger and trigger not in VALID_TRIGGERS:
            errors.append(
                f"{prefix}.trigger: '{trigger}' is not one of {sorted(VALID_TRIGGERS)} "
                f"and does not start with '{QE_EVALUATOR_TRIGGER_PREFIX}'"
            )

    # v1.1.0: qe-evaluator triggers must have empty mutations and mutations_applied.
    trigger_str = trigger if isinstance(trigger, str) else ""
    is_qe_trigger = trigger_str.startswith(QE_EVALUATOR_TRIGGER_PREFIX)
    if is_qe_trigger:
        mutations_val = record.get("mutations")
        if isinstance(mutations_val, list) and mutations_val:
            errors.append(
                f"{prefix}: qe-evaluator trigger must have empty mutations list; "
                f"got {len(mutations_val)} item(s)"
            )
        applied_val = record.get("mutations_applied")
        if isinstance(applied_val, list) and applied_val:
            errors.append(
                f"{prefix}: qe-evaluator trigger must have empty mutations_applied list; "
                f"got {len(applied_val)} item(s)"
            )

    # v1.1.0: validate optional archetype field when present.
    archetype = record.get("archetype")
    if archetype is not None:
        if archetype not in VALID_ARCHETYPES:
            errors.append(
                f"{prefix}.archetype: '{archetype}' is not one of "
                f"{sorted(VALID_ARCHETYPES)}"
            )

    # v1.1.0: validate archetype_evidence.conditions_deferred manifest_path prefixes.
    archetype_evidence = record.get("archetype_evidence")
    if isinstance(archetype_evidence, dict) and is_qe_trigger:
        conditions_deferred = archetype_evidence.get("conditions_deferred", [])
        if isinstance(conditions_deferred, list):
            for i, cond in enumerate(conditions_deferred):
                if not isinstance(cond, dict):
                    continue
                manifest_path = cond.get("manifest_path", "")
                if not manifest_path:
                    continue
                if not any(
                    manifest_path.startswith(pfx)
                    for pfx in ALLOWED_QE_MANIFEST_PREFIXES
                ):
                    errors.append(
                        f"{prefix}.archetype_evidence.conditions_deferred[{i}]"
                        f".manifest_path '{manifest_path}' must start with one of "
                        f"{list(ALLOWED_QE_MANIFEST_PREFIXES)} for qe-evaluator triggers"
                    )
                for disallowed in DISALLOWED_QE_MANIFEST_PREFIXES:
                    if manifest_path.startswith(disallowed):
                        errors.append(
                            f"{prefix}.archetype_evidence.conditions_deferred[{i}]"
                            f".manifest_path '{manifest_path}' must not start with "
                            f"'{disallowed}' for qe-evaluator triggers"
                        )

    # rigor tiers
    for tier_key in ("prior_rigor_tier", "new_rigor_tier"):
        tier_val = record.get(tier_key)
        if tier_val is not None and tier_val not in VALID_RIGOR_TIERS:
            errors.append(
                f"{prefix}.{tier_key}: '{tier_val}' is not one of {sorted(VALID_RIGOR_TIERS)}"
            )

    # mutations must be a list
    mutations = record.get("mutations")
    if mutations is not None:
        if not isinstance(mutations, list):
            errors.append(f"{prefix}.mutations: must be a JSON array")
        else:
            for i, mut in enumerate(mutations):
                errors.extend(_validate_mutation(mut, f"{prefix}.mutations[{i}]"))

    # mutations_applied ⊆ mutations
    applied = record.get("mutations_applied")
    deferred = record.get("mutations_deferred")
    if isinstance(mutations, list) and isinstance(applied, list):
        if not _is_subset(applied, mutations):
            errors.append(
                f"{prefix}: mutations_applied contains entries not present in mutations"
            )
    elif applied is not None and not isinstance(applied, list):
        errors.append(f"{prefix}.mutations_applied: must be a JSON array")

    # mutations_deferred ⊆ mutations
    if isinstance(mutations, list) and isinstance(deferred, list):
        if not _is_subset(deferred, mutations):
            errors.append(
                f"{prefix}: mutations_deferred contains entries not present in mutations"
            )
    elif deferred is not None and not isinstance(deferred, list):
        errors.append(f"{prefix}.mutations_deferred: must be a JSON array")

    return errors


def validate_jsonl_path(path: Path) -> "tuple[bool, list[str]]":
    """Validate every line in a JSONL file.

    Returns (is_valid, errors).  Stops on the first invalid line.
    """
    if not path.exists():
        return False, [f"File not found: {path}"]
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, [f"Cannot read {path}: {exc}"]

    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue  # skip blank lines
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_num}: JSON parse error — {exc}")
            return False, errors
        line_errors = validate_record(record, line_num)
        if line_errors:
            errors.extend(line_errors)
            return False, errors

    return True, []


def validate_stdin_record() -> "tuple[bool, list[str]]":
    """Read a single JSON record from stdin and validate it."""
    raw = sys.stdin.read()
    if not raw.strip():
        return False, ["stdin: no input received"]
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, [f"stdin: JSON parse error — {exc}"]
    errors = validate_record(record, line_num=None)
    if errors:
        return False, errors
    return True, []


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

_VALID_RECORD = {
    "chain_id": "v6-reliable-autonomy.design",
    "triggered_at": "2026-04-18T18:45:00Z",
    "trigger": "phase-end",
    "prior_rigor_tier": "full",
    "new_rigor_tier": "standard",
    "factor_deltas": {
        "compliance_scope": {"old_reading": "HIGH", "new_reading": "LOW"}
    },
    "mutations": [
        {"op": "re_tier", "new_rigor_tier": "standard", "why": "2 factors disproven"},
        {"op": "augment", "task_id": "t5b", "why": "Schema migration needed"},
        {"op": "prune", "task_id": "t4c", "why": "Auth scaffolding already exists"},
    ],
    "mutations_applied": [
        {"op": "re_tier", "new_rigor_tier": "standard", "why": "2 factors disproven"},
        {"op": "augment", "task_id": "t5b", "why": "Schema migration needed"},
        {"op": "prune", "task_id": "t4c", "why": "Auth scaffolding already exists"},
    ],
    "mutations_deferred": [],
    "validator_version": "1.0.0",
}


def _run_selftest() -> bool:
    """Run built-in self-test.  Returns True on pass."""
    failed = []

    # Case 1: valid record → no errors
    errs = validate_record(_VALID_RECORD)
    if errs:
        failed.append(f"FAIL valid-record: unexpected errors {errs}")
    else:
        print("PASS valid-record", file=sys.stderr)

    # Case 2: missing required key
    bad = dict(_VALID_RECORD)
    del bad["chain_id"]
    errs = validate_record(bad)
    if not any("chain_id" in e for e in errs):
        failed.append("FAIL missing-key: expected error for missing chain_id")
    else:
        print("PASS missing-key", file=sys.stderr)

    # Case 3: unknown trigger
    bad = dict(_VALID_RECORD, trigger="unknown-trigger")
    errs = validate_record(bad)
    if not any("trigger" in e for e in errs):
        failed.append("FAIL unknown-trigger: expected error")
    else:
        print("PASS unknown-trigger", file=sys.stderr)

    # Case 4: mutations_applied not subset of mutations
    bad = dict(_VALID_RECORD)
    bad["mutations_applied"] = [{"op": "prune", "task_id": "t99", "why": "orphan"}]
    errs = validate_record(bad)
    if not any("mutations_applied" in e for e in errs):
        failed.append("FAIL applied-not-subset: expected error")
    else:
        print("PASS applied-not-subset", file=sys.stderr)

    # Case 5: invalid rigor tier
    bad = dict(_VALID_RECORD, new_rigor_tier="ultra")
    errs = validate_record(bad)
    if not any("new_rigor_tier" in e for e in errs):
        failed.append("FAIL bad-tier: expected error")
    else:
        print("PASS bad-tier", file=sys.stderr)

    if failed:
        for msg in failed:
            print(msg, file=sys.stderr)
        return False
    print("All selftests PASSED", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a re-evaluation addendum JSONL file or stdin record."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to a reeval-log.jsonl file (mutually exclusive with --stdin)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read a single JSON record from stdin instead of a file",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run built-in self-test and exit 0/1",
    )
    args = parser.parse_args()

    if args.selftest:
        sys.exit(0 if _run_selftest() else 1)

    if args.stdin:
        valid, errors = validate_stdin_record()
    elif args.path:
        valid, errors = validate_jsonl_path(Path(args.path))
    else:
        parser.error("Provide a file path or use --stdin / --selftest")
        return  # unreachable; satisfies type checkers

    if not valid:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
