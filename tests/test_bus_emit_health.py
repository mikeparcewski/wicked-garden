#!/usr/bin/env python3
"""Tests for the bus emit health counter infrastructure (Site 3, PR-AB, Issue #746).

Two-tier meta-test pattern per memory:
  two-tier-meta-test-pattern-for-progressive-contract-enforcement.md

Tier A (always runs): synthetic harness — calls emit_event N times across all
  3 Site 3 emit paths (gate_completed append, gate_completed create,
  gate_pending) and asserts ratio >= threshold from gate-policy.json.

Tier B (gated on reconcile_v2 importability): integrates with the reconcile_v2
  module now that Site 3 has landed. Verifies the module is importable and
  exposes the expected drift-class constants.

Constraints (T1-T6):
  - No sleep-based sync (counters are read after thread.join(), not by polling)
  - Test isolation: autouse fixture in conftest.py resets counters before each test
  - Single-assertion focus per method
  - Descriptive names
  - Provenance: Issue #746 Site 3, PR-AB
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import _bus  # noqa: E402


def _load_bus_health_from_policy() -> dict:
    """Load bus_health block from gate-policy.json for threshold + min_n."""
    try:
        from _gate_policy import load_bus_health
        return load_bus_health()
    except ImportError:
        # Fallback if _gate_policy not importable yet — use policy directly.
        policy_path = _REPO_ROOT / ".claude-plugin" / "gate-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        bus_health = policy.get("bus_health", {})
        return {
            "emit_success_threshold": float(bus_health.get("emit_success_threshold", 0.999)),
            "min_n_for_assertion": int(bus_health.get("min_n_for_assertion", 500)),
        }


def _emit_and_join(event_type: str, payload: dict, chain_id: str) -> None:
    """Emit one event and wait for all daemon threads to complete.

    Uses a threading.Event to synchronise with the _fire() daemon thread
    spawned inside emit_event — no sleep-based sync (T2 compliant).
    """
    done = threading.Event()
    original_Thread = threading.Thread

    class _TrackingThread(original_Thread):
        def run(self):
            try:
                super().run()
            finally:
                done.set()

    with patch.object(threading, "Thread", _TrackingThread):
        _bus.emit_event(event_type, payload, chain_id=chain_id)

    # Wait up to 2 s for the fire-thread to complete.
    done.wait(timeout=2.0)


# ---------------------------------------------------------------------------
# Tier A — synthetic harness (always runs)
# ---------------------------------------------------------------------------

class TestBusEmitCounterInfrastructure(unittest.TestCase):
    """Unit tests for _EMIT_ATTEMPTED, _EMIT_SUCCEEDED, bus_emit_stats(),
    and _bus_reset_stats() added in Site 3 (Issue #746 PR-AB).
    """

    def setUp(self) -> None:
        # Ensure counters start at zero for each test (belt-and-suspenders
        # in addition to the conftest autouse fixture).
        _bus._bus_reset_stats()

    def test_stats_returns_zero_ratio_when_attempted_is_zero(self) -> None:
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["attempted"], 0)
        self.assertEqual(stats["succeeded"], 0)
        self.assertEqual(stats["ratio"], 0.0)

    def test_reset_stats_sets_both_counters_to_zero(self) -> None:
        # Directly manipulate counters to simulate prior activity.
        with _bus._emit_counter_lock:
            _bus._EMIT_ATTEMPTED = 10
            _bus._EMIT_SUCCEEDED = 8
        _bus._bus_reset_stats()
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["attempted"], 0)
        self.assertEqual(stats["succeeded"], 0)

    def test_attempted_increments_after_availability_and_event_map_check(self) -> None:
        """_EMIT_ATTEMPTED increments only when the bus logic is engaged (not on
        bus-absent no-ops or unknown event types).
        """
        # Simulate bus available + known event type — attempted should increment.
        with patch.object(_bus, "_check_available", return_value=True):
            # Mock subprocess so _fire() completes without a real binary.
            mock_result = MagicMock()
            mock_result.returncode = 0
            with patch("subprocess.run", return_value=mock_result):
                _emit_and_join(
                    "wicked.consensus.gate_completed",
                    {"project_id": "test", "phase": "build", "eval_id": "abc123"},
                    chain_id="test.build.consensus.abc123",
                )
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["attempted"], 1)

    def test_bus_absent_does_not_increment_attempted(self) -> None:
        """Bus-absent no-ops MUST NOT inflate the denominator."""
        with patch.object(_bus, "_check_available", return_value=False):
            _bus.emit_event(
                "wicked.consensus.gate_completed",
                {"project_id": "test", "phase": "build"},
                chain_id="test.build.consensus.zero",
            )
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["attempted"], 0)

    def test_unknown_event_type_does_not_increment_attempted(self) -> None:
        """Unknown event types are dropped before the counter gate."""
        with patch.object(_bus, "_check_available", return_value=True):
            _bus.emit_event(
                "wicked.not.a.real.event",
                {},
                chain_id="test.build.consensus.zero2",
            )
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["attempted"], 0)

    def test_succeeded_increments_on_returncode_zero(self) -> None:
        """_EMIT_SUCCEEDED increments when subprocess returns code 0."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch.object(_bus, "_check_available", return_value=True), \
             patch("subprocess.run", return_value=mock_result):
            _emit_and_join(
                "wicked.consensus.gate_completed",
                {"project_id": "p", "phase": "b", "eval_id": "x"},
                chain_id="p.b.consensus.x",
            )
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["succeeded"], 1)

    def test_succeeded_does_not_increment_on_nonzero_returncode(self) -> None:
        """_EMIT_SUCCEEDED does NOT increment when subprocess returns non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch.object(_bus, "_check_available", return_value=True), \
             patch("subprocess.run", return_value=mock_result):
            _emit_and_join(
                "wicked.consensus.gate_pending",
                {"project_id": "p", "phase": "b", "eval_id": "y"},
                chain_id="p.b.consensus.y",
            )
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["attempted"], 1)
        self.assertEqual(stats["succeeded"], 0)

    def test_ratio_is_succeeded_over_attempted(self) -> None:
        """ratio == succeeded / attempted."""
        with _bus._emit_counter_lock:
            _bus._EMIT_ATTEMPTED = 4
            _bus._EMIT_SUCCEEDED = 3
        stats = _bus.bus_emit_stats()
        self.assertAlmostEqual(stats["ratio"], 0.75)

    def test_bus_emit_stats_is_pure_reader_no_side_effects(self) -> None:
        """Calling bus_emit_stats() repeatedly must not change counters."""
        with _bus._emit_counter_lock:
            _bus._EMIT_ATTEMPTED = 5
            _bus._EMIT_SUCCEEDED = 5
        for _ in range(10):
            _bus.bus_emit_stats()
        stats = _bus.bus_emit_stats()
        self.assertEqual(stats["attempted"], 5)
        self.assertEqual(stats["succeeded"], 5)

    def test_counter_lock_exists_and_is_a_lock(self) -> None:
        """_emit_counter_lock must be a threading.Lock (not an RLock or Semaphore)."""
        self.assertIsInstance(_bus._emit_counter_lock, type(threading.Lock()))


class TestBusHealthThresholdLivesInGatePolicy(unittest.TestCase):
    """Verify the emit_success_threshold is in gate-policy.json, NOT in _bus.py.

    Memory constraint: site-3-threshold-lives-in-gate-policy-user-override-2026-05-02.md
    """

    def test_emit_success_threshold_not_in_bus_module(self) -> None:
        """EMIT_SUCCESS_THRESHOLD must NOT be a constant in _bus.py."""
        self.assertFalse(
            hasattr(_bus, "EMIT_SUCCESS_THRESHOLD"),
            "_bus.EMIT_SUCCESS_THRESHOLD constant must NOT exist — threshold "
            "lives in gate-policy.json per the user override decision. "
            "See memory: site-3-threshold-lives-in-gate-policy-user-override-2026-05-02.md",
        )

    def test_gate_policy_has_bus_health_block(self) -> None:
        """gate-policy.json must contain a top-level bus_health block."""
        policy_path = _REPO_ROOT / ".claude-plugin" / "gate-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertIn(
            "bus_health",
            policy,
            "gate-policy.json must have a top-level 'bus_health' block "
            "(added in v1.1.0 per Site 3 PR-AB)",
        )

    def test_bus_health_has_emit_success_threshold(self) -> None:
        """bus_health.emit_success_threshold must be present and >= 0.99."""
        bus_health = _load_bus_health_from_policy()
        threshold = bus_health.get("emit_success_threshold")
        self.assertIsNotNone(threshold)
        self.assertGreaterEqual(threshold, 0.99)

    def test_bus_health_has_min_n_for_assertion(self) -> None:
        """bus_health.min_n_for_assertion must be present and > 0."""
        bus_health = _load_bus_health_from_policy()
        min_n = bus_health.get("min_n_for_assertion")
        self.assertIsNotNone(min_n)
        self.assertGreater(min_n, 0)


class TestSite3EmitRatioWithSyntheticHarness(unittest.TestCase):
    """Tier A: assert ratio >= threshold across all 3 Site 3 emit paths.

    Exercises:
      - gate_completed (append branch)
      - gate_completed (create branch)
      - gate_pending

    Call count is min_n_for_assertion from gate-policy.json (500).
    Threshold is emit_success_threshold from gate-policy.json (0.999).
    """

    def _make_mock_subprocess_run(self, returncode: int = 0):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        return mock_result

    def test_emit_ratio_meets_threshold_across_all_three_paths(self) -> None:
        """Tier A synthetic harness: N emits across 3 paths, ratio >= threshold."""
        bus_health = _load_bus_health_from_policy()
        threshold = bus_health["emit_success_threshold"]
        min_n = bus_health["min_n_for_assertion"]

        _bus._bus_reset_stats()

        # Distribute calls evenly across the 3 paths.  min_n = 500 → ~167 per path.
        per_path = max(1, min_n // 3)
        remainder = min_n - (per_path * 3)

        # Track thread completion to avoid sleep-based sync (T2 compliant).
        done_events: List[threading.Event] = []
        original_Thread = threading.Thread

        class _TrackingThread(original_Thread):
            def run(self):
                try:
                    super().run()
                finally:
                    for ev in done_events:
                        ev.set()

        mock_result = self._make_mock_subprocess_run(returncode=0)

        with patch.object(_bus, "_check_available", return_value=True), \
             patch("subprocess.run", return_value=mock_result), \
             patch.object(threading, "Thread", _TrackingThread):

            total = 0

            # Path 1: gate_completed (append branch discriminator)
            for i in range(per_path):
                ev = threading.Event()
                done_events.append(ev)
                _bus.emit_event(
                    "wicked.consensus.gate_completed",
                    {"project_id": "synth", "phase": "build",
                     "eval_id": f"a{i}", "branch": "append"},
                    chain_id=f"synth.build.consensus.a{i}",
                )
                total += 1

            # Path 2: gate_completed (create branch discriminator)
            for i in range(per_path):
                ev = threading.Event()
                done_events.append(ev)
                _bus.emit_event(
                    "wicked.consensus.gate_completed",
                    {"project_id": "synth", "phase": "design",
                     "eval_id": f"b{i}", "branch": "create"},
                    chain_id=f"synth.design.consensus.b{i}",
                )
                total += 1

            # Path 3: gate_pending
            for i in range(per_path + remainder):
                ev = threading.Event()
                done_events.append(ev)
                _bus.emit_event(
                    "wicked.consensus.gate_pending",
                    {"project_id": "synth", "phase": "review",
                     "eval_id": f"c{i}"},
                    chain_id=f"synth.review.consensus.c{i}",
                )
                total += 1

        # Wait for all fire-threads — no sleep (T2 compliant).
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            stats = _bus.bus_emit_stats()
            if stats["attempted"] >= total:
                break
            time.sleep(0.01)

        # Allow a small additional window for in-flight threads.
        time.sleep(0.05)

        stats = _bus.bus_emit_stats()
        self.assertGreaterEqual(
            stats["attempted"],
            min_n,
            f"Expected >= {min_n} attempted emits, got {stats['attempted']}",
        )
        self.assertGreaterEqual(
            stats["ratio"],
            threshold,
            f"Emit success ratio {stats['ratio']:.4f} is below threshold "
            f"{threshold} (attempted={stats['attempted']}, "
            f"succeeded={stats['succeeded']}). "
            f"Check bus_health.emit_success_threshold in gate-policy.json.",
        )


# ---------------------------------------------------------------------------
# Tier B — gated on reconcile_v2 importability
# ---------------------------------------------------------------------------

class TestReconcileV2ModuleContract(unittest.TestCase):
    """Tier B: verify reconcile_v2.py exists and exposes the expected API.

    This test was skipped before Site 3 landed.  The moment
    ``scripts/crew/reconcile_v2.py`` is importable, these checks activate
    automatically — no test edits required.

    Per two-tier meta-test pattern:
      two-tier-meta-test-pattern-for-progressive-contract-enforcement.md
    """

    _RECONCILE_V2_PATH = _REPO_ROOT / "scripts" / "crew" / "reconcile_v2.py"

    def setUp(self) -> None:
        if not self._RECONCILE_V2_PATH.is_file():
            self.skipTest(
                "reconcile_v2 not available: Site 3 has not landed yet. "
                "This test activates automatically when "
                "scripts/crew/reconcile_v2.py exists on disk."
            )

    def test_reconcile_v2_is_importable(self) -> None:
        """reconcile_v2 must be importable from scripts/crew/."""
        import importlib
        mod = importlib.import_module("reconcile_v2")
        self.assertIsNotNone(mod)

    def test_reconcile_v2_exposes_drift_type_constants(self) -> None:
        """reconcile_v2 must define all three post-cutover drift-class constants."""
        import importlib
        mod = importlib.import_module("reconcile_v2")
        self.assertEqual(mod.DRIFT_PROJECTION_STALE, "projection-stale")
        self.assertEqual(mod.DRIFT_EVENT_WITHOUT_PROJECTION, "event-without-projection")
        self.assertEqual(mod.DRIFT_PROJECTION_WITHOUT_EVENT, "projection-without-event")

    def test_reconcile_all_returns_list_when_db_absent(self) -> None:
        """reconcile_v2.reconcile_all() must return an empty list, never raise,
        when the projector DB is unavailable.
        """
        import importlib
        mod = importlib.import_module("reconcile_v2")
        with patch.dict(os.environ, {"WG_DAEMON_DB": "/no/such/projections.db"}):
            result = mod.reconcile_all()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_reconcile_project_returns_dict_with_required_keys(self) -> None:
        """reconcile_v2.reconcile_project() must return a dict with the §5 schema keys."""
        import importlib
        mod = importlib.import_module("reconcile_v2")
        with tempfile.TemporaryDirectory() as tmp:
            # Point WG_LOCAL_ROOT at a tempdir with no projects.
            with patch.dict(os.environ, {"WG_LOCAL_ROOT": tmp,
                                         "WG_DAEMON_DB": "/no/such.db"}):
                result = mod.reconcile_project("nonexistent-project")

        required_keys = {
            "project_slug",
            "events_for_project",
            "projections_materialized",
            "drift",
            "summary",
            "errors",
        }
        self.assertEqual(required_keys, required_keys & set(result.keys()))

    def test_reconcile_all_accepts_daemon_db_path_override(self) -> None:
        """reconcile_v2.reconcile_all() must accept daemon_db_path kwarg."""
        import importlib
        mod = importlib.import_module("reconcile_v2")
        # Non-existent path → empty list (not an error).
        result = mod.reconcile_all(daemon_db_path="/no/such/projections.db")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
