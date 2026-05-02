"""Unit tests for #734 Part C emit additions in dispatch_log.py + consensus_gate.py.

Verifies that:
    * dispatch_log.append emits wicked.dispatch.log_entry_appended after the
      JSONL write succeeds (not before — projector must see write-then-emit
      ordering)
    * consensus_gate._write_consensus_report emits
      wicked.consensus.report_created
    * consensus_gate._write_consensus_evidence emits
      wicked.consensus.evidence_recorded
    * each emit fail-opens — bus errors must not break the calling write path
    * each emit only fires when the underlying write succeeded (no orphan
      emits when the disk write failed)

Mocks _bus.emit_event to avoid spawning real subprocesses.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from crew import dispatch_log as dl  # noqa: E402


class TestDispatchLogEmits(unittest.TestCase):
    def test_emit_after_successful_append(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            with patch("crew.dispatch_log._bus_emit_helper", create=True), \
                 patch("crew.dispatch_log.emit_event", create=True) as mock_emit, \
                 patch.object(dl, "_compute_hmac", return_value="deadbeef"), \
                 patch.object(dl, "_current_hmac_secret", return_value=b"secret"):
                # Patch the actual import inside the function — emit_event is
                # imported lazily from _bus, so we patch that namespace.
                import _bus  # type: ignore[import]
                with patch.object(_bus, "emit_event") as mock_emit_real:
                    dl.append(
                        project_dir,
                        "build",
                        reviewer="rev-1",
                        gate="testability",
                        dispatch_id="abc123",
                    )
                    self.assertTrue(mock_emit_real.called,
                                    "emit_event should be called after successful append")
                    args, kwargs = mock_emit_real.call_args
                    self.assertEqual(args[0], "wicked.dispatch.log_entry_appended")
                    payload = args[1]
                    self.assertEqual(payload["project_id"], "demo-proj")
                    self.assertEqual(payload["phase"], "build")
                    self.assertEqual(payload["gate"], "testability")
                    self.assertEqual(payload["reviewer"], "rev-1")
                    self.assertEqual(payload["dispatch_id"], "abc123")
                    self.assertTrue(payload["hmac_present"])
                    self.assertEqual(kwargs.get("chain_id"), "demo-proj.build.testability")

    def test_no_emit_when_write_fails(self):
        """Disk write fails → no orphan emit. Otherwise the projector
        would record a phantom dispatch that never made it to disk.

        Patches ``Path.open`` (which the dispatch-log path uses) rather
        than ``builtins.open`` — patching builtins.open would also break
        the lazy ``from _bus import emit_event`` import inside the
        function, masking what the test is trying to measure.
        """
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            with patch.object(dl, "_compute_hmac", return_value="deadbeef"), \
                 patch.object(dl, "_current_hmac_secret", return_value=b"secret"), \
                 patch("crew.dispatch_log.Path.open",
                       side_effect=OSError("disk full")):
                import _bus  # type: ignore[import]
                with patch.object(_bus, "emit_event") as mock_emit:
                    dl.append(
                        project_dir,
                        "build",
                        reviewer="rev-1",
                        gate="testability",
                        dispatch_id="abc123",
                    )
                    # Filter to just the Part-C emit (rotate may emit others).
                    target_calls = [
                        c for c in mock_emit.call_args_list
                        if c.args
                        and c.args[0] == "wicked.dispatch.log_entry_appended"
                    ]
                    self.assertEqual(target_calls, [],
                                     "emit must NOT fire when the disk write failed")

    def test_emit_failure_does_not_break_dispatch(self):
        """Bus emit raising must not propagate — fail-open contract."""
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            with patch.object(dl, "_compute_hmac", return_value="deadbeef"), \
                 patch.object(dl, "_current_hmac_secret", return_value=b"secret"):
                import _bus  # type: ignore[import]
                with patch.object(_bus, "emit_event",
                                  side_effect=RuntimeError("bus down")):
                    # Must NOT raise.
                    dl.append(
                        project_dir,
                        "build",
                        reviewer="rev-1",
                        gate="testability",
                        dispatch_id="abc123",
                    )
                    # And the JSONL line must still be on disk.
                    log_path = dl._resolve_log_path(project_dir, "build")
                    self.assertTrue(log_path.is_file())
                    line = log_path.read_text(encoding="utf-8").strip()
                    record = json.loads(line)
                    self.assertEqual(record["reviewer"], "rev-1")


class TestConsensusEmits(unittest.TestCase):
    """Use the public _write_consensus_* helpers via direct import."""

    def _build_result_obj(self):
        # ConsensusResult lives in jam.consensus (re-exported by consensus_gate).
        from jam.consensus import ConsensusResult, DissentingView
        return ConsensusResult(
            decision="APPROVE",
            confidence=0.85,
            participants=2,
            rounds=2,
            consensus_points=[{"point": "fast", "agreement": 2, "of": 2}],
            dissenting_views=[
                DissentingView(persona="rev-c", view="too fast",
                               strength="moderate")
            ],
            open_questions=["scope?"],
        )

    def test_report_emit_after_successful_write(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            from crew import consensus_gate as cg
            result = self._build_result_obj()
            scores = {"agreement_ratio": 0.92, "divergent_points": []}
            import _bus  # type: ignore[import]
            with patch.object(_bus, "emit_event") as mock_emit:
                cg._write_consensus_report(project_dir, "design", result, scores)
                # Find the report-created emit (there should be exactly one).
                report_calls = [c for c in mock_emit.call_args_list
                                if c.args and c.args[0] == "wicked.consensus.report_created"]
                self.assertEqual(len(report_calls), 1,
                                 f"expected one report emit, got {len(report_calls)}")
                payload = report_calls[0].args[1]
                self.assertEqual(payload["project_id"], "demo-proj")
                self.assertEqual(payload["phase"], "design")
                self.assertEqual(payload["decision"], "APPROVE")
                self.assertAlmostEqual(payload["agreement_ratio"], 0.92)
                self.assertEqual(report_calls[0].kwargs.get("chain_id"),
                                 "demo-proj.design")

    def test_evidence_emit_after_successful_write(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            from crew import consensus_gate as cg
            consensus_result = {
                "result": "REJECT",
                "reason": "agreement below threshold",
                "consensus_confidence": 0.4,
                "agreement_ratio": 0.45,
                "dissenting_views": [],
                "participants": ["rev-a", "rev-b"],
            }
            import _bus  # type: ignore[import]
            with patch.object(_bus, "emit_event") as mock_emit:
                cg._write_consensus_evidence(project_dir, "review", consensus_result)
                evidence_calls = [c for c in mock_emit.call_args_list
                                  if c.args and c.args[0] == "wicked.consensus.evidence_recorded"]
                self.assertEqual(len(evidence_calls), 1)
                payload = evidence_calls[0].args[1]
                self.assertEqual(payload["project_id"], "demo-proj")
                self.assertEqual(payload["phase"], "review")
                self.assertEqual(payload["result"], "REJECT")
                self.assertEqual(evidence_calls[0].kwargs.get("chain_id"),
                                 "demo-proj.review")

    def test_evidence_no_emit_when_write_fails(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            from crew import consensus_gate as cg
            consensus_result = {"result": "REJECT", "reason": "x"}
            with patch("crew.consensus_gate.Path.write_text",
                       side_effect=OSError("disk full")):
                import _bus  # type: ignore[import]
                with patch.object(_bus, "emit_event") as mock_emit:
                    cg._write_consensus_evidence(project_dir, "review", consensus_result)
                    evidence_calls = [c for c in mock_emit.call_args_list
                                      if c.args and c.args[0] == "wicked.consensus.evidence_recorded"]
                    self.assertEqual(evidence_calls, [],
                                     "must not emit when disk write failed")


if __name__ == "__main__":
    unittest.main()
