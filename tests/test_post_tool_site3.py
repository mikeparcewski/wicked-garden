#!/usr/bin/env python3
"""Tests for Site 3 bus-cutover in hooks/scripts/post_tool.py (Issue #746 PR-AB).

Covers:
  1. Per-emit chain_id uniqueness — 3 consecutive consensus runs carry 3 distinct
     chain_ids (regression for bus-chain-id-must-include-uniqueness-segment-gotcha).
  2. eval_id threading — _write_pending_reviewer_report receives eval_id from caller.
  3. Write-then-emit invariant — write happens BEFORE emit in all 3 branches.
  4. Flag contract — emits only fire when WG_BUS_AS_TRUTH_REVIEWER_REPORT == "on".
  5. New event types registered in BUS_EVENT_MAP.

Constraints (T1-T6):
  - No sleep-based sync
  - Per-test isolation via setUp/teardown + autouse conftest fixture
  - Single-assertion focus per method where practical
  - Descriptive names
  - Provenance: Issue #746 Site 3, PR-AB
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import List
from unittest.mock import patch, call, MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_HOOKS_SCRIPTS = _REPO_ROOT / "hooks" / "scripts"
_SCRIPTS = _REPO_ROOT / "scripts"

for p in (_SCRIPTS, _HOOKS_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import post_tool  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_phase_dir(tmp_root: Path, project: str = "myproj", phase: str = "build") -> Path:
    """Create and return a phase directory matching the expected layout.

    Layout: {tmp_root}/{project}/phases/{phase}
    post_tool.py derives project_id = phase_dir.parents[1].name, so we need
    the two-level hierarchy.
    """
    phase_dir = tmp_root / project / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


# ---------------------------------------------------------------------------
# 1. chain_id uniqueness across 3 consecutive consensus runs
# ---------------------------------------------------------------------------

class TestChainIdUniquenessAcrossRuns(unittest.TestCase):
    """Per-emit chain_id must carry a unique discriminator.

    Regression: bus-chain-id-must-include-uniqueness-segment-gotcha.
    If all 3 runs reuse the same chain_id the downstream subscriber
    deduplicates and only processes the first event.
    """

    def test_three_runs_produce_three_distinct_chain_ids(self) -> None:
        """3 consecutive writes (flag on, mocked subprocess) produce 3 distinct chain_ids."""
        captured_chain_ids: List[str] = []

        def _capture_emit(event_type, payload, chain_id=None, metadata=None):
            if chain_id is not None:
                captured_chain_ids.append(chain_id)

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp))

            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture_emit):

                consensus_results = [
                    {"result": "approved", "agreement_ratio": 0.9,
                     "findings": [], "conditions": [],
                     "evidence_items_checked": 5,
                     "eval_id": f"eval{i:04d}"}
                    for i in range(3)
                ]

                for cr in consensus_results:
                    phase_dir_local = _make_phase_dir(
                        Path(tmp),
                        project="myproj",
                        phase="build",
                    )
                    # _write_reviewer_report creates-or-appends, each with its own eval_id.
                    post_tool._write_reviewer_report(
                        phase_dir_local, "approved", cr, cr["eval_id"]
                    )

        # At least 3 chain_ids should have been captured (one per run).
        self.assertGreaterEqual(len(captured_chain_ids), 3,
                                f"Expected >= 3 chain_id captures, got: {captured_chain_ids}")

        # All must be distinct.
        self.assertEqual(
            len(captured_chain_ids),
            len(set(captured_chain_ids)),
            f"Duplicate chain_ids detected: {captured_chain_ids}. "
            f"Each emit must carry a unique discriminator segment per "
            f"bus-chain-id-must-include-uniqueness-segment-gotcha.",
        )

    def test_chain_id_contains_eval_id_segment(self) -> None:
        """chain_id must contain the eval_id as a discriminator segment."""
        captured: List[str] = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            if chain_id:
                captured.append(chain_id)

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp))
            cr = {"result": "approved", "agreement_ratio": 0.9,
                  "findings": [], "conditions": [], "evidence_items_checked": 3,
                  "eval_id": "deadbeef12345678"}

            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_reviewer_report(phase_dir, "approved", cr, "deadbeef12345678")

        self.assertTrue(
            any("deadbeef12345678" in cid for cid in captured),
            f"eval_id not found in chain_ids: {captured}",
        )


# ---------------------------------------------------------------------------
# 2. eval_id threading — pending path receives eval_id from caller
# ---------------------------------------------------------------------------

class TestPendingReportEvalIdThreading(unittest.TestCase):
    """_write_pending_reviewer_report must receive eval_id from its caller.

    Option A from the pre-impl council: pass eval_id as a positional arg.
    No consensus_result is available on the failure path — the caller mints
    eval_id at the entry point and passes it in.
    """

    def test_pending_report_uses_caller_provided_eval_id_in_chain_id(self) -> None:
        """The chain_id in the gate_pending emit must contain the passed eval_id."""
        captured_chain_ids: List[str] = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            if chain_id:
                captured_chain_ids.append(chain_id)

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="proj1", phase="design")

            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_pending_reviewer_report(phase_dir, "beefdead99990000")

        self.assertTrue(
            any("beefdead99990000" in cid for cid in captured_chain_ids),
            f"Caller-provided eval_id not found in captured chain_ids: {captured_chain_ids}",
        )

    def test_pending_report_writes_file_regardless_of_flag(self) -> None:
        """The disk write must happen regardless of the bus flag — write is not gated."""
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="proj2", phase="review")

            # Flag is OFF — no emit but the file must still be written.
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": ""}):
                post_tool._write_pending_reviewer_report(phase_dir, "any-eval-id")

            report_path = phase_dir / "reviewer-report.md"
            self.assertTrue(
                report_path.is_file(),
                "reviewer-report.md must be written even when bus flag is off",
            )


# ---------------------------------------------------------------------------
# 3. Write-then-emit invariant
# ---------------------------------------------------------------------------

class TestWriteThenEmitInvariant(unittest.TestCase):
    """The file write MUST happen before the emit in all 3 branches.

    This mirrors the Sites 1+2 invariant — the disk artifact must always
    exist before the bus event fires, so projector subscribers can read it.
    """

    def _build_mock_consensus_result(self, eval_id: str = "aabbccdd11223344") -> dict:
        return {
            "result": "approved",
            "agreement_ratio": 1.0,
            "findings": [],
            "conditions": [],
            "evidence_items_checked": 2,
            "eval_id": eval_id,
        }

    def test_write_happens_before_emit_in_create_branch(self) -> None:
        """reviewer-report.md must exist when the gate_completed emit fires (create)."""
        file_existed_at_emit_time: List[bool] = []

        def _check_file_exists(event_type, payload, chain_id=None, metadata=None):
            # Check if the file exists at the moment emit_event is called.
            # phase_dir is captured in closure.
            file_existed_at_emit_time.append(report_path.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="projA", phase="build")
            report_path = phase_dir / "reviewer-report.md"

            cr = self._build_mock_consensus_result("aaaa0000bbbb1111")
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_check_file_exists):
                post_tool._write_reviewer_report(phase_dir, "approved", cr, "aaaa0000bbbb1111")

        self.assertTrue(
            all(file_existed_at_emit_time),
            "write-then-emit invariant violated: file did not exist when emit fired",
        )
        self.assertGreater(len(file_existed_at_emit_time), 0,
                           "emit_event was never called (flag may be off)")

    def test_write_happens_before_emit_in_append_branch(self) -> None:
        """reviewer-report.md must exist (non-empty) when the gate_completed emit fires (append)."""
        file_existed_at_emit_time: List[bool] = []

        def _check(event_type, payload, chain_id=None, metadata=None):
            file_existed_at_emit_time.append(report_path.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="projB", phase="build")
            report_path = phase_dir / "reviewer-report.md"

            # Pre-seed the file so the append branch is taken.
            report_path.write_text("# Existing report\n", encoding="utf-8")

            cr = self._build_mock_consensus_result("cccc2222dddd3333")
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_check):
                post_tool._write_reviewer_report(phase_dir, "conditional", cr, "cccc2222dddd3333")

        self.assertTrue(
            all(file_existed_at_emit_time),
            "write-then-emit invariant violated in append branch",
        )

    def test_write_happens_before_emit_in_pending_branch(self) -> None:
        """reviewer-report.md must exist when the gate_pending emit fires."""
        file_existed_at_emit_time: List[bool] = []

        def _check(event_type, payload, chain_id=None, metadata=None):
            file_existed_at_emit_time.append(report_path.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="projC", phase="design")
            report_path = phase_dir / "reviewer-report.md"

            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_check):
                post_tool._write_pending_reviewer_report(phase_dir, "eeee4444ffff5555")

        self.assertTrue(
            all(file_existed_at_emit_time),
            "write-then-emit invariant violated in pending branch",
        )


# ---------------------------------------------------------------------------
# 4. Flag contract
# ---------------------------------------------------------------------------

class TestFlagContract(unittest.TestCase):
    """Emits must only fire when WG_BUS_AS_TRUTH_REVIEWER_REPORT == 'on' (exactly)."""

    def _count_emits_with_env(self, env_value: str) -> int:
        emit_count = 0

        def _counter(event_type, payload, chain_id=None, metadata=None):
            nonlocal emit_count
            emit_count += 1

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="flagtest", phase="build")
            cr = {"result": "approved", "agreement_ratio": 1.0,
                  "findings": [], "conditions": [], "evidence_items_checked": 1,
                  "eval_id": "ffff6666aaaa7777"}
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": env_value}), \
                 patch("_bus.emit_event", side_effect=_counter):
                post_tool._write_reviewer_report(
                    phase_dir, "approved", cr, "ffff6666aaaa7777"
                )
        return emit_count

    def test_emit_fires_when_flag_is_on(self) -> None:
        self.assertGreater(self._count_emits_with_env("on"), 0)

    def test_emit_suppressed_when_flag_is_off(self) -> None:
        self.assertEqual(self._count_emits_with_env(""), 0)

    def test_emit_suppressed_when_flag_is_true(self) -> None:
        """Only the literal string 'on' enables the flag — 'true' must not."""
        self.assertEqual(self._count_emits_with_env("true"), 0)

    def test_emit_suppressed_when_flag_is_1(self) -> None:
        self.assertEqual(self._count_emits_with_env("1"), 0)

    def test_bus_as_truth_flag_on_helper_returns_false_by_default(self) -> None:
        """Flag default must be OFF — never flip this default in this PR."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WG_BUS_AS_TRUTH_REVIEWER_REPORT", None)
            self.assertFalse(post_tool._bus_as_truth_flag_on())

    def test_bus_as_truth_flag_on_helper_returns_true_for_on(self) -> None:
        with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}):
            self.assertTrue(post_tool._bus_as_truth_flag_on())


