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
                    # Site 1 (#751) C5 — chain_id includes dispatch_id so retries
                    # do not collide on the bus dedupe ledger.  This assertion
                    # was originally `"demo-proj.build.testability"` (pre-#751).
                    self.assertEqual(
                        kwargs.get("chain_id"),
                        "demo-proj.build.testability.abc123",
                    )

    def test_emit_fires_independently_of_disk_state(self):
        """Site 1 emit-only contract (PR #800).

        Pre-PR-#800 the helper did write-then-emit: a disk failure
        suppressed the emit (no phantom event in event_log).  After
        legacy-write deletion the helper is emit-only — the projector
        materialises the file from the bus event.  The emit must fire
        regardless of any disk state at the source side.
        """
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            with patch.object(dl, "_compute_hmac", return_value="deadbeef"), \
                 patch.object(dl, "_current_hmac_secret", return_value=b"secret"):
                import _bus  # type: ignore[import]
                with patch.object(_bus, "emit_event") as mock_emit:
                    dl.append(
                        project_dir,
                        "build",
                        reviewer="rev-1",
                        gate="testability",
                        dispatch_id="abc123",
                    )
                    target_calls = [
                        c for c in mock_emit.call_args_list
                        if c.args
                        and c.args[0] == "wicked.dispatch.log_entry_appended"
                    ]
                    self.assertEqual(
                        len(target_calls), 1,
                        "emit-only contract: the bus event must fire — "
                        "the projector materialises the file from raw_payload.",
                    )
                    # Source-side never touches disk.
                    log_path = dl._resolve_log_path(project_dir, "build")
                    self.assertFalse(
                        log_path.exists(),
                        "PR #800 deleted the source-side disk write; helper "
                        "must emit only.",
                    )

    def test_emit_failure_does_not_break_dispatch(self):
        """Bus emit raising must not propagate — fail-open contract.

        Post PR-#800 the source side never touches disk; we just verify
        the caller does not see the bus exception.  The on-disk file
        appears later when the daemon's projector replays the queued
        event (which doesn't exist in this test, so we assert nothing
        about the file).
        """
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
                # Site 2 (#746) C9 — pass an explicit eval_id so the chain_id
                # is deterministic.  When the caller omits eval_id, the helper
                # mints a uuid; this test pins the format independent of uuid
                # generation by supplying it explicitly.
                cg._write_consensus_report(
                    project_dir, "design", result, scores,
                    eval_id="abcdef123456",
                )
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
                # Site 2 (#746) C9 — chain_id includes eval_id discriminator.
                # Pre-#746 was `"demo-proj.design"` which collided on retries.
                self.assertEqual(
                    report_calls[0].kwargs.get("chain_id"),
                    "demo-proj.design.consensus.abcdef123456",
                )
                # Site 2 (#746) C10 — raw_payload REQUIRED in the emit.
                self.assertIn("raw_payload", payload,
                              "C10 violation: raw_payload missing from emit")
                self.assertEqual(payload["eval_id"], "abcdef123456")

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
                # Site 2 (#746) C9 — caller threads eval_id through so
                # report and evidence chain_ids share the same eval segment.
                "eval_id": "abcdef123456",
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
                # Site 2 (#746) C9 — evidence chain_id includes both eval_id
                # AND a `.evidence` discriminator so it stays distinct from
                # the report emit's chain_id within the same eval.
                # Pre-#746 was `"demo-proj.review"` which collided.
                self.assertEqual(
                    evidence_calls[0].kwargs.get("chain_id"),
                    "demo-proj.review.consensus.abcdef123456.evidence",
                )
                # Site 2 (#746) C10 — raw_payload REQUIRED.
                self.assertIn("raw_payload", payload,
                              "C10 violation: raw_payload missing from evidence emit")
                self.assertEqual(payload["eval_id"], "abcdef123456")

    def test_evidence_emit_fires_independently_of_disk_state(self):
        """Site 2 cutover (#746, PR #798) — emit-only contract.

        Pre-PR-#798 the helper did write-then-emit, so a disk failure
        suppressed the emit (Council Condition C4 soak-window contract).
        After legacy-write deletion the helper is emit-only — the
        projector materialises the file from the bus event.  The emit
        must fire regardless of any disk state at the source side.
        """
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo-proj"
            project_dir.mkdir()
            from crew import consensus_gate as cg
            consensus_result = {"result": "REJECT", "reason": "x"}
            import _bus  # type: ignore[import]
            with patch.object(_bus, "emit_event") as mock_emit:
                cg._write_consensus_evidence(project_dir, "review", consensus_result)
                evidence_calls = [c for c in mock_emit.call_args_list
                                  if c.args and c.args[0] == "wicked.consensus.evidence_recorded"]
                self.assertEqual(len(evidence_calls), 1,
                                 "emit-only contract: bus event must fire — projector "
                                 "materialises the file from raw_payload async.")
                # Source side never touches disk, so there is no disk file
                # to assert on; the projector is the canonical writer now.
                evidence_path = project_dir / "phases" / "review" / "consensus-evidence.json"
                self.assertFalse(evidence_path.exists(),
                                 "PR #798 deleted the source-side disk write; the file "
                                 "must NOT appear from this helper alone.")


if __name__ == "__main__":
    unittest.main()
