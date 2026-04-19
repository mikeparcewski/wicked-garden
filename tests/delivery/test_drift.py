"""Unit tests for scripts/delivery/drift.py (Issue #443).

Covers the acceptance criteria:
- >=5 session timeline required to classify drift (else zone=insufficient)
- gate pass rate dropping 2σ below baseline emits drift event candidate
- >=15% drop below 4-session baseline flags drift
- common-cause variation is NOT actionable (no new gate)
- EWMA slope over trending negative series reported
- summarize / is_actionable helpers behave per contract
- emit_drift_event fails-open when wicked-bus is absent

Stdlib-only, deterministic — no wall-clock, no network.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "delivery"))

import drift  # noqa: E402


def _mk_records(values, metric="gate_pass_rate", project="demo"):
    """Build synthetic timeline records."""
    out = []
    for i, v in enumerate(values):
        out.append({
            "version": "1",
            "session_id": f"s{i:03d}",
            "project": project,
            "recorded_at": f"2026-01-{i+1:02d}T00:00:00Z",
            "metrics": {metric: v},
        })
    return out


class DriftClassifyTests(unittest.TestCase):
    def test_insufficient_samples_below_5(self):
        """AC: <5 sessions → zone=insufficient, drift=False."""
        records = _mk_records([0.9, 0.85, 0.88, 0.82])
        cls = drift.classify(records)
        self.assertEqual(cls["zone"], "insufficient")
        self.assertFalse(cls["drift"])
        self.assertEqual(cls["session_count"], 4)

    def test_common_cause_stable_baseline(self):
        """Values within normal variation → common-cause noise, not actionable."""
        # Stable-ish baseline with small variation, latest close to mean.
        values = [0.88, 0.86, 0.90, 0.87, 0.89]
        cls = drift.classify(_mk_records(values))
        self.assertGreaterEqual(cls["session_count"], 5)
        self.assertEqual(cls["zone"], "common-cause")
        self.assertFalse(cls["drift"])
        self.assertFalse(drift.is_actionable(cls))

    def test_drop_pct_breach_flags_drift(self):
        """AC: latest drops >=15% below 4-session baseline → drift=True."""
        # Baseline mean ~0.90, latest 0.70 → ~22% drop.
        values = [0.90, 0.92, 0.88, 0.90, 0.70]
        cls = drift.classify(_mk_records(values))
        self.assertTrue(cls["drift"])
        self.assertGreaterEqual(cls["drop_pct"], 0.15)
        self.assertTrue(drift.is_actionable(cls))
        # Reasons include drop_pct breach.
        self.assertTrue(any("drop_pct" in r for r in cls["reasons"]))

    def test_special_cause_three_sigma(self):
        """Latest beyond 3σ below baseline → special-cause zone + drift."""
        # Baseline samples clustered tightly; latest far below.
        values = [0.90, 0.91, 0.89, 0.90, 0.50]
        cls = drift.classify(_mk_records(values))
        self.assertEqual(cls["zone"], "special-cause")
        self.assertTrue(cls["drift"])
        self.assertTrue(drift.is_actionable(cls))

    def test_warn_zone_between_2_and_3_sigma(self):
        """Latest between 2σ and 3σ → warn, but below drop threshold."""
        # Baseline [0.90, 0.92, 0.88, 0.90] has mean=0.90, stddev≈0.01414.
        # Latest 0.87: z = 0.03 / 0.01414 ≈ 2.12σ (warn zone), drop = 3.3% (< 15%).
        values = [0.90, 0.92, 0.88, 0.90, 0.87]
        cls = drift.classify(_mk_records(values))
        self.assertEqual(cls["zone"], "warn",
                         f"Expected warn, got {cls['zone']} "
                         f"(baseline={cls.get('baseline')}, latest={cls.get('latest')})")
        self.assertFalse(cls["drift"])  # warn alone is not drift

    def test_trending_down_populates_ewma_slope(self):
        """A consistently declining series produces a negative EWMA slope."""
        values = [0.95, 0.90, 0.85, 0.80, 0.75, 0.70]
        cls = drift.classify(_mk_records(values))
        self.assertIsNotNone(cls["ewma_slope"])
        self.assertLess(cls["ewma_slope"], 0)

    def test_missing_metric_returns_insufficient(self):
        """No observations for the metric → zone=insufficient."""
        records = _mk_records([0.9, 0.9, 0.9, 0.9, 0.9], metric="other_metric")
        cls = drift.classify(records, metric="gate_pass_rate")
        self.assertEqual(cls["zone"], "insufficient")


class IsActionableTests(unittest.TestCase):
    def test_is_actionable_special_cause_true(self):
        cls = {"zone": "special-cause", "drop_pct": 0.05}
        self.assertTrue(drift.is_actionable(cls))

    def test_is_actionable_common_cause_false(self):
        """AC: common-cause variation MUST NOT be actionable."""
        cls = {"zone": "common-cause", "drop_pct": 0.02}
        self.assertFalse(drift.is_actionable(cls))

    def test_is_actionable_drop_pct_true(self):
        cls = {"zone": "common-cause", "drop_pct": 0.25}
        self.assertTrue(drift.is_actionable(cls))

    def test_is_actionable_empty_false(self):
        self.assertFalse(drift.is_actionable({}))


class SummarizeTests(unittest.TestCase):
    def test_summarize_insufficient(self):
        cls = {"zone": "insufficient", "metric": "gate_pass_rate", "session_count": 3}
        out = drift.summarize(cls)
        self.assertIn("insufficient", out)
        self.assertIn("3 sessions", out)

    def test_summarize_signal(self):
        cls = {
            "zone": "special-cause",
            "metric": "gate_pass_rate",
            "latest": 0.5,
            "baseline": {"mean": 0.9},
            "drop_pct": 0.444,
        }
        out = drift.summarize(cls)
        self.assertIn("SIGNAL", out)
        self.assertIn("gate_pass_rate", out)


class EmitDriftEventTests(unittest.TestCase):
    def test_emit_skipped_when_not_actionable(self):
        cls = {"zone": "common-cause", "drop_pct": 0.01}
        self.assertFalse(drift.emit_drift_event("demo", cls))

    def test_emit_fails_open_when_bus_missing(self):
        """Actionable drift with no wicked-bus binary → returns False/True without raising."""
        cls = {
            "zone": "special-cause",
            "metric": "gate_pass_rate",
            "latest": 0.4,
            "baseline": {"mean": 0.9, "stddev": 0.03},
            "drop_pct": 0.55,
            "ewma_slope": -0.05,
            "reasons": ["outside 3σ"],
            "session_count": 5,
        }
        # Patch _bus.emit_event to raise so we exercise the fail-open branch.
        import _bus
        with patch.object(_bus, "emit_event", side_effect=RuntimeError("bus down")):
            # Should not raise
            result = drift.emit_drift_event("demo", cls)
            self.assertFalse(result)


class FiveSessionScenarioTest(unittest.TestCase):
    """End-to-end: synthetic 5-session timeline validates the full acceptance scenario.

    Scenario:
        sessions 1-4: gate_pass_rate stays ~0.90 (healthy baseline)
        session 5:    gate_pass_rate drops to 0.70 — a 22% drop + beyond 3σ

    Expected:
        classify() returns zone=special-cause AND drift=True
        is_actionable() is True
        summarize() mentions SIGNAL
        emit_drift_event() attempts emission (returns True when bus mocked ok)
    """

    def test_synthetic_5_session_timeline(self):
        values = [0.90, 0.91, 0.89, 0.90, 0.70]
        records = _mk_records(values, project="e2e")
        cls = drift.classify(records)

        # Acceptance assertions
        self.assertEqual(cls["session_count"], 5)
        self.assertEqual(cls["zone"], "special-cause")
        self.assertTrue(cls["drift"])
        self.assertGreaterEqual(cls["drop_pct"], 0.15)
        self.assertTrue(drift.is_actionable(cls))
        summary = drift.summarize(cls)
        self.assertIn("SIGNAL", summary)

        # Mock a healthy bus to verify emission payload is built correctly.
        import _bus
        captured = {}

        def fake_emit(event_type, payload, **kw):
            captured["event_type"] = event_type
            captured["payload"] = payload

        with patch.object(_bus, "emit_event", side_effect=fake_emit):
            ok = drift.emit_drift_event("e2e", cls)

        self.assertTrue(ok, "emit_drift_event should return True when bus succeeds")
        self.assertEqual(captured["event_type"], "wicked.quality.drift_detected")
        payload = captured["payload"]
        self.assertEqual(payload["project"], "e2e")
        self.assertEqual(payload["metric"], "gate_pass_rate")
        self.assertEqual(payload["zone"], "special-cause")
        self.assertEqual(payload["session_count"], 5)
        self.assertIn("reasons", payload)


class WesternElectricRulesTests(unittest.TestCase):
    """WE runs rules beyond zone-A (issue #459)."""

    def test_2_of_3_zone_b_direct_helper(self):
        """Test the _we_2_of_3_zone_b helper directly with controlled inputs."""
        # mean=0.90, stddev=0.01 → threshold at 2σ below = 0.88.
        # 2 of last 3 below 0.88 → rule fires.
        series = [0.90, 0.91, 0.89, 0.90, 0.85, 0.90, 0.85]
        self.assertTrue(drift._we_2_of_3_zone_b(series, 0.90, 0.01))

        # Only 1 of last 3 below threshold → rule does NOT fire.
        series_one_breach = [0.90, 0.91, 0.89, 0.90, 0.90, 0.90, 0.85]
        self.assertFalse(drift._we_2_of_3_zone_b(series_one_breach, 0.90, 0.01))

        # Zero stddev → rule never fires (fail-safe).
        self.assertFalse(drift._we_2_of_3_zone_b(series, 0.90, 0.0))

        # Too few points → rule never fires.
        self.assertFalse(drift._we_2_of_3_zone_b([0.85, 0.85], 0.90, 0.01))

    def test_trending_down_6_consecutive(self):
        """6 consecutive strictly decreasing points → trending_down fires."""
        # Strictly monotonic decline — classic SPC trend signal.
        series = [0.95, 0.90, 0.85, 0.80, 0.75, 0.70]
        self.assertTrue(drift._we_trending(series, direction="down"))

        # Break monotonicity with a flat point → does NOT fire.
        series_flat = [0.95, 0.90, 0.90, 0.80, 0.75, 0.70]
        self.assertFalse(drift._we_trending(series_flat, direction="down"))

        # Break monotonicity with an uptick → does NOT fire.
        series_blip = [0.95, 0.90, 0.85, 0.86, 0.75, 0.70]
        self.assertFalse(drift._we_trending(series_blip, direction="down"))

        # Only 5 points → below WE_TRENDING_WINDOW of 6 → does NOT fire.
        self.assertFalse(drift._we_trending([0.95, 0.90, 0.85, 0.80, 0.75], "down"))

    def test_trending_up_6_consecutive(self):
        """6 consecutive strictly increasing points → trending_up fires."""
        series = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
        self.assertTrue(drift._we_trending(series, direction="up"))

        # Break with flat → no.
        self.assertFalse(
            drift._we_trending([0.70, 0.75, 0.75, 0.85, 0.90, 0.95], "up")
        )

    def test_classify_trending_down_flips_zone_to_special_cause(self):
        """6-monotonic-decline series → zone=special-cause + drift=True."""
        records = _mk_records([0.95, 0.90, 0.85, 0.80, 0.75, 0.70])
        cls = drift.classify(records)
        self.assertIn("trending_down", cls.get("we_rules", []))
        self.assertEqual(cls["zone"], "special-cause")
        self.assertTrue(cls["drift"])
        self.assertTrue(drift.is_actionable(cls))

    def test_classify_trending_up_is_informational(self):
        """Rising metric on higher-is-better axis: trending_up reported, no drift."""
        # 6 monotonic increase below special-cause z-score.
        # Baseline_window default=4, so baseline = series[-5:-1].
        records = _mk_records([0.50, 0.60, 0.70, 0.80, 0.85, 0.90])
        cls = drift.classify(records)
        self.assertIn("trending_up", cls.get("we_rules", []))
        # trending_up MUST NOT flip drift (higher-is-better metric).
        # Zone depends on z-score — latest is above baseline, so z<=0 → common-cause.
        self.assertFalse(cls["drift"], f"trending_up should not flip drift; got {cls}")

    def test_we_rules_field_present_on_every_classification(self):
        """Every classify() return has the we_rules list (may be empty)."""
        records = _mk_records([0.88, 0.86, 0.90, 0.87, 0.89])
        cls = drift.classify(records)
        self.assertIn("we_rules", cls)
        self.assertIsInstance(cls["we_rules"], list)


class SessionStateProducerTests(unittest.TestCase):
    """SessionState producer wiring for #459 telemetry fields."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        # Isolate session state to a tmpdir so producer tests don't clobber
        # the developer's real session state.
        import os as _os
        self._prev_tmpdir = _os.environ.get("TMPDIR")
        self._prev_session = _os.environ.get("CLAUDE_SESSION_ID")
        _os.environ["TMPDIR"] = self.tmp.name
        _os.environ["CLAUDE_SESSION_ID"] = "test-producer-459"
        # Fresh import — session path is captured at module-import time via
        # _state_file_path() which reads TMPDIR each call, so no reload needed.
        import importlib
        scripts_root = _REPO_ROOT / "scripts"
        if str(scripts_root) not in sys.path:
            sys.path.insert(0, str(scripts_root))
        if "_session" in sys.modules:
            importlib.reload(sys.modules["_session"])
        from _session import SessionState  # noqa: E402
        self.SessionState = SessionState
        # Start every test from a clean state.
        SessionState().save()

    def tearDown(self):
        import os as _os
        if self._prev_tmpdir is None:
            _os.environ.pop("TMPDIR", None)
        else:
            _os.environ["TMPDIR"] = self._prev_tmpdir
        if self._prev_session is None:
            _os.environ.pop("CLAUDE_SESSION_ID", None)
        else:
            _os.environ["CLAUDE_SESSION_ID"] = self._prev_session
        self.tmp.cleanup()

    def test_session_state_has_telemetry_fields(self):
        """SessionState exposes the fields telemetry.py reads."""
        s = self.SessionState()
        # Defaults documented in _session.py.
        self.assertEqual(s.skip_reeval_count, 0)
        self.assertIsNone(s.complexity_at_session_open)
        self.assertEqual(s.complexity_score, 0)

    def test_increment_skip_reeval_count_producer(self):
        """phase_manager._increment_skip_reeval_count bumps the session field."""
        crew_path = _REPO_ROOT / "scripts" / "crew"
        if str(crew_path) not in sys.path:
            sys.path.insert(0, str(crew_path))
        import importlib
        if "phase_manager" in sys.modules:
            importlib.reload(sys.modules["phase_manager"])
        from phase_manager import _increment_skip_reeval_count  # noqa: E402

        _increment_skip_reeval_count()
        s = self.SessionState.load()
        self.assertEqual(s.skip_reeval_count, 1)

        _increment_skip_reeval_count()
        _increment_skip_reeval_count()
        s = self.SessionState.load()
        self.assertEqual(s.skip_reeval_count, 3)

    def test_complexity_snapshot_first_write_anchors_open(self):
        """First _record_complexity_snapshot sets complexity_at_session_open."""
        crew_path = _REPO_ROOT / "scripts" / "crew"
        if str(crew_path) not in sys.path:
            sys.path.insert(0, str(crew_path))
        import importlib
        if "phase_manager" in sys.modules:
            importlib.reload(sys.modules["phase_manager"])
        from phase_manager import _record_complexity_snapshot  # noqa: E402

        _record_complexity_snapshot(3)
        s = self.SessionState.load()
        self.assertEqual(s.complexity_at_session_open, 3)
        self.assertEqual(s.complexity_score, 3)

        # Subsequent writes update complexity_score but NOT the open anchor.
        _record_complexity_snapshot(5)
        s = self.SessionState.load()
        self.assertEqual(
            s.complexity_at_session_open, 3,
            "first-observation anchor must be sticky",
        )
        self.assertEqual(s.complexity_score, 5)

    def test_telemetry_reads_producer_fields(self):
        """Telemetry._extract_session_extras picks up our producer writes."""
        # Prime SessionState with producer values.
        s = self.SessionState.load()
        s.skip_reeval_count = 2
        s.complexity_at_session_open = 4
        s.complexity_score = 6
        s.save()

        # Fresh-import telemetry so its sys.path lookup resolves our isolated
        # _session module.
        delivery_path = _REPO_ROOT / "scripts" / "delivery"
        if str(delivery_path) not in sys.path:
            sys.path.insert(0, str(delivery_path))
        import importlib
        if "telemetry" in sys.modules:
            importlib.reload(sys.modules["telemetry"])
        import telemetry as tele  # noqa: E402

        extras = tele._extract_session_extras()
        self.assertEqual(extras["skip_reeval_count"], 2)
        # complexity_delta = close(6) - open(4) = 2.
        self.assertEqual(extras["complexity_delta"], 2)


if __name__ == "__main__":
    unittest.main()
