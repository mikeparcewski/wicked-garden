#!/usr/bin/env python3
"""
Gate-1 measurement: score facilitator rubric output against canonical scenarios.

Usage:
    python3 scripts/ci/measure_facilitator.py [--scenarios DIR] [--output DIR]
    python3 scripts/ci/measure_facilitator.py --scenario 04-auth-rewrite

Mechanics
---------
Each scenario under scenarios/crew/facilitator-rubric/ carries a YAML
expected_outcome block inside ```yaml ... ``` fences. The facilitator rubric
(skills/propose-process) emits a JSON object matching
refs/output-schema.md. This script loads both, compares them across six
dimensions, and prints a per-scenario + overall pass/fail report.

The LLM invocation itself is deferred — this script can run in two modes:

- "live": spawns a Claude invocation (future work, stubbed).
- "replay": reads pre-captured JSON outputs from a directory (default:
  scripts/ci/facilitator_outputs/<scenario>.json). This is the CI mode.

Replay mode lets Gate-1 iterate on the rubric: capture output once by running
the facilitator skill manually, save JSON per scenario, then run this script
to see the score.

Stdlib only — no third-party deps. Cross-platform (macOS, Linux, Windows).

Exit codes:
    0 — overall pass (>= 80% scenarios match)
    1 — overall fail
    2 — configuration error (missing scenarios, bad YAML, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SCENARIOS = REPO_ROOT / "scenarios" / "crew" / "facilitator-rubric"
DEFAULT_OUTPUTS = REPO_ROOT / "scripts" / "ci" / "facilitator_outputs"

# Dimensions scored per scenario.
DIMENSIONS = [
    "specialists",
    "phases",
    "evidence_required",
    "test_types",
    "complexity",
    "rigor_tier",
]

# Per-scenario pass threshold (fraction of applicable dimensions matched).
SCENARIO_PASS_THRESHOLD = 0.80

# Overall Gate-1 pass threshold (fraction of scenarios passing).
GATE_PASS_THRESHOLD = 0.80


# ----------------------------------------------------------------------------
# Minimal YAML parser (sufficient for our expected_outcome blocks).
# ----------------------------------------------------------------------------

def _parse_yaml(text: str) -> dict:
    """Parse a subset of YAML: keys, strings, ints, bools, lists of scalars,
    nested mappings. Enough for the expected_outcome blocks in scenarios.
    Raises ValueError on unsupported constructs."""

    root: dict = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    list_key: list[tuple[int, str]] = []

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        # strip trailing comments (outside quotes)
        line = _strip_comment(line)
        if not line.strip():
            i += 1
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        # Pop contexts with greater-or-equal indent.
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            stack = [(-1, root)]

        parent_indent, parent = stack[-1]

        if stripped.startswith("- "):
            # list item
            value = stripped[2:].strip()
            # find the list this belongs to in parent
            # The parent should be a list OR we should have set one implicitly.
            if not isinstance(parent, list):
                # Nearest key whose value is a list
                raise ValueError(f"list item without containing list: {stripped!r}")
            # nested mapping in list item?
            if ":" in value and not value.startswith('"') and not value.startswith("'"):
                entry: dict = {}
                k, _, v = value.partition(":")
                k = k.strip()
                v = v.strip()
                if v:
                    entry[k] = _scalar(v)
                else:
                    pass  # intentional no-op: value continues as a nested mapping on subsequent indented lines
                parent.append(entry)
                stack.append((indent, entry))
            else:
                parent.append(_scalar(value))
            i += 1
            continue

        if ":" in stripped:
            key, _, rest = stripped.partition(":")
            key = key.strip()
            rest = rest.strip()

            if rest == "":
                # nested structure follows — peek ahead.
                # create an empty placeholder, decide dict vs list from next line
                next_idx = i + 1
                while next_idx < len(lines):
                    nxt = lines[next_idx]
                    nxt_stripped = _strip_comment(nxt).strip()
                    if nxt_stripped:
                        break
                    next_idx += 1
                nxt_indent = (
                    len(lines[next_idx]) - len(lines[next_idx].lstrip(" "))
                    if next_idx < len(lines)
                    else indent
                )
                if next_idx < len(lines) and nxt_indent > indent and lines[
                    next_idx
                ].lstrip().startswith("- "):
                    container: Any = []
                else:
                    container = {}
                if isinstance(parent, dict):
                    parent[key] = container
                elif isinstance(parent, list):
                    raise ValueError(
                        f"unexpected mapping key inside list: {stripped!r}"
                    )
                stack.append((indent, container))
            else:
                value = _scalar(rest)
                if isinstance(parent, dict):
                    parent[key] = value
                else:
                    raise ValueError(f"mapping into non-dict: {stripped!r}")
            i += 1
            continue

        raise ValueError(f"unparseable line: {raw!r}")

    return root


def _strip_comment(line: str) -> str:
    """Strip # comments outside quoted strings."""
    out = []
    in_single = in_double = False
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out)


