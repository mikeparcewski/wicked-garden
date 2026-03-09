#!/usr/bin/env python3
"""
tests/smaht/test_orchestrator_metrics.py

Unit tests for Orchestrator._update_metrics and get_session_metrics (Task 4.4).

AC coverage: AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5
Scenario coverage: S-MET-1..8, S-NEG-3, S-NEG-4, Gap G-3, G-6

Tests use tempfile.TemporaryDirectory to avoid cross-test file contamination.
Orchestrator is constructed with patched HistoryCondenser, FastPathAssembler,
and SlowPathAssembler to prevent real DomainStore / filesystem access.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_V2_DIR = _REPO_ROOT / "scripts" / "smaht" / "v2"
_ADAPTERS_DIR = _REPO_ROOT / "scripts" / "smaht"

sys.path.insert(0, str(_V2_DIR))
sys.path.insert(0, str(_ADAPTERS_DIR))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))


def _make_orchestrator(session_dir: Path):
    """Build an Orchestrator instance with all heavy dependencies mocked.

    The condenser is replaced with a mock whose session_dir points to our
    temp directory, and whose _atomic_write does a real write (the method
    under test uses it). This keeps the metrics write path real while avoiding
    DomainStore / filesystem side effects from HistoryCondenser.__init__.
    """
    with patch("orchestrator.HistoryCondenser") as MockCondenser, \
         patch("orchestrator.FastPathAssembler"), \
         patch("orchestrator.SlowPathAssembler"), \
         patch("orchestrator.Router"):

        mock_condenser = MagicMock()
        mock_condenser.session_dir = session_dir
        mock_condenser.summary = MagicMock()
        mock_condenser.summary.topics = []

        # _atomic_write: use real implementation (write + rename) for metrics tests.
        # We replicate the logic from HistoryCondenser._atomic_write here.
        def real_atomic_write(path: Path, content: str):
            fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, str(path))
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

        mock_condenser._atomic_write = real_atomic_write

        MockCondenser.return_value = mock_condenser

        from orchestrator import Orchestrator
        orch = Orchestrator(session_id="test-session")
        orch.condenser = mock_condenser

    return orch


# ---------------------------------------------------------------------------
# TestUpdateMetrics — _update_metrics writes adapter_timings to metrics.json
# ---------------------------------------------------------------------------

class TestUpdateMetrics(unittest.TestCase):
    """S-MET-1..4, S-NEG-3, S-NEG-4, Gap G-3: _update_metrics correctness."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.tmpdir.name)
        self.orch = _make_orchestrator(self.session_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _read_metrics(self) -> dict:
        return json.loads((self.session_dir / "metrics.json").read_text())

    def test_update_metrics_writes_adapter_timings(self):
        """S-MET-1 / AC-2.1: adapter_timings written to metrics.json with correct values."""
        self.orch._update_metrics(
            5,
            {"domain": {"total_ms": 100, "call_count": 2, "cache_hits": 0, "failures": 0}},
        )

        metrics = self._read_metrics()
        self.assertIn("adapter_timings", metrics)
        self.assertIn("domain", metrics["adapter_timings"])
        self.assertEqual(metrics["adapter_timings"]["domain"]["total_ms"], 100)
        self.assertEqual(metrics["adapter_timings"]["domain"]["call_count"], 2)
        self.assertEqual(metrics["adapter_timings"]["domain"]["avg_ms"], 50.0)
        self.assertEqual(metrics["items_pre_loaded"], 5)

    def test_update_metrics_accumulates_across_calls(self):
        """S-MET-2 / AC-2.1: Second call merges totals, not overwrites."""
        self.orch._update_metrics(
            3,
            {"domain": {"total_ms": 100, "call_count": 2, "cache_hits": 0, "failures": 0}},
        )
        self.orch._update_metrics(
            3,
            {"domain": {"total_ms": 60, "call_count": 1, "cache_hits": 1, "failures": 0}},
        )

        metrics = self._read_metrics()
        domain = metrics["adapter_timings"]["domain"]
        self.assertEqual(domain["total_ms"], 160)
        self.assertEqual(domain["call_count"], 3)
        self.assertEqual(domain["cache_hits"], 1)
        self.assertAlmostEqual(domain["avg_ms"], round(160 / 3, 1))

    def test_update_metrics_cache_hit_does_not_corrupt_avg(self):
        """S-MET-3 / AC-2.2: Cache hit increments cache_hits, does not change total_ms or avg_ms."""
        # Seed with real call data
        self.orch._update_metrics(
            4,
            {"domain": {"total_ms": 400, "call_count": 4, "cache_hits": 0, "failures": 0}},
        )
        # Now record a pure cache hit (no call, no timing)
        self.orch._update_metrics(
            0,
            {"domain": {"total_ms": 0, "call_count": 0, "cache_hits": 1, "failures": 0}},
        )

        metrics = self._read_metrics()
        domain = metrics["adapter_timings"]["domain"]
        self.assertEqual(domain["cache_hits"], 1)
        self.assertEqual(domain["call_count"], 4)  # unchanged
        self.assertEqual(domain["total_ms"], 400)  # unchanged
        self.assertEqual(domain["avg_ms"], 100.0)  # unchanged

    def test_update_metrics_failure_does_not_corrupt_total_ms(self):
        """S-MET-4 / AC-2.3: Failed call increments failures, does not change total_ms."""
        self.orch._update_metrics(
            4,
            {"domain": {"total_ms": 200, "call_count": 4, "cache_hits": 0, "failures": 0}},
        )
        # Record a failure (total_ms=0, call_count=0 for failed call)
        self.orch._update_metrics(
            0,
            {"domain": {"total_ms": 0, "call_count": 0, "cache_hits": 0, "failures": 1}},
        )

        metrics = self._read_metrics()
        domain = metrics["adapter_timings"]["domain"]
        self.assertEqual(domain["failures"], 1)
        self.assertEqual(domain["total_ms"], 200)  # unchanged
        self.assertEqual(domain["avg_ms"], 50.0)   # unchanged

    def test_update_metrics_without_timings(self):
        """S-MET-6: _update_metrics(n, None) creates metrics.json with adapter_timings={}."""
        self.orch._update_metrics(3, None)

        metrics = self._read_metrics()
        self.assertIn("adapter_timings", metrics)
        self.assertEqual(metrics["adapter_timings"], {})
        self.assertEqual(metrics["items_pre_loaded"], 3)

    def test_update_metrics_avg_ms_division_by_zero_guard(self):
        """Gap G-3: avg_ms not computed when call_count=0 (only cache hits) — no ZeroDivisionError."""
        # Only cache hits — call_count stays 0
        self.orch._update_metrics(
            0,
            {"domain": {"total_ms": 0, "call_count": 0, "cache_hits": 5, "failures": 0}},
        )

        # Must not raise and metrics.json must be valid
        metrics = self._read_metrics()
        domain = metrics["adapter_timings"]["domain"]
        self.assertEqual(domain["cache_hits"], 5)
        self.assertEqual(domain["call_count"], 0)
        # avg_ms should remain at default 0.0 (not computed when call_count=0)
        self.assertEqual(domain.get("avg_ms", 0.0), 0.0)

    def test_update_metrics_partial_timing_data_no_key_error(self):
        """S-NEG-4: Partial timing dict with missing sub-keys — no KeyError."""
        # Only total_ms provided (missing call_count, cache_hits, failures)
        self.orch._update_metrics(
            1,
            {"domain": {"total_ms": 50}},
        )

        # Must not raise
        metrics = self._read_metrics()
        self.assertIn("domain", metrics["adapter_timings"])

    def test_update_metrics_corrupted_metrics_json_handled(self):
        """S-NEG-3: Corrupted metrics.json — _update_metrics does not crash."""
        metrics_path = self.session_dir / "metrics.json"
        metrics_path.write_text("{corrupt json[")

        # Must not raise (fail open)
        self.orch._update_metrics(
            2,
            {"domain": {"total_ms": 30, "call_count": 1, "cache_hits": 0, "failures": 0}},
        )

    def test_update_metrics_multiple_adapters_in_single_call(self):
        """Multiple adapter entries in one call all written correctly."""
        self.orch._update_metrics(
            6,
            {
                "domain": {"total_ms": 100, "call_count": 1, "cache_hits": 0, "failures": 0},
                "context7": {"total_ms": 200, "call_count": 2, "cache_hits": 1, "failures": 0},
                "mem": {"total_ms": 50, "call_count": 1, "cache_hits": 0, "failures": 0},
            },
        )

        metrics = self._read_metrics()
        at = metrics["adapter_timings"]
        self.assertEqual(at["domain"]["call_count"], 1)
        self.assertEqual(at["context7"]["call_count"], 2)
        self.assertEqual(at["context7"]["cache_hits"], 1)
        self.assertEqual(at["mem"]["total_ms"], 50)


# ---------------------------------------------------------------------------
# TestMetricsFailOpen — AC-2.4
# ---------------------------------------------------------------------------

class TestMetricsFailOpen(unittest.TestCase):
    """S-MET-5 / AC-2.4: Metrics write errors are swallowed, gather_context proceeds."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.tmpdir.name)
        self.orch = _make_orchestrator(self.session_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_write_error_does_not_raise(self):
        """AC-2.4: _atomic_write failure is silently swallowed."""
        # Replace _atomic_write with one that raises PermissionError
        self.orch.condenser._atomic_write = MagicMock(side_effect=PermissionError("disk full"))

        # Must not raise
        self.orch._update_metrics(
            1,
            {"domain": {"total_ms": 50, "call_count": 1, "cache_hits": 0, "failures": 0}},
        )

    def test_write_error_returns_none(self):
        """AC-2.4: _update_metrics returns None even on write failure."""
        self.orch.condenser._atomic_write = MagicMock(side_effect=OSError("no space"))

        result = self.orch._update_metrics(
            1,
            {"domain": {"total_ms": 50, "call_count": 1, "cache_hits": 0, "failures": 0}},
        )
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# TestGetSessionMetrics — AC-2.5 + Gap G-6
# ---------------------------------------------------------------------------

class TestGetSessionMetrics(unittest.TestCase):
    """S-MET-7, S-MET-8 / AC-2.5, Gap G-6: get_session_metrics includes adapter_timings."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.tmpdir.name)
        self.orch = _make_orchestrator(self.session_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_session_metrics_returns_adapter_timings_key(self):
        """S-MET-7 / AC-2.5: Written metrics.json is returned with adapter_timings."""
        metrics_path = self.session_dir / "metrics.json"
        metrics_data = {
            "items_pre_loaded": 4,
            "queries_made": 2,
            "estimated_turns_saved": 6,
            "adapter_timings": {
                "domain": {"total_ms": 200, "call_count": 2, "avg_ms": 100.0, "cache_hits": 1, "failures": 0}
            },
        }
        metrics_path.write_text(json.dumps(metrics_data))

        result = self.orch.get_session_metrics()

        self.assertIn("adapter_timings", result)
        self.assertEqual(result["adapter_timings"]["domain"]["total_ms"], 200)

    def test_get_session_metrics_default_includes_adapter_timings_key(self):
        """S-MET-8 / Gap G-6: Default (no metrics.json) returns dict with adapter_timings key."""
        # No metrics.json written — get_session_metrics must return defaults with adapter_timings
        result = self.orch.get_session_metrics()

        self.assertIn(
            "adapter_timings",
            result,
            "get_session_metrics default must include 'adapter_timings' key (Gap G-6)",
        )
        self.assertEqual(result["adapter_timings"], {})
        self.assertEqual(result["items_pre_loaded"], 0)
        self.assertEqual(result["queries_made"], 0)

    def test_get_session_metrics_corrupted_file_returns_defaults(self):
        """Corrupted metrics.json — get_session_metrics fails open with defaults."""
        metrics_path = self.session_dir / "metrics.json"
        metrics_path.write_text("{invalid")

        result = self.orch.get_session_metrics()

        self.assertIn("adapter_timings", result)
        self.assertEqual(result["items_pre_loaded"], 0)

    def test_roundtrip_update_then_get(self):
        """AC-2.5: _update_metrics then get_session_metrics returns consistent data."""
        self.orch._update_metrics(
            3,
            {"domain": {"total_ms": 150, "call_count": 3, "cache_hits": 2, "failures": 0}},
        )

        result = self.orch.get_session_metrics()

        self.assertIn("adapter_timings", result)
        self.assertEqual(result["adapter_timings"]["domain"]["total_ms"], 150)
        self.assertEqual(result["adapter_timings"]["domain"]["call_count"], 3)
        self.assertEqual(result["adapter_timings"]["domain"]["cache_hits"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
