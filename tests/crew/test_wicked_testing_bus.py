"""tests/crew/test_wicked_testing_bus.py — wicked-testing bus subscriber tests.

Covers:
  AC-24 — no legacy qe namespace in dispatch paths
  AC-25 — bus subscriber happy path
  AC-26 — verdict mapping PASS/FAIL/N-A/SKIP -> APPROVE/REJECT/CONDITIONAL
  AC-27 — bus-absent fallback
  AC-28 — four test cases (dispatch rename, bus happy path, absent fallback, verdict map)
  AC-46 — BLEND aggregation across namespaces
  AC-47 — partial-panel invariant + deduplication by run_id

Rules:
  T1: deterministic — no randomness, no wall-clock, no sleep
  T2: condition-based waits only (none here)
  T3: isolated — uses in-memory fixtures, injectable stubs
  T4: single behavior per test
  T5: descriptive names
  T6: docstrings cite ACs
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_SCRIPTS_CREW = _SCRIPTS_DIR / "crew"

for _p in [str(_SCRIPTS_CREW), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _wicked_testing_bus as wtb  # noqa: E402
import gate_dispatch as gd  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bus_event(
    reviewer: str,
    run_id: str,
    verdict: str,
    chain_id: str = "proj.design",
    score: float = 0.8,
) -> Dict:
    return {
        "event_id": 1,
        "event_type": "wicked.verdict.recorded",
        "payload": {
            "domain": "wicked-testing",
            "reviewer": reviewer,
            "run_id": run_id,
            "verdict": verdict,
            "score": score,
        },
        "metadata": {
            "chain_id": chain_id,
        },
    }


def _available():
    return True


def _unavailable():
    return False


def _make_poll_fn(events: List[Dict]):
    def _poll(_event_type):
        return events
    return _poll


def _noop_ack(_last_id: int):
    pass


# ---------------------------------------------------------------------------
# AC-24: dispatch rename — no legacy qe namespace in phase_manager dispatch paths
# ---------------------------------------------------------------------------

def test_phase_manager_has_no_legacy_qe_namespace():
    """
    AC-24 — static assertion: no legacy qe namespace string in phase_manager.py
    dispatcher call targets. The file should only reference wicked-garden:crew:*
    or wicked-testing:* (via _resolve_reviewer_subagent_type).
    """
    import re
    phase_manager_path = _SCRIPTS_CREW / "phase_manager.py"
    content = phase_manager_path.read_text(encoding="utf-8")
    # Find all dispatcher( ... ) call target strings
    dispatch_calls = re.findall(r'dispatcher\s*\(\s*(["\'].*?["\'])', content)
    _legacy_prefix = ":".join(["wicked-garden", "qe", ""])
    for call_target in dispatch_calls:
        assert _legacy_prefix not in call_target, (
            f"Found legacy qe namespace in dispatcher call: {call_target!r}"
        )


def test_resolve_reviewer_subagent_type_bare_name():
    """
    AC-24 — bare reviewer name gets wicked-garden:crew: prefix.
    """
    import phase_manager as pm
    assert pm._resolve_reviewer_subagent_type("gate-adjudicator") == (
        "wicked-garden:crew:gate-adjudicator"
    )


def test_resolve_reviewer_subagent_type_wicked_testing():
    """
    AC-24 — fully qualified wicked-testing:* name is used as-is (no double prefix).
    """
    import phase_manager as pm
    assert pm._resolve_reviewer_subagent_type("wicked-testing:testability-reviewer") == (
        "wicked-testing:testability-reviewer"
    )


def test_resolve_reviewer_subagent_type_wg_crew_fully_qualified():
    """
    AC-24 — already-qualified wicked-garden:crew:* names pass through unchanged.
    """
    import phase_manager as pm
    assert pm._resolve_reviewer_subagent_type("wicked-garden:crew:gate-adjudicator") == (
        "wicked-garden:crew:gate-adjudicator"
    )


# ---------------------------------------------------------------------------
# AC-26: verdict mapping PASS / FAIL / N-A / SKIP + unmapped
# ---------------------------------------------------------------------------

def test_verdict_map_pass():
    """AC-26 — PASS maps to APPROVE."""
    assert wtb.map_verdict("PASS") == "APPROVE"


def test_verdict_map_fail():
    """AC-26 — FAIL maps to REJECT."""
    assert wtb.map_verdict("FAIL") == "REJECT"


def test_verdict_map_na():
    """AC-26 — N-A maps to CONDITIONAL."""
    assert wtb.map_verdict("N-A") == "CONDITIONAL"


def test_verdict_map_skip():
    """AC-26 — SKIP maps to CONDITIONAL."""
    assert wtb.map_verdict("SKIP") == "CONDITIONAL"


def test_verdict_map_unknown_is_reject():
    """AC-26 — unknown verdict value maps to REJECT and logs an error."""
    with patch.object(wtb.logger, "error") as mock_error:
        result = wtb.map_verdict("UNKNOWN")
    assert result == "REJECT"
    mock_error.assert_called_once()
    assert "UNKNOWN" in str(mock_error.call_args)


# ---------------------------------------------------------------------------
# AC-25: bus subscriber happy path
# ---------------------------------------------------------------------------

def test_subscribe_to_verdicts_happy_path():
    """
    AC-25 — bus present, PASS event emitted: subscriber yields mapped Verdict APPROVE.
    """
    event = _make_bus_event(
        "wicked-testing:testability-reviewer",
        "run-abc",
        "PASS",
        chain_id="proj.design",
    )

    verdicts = list(wtb.subscribe_to_verdicts(
        "proj.design",
        _bus_available_fn=_available,
        _poll_fn=_make_poll_fn([event]),
        _ack_fn=_noop_ack,
    ))

    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.reviewer == "wicked-testing:testability-reviewer"
    assert v.run_id == "run-abc"
    assert v.verdict == "APPROVE"
    assert v.raw_verdict == "PASS"
    assert v.delivery_path == "bus"


def test_subscribe_to_verdicts_fail_event():
    """AC-25 + AC-26 — FAIL event maps to REJECT."""
    event = _make_bus_event(
        "wicked-testing:risk-assessor",
        "run-fail",
        "FAIL",
        chain_id="proj.test",
        score=0.1,
    )
    verdicts = list(wtb.subscribe_to_verdicts(
        "proj.test",
        _bus_available_fn=_available,
        _poll_fn=_make_poll_fn([event]),
        _ack_fn=_noop_ack,
    ))
    assert len(verdicts) == 1
    assert verdicts[0].verdict == "REJECT"
    assert verdicts[0].score == 0.1


def test_subscribe_to_verdicts_filters_other_chain_id():
    """
    AC-25 — events for a different chain_id are filtered out.
    """
    event = _make_bus_event(
        "wicked-testing:testability-reviewer",
        "run-xyz",
        "PASS",
        chain_id="other.chain",
    )
    verdicts = list(wtb.subscribe_to_verdicts(
        "proj.design",
        _bus_available_fn=_available,
        _poll_fn=_make_poll_fn([event]),
        _ack_fn=_noop_ack,
    ))
    assert verdicts == []


def test_subscribe_to_verdicts_skips_events_missing_reviewer():
    """AC-25 — events without reviewer are skipped without raising."""
    bad_event = {
        "event_id": 1,
        "event_type": "wicked.verdict.recorded",
        "payload": {"domain": "wicked-testing", "run_id": "r1", "verdict": "PASS"},
        "metadata": {"chain_id": "proj.design"},
    }
    verdicts = list(wtb.subscribe_to_verdicts(
        "proj.design",
        _bus_available_fn=_available,
        _poll_fn=_make_poll_fn([bad_event]),
        _ack_fn=_noop_ack,
    ))
    assert verdicts == []


# ---------------------------------------------------------------------------
# AC-27: bus-absent fallback
# ---------------------------------------------------------------------------

def test_subscribe_to_verdicts_bus_absent_returns_empty():
    """
    AC-27 — wicked-bus unavailable: yields nothing, no exception raised,
    one debug log emitted.
    """
    with patch.object(wtb.logger, "debug") as mock_debug:
        verdicts = list(wtb.subscribe_to_verdicts(
            "proj.design",
            _bus_available_fn=_unavailable,
        ))

    assert verdicts == []
    mock_debug.assert_called_once()
    assert "falling back" in mock_debug.call_args[0][0]


def test_subscribe_to_verdicts_poll_raises_returns_empty():
    """
    AC-27 — poll function raises: subscriber yields nothing gracefully.
    """
    def _raising_poll(_event_type):
        raise ConnectionError("bus refused")

    verdicts = list(wtb.subscribe_to_verdicts(
        "proj.design",
        _bus_available_fn=_available,
        _poll_fn=_raising_poll,
        _ack_fn=_noop_ack,
    ))
    assert verdicts == []


# ---------------------------------------------------------------------------
# Deduplication by run_id (AC-47)
# ---------------------------------------------------------------------------

def test_subscribe_deduplicates_same_run_id():
    """AC-47 — two events with same (reviewer, run_id): only first is yielded."""
    events = [
        _make_bus_event("wicked-testing:risk-assessor", "r1", "PASS",
                        chain_id="proj.design"),
        _make_bus_event("wicked-testing:risk-assessor", "r1", "FAIL",
                        chain_id="proj.design"),
    ]
    verdicts = list(wtb.subscribe_to_verdicts(
        "proj.design",
        _bus_available_fn=_available,
        _poll_fn=_make_poll_fn(events),
        _ack_fn=_noop_ack,
    ))
    assert len(verdicts) == 1
    assert verdicts[0].verdict == "APPROVE"   # first wins


def test_dedupe_by_run_id_first_seen_wins():
    """
    AC-47 — same (reviewer, run_id) from two paths: dispatch-log wins.
    """
    v1 = {"reviewer": "wicked-testing:risk-assessor", "run_id": "r1",
           "verdict": "APPROVE", "score": 0.9, "delivery_path": "dispatch-log"}
    v2 = {"reviewer": "wicked-testing:risk-assessor", "run_id": "r1",
           "verdict": "REJECT", "score": 0.1, "delivery_path": "bus"}

    result = gd.dedupe_by_run_id([v1, v2])
    assert len(result) == 1
    assert result[0]["verdict"] == "APPROVE"
    assert result[0]["delivery_path"] == "dispatch-log"


def test_dedupe_by_run_id_bus_loses_to_dispatch_log():
    """
    AC-47 — dispatch-log entry takes precedence over bus entry for same run_id.
    Design §4 DQ-4: dispatch-log is the authoritative path.
    """
    bus_v = {"reviewer": "wicked-testing:testability-reviewer", "run_id": "r2",
             "verdict": "REJECT", "score": 0.2, "delivery_path": "bus"}
    log_v = {"reviewer": "wicked-testing:testability-reviewer", "run_id": "r2",
              "verdict": "APPROVE", "score": 0.85, "delivery_path": "dispatch-log"}

    result = gd.dedupe_by_run_id([bus_v, log_v])
    assert len(result) == 1
    assert result[0]["delivery_path"] == "dispatch-log"
    assert result[0]["verdict"] == "APPROVE"


def test_dedupe_different_run_ids_both_kept():
    """AC-47 — different run_ids are not deduplicated."""
    v1 = {"reviewer": "wicked-testing:risk-assessor", "run_id": "r1",
           "verdict": "APPROVE", "score": 0.8, "delivery_path": "bus"}
    v2 = {"reviewer": "wicked-testing:risk-assessor", "run_id": "r2",
           "verdict": "REJECT", "score": 0.3, "delivery_path": "bus"}
    result = gd.dedupe_by_run_id([v1, v2])
    assert len(result) == 2


# ---------------------------------------------------------------------------
# AC-46: BLEND aggregation across namespaces
# ---------------------------------------------------------------------------

def test_aggregate_blend_approve_both():
    """
    AC-46 — two APPROVE verdicts: formula applied, final APPROVE.
    Scenario G12-A: gate-adjudicator 0.75, wicked-testing:risk-assessor 0.65
    Expected: 0.4 * 0.65 + 0.6 * 0.70 = 0.68
    """
    verdicts = [
        {"reviewer": "wicked-garden:crew:gate-adjudicator",
         "verdict": "APPROVE", "score": 0.75},
        {"reviewer": "wicked-testing:risk-assessor",
         "verdict": "APPROVE", "score": 0.65},
    ]
    result = gd.aggregate_blend(verdicts)
    assert result.verdict == "APPROVE"
    assert result.score == pytest.approx(0.68, abs=0.001)
    assert result.partial_panel is False


def test_aggregate_blend_partial_panel_returns_pending():
    """
    AC-47 — partial panel: aggregate_blend returns pending when
    len(verdicts) < expected_count.
    """
    verdicts = [
        {"reviewer": "wicked-garden:crew:gate-adjudicator",
         "verdict": "APPROVE", "score": 0.75},
    ]
    result = gd.aggregate_blend(verdicts, expected_count=2)
    assert result.verdict == "pending"
    assert result.score is None
    assert result.partial_panel is True


def test_aggregate_blend_reject_short_circuits():
    """
    AC-46 — one REJECT in the panel: final verdict is REJECT regardless of others.
    """
    verdicts = [
        {"reviewer": "wicked-garden:crew:gate-adjudicator",
         "verdict": "APPROVE", "score": 0.85},
        {"reviewer": "wicked-testing:risk-assessor",
         "verdict": "REJECT", "score": 0.2},
    ]
    result = gd.aggregate_blend(verdicts)
    assert result.verdict == "REJECT"


def test_aggregate_blend_empty_returns_pending():
    """AC-47 — empty verdicts list: aggregate_blend returns pending."""
    result = gd.aggregate_blend([])
    assert result.verdict == "pending"
    assert result.score is None


def test_aggregate_blend_single_reviewer_approve():
    """AC-46 — single APPROVE: formula collapses to score itself (0.4*s + 0.6*s = s)."""
    verdicts = [
        {"reviewer": "wicked-testing:testability-reviewer",
         "verdict": "APPROVE", "score": 0.9},
    ]
    result = gd.aggregate_blend(verdicts)
    assert result.verdict == "APPROVE"
    assert result.score == pytest.approx(0.9, abs=0.001)


# ---------------------------------------------------------------------------
# Clock injection tests (QE-EVAL-clock-injection-unresolved condition)
# ---------------------------------------------------------------------------

def test_collect_clock_parameter_accepted():
    """
    CH-02 / QE-EVAL-clock-injection-unresolved — collect() accepts clock=None
    parameter and defaults to None (uses time.time internally).
    """
    import inspect
    sig = inspect.signature(gd.collect)
    assert "clock" in sig.parameters, (
        "collect() must have a clock=None parameter (clock injection seam)"
    )
    default = sig.parameters["clock"].default
    assert default is None, (
        f"collect() clock parameter must default to None, got {default!r}"
    )


def test_aggregate_blend_clock_parameter_accepted():
    """CH-02 — aggregate_blend() accepts clock=None parameter."""
    import inspect
    sig = inspect.signature(gd.aggregate_blend)
    assert "clock" in sig.parameters, (
        "aggregate_blend() must have a clock=None parameter"
    )


def test_collect_with_mock_clock_window_zero_is_deterministic():
    """
    CH-02 + WG_GATE_VERDICT_WINDOW_SECS=0 test-mode sentinel.
    Injecting a mock clock confirms aggregation is deterministic (no wall-clock).
    With window=0 and a complete panel, result is APPROVE immediately.
    """
    call_count = [0]

    def mock_clock() -> float:
        call_count[0] += 1
        return 1000.0 + call_count[0]

    gate_policy_entry = {
        "reviewers": ["wicked-testing:testability-reviewer"],
        "mode": "council",
        "min_score": 0.7,
    }
    preloaded = [
        {
            "reviewer": "wicked-testing:testability-reviewer",
            "run_id": "r-sentinel",
            "verdict": "APPROVE",
            "score": 0.85,
            "delivery_path": "dispatch-log",
        }
    ]

    with patch.dict(os.environ, {"WG_GATE_VERDICT_WINDOW_SECS": "0"}):
        result = gd.collect(
            gate_policy_entry,
            chain_id="proj.test",
            clock=mock_clock,
            existing_verdicts=preloaded,
            _bus_available_fn=_unavailable,
        )

    assert result.verdict == "APPROVE"
    assert result.score is not None
    assert result.partial_panel is False


def test_collect_window_zero_partial_panel_stays_pending():
    """
    CH-02 — WG_GATE_VERDICT_WINDOW_SECS=0 (test-mode sentinel):
    With a missing reviewer and window=0, partial panel stays pending
    (no timeout-CONDITIONAL synthetic verdict injected).
    """
    gate_policy_entry = {
        "reviewers": [
            "wicked-garden:crew:gate-adjudicator",
            "wicked-testing:risk-assessor",
        ],
        "mode": "council",
        "min_score": 0.7,
    }
    # Only one of the two reviewers delivered
    preloaded = [
        {
            "reviewer": "wicked-garden:crew:gate-adjudicator",
            "run_id": "r1",
            "verdict": "APPROVE",
            "score": 0.75,
            "delivery_path": "dispatch-log",
        }
    ]

    with patch.dict(os.environ, {"WG_GATE_VERDICT_WINDOW_SECS": "0"}):
        result = gd.collect(
            gate_policy_entry,
            chain_id="proj.test",
            existing_verdicts=preloaded,
            _bus_available_fn=_unavailable,
        )

    assert result.verdict == "pending"
    assert result.partial_panel is True
    assert result.late_verdicts == []


# ---------------------------------------------------------------------------
# collect() — bus-absent fallback path  (AC-27)
# ---------------------------------------------------------------------------

def test_collect_bus_absent_uses_existing_verdicts():
    """
    AC-27 — collect() falls back to existing_verdicts when bus is absent.
    No error emitted; result is derived from pre-collected dispatch-log data.
    """
    gate_policy_entry = {
        "reviewers": ["wicked-testing:testability-reviewer"],
        "mode": "sequential",
        "min_score": 0.6,
    }
    preloaded = [
        {
            "reviewer": "wicked-testing:testability-reviewer",
            "run_id": "r-fallback",
            "verdict": "APPROVE",
            "score": 0.80,
            "delivery_path": "dispatch-log",
        }
    ]

    result = gd.collect(
        gate_policy_entry,
        chain_id="proj.review",
        existing_verdicts=preloaded,
        _bus_available_fn=_unavailable,
    )

    assert result.verdict == "APPROVE"
    assert result.score is not None
    assert result.partial_panel is False


def test_collect_bus_verdict_merged_with_dispatch_log():
    """
    AC-25 + AC-47 — bus verdict for wicked-testing reviewer is merged with
    dispatch-log verdict for crew reviewer; BLEND applied across both.
    """
    gate_policy_entry = {
        "reviewers": [
            "wicked-garden:crew:gate-adjudicator",
            "wicked-testing:risk-assessor",
        ],
        "mode": "council",
        "min_score": 0.7,
    }
    # Crew reviewer's result pre-collected from dispatch-log
    preloaded = [
        {
            "reviewer": "wicked-garden:crew:gate-adjudicator",
            "run_id": "r-crew",
            "verdict": "APPROVE",
            "score": 0.80,
            "delivery_path": "dispatch-log",
        }
    ]
    # wicked-testing reviewer arrives via bus
    bus_verdict = wtb.Verdict(
        reviewer="wicked-testing:risk-assessor",
        run_id="r-bus",
        verdict="APPROVE",
        score=0.70,
        delivery_path="bus",
        raw_verdict="PASS",
    )

    def _mock_collect_from_bus(chain_id, expected_reviewers, seen=None, **kw):
        return [bus_verdict]

    with patch.object(gd, "_collect_bus_verdicts", _mock_collect_from_bus):
        result = gd.collect(
            gate_policy_entry,
            chain_id="proj.review",
            existing_verdicts=preloaded,
        )

    # 0.4 * 0.70 + 0.6 * 0.75 = 0.28 + 0.45 = 0.73
    assert result.verdict == "APPROVE"
    assert result.score is not None
    assert result.partial_panel is False


# ---------------------------------------------------------------------------
# Tier-1 allowlist — no invalid wicked-testing names used in test fixtures
# ---------------------------------------------------------------------------

def test_all_reviewers_in_test_fixtures_are_tier1():
    """
    AC-44 — every wicked-testing:* name used in this test file is in TIER1_AGENTS.
    """
    from _wicked_testing_tier1 import TIER1_AGENTS

    used_names = {
        "wicked-testing:testability-reviewer",
        "wicked-testing:risk-assessor",
    }
    for name in used_names:
        assert name in TIER1_AGENTS, (
            f"Test fixture uses unknown Tier-1 name: {name!r}"
        )