def _split_flow_items(text: str) -> list[str]:
    """Split `foo, "bar, baz", qux` respecting quoted commas."""
    items: list[str] = []
    buf: list[str] = []
    in_quote: str | None = None
    for ch in text:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            buf.append(ch)
        elif ch == ",":
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf).strip())
    return [i for i in items if i]


def _scalar(text: str) -> Any:
    """Coerce a YAML scalar to Python."""
    t = text.strip()
    if t.startswith('"') and t.endswith('"'):
        return t[1:-1]
    if t.startswith("'") and t.endswith("'"):
        return t[1:-1]
    # Inline flow lists — `[]` or `[foo, bar, "baz"]`
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        if not inner:
            return []
        return [_scalar(item) for item in _split_flow_items(inner)]
    # Inline flow dicts — `{}` (empty only; not needed beyond that here)
    if t == "{}":
        return {}
    if t.lower() in {"true", "yes"}:
        return True
    if t.lower() in {"false", "no"}:
        return False
    if t.lower() in {"null", "~", ""}:
        return None
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    return t


# ----------------------------------------------------------------------------
# Scenario loading.
# ----------------------------------------------------------------------------


@dataclass
class Scenario:
    name: str
    path: Path
    expected: dict
    # For scenario 09 which has pass-1 AND pass-2 blocks.
    extra_blocks: list[dict] = field(default_factory=list)


def load_scenario(path: Path) -> Scenario:
    text = path.read_text(encoding="utf-8")
    # Collect all ```yaml code fences after the "Expected outcome" heading.
    blocks = _extract_yaml_blocks(text)
    if not blocks:
        raise ValueError(f"{path}: no ```yaml expected_outcome block found")
    return Scenario(
        name=path.stem,
        path=path,
        expected=blocks[0],
        extra_blocks=blocks[1:],
    )


def _extract_yaml_blocks(text: str) -> list[dict]:
    blocks = []
    fence_re = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)
    for m in fence_re.finditer(text):
        raw = m.group(1)
        try:
            parsed = _parse_yaml(raw)
        except ValueError as e:
            raise ValueError(f"bad YAML in block: {e}\n---\n{raw}")
        blocks.append(parsed)
    return blocks


# ----------------------------------------------------------------------------
# Scoring.
# ----------------------------------------------------------------------------


@dataclass
class DimensionResult:
    name: str
    matched: bool
    detail: str


@dataclass
class ScenarioResult:
    scenario: str
    dimensions: list[DimensionResult]

    @property
    def applicable_count(self) -> int:
        return len(self.dimensions)

    @property
    def matched_count(self) -> int:
        return sum(1 for d in self.dimensions if d.matched)

    @property
    def score(self) -> float:
        if not self.dimensions:
            return 0.0
        return self.matched_count / self.applicable_count

    @property
    def passed(self) -> bool:
        return self.score >= SCENARIO_PASS_THRESHOLD


