#!/usr/bin/env python3
"""
Gate 4 Phase 1 — facilitator smoke suite.

Loads unseen project descriptions from scripts/ci/gate4_smoke_inputs/, checks
that a pre-captured facilitator plan exists for each under
scripts/ci/facilitator_outputs/smoke-NN-<slug>.json, scores each plan against
the input's expected_outcome block, and emits pass/fail.

Scoring is deliberately loose — these inputs are unseen by Gate 1 calibration,
so the rubric uses "subset" / "one_of" / "candidate_ok" gates rather than
strict equality. The point is to catch obviously-wrong plans (full rigor on a
typo, minimal rigor on a migration), not to re-litigate calibration.

Usage
-----
    python3 scripts/ci/gate4_smoke.py                      # score captured outputs
    python3 scripts/ci/gate4_smoke.py --input smoke-02     # single input

Exit codes: 0 all pass, 1 at least one fail, 2 configuration error.

Stdlib-only. Cross-platform (macOS, Linux, Windows).

Note: the v5 `--with-legacy` / `--capture` flag was removed in #428 when
`scripts/crew/smart_decisioning.py` was deleted alongside the rule engine.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INPUTS_DIR = REPO_ROOT / "scripts" / "ci" / "gate4_smoke_inputs"
OUTPUTS_DIR = REPO_ROOT / "scripts" / "ci" / "facilitator_outputs"


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

_YAML_FENCE = re.compile(r"```yaml\s*\n(.*?)\n```", re.DOTALL)


def _read_yaml_block(text: str) -> dict:
    """Extract and parse the expected_outcome YAML block.

    Intentionally minimal parser — we only need to handle the flat key:value
    and simple list shapes used in the smoke input files. Avoids PyYAML dep.
    """
    m = _YAML_FENCE.search(text)
    if not m:
        raise ValueError("input missing ```yaml ... ``` block")
    body = m.group(1)
    return _parse_simple_yaml(body)


def _parse_simple_yaml(body: str) -> dict:
    """Very small YAML subset parser covering our smoke input shape.

    Supports: top-level scalars (str, int, bool), flow lists [a, b, c],
    block lists (- item), and one level of nested dicts.
    """
    out: dict = {}
    lines = [ln.rstrip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0 and ":" in stripped:
            key, _, rest = stripped.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest == "":
                # Block value: either a nested dict or a block list follows
                collected_dict: dict = {}
                collected_list: list = []
                j = i + 1
                mode = None
                while j < len(lines):
                    sub = lines[j]
                    sub_stripped = sub.lstrip()
                    sub_indent = len(sub) - len(sub_stripped)
                    if sub_indent == 0:
                        break
                    if sub_stripped.startswith("- "):
                        mode = "list"
                        collected_list.append(_coerce_scalar(sub_stripped[2:].strip()))
                    elif ":" in sub_stripped:
                        mode = "dict"
                        k2, _, v2 = sub_stripped.partition(":")
                        collected_dict[k2.strip()] = _coerce_value(v2.strip())
                    j += 1
                out[key] = collected_list if mode == "list" else collected_dict
                i = j
                continue
            out[key] = _coerce_value(rest)
        i += 1
    return out


def _coerce_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_coerce_scalar(part.strip()) for part in inner.split(",")]
    return _coerce_scalar(raw)


def _coerce_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        return raw


_DESC_HEADER = re.compile(r"^##\s+description\s*$", re.MULTILINE | re.IGNORECASE)


def _read_description(text: str) -> str:
    m = _DESC_HEADER.search(text)
    if not m:
        raise ValueError("input missing '## description' section")
    tail = text[m.end():]
    # Take everything until next ## header
    stop = re.search(r"^##\s+", tail, re.MULTILINE)
    body = tail[: stop.start()] if stop else tail
    return body.strip()


def load_input(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    return {
        "slug": path.stem.split("-", 1)[1] if "-" in path.stem else path.stem,
        "id": path.stem,
        "path": str(path),
        "description": _read_description(raw),
        "expected_outcome": _read_yaml_block(raw),
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _names(items: list) -> list[str]:
    """Normalize list-of-dicts-with-name or list-of-strings to list of names."""
    out: list[str] = []
    for it in items or []:
        if isinstance(it, dict):
            n = it.get("name") or it.get("id")
            if n:
                out.append(str(n))
        else:
            out.append(str(it))
    return out


def _phase_names(plan: dict) -> list[str]:
    return _names(plan.get("phases") or [])


def _specialist_names(plan: dict) -> list[str]:
    return _names(plan.get("specialists") or [])


def _evidence_union(plan: dict) -> set[str]:
    out: set[str] = set()
    for e in plan.get("evidence_required") or []:
        out.add(str(e))
    for t in plan.get("tasks") or []:
        for e in (t.get("metadata") or {}).get("evidence_required") or []:
            out.add(str(e))
    return out


def _test_types_union(plan: dict) -> set[str]:
    out: set[str] = set()
    for tt in plan.get("test_types") or []:
        out.add(str(tt))
    for t in plan.get("tasks") or []:
        for tt in (t.get("metadata") or {}).get("test_types") or []:
            out.add(str(tt))
    return out


def _factor_reading(plan: dict, factor: str) -> str:
    # NB(#627): scenario YAMLs declare expectations as LOW/MEDIUM/HIGH (the
    # backward-compat `reading` convention; HIGH=safest). Internal-only CI
    # comparison — never surfaced to users in this form. User-facing output
    # should prefer the `risk_level` field (`low_risk`/`medium_risk`/`high_risk`).
    f = (plan.get("factors") or {}).get(factor) or {}
    return str(f.get("reading") or "").upper()


def score_plan(plan: dict, expected: dict) -> dict:
    """Return dict of dimension -> (pass: bool, note: str)."""
    results: dict[str, tuple[bool, str]] = {}

    # rigor_tier
    if "rigor_tier" in expected:
        want = str(expected["rigor_tier"])
        got = str(plan.get("rigor_tier") or "")
        results["rigor_tier"] = (got == want, f"want={want} got={got}")
    elif "rigor_tier_one_of" in expected:
        want = expected["rigor_tier_one_of"]
        got = str(plan.get("rigor_tier") or "")
        results["rigor_tier"] = (got in want, f"one_of={want} got={got}")

    # complexity
    if "complexity_range" in expected:
        lo, hi = expected["complexity_range"]
        got = int(plan.get("complexity") or -1)
        results["complexity"] = (lo <= got <= hi, f"range=[{lo},{hi}] got={got}")

    # tasks count
    task_count = len(plan.get("tasks") or [])
    if "tasks_min" in expected:
        mn = int(expected["tasks_min"])
        results["tasks_min"] = (task_count >= mn, f"min={mn} got={task_count}")
    if "tasks_max" in expected:
        mx = int(expected["tasks_max"])
        results["tasks_max"] = (task_count <= mx, f"max={mx} got={task_count}")

    # phases
    plan_phases = set(_phase_names(plan))
    if "phases_subset" in expected:
        want = set(expected["phases_subset"])
        missing = want - plan_phases
        results["phases_subset"] = (not missing, f"want_subset={sorted(want)} missing={sorted(missing)}")
    if "phases_must_not_include" in expected:
        want_out = set(expected["phases_must_not_include"])
        intersect = want_out & plan_phases
        results["phases_must_not_include"] = (not intersect, f"forbidden={sorted(want_out)} found={sorted(intersect)}")
    if "phases_strongly_preferred" in expected:
        want_pref = set(expected["phases_strongly_preferred"])
        missing = want_pref - plan_phases
        # Preferred = warning, not fail. Note only.
        results["phases_strongly_preferred"] = (True, f"preferred={sorted(want_pref)} missing={sorted(missing)} (advisory)")

    # specialists — subset must appear; candidate_ok is informational
    plan_specialists = set(_specialist_names(plan))
    if "specialists_subset" in expected:
        want = set(expected["specialists_subset"])
        missing = want - plan_specialists
        results["specialists_subset"] = (not missing, f"want_subset={sorted(want)} missing={sorted(missing)}")

    # evidence
    plan_evidence = _evidence_union(plan)
    if "evidence_one_of" in expected:
        want_any = set(expected["evidence_one_of"])
        ok = bool(want_any & plan_evidence)
        results["evidence_one_of"] = (ok, f"one_of={sorted(want_any)} got={sorted(plan_evidence)}")
    if "evidence_subset" in expected:
        want_all = set(expected["evidence_subset"])
        missing = want_all - plan_evidence
        results["evidence_subset"] = (not missing, f"want_subset={sorted(want_all)} missing={sorted(missing)}")

    # test_types
    plan_test_types = _test_types_union(plan)
    if "test_types_one_of" in expected:
        want_any = set(expected["test_types_one_of"])
        ok = bool(want_any & plan_test_types)
        results["test_types_one_of"] = (ok, f"one_of={sorted(want_any)} got={sorted(plan_test_types)}")
    if "test_types_subset" in expected:
        want_all = set(expected["test_types_subset"])
        missing = want_all - plan_test_types
        results["test_types_subset"] = (not missing, f"want_subset={sorted(want_all)} missing={sorted(missing)}")

    # factors
    want_factors = expected.get("factors") or {}
    for factor, allowed in want_factors.items():
        got = _factor_reading(plan, factor)
        allowed_upper = [str(a).upper() for a in allowed]
        results[f"factor:{factor}"] = (got in allowed_upper, f"allowed={allowed_upper} got={got}")

    # open_questions_allowed
    if "open_questions_allowed" in expected:
        allowed = bool(expected["open_questions_allowed"])
        has = bool(plan.get("open_questions"))
        if not allowed:
            results["open_questions"] = (not has, f"forbidden; got {len(plan.get('open_questions') or [])}")
        else:
            results["open_questions"] = (True, f"allowed; got {len(plan.get('open_questions') or [])}")

    return results


def verdict(dimension_results: dict) -> tuple[bool, int, int]:
    """(pass, num_passed, num_total). Advisory dims (phases_strongly_preferred) don't count."""
    passed = 0
    total = 0
    for k, (ok, _) in dimension_results.items():
        if k == "phases_strongly_preferred":
            continue
        total += 1
        if ok:
            passed += 1
    return (passed == total, passed, total)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def iter_inputs(filter_id: str | None = None) -> list[dict]:
    if not INPUTS_DIR.exists():
        raise SystemExit(f"[gate4_smoke] inputs dir missing: {INPUTS_DIR}")
    out: list[dict] = []
    for p in sorted(INPUTS_DIR.glob("smoke-*.md")):
        data = load_input(p)
        if filter_id and filter_id not in data["id"]:
            continue
        out.append(data)
    return out


