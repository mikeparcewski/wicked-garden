"""Unit tests for scripts/crew/phase_start_gate.py (AC-3, AC-5 unit, AC-10, D6).

Tests:
    test_no_change_returns_ok               Baseline — no signal, returns {"ok": True}
    test_task_count_triggers                 Heuristic 1 — completed count increased
    test_ambiguous_mtime_is_change_detected  D6 bias — mtime == last_reeval_ts triggers
    test_evidence_mtime_after_triggers       mtime > last_reeval_ts triggers
    test_no_prior_reeval_ts_with_tasks       No prior ts + completed tasks → change
    test_no_prior_reeval_ts_no_tasks         No prior ts + 0 completed → ok
    test_fail_open_missing_chain_script      AC-10 — chain_snapshot is None → fail-open
    test_fail_open_on_exception              AC-10 — exception in state → fail-open
    test_structured_current_chain_output     AC-5 unit — systemMessage contains current_chain-style data

All deterministic (no sleep, no wall-clock).  Stdlib-only.
"""

import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

from phase_start_gate import check


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TS_LAST_REEVAL = "2026-04-18T12:00:00Z"
_TS_BEFORE = "2026-04-18T11:59:59Z"   # strictly before
_TS_EQUAL = "2026-04-18T12:00:00Z"    # == last_reeval_ts  (D6: treat as change)
_TS_AFTER = "2026-04-18T12:00:01Z"    # strictly after


def _state(last_reeval_ts=_TS_LAST_REEVAL, last_reeval_task_count=5) -> dict:
    return {
        "last_reeval_ts": last_reeval_ts,
        "last_reeval_task_count": last_reeval_task_count,
    }