def score_scenario(scen: Scenario, output: dict) -> ScenarioResult:
    expected = scen.expected
    results: list[DimensionResult] = []

    # specialists — expected ⊆ picked; banned names cannot appear.
    picked = _collect_specialists(output)
    expected_specs = _as_list(expected.get("specialists"))
    banned = _as_list(expected.get("banned_specialists"))
    missing = [s for s in expected_specs if s not in picked]
    banned_hits = [s for s in banned if s in picked]
    if not missing and not banned_hits:
        results.append(DimensionResult("specialists", True, "ok"))
    else:
        detail = []
        if missing:
            detail.append(f"missing: {missing}")
        if banned_hits:
            detail.append(f"banned picked: {banned_hits}")
        results.append(
            DimensionResult("specialists", False, "; ".join(detail))
        )

    # phases — expected ⊆ output.phases; extras OK.
    picked_phases = [p["name"] if isinstance(p, dict) else p for p in
                     _as_list(output.get("phases"))]
    expected_phases = _as_list(expected.get("phases"))
    missing_phases = [p for p in expected_phases if p not in picked_phases]
    if not missing_phases:
        results.append(DimensionResult("phases", True, "ok"))
    else:
        results.append(
            DimensionResult("phases", False, f"missing: {missing_phases}")
        )

    # evidence_required — expected ⊆ union over tasks.
    picked_evidence = _union_over_tasks(output, "evidence_required")
    # Also accept a top-level evidence_required if present (some scenarios use it).
    picked_evidence |= set(_as_list(output.get("evidence_required")))
    expected_evidence = set(_as_list(expected.get("evidence_required")))
    missing_evidence = expected_evidence - picked_evidence
    if not missing_evidence:
        results.append(DimensionResult("evidence_required", True, "ok"))
    else:
        results.append(
            DimensionResult(
                "evidence_required", False,
                f"missing: {sorted(missing_evidence)}"
            )
        )

    # test_types — expected ⊆ union over tasks + top-level.
    picked_types = _union_over_tasks(output, "test_types")
    picked_types |= set(_as_list(output.get("test_types")))
    expected_types = set(_as_list(expected.get("test_types")))
    missing_types = expected_types - picked_types
    if not missing_types:
        results.append(DimensionResult("test_types", True, "ok"))
    else:
        results.append(
            DimensionResult(
                "test_types", False, f"missing: {sorted(missing_types)}"
            )
        )

    # complexity — abs(expected - actual) <= tolerance.
    expected_complexity = expected.get("complexity")
    actual_complexity = output.get("complexity")
    tolerance = 1
    if scen.name.startswith("08-"):
        tolerance = 2
    if (
        isinstance(expected_complexity, int)
        and isinstance(actual_complexity, int)
        and abs(expected_complexity - actual_complexity) <= tolerance
    ):
        results.append(DimensionResult("complexity", True, "ok"))
    else:
        results.append(
            DimensionResult(
                "complexity",
                False,
                f"expected {expected_complexity} +/- {tolerance}, "
                f"got {actual_complexity}",
            )
        )

    # rigor_tier — exact match, with a permissive rule for scenario 05/06
    # that allow either minimal or standard provided the plan explains why.
    expected_rigor = expected.get("rigor_tier")
    actual_rigor = output.get("rigor_tier")
    if expected_rigor == actual_rigor:
        results.append(DimensionResult("rigor_tier", True, "ok"))
    else:
        results.append(
            DimensionResult(
                "rigor_tier",
                False,
                f"expected {expected_rigor!r}, got {actual_rigor!r}",
            )
        )

    # Scenario 8: open_questions must be non-empty.
    if scen.name.startswith("08-"):
        oq = _as_list(output.get("open_questions"))
        matched = len(oq) >= 2
        results.append(
            DimensionResult(
                "open_questions",
                matched,
                "ok" if matched else f"expected >=2, got {len(oq)}",
            )
        )

    # Scenario 9: re-evaluation must augment.
    if scen.name.startswith("09-") and scen.extra_blocks:
        reev = output.get("re_evaluation") or {}
        augmented = _as_list(reev.get("augmented"))
        matched = len(augmented) >= 1
        results.append(
            DimensionResult(
                "re_evaluation",
                matched,
                "ok" if matched else "no augmentation in pass-2 output",
            )
        )

    # Scenario 4 and 10: yolo_forbidden must be honored.
    if scen.name.startswith(("04-", "10-")):
        yf = output.get("yolo_forbidden")
        matched = yf is True
        results.append(
            DimensionResult(
                "yolo_forbidden",
                matched,
                "ok" if matched else f"expected True, got {yf!r}",
            )
        )

    return ScenarioResult(scen.name, results)


def _collect_specialists(output: dict) -> set[str]:
    """Union across top-level specialists[] and per-task specialist."""
    out = set()
    for s in _as_list(output.get("specialists")):
        if isinstance(s, dict):
            out.add(s.get("name"))
        else:
            out.add(s)
    for t in _as_list(output.get("tasks")):
        if isinstance(t, dict) and t.get("specialist"):
            out.add(t["specialist"])
    return {s for s in out if s}