def load_facilitator_plan(input_id: str) -> dict | None:
    candidate = OUTPUTS_DIR / f"{input_id}.json"
    if not candidate.exists():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"[gate4_smoke] plan parse error {candidate}: {e}\n")
        return None


def print_report(input_data: dict, plan: dict, scores: dict) -> bool:
    ok, passed, total = verdict(scores)
    status = "PASS" if ok else "FAIL"
    print(f"\n=== {input_data['id']} — {status} ({passed}/{total}) ===")
    print(f"  slug            : {plan.get('project_slug', '(missing)')}")
    print(f"  rigor_tier      : {plan.get('rigor_tier')}")
    print(f"  complexity      : {plan.get('complexity')}")
    print(f"  tasks           : {len(plan.get('tasks') or [])}")
    print(f"  phases          : {_phase_names(plan)}")
    print(f"  specialists     : {_specialist_names(plan)}")
    print(f"  evidence        : {sorted(_evidence_union(plan))}")
    print(f"  test_types      : {sorted(_test_types_union(plan))}")
    print(f"  open_questions  : {len(plan.get('open_questions') or [])}")
    print("  --- dimensions ---")
    for dim, (dok, note) in sorted(scores.items()):
        marker = "OK" if dok else "XX"
        print(f"    [{marker}] {dim:30s} {note}")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gate 4 facilitator smoke suite")
    ap.add_argument("--input", type=str, default=None,
                    help="filter inputs by id substring (e.g. smoke-02)")
    args = ap.parse_args(argv)

    try:
        inputs = iter_inputs(args.input)
    except SystemExit:
        raise
    if not inputs:
        sys.stderr.write("[gate4_smoke] no inputs found\n")
        return 2

    overall_ok = True
    results_by_id: dict[str, dict] = {}
    for item in inputs:
        plan = load_facilitator_plan(item["id"])
        if plan is None:
            print(f"\n=== {item['id']} — FAIL (no plan captured) ===")
            print(f"    expected: {OUTPUTS_DIR / (item['id'] + '.json')}")
            overall_ok = False
            results_by_id[item["id"]] = {"pass": False, "note": "plan missing"}
            continue
        scores = score_plan(plan, item["expected_outcome"])
        ok = print_report(item, plan, scores)
        overall_ok = overall_ok and ok
        results_by_id[item["id"]] = {
            "pass": ok,
            "scores": {k: {"pass": v[0], "note": v[1]} for k, v in scores.items()},
        }

    print("\n=== overall ===")
    print(f"  verdict: {'PASS' if overall_ok else 'FAIL'}")
    print(f"  inputs : {len(inputs)}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
