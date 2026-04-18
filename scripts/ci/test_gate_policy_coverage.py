#!/usr/bin/env python3
"""CI unit test: validate gate-policy.json covers all 18 (gate, rigor_tier) combos.

Tests:
- All 18 combinations resolve to a dispatch block (AC-2c).
- Empty reviewers list is only valid when mode == "self-check".
- mode == "council" requires len(reviewers) >= 2.
- Missing file raises FileNotFoundError (C-ts-2 from test-strategy gate).
- _resolve_gate_reviewer raises ValueError for unknown gate / tier.

Runs in < 1s (AC-2 requirement).  Stdlib-only.

Usage:
    python test_gate_policy_coverage.py
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate the repo root and import phase_manager helpers
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]  # scripts/ci/ -> scripts/ -> repo root

sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

from phase_manager import _resolve_gate_reviewer, _load_gate_policy, _get_plugin_root

# ---------------------------------------------------------------------------
# Expected matrix
# ---------------------------------------------------------------------------

EXPECTED_GATES = [
    "requirements-quality",
    "design-quality",
    "testability",
    "code-quality",
    "evidence-quality",
    "final-audit",
]
EXPECTED_TIERS = ["minimal", "standard", "full"]
TOTAL_EXPECTED = len(EXPECTED_GATES) * len(EXPECTED_TIERS)  # 18

# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"  FAIL: {msg}", file=sys.stderr)


def _pass(msg: str) -> None:
    print(f"  PASS: {msg}", file=sys.stderr)


def test_all_18_combinations_resolve() -> None:
    """All 18 (gate, rigor_tier) pairs must resolve without raising."""
    # Reset cache so each test run reloads from disk
    import phase_manager as pm
    pm._GATE_POLICY_CACHE = None

    resolved = 0
    for gate in EXPECTED_GATES:
        for tier in EXPECTED_TIERS:
            try:
                block = _resolve_gate_reviewer(gate, tier)
                assert isinstance(block, dict), f"{gate}/{tier}: block is not a dict"
                assert "reviewers" in block, f"{gate}/{tier}: missing 'reviewers'"
                assert "mode" in block, f"{gate}/{tier}: missing 'mode'"
                assert "fallback" in block, f"{gate}/{tier}: missing 'fallback'"
                resolved += 1
            except Exception as exc:
                _fail(f"test_all_18_combinations_resolve [{gate}/{tier}]: {exc}")

    if resolved == TOTAL_EXPECTED:
        _pass(f"test_all_18_combinations_resolve: all {TOTAL_EXPECTED} combos resolved")
    else:
        _fail(f"test_all_18_combinations_resolve: resolved {resolved}/{TOTAL_EXPECTED}")


def test_empty_reviewers_only_on_self_check() -> None:
    """Empty reviewers list is only valid when mode == 'self-check'."""
    import phase_manager as pm
    pm._GATE_POLICY_CACHE = None

    for gate in EXPECTED_GATES:
        for tier in EXPECTED_TIERS:
            block = _resolve_gate_reviewer(gate, tier)
            reviewers = block.get("reviewers", [])
            mode = block.get("mode", "")
            if len(reviewers) == 0 and mode != "self-check":
                _fail(
                    f"test_empty_reviewers_only_on_self_check [{gate}/{tier}]: "
                    f"empty reviewers but mode='{mode}' (expected 'self-check')"
                )

    _pass("test_empty_reviewers_only_on_self_check")


def test_council_mode_has_multi_reviewer() -> None:
    """mode == 'council' requires len(reviewers) >= 2."""
    import phase_manager as pm
    pm._GATE_POLICY_CACHE = None

    for gate in EXPECTED_GATES:
        for tier in EXPECTED_TIERS:
            block = _resolve_gate_reviewer(gate, tier)
            mode = block.get("mode", "")
            reviewers = block.get("reviewers", [])
            if mode == "council" and len(reviewers) < 2:
                _fail(
                    f"test_council_mode_has_multi_reviewer [{gate}/{tier}]: "
                    f"mode='council' but only {len(reviewers)} reviewer(s)"
                )

    _pass("test_council_mode_has_multi_reviewer")


def test_missing_file_raises() -> None:
    """Loading gate-policy.json from a non-existent path raises FileNotFoundError."""
    import phase_manager as pm
    pm._GATE_POLICY_CACHE = None

    # Temporarily point _get_plugin_root to a temp dir without the file
    import tempfile, os
    orig_root = pm._get_plugin_root

    def _fake_root():
        return Path(tempfile.gettempdir()) / "no-such-plugin-root-xyzzy"

    pm._get_plugin_root = _fake_root
    pm._GATE_POLICY_CACHE = None

    try:
        pm._load_gate_policy()
        _fail("test_missing_file_raises: expected FileNotFoundError, got nothing")
    except FileNotFoundError:
        _pass("test_missing_file_raises: FileNotFoundError raised as expected")
    except Exception as exc:
        _fail(f"test_missing_file_raises: unexpected exception {type(exc).__name__}: {exc}")
    finally:
        pm._get_plugin_root = orig_root
        pm._GATE_POLICY_CACHE = None


def test_invalid_gate_raises() -> None:
    """Unknown gate name raises ValueError."""
    import phase_manager as pm
    pm._GATE_POLICY_CACHE = None

    try:
        _resolve_gate_reviewer("no-such-gate", "standard")
        _fail("test_invalid_gate_raises: expected ValueError")
    except ValueError:
        _pass("test_invalid_gate_raises: ValueError raised for unknown gate")


def test_invalid_tier_raises() -> None:
    """Unknown rigor tier raises ValueError."""
    import phase_manager as pm
    pm._GATE_POLICY_CACHE = None

    try:
        _resolve_gate_reviewer("requirements-quality", "ultra")
        _fail("test_invalid_tier_raises: expected ValueError")
    except ValueError:
        _pass("test_invalid_tier_raises: ValueError raised for unknown tier")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== test_gate_policy_coverage ===", file=sys.stderr)
    test_all_18_combinations_resolve()
    test_empty_reviewers_only_on_self_check()
    test_council_mode_has_multi_reviewer()
    test_missing_file_raises()
    test_invalid_gate_raises()
    test_invalid_tier_raises()

    if _FAILURES:
        print(
            f"\n{len(_FAILURES)} test(s) FAILED:",
            file=sys.stderr,
        )
        for f in _FAILURES:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    total = 6
    print(f"\nAll {total} tests PASSED.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