def _union_over_tasks(output: dict, key: str) -> set[str]:
    out: set[str] = set()
    for t in _as_list(output.get("tasks")):
        if not isinstance(t, dict):
            continue
        meta = t.get("metadata") or t
        for v in _as_list(meta.get(key)):
            out.add(v)
    return out


def _as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


# ----------------------------------------------------------------------------
# CLI + reporting.
# ----------------------------------------------------------------------------


def discover_scenarios(root: Path, only: str | None) -> list[Scenario]:
    if not root.exists():
        raise FileNotFoundError(root)
    paths = sorted(root.glob("*.md"))
    if only:
        paths = [p for p in paths if p.stem == only or p.stem.startswith(only)]
    return [load_scenario(p) for p in paths]


def load_output(outputs_dir: Path, scenario: Scenario) -> dict | None:
    path = outputs_dir / f"{scenario.name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON: {e}") from e


def print_report(results: list[ScenarioResult]) -> bool:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    overall = (passed / total) if total else 0.0

    # Per-dimension tallies across all scenarios.
    dim_totals: dict[str, tuple[int, int]] = {}
    for r in results:
        for d in r.dimensions:
            m, a = dim_totals.get(d.name, (0, 0))
            dim_totals[d.name] = (m + (1 if d.matched else 0), a + 1)

    print("=" * 70)
    print("Facilitator Rubric — Gate-1 Measurement")
    print("=" * 70)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n[{status}] {r.scenario}  ({r.matched_count}/{r.applicable_count})")
        for d in r.dimensions:
            mark = "OK  " if d.matched else "FAIL"
            print(f"    {mark}  {d.name:22s} {d.detail}")

    print("\n" + "-" * 70)
    print("Per-dimension totals (passed/applicable):")
    for name in sorted(dim_totals):
        m, a = dim_totals[name]
        pct = (m / a * 100) if a else 0.0
        print(f"  {name:22s} {m}/{a}  ({pct:5.1f}%)")

    print("-" * 70)
    print(f"Scenarios passed: {passed}/{total}  ({overall * 100:.1f}%)")
    print(f"Gate threshold:   {GATE_PASS_THRESHOLD * 100:.0f}%")
    gate_pass = overall >= GATE_PASS_THRESHOLD
    print(f"Result:           {'PASS' if gate_pass else 'FAIL'}")
    print("=" * 70)
    return gate_pass


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=DEFAULT_SCENARIOS,
        help="Directory containing scenario *.md files",
    )
    parser.add_argument(
        "--outputs",
        type=Path,
        default=DEFAULT_OUTPUTS,
        help="Directory containing captured JSON outputs (replay mode)",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Score only this scenario (name prefix, e.g. '04' or '04-auth-rewrite')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout (in addition to report)",
    )
    args = parser.parse_args(argv)

    try:
        scenarios = discover_scenarios(args.scenarios, args.scenario)
    except FileNotFoundError as e:
        print(f"error: scenarios dir not found: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not scenarios:
        print("error: no scenarios matched", file=sys.stderr)
        return 2

    results: list[ScenarioResult] = []
    missing_outputs: list[str] = []
    for scen in scenarios:
        output = load_output(args.outputs, scen)
        if output is None:
            missing_outputs.append(scen.name)
            # Emit an empty result so the report still shows the row.
            results.append(ScenarioResult(scen.name, [
                DimensionResult(d, False, "no captured output")
                for d in DIMENSIONS
            ]))
            continue
        results.append(score_scenario(scen, output))

    gate_pass = print_report(results)

    if missing_outputs:
        print(
            "\nNOTE: no captured facilitator output for: "
            + ", ".join(missing_outputs),
            file=sys.stderr,
        )
        print(
            f"Capture JSON under {args.outputs}/<scenario>.json "
            "(see skills/propose-process/refs/output-schema.md).",
            file=sys.stderr,
        )

    if args.json:
        print(json.dumps({
            "scenarios": [
                {
                    "name": r.scenario,
                    "passed": r.passed,
                    "score": r.score,
                    "dimensions": [
                        {"name": d.name, "matched": d.matched, "detail": d.detail}
                        for d in r.dimensions
                    ],
                }
                for r in results
            ],
            "overall_passed": gate_pass,
            "overall_score": (
                sum(1 for r in results if r.passed) / len(results)
                if results else 0.0
            ),
        }, indent=2))

    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