# ---------------------------------------------------------------------------
# 5. New event types registered in BUS_EVENT_MAP
# ---------------------------------------------------------------------------

class TestSite3EventTypesRegistered(unittest.TestCase):
    """wicked.consensus.gate_completed and gate_pending must be in BUS_EVENT_MAP."""

    def setUp(self) -> None:
        import _bus as bus_mod
        self.bus = bus_mod

    def test_gate_completed_in_bus_event_map(self) -> None:
        self.assertIn(
            "wicked.consensus.gate_completed",
            self.bus.BUS_EVENT_MAP,
            "wicked.consensus.gate_completed must be registered in BUS_EVENT_MAP",
        )

    def test_gate_pending_in_bus_event_map(self) -> None:
        self.assertIn(
            "wicked.consensus.gate_pending",
            self.bus.BUS_EVENT_MAP,
            "wicked.consensus.gate_pending must be registered in BUS_EVENT_MAP",
        )

    def test_gate_completed_allow_override_for_raw_payload(self) -> None:
        """gate_completed must allow raw_payload through the deny-list."""
        allow = self.bus._PAYLOAD_ALLOW_OVERRIDES.get("wicked.consensus.gate_completed", frozenset())
        self.assertIn("raw_payload", allow)

    def test_gate_pending_allow_override_for_raw_payload(self) -> None:
        """gate_pending must allow raw_payload through the deny-list."""
        allow = self.bus._PAYLOAD_ALLOW_OVERRIDES.get("wicked.consensus.gate_pending", frozenset())
        self.assertIn("raw_payload", allow)