def _snapshot(
    completed=5,
    evidence_mtimes: "list[str]" = None,
    task_updated_ats: "list[str]" = None,
    phase="design",
) -> dict:
    evidence_manifests = [
        {"path": f"evidence-{i}.md", "mtime_iso": mtime}
        for i, mtime in enumerate(evidence_mtimes or [])
    ]
    tasks = [
        {"id": f"t{i}", "status": "completed", "updated_at": ua}
        for i, ua in enumerate(task_updated_ats or [])
    ]
    return {
        "phase": phase,
        "counts": {"total": completed, "completed": completed, "in_progress": 0,
                   "pending": 0, "blocked": 0},
        "tasks": tasks,
        "evidence_manifests": evidence_manifests,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNoChangeReturnsOk(unittest.TestCase):
    """Baseline: no heuristic fires → {"ok": True} with no systemMessage."""

    def test_no_change_returns_ok(self):
        state = _state(last_reeval_task_count=5)
        snapshot = _snapshot(
            completed=5,
            evidence_mtimes=[_TS_BEFORE],
            task_updated_ats=[_TS_BEFORE],
        )
        result = check(state, snapshot)
        self.assertTrue(result["ok"])
        self.assertNotIn("systemMessage", result)


class TestTaskCountTriggers(unittest.TestCase):
    """Heuristic 1: completed count > last_reeval_task_count → change detected."""

    def test_task_count_triggers(self):
        state = _state(last_reeval_task_count=3)
        snapshot = _snapshot(completed=5)
        result = check(state, snapshot)
        self.assertTrue(result["ok"])
        self.assertIn("systemMessage", result)
        self.assertEqual(result.get("detail"), "task-count-increased")


class TestAmbiguousMtimeIsChangeDetected(unittest.TestCase):
    """D6 bias: mtime == last_reeval_ts (ambiguous) MUST trigger change detected."""

    def test_ambiguous_mtime_is_change_detected(self):
        state = _state(last_reeval_ts=_TS_LAST_REEVAL, last_reeval_task_count=5)
        snapshot = _snapshot(
            completed=5,  # count unchanged — only mtime triggers
            evidence_mtimes=[_TS_EQUAL],  # exactly equal — ambiguous
        )
        result = check(state, snapshot)
        self.assertTrue(result["ok"])
        self.assertIn("systemMessage", result,
                      "Ambiguous mtime should trigger re-eval (D6 false-positive bias)")
        self.assertEqual(result.get("detail"), "evidence-mtime-gte-last-reeval")


class TestEvidenceMtimeAfterTriggers(unittest.TestCase):
    """mtime strictly after last_reeval_ts → change detected."""

    def test_evidence_mtime_after_triggers(self):
        state = _state(last_reeval_ts=_TS_LAST_REEVAL, last_reeval_task_count=5)
        snapshot = _snapshot(completed=5, evidence_mtimes=[_TS_AFTER])
        result = check(state, snapshot)
        self.assertIn("systemMessage", result)


class TestNoPriorReevalTsWithTasks(unittest.TestCase):
    """No last_reeval_ts + completed tasks → change detected (no-prior-reeval).

    We set last_reeval_task_count == completed so Heuristic 1 (count increased)
    does NOT fire.  The no-prior-ts branch then fires because completed > 0.
    """

    def test_no_prior_reeval_ts_with_tasks(self):
        state = {"last_reeval_ts": None, "last_reeval_task_count": 3}
        snapshot = _snapshot(completed=3)
        result = check(state, snapshot)
        self.assertIn("systemMessage", result)
        self.assertEqual(result.get("detail"), "no-prior-reeval-tasks-exist")


class TestNoPriorReevalTsNoTasks(unittest.TestCase):
    """No last_reeval_ts + 0 completed tasks → no-op (first phase, nothing done)."""

    def test_no_prior_reeval_ts_no_tasks(self):
        state = {"last_reeval_ts": None, "last_reeval_task_count": 0}
        snapshot = _snapshot(completed=0)
        result = check(state, snapshot)
        self.assertTrue(result["ok"])
        self.assertNotIn("systemMessage", result)


class TestFailOpenMissingChainScript(unittest.TestCase):
    """AC-10: chain_snapshot is None or empty → fail-open, never raises."""

    def test_fail_open_missing_chain_script(self):
        state = _state()
        result = check(state, None)
        self.assertTrue(result["ok"])
        self.assertIn("fail-open", result.get("detail", ""))
        self.assertNotIn("systemMessage", result)

    def test_fail_open_empty_chain_snapshot(self):
        state = _state()
        result = check(state, {})
        # Empty snapshot: completed=0, last_count=5 → count not exceeded; but
        # no evidence/tasks either. No prior ts check applies if last_ts is set.
        # The function should not raise.
        self.assertTrue(result["ok"])


class TestFailOpenOnException(unittest.TestCase):
    """AC-10: unexpected exception in state handling → fail-open."""

    def test_fail_open_on_bad_state(self):
        class _BadState:
            def get(self, *args, **kwargs):
                raise RuntimeError("state exploded")

        result = check(_BadState(), _snapshot())
        self.assertTrue(result["ok"])
        self.assertIn("fail-open", result.get("detail", ""))


class TestStructuredCurrentChainOutput(unittest.TestCase):
    """AC-5 unit: when change is detected, the systemMessage includes current_chain data.

    The full AC-5 acceptance test lives in scenarios/crew/phase-boundary-reeval.md
    (a t3 deliverable).  This unit test verifies the systemMessage contains the
    phase name — a proxy for structured context being embedded in the directive.
    """

    def test_structured_current_chain_output(self):
        state = _state(last_reeval_task_count=0)
        snapshot = _snapshot(completed=3, phase="test-strategy")
        result = check(state, snapshot)
        self.assertIn("systemMessage", result)
        msg = result["systemMessage"]
        # The message should reference the phase name (D6/AC-5 structural check)
        self.assertIn("test-strategy", msg)
        # The message must instruct invoke of propose-process
        self.assertIn("propose-process", msg)


if __name__ == "__main__":
    unittest.main()
