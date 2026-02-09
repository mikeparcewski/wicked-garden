#!/usr/bin/env python3
"""
E2E Test Runner for wicked-smaht v2.

Tests the orchestrator with real scenarios and validates:
1. Correct routing (fast vs slow path)
2. Intent detection accuracy
3. Latency within targets
4. Context quality (sources queried)

Usage:
    python test_runner.py                    # Run all scenarios (routing only)
    python test_runner.py --scenario small-01  # Run specific scenario
    python test_runner.py --execute          # Actually execute tasks (needs Claude)
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add v2 scripts to path
V2_DIR = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(V2_DIR))

from router import Router, IntentType, PathDecision
from orchestrator import Orchestrator


@dataclass
class ScenarioResult:
    """Result of running a scenario."""
    scenario_id: str
    name: str
    complexity: str

    # Routing results
    actual_path: str
    expected_path: str
    path_correct: bool

    actual_intent: str
    expected_intent: str
    intent_correct: bool

    latency_ms: int
    latency_ok: bool  # < 1s for fast, < 5s for slow

    sources_queried: list[str]
    sources_failed: list[str]

    # Overall
    passed: bool
    notes: str = ""


def load_scenarios(scenario_file: Path = None) -> list[dict]:
    """Load test scenarios from JSON file."""
    if scenario_file is None:
        scenario_file = Path(__file__).parent / "scenarios.json"

    with open(scenario_file) as f:
        data = json.load(f)
    return data["scenarios"]


async def run_scenario(scenario: dict, session_id: str = "e2e-test") -> ScenarioResult:
    """Run a single scenario through the orchestrator."""
    orchestrator = Orchestrator(session_id=session_id)

    # Gather context
    result = await orchestrator.gather_context(scenario["prompt"])

    # Evaluate routing
    path_correct = result.path_used == scenario["expected_path"]

    # Evaluate intent (need to route again to get analysis)
    router = Router()
    decision = router.route(scenario["prompt"])
    actual_intent = decision.analysis.intent_type.value
    intent_correct = actual_intent == scenario["expected_intent"]

    # Evaluate latency
    if result.path_used == "fast":
        latency_ok = result.latency_ms < 1000
    else:
        latency_ok = result.latency_ms < 5000

    # Overall pass
    passed = path_correct and intent_correct and latency_ok

    notes = []
    if not path_correct:
        notes.append(f"path: expected {scenario['expected_path']}, got {result.path_used}")
    if not intent_correct:
        notes.append(f"intent: expected {scenario['expected_intent']}, got {actual_intent}")
    if not latency_ok:
        notes.append(f"latency: {result.latency_ms}ms exceeds target")

    return ScenarioResult(
        scenario_id=scenario["id"],
        name=scenario["name"],
        complexity=scenario["complexity"],
        actual_path=result.path_used,
        expected_path=scenario["expected_path"],
        path_correct=path_correct,
        actual_intent=actual_intent,
        expected_intent=scenario["expected_intent"],
        intent_correct=intent_correct,
        latency_ms=result.latency_ms,
        latency_ok=latency_ok,
        sources_queried=result.sources_queried,
        sources_failed=result.sources_failed,
        passed=passed,
        notes="; ".join(notes) if notes else "OK",
    )


def print_result(result: ScenarioResult):
    """Print a single result."""
    status = "✓ PASS" if result.passed else "✗ FAIL"
    print(f"\n{status} [{result.scenario_id}] {result.name}")
    print(f"  Complexity: {result.complexity}")
    print(f"  Path: {result.actual_path} (expected: {result.expected_path}) {'✓' if result.path_correct else '✗'}")
    print(f"  Intent: {result.actual_intent} (expected: {result.expected_intent}) {'✓' if result.intent_correct else '✗'}")
    print(f"  Latency: {result.latency_ms}ms {'✓' if result.latency_ok else '✗'}")
    print(f"  Sources: {result.sources_queried}")
    if result.sources_failed:
        print(f"  Failed: {result.sources_failed}")
    if result.notes != "OK":
        print(f"  Notes: {result.notes}")


def print_summary(results: list[ScenarioResult]):
    """Print test summary."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} scenarios passed")
    print("=" * 60)

    # By complexity
    for complexity in ["small", "medium", "complex"]:
        subset = [r for r in results if r.complexity == complexity]
        if subset:
            subset_passed = sum(1 for r in subset if r.passed)
            print(f"  {complexity}: {subset_passed}/{len(subset)}")

    # Latency stats
    fast_latencies = [r.latency_ms for r in results if r.actual_path == "fast"]
    slow_latencies = [r.latency_ms for r in results if r.actual_path == "slow"]

    if fast_latencies:
        print(f"\n  Fast path avg latency: {sum(fast_latencies)//len(fast_latencies)}ms")
    if slow_latencies:
        print(f"  Slow path avg latency: {sum(slow_latencies)//len(slow_latencies)}ms")

    # Failed scenarios
    failed = [r for r in results if not r.passed]
    if failed:
        print("\nFailed scenarios:")
        for r in failed:
            print(f"  - [{r.scenario_id}] {r.name}: {r.notes}")


async def main():
    parser = argparse.ArgumentParser(description="E2E Test Runner for wicked-smaht v2")
    parser.add_argument("--scenario", "-s", help="Run specific scenario by ID")
    parser.add_argument("--complexity", "-c", choices=["small", "medium", "complex"],
                       help="Run scenarios of specific complexity")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    scenarios = load_scenarios()

    # Filter scenarios
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            print(f"Scenario '{args.scenario}' not found")
            sys.exit(1)

    if args.complexity:
        scenarios = [s for s in scenarios if s["complexity"] == args.complexity]

    print(f"Running {len(scenarios)} scenarios...")

    results = []
    for scenario in scenarios:
        result = await run_scenario(scenario)
        results.append(result)

        if not args.json:
            print_result(result)

    if args.json:
        output = [{
            "id": r.scenario_id,
            "name": r.name,
            "passed": r.passed,
            "path": r.actual_path,
            "intent": r.actual_intent,
            "latency_ms": r.latency_ms,
            "notes": r.notes,
        } for r in results]
        print(json.dumps(output, indent=2))
    else:
        print_summary(results)

    # Exit with error if any failed
    if not all(r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