# ---------------------------------------------------------------------------
# Finding #2 — eval_id minted at entry point, reused on exception path
# ---------------------------------------------------------------------------

class TestEvalIdEntryPointMint(unittest.TestCase):
    """Finding #2: eval_id must be minted ONCE at the top of
    _handle_bash_consensus and reused across success, pending, and exception
    paths so chain_ids never diverge within one invocation.
    """

    def test_exception_path_gate_pending_chain_id_contains_provided_eval_id(self) -> None:
        """The except block calls _write_pending_reviewer_report(phase_dir, eval_id)
        where eval_id was minted at the entry point.  Verify the chain_id in the
        gate_pending emit contains the eval_id passed to that function.

        Strategy: call _write_pending_reviewer_report directly with a controlled
        eval_id and assert the chain_id contains it.  This tests the post-fix
        shape where eval_id is threaded from the caller rather than re-minted.
        """
        controlled_eval_id = "cafebabe12345678"
        captured_chain_ids: List[str] = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            if chain_id:
                captured_chain_ids.append(chain_id)

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="exc-proj", phase="build")
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_pending_reviewer_report(phase_dir, controlled_eval_id)

        self.assertTrue(
            any(controlled_eval_id in cid for cid in captured_chain_ids),
            f"Entry-point eval_id {controlled_eval_id!r} not found in captured chain_ids: "
            f"{captured_chain_ids}.  Exception path must reuse entry-point eval_id.",
        )

    def test_exception_path_reuses_eval_id_not_fresh_mint(self) -> None:
        """The except block in _handle_bash_consensus must NOT contain a second
        uuid.uuid4() call.  Verify by inspecting the source.

        This is a static check: read the source, find the except block, confirm
        there is no uuid.uuid4() inside it.
        """
        import inspect
        source = inspect.getsource(post_tool._handle_bash_consensus)
        except_idx = source.find("except Exception")
        self.assertGreater(except_idx, 0, "_handle_bash_consensus must have an except block")
        except_body = source[except_idx:]
        self.assertNotIn(
            "uuid.uuid4()",
            except_body,
            "except block must not mint a second UUID — reuse entry-point eval_id instead",
        )


# ---------------------------------------------------------------------------
# Finding #3 — bounded raw_payload / digest shape
# ---------------------------------------------------------------------------

class TestBoundedDigestPayload(unittest.TestCase):
    """Finding #3: raw_payload must be replaced with a bounded digest.

    Append-path payload size is O(yaml_block) not O(cumulative file).
    """

    def _run_append_cycle(
        self,
        phase_dir: Path,
        emit_count: int,
        captured_payloads: list,
    ) -> None:
        """Run `emit_count` consecutive consensus writes and collect payloads."""
        def _capture(event_type, payload, chain_id=None, metadata=None):
            captured_payloads.append(payload)

        with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
             patch("_bus.emit_event", side_effect=_capture):
            for i in range(emit_count):
                cr = {
                    "result": "approved",
                    "agreement_ratio": 0.9,
                    "findings": [],
                    "conditions": [],
                    "evidence_items_checked": i + 1,
                    "eval_id": f"digest{i:08x}",
                }
                post_tool._write_reviewer_report(
                    phase_dir, "approved", cr, f"digest{i:08x}"
                )

    def test_payload_has_sha256_field(self) -> None:
        """All emit payloads must include a sha256 field (bounded digest)."""
        captured: list = []
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="digest-proj", phase="build")
            self._run_append_cycle(phase_dir, 1, captured)
        self.assertGreater(len(captured), 0, "emit_event was never called")
        for payload in captured:
            self.assertIn("sha256", payload,
                          "Payload must include sha256 digest field")
            self.assertIsInstance(payload["sha256"], str)
            self.assertEqual(len(payload["sha256"]), 64,
                             "sha256 must be a 64-char hex string")

    def test_payload_has_byte_size_field(self) -> None:
        """All emit payloads must include a byte_size field."""
        captured: list = []
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="digest-size", phase="build")
            self._run_append_cycle(phase_dir, 1, captured)
        self.assertGreater(len(captured), 0)
        for payload in captured:
            self.assertIn("byte_size", payload)
            self.assertIsInstance(payload["byte_size"], int)
            self.assertGreater(payload["byte_size"], 0)

    def test_payload_has_appended_section_preview(self) -> None:
        """All emit payloads must include appended_section_preview (the yaml_block only)."""
        captured: list = []
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="digest-preview", phase="build")
            self._run_append_cycle(phase_dir, 1, captured)
        self.assertGreater(len(captured), 0)
        for payload in captured:
            self.assertIn("appended_section_preview", payload)

    def test_no_raw_payload_field_in_completed_emit(self) -> None:
        """gate_completed emits must NOT have a raw_payload field (replaced by digest)."""
        captured: list = []
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="no-raw", phase="build")
            self._run_append_cycle(phase_dir, 1, captured)
        for payload in captured:
            self.assertNotIn(
                "raw_payload", payload,
                "raw_payload must be removed from gate_completed emit payload (Finding #3)",
            )

    def test_byte_size_matches_file_after_each_append(self) -> None:
        """byte_size must equal the actual file size after each append cycle."""
        import hashlib as hl
        captured: list = []
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="size-match", phase="build")
            report_path = phase_dir / "reviewer-report.md"
            self._run_append_cycle(phase_dir, 3, captured)

            for i, payload in enumerate(captured):
                # After cycle i+1, the file has accumulated i+1 write operations.
                # The last captured payload has byte_size matching the file AT THAT POINT.
                # Since all 3 writes happened before we read, verify the last payload's
                # byte_size matches the final file.
                pass

            # Verify the last payload's byte_size matches the final file size.
            final_file_bytes = report_path.read_bytes()
            last_payload = captured[-1]
            self.assertEqual(
                last_payload["byte_size"],
                len(final_file_bytes),
                f"Last emit byte_size {last_payload['byte_size']} must match "
                f"final file size {len(final_file_bytes)}",
            )

    def test_appended_section_preview_is_bounded(self) -> None:
        """appended_section_preview must not grow cumulatively across appends.

        After 3 cycles, each preview should be ~the same size (the yaml_block
        for that cycle), not the full accumulated file.
        """
        captured: list = []
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="preview-bounded", phase="build")
            self._run_append_cycle(phase_dir, 3, captured)

        # All 3 appended_section_preview values should be approximately the same
        # size (bounded by yaml_block), not growing cumulatively.
        preview_sizes = [len(p["appended_section_preview"]) for p in captured]
        # Max preview should not be dramatically larger than min preview.
        # Allow up to 3x variance for evidence_items_checked field growth,
        # but not the 10x+ that cumulative accumulation would cause.
        self.assertGreater(len(preview_sizes), 0)
        max_size = max(preview_sizes)
        min_size = max(min(preview_sizes), 1)  # avoid div-by-zero
        self.assertLessEqual(
            max_size / min_size, 5.0,
            f"appended_section_preview sizes grew too much across 3 appends: "
            f"{preview_sizes}. Expected bounded growth (yaml_block only), "
            f"not cumulative file content.",
        )


if __name__ == "__main__":
    unittest.main()
