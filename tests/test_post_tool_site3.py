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

            # Flag explicitly OFF — no emit but the file must still be written.
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "off"}):
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
    """Flag contract for WG_BUS_AS_TRUTH_REVIEWER_REPORT after flag-fold (PR #777).

    Resolution order:
      1. Explicit ``"on"``  (case/whitespace normalised) → emits fire.
      2. Explicit ``"off"`` (case/whitespace normalised) → emits suppressed.
      3. Empty / any other value → default-ON (REVIEWER_REPORT is a shipped site).

    The old literal-``"on"``-only contract (pre-fold) is replaced by a
    normalization + default-map fall-through.  Tests updated accordingly.
    """

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

    def test_emit_suppressed_when_flag_is_explicit_off(self) -> None:
        """Explicit ``"off"`` is the canonical opt-out — emits suppressed."""
        self.assertEqual(self._count_emits_with_env("off"), 0)

    def test_emit_fires_for_non_on_off_shipped_site(self) -> None:
        """Non-``"on"``/``"off"`` value for a shipped site → default-ON → emits fire.

        Pre-fold, ``"true"`` would suppress emits (literal-``"on"``-only contract).
        Post-fold (PR #777), ``"true"`` falls through to the default-ON map
        (REVIEWER_REPORT is a shipped site) → flag is ON → emits fire."""
        self.assertGreater(self._count_emits_with_env("true"), 0)

    def test_emit_fires_for_1_on_shipped_site(self) -> None:
        """``"1"`` for a shipped site → default-ON → emits fire (Finding #4 fix)."""
        self.assertGreater(self._count_emits_with_env("1"), 0)

    def test_bus_as_truth_flag_on_helper_returns_true_by_default(self) -> None:
        """Flag default is ON for REVIEWER_REPORT (shipped Site 3, PR #776/#777)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WG_BUS_AS_TRUTH_REVIEWER_REPORT", None)
            self.assertTrue(post_tool._bus_as_truth_flag_on())

    def test_bus_as_truth_flag_on_helper_returns_false_when_off(self) -> None:
        """Explicit ``"off"`` opts out — helper returns False."""
        with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "off"}):
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
# raw_payload = per-section payload (#770 resolution)
# ---------------------------------------------------------------------------

class TestPerSectionPayload(unittest.TestCase):
    """raw_payload must be the just-written content (per-section shape, #770).

    - append branch: raw_payload == yaml_block (just the section appended),
      NOT the cumulative file.  Matches Site 1 per-entry contract.
    - create branch: raw_payload == yaml_block (which IS the full file on
      create since the file is fresh) — unchanged from prior shape.
    - pending branch: raw_payload == pending_content (full template) —
      unchanged, already correct shape.

    The projector handler reconstructs the cumulative file by reading the
    existing file and applying the standard separator.
    """

    def _capture_emit(
        self,
        phase_dir: Path,
        eval_id: str,
    ) -> list:
        """Run one consensus write and return captured payloads."""
        captured: list = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            captured.append(payload)

        cr = {
            "result": "approved",
            "agreement_ratio": 0.9,
            "findings": [],
            "conditions": [],
            "evidence_items_checked": 1,
            "eval_id": eval_id,
        }
        with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
             patch("_bus.emit_event", side_effect=_capture):
            post_tool._write_reviewer_report(phase_dir, "approved", cr, eval_id)

        return captured

    def test_append_path_raw_payload_equals_yaml_block_not_full_file(self) -> None:
        """append branch: raw_payload must equal yaml_block (just the section),
        NOT the full cumulative file.  Per-section payload contract (#770).
        """
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="rp-append", phase="build")
            report_path = phase_dir / "reviewer-report.md"

            # First write — creates the file (yaml_block = full file on create).
            captured1 = self._capture_emit(phase_dir, "eval00000001")
            self.assertGreater(len(captured1), 0, "emit_event was never called (create)")
            first_yaml_block = captured1[0]["raw_payload"]

            # Second write — appends to the file (triggers append branch).
            captured2 = self._capture_emit(phase_dir, "eval00000002")
            self.assertGreater(len(captured2), 0, "emit_event was never called (append)")

            file_content = report_path.read_text(encoding="utf-8")
            append_payload = captured2[-1]
            self.assertIn("raw_payload", append_payload,
                          "append branch must emit raw_payload field")

            # raw_payload must be the yaml_block ONLY — NOT the cumulative file.
            yaml_block = append_payload["raw_payload"]
            self.assertNotEqual(
                yaml_block,
                file_content,
                "append branch raw_payload must NOT equal the full cumulative file",
            )
            # The cumulative file contains the first section + separator + second section.
            # The second section (yaml_block) must appear at the END of the file.
            self.assertTrue(
                file_content.endswith(yaml_block),
                "Cumulative file must end with the just-written yaml_block",
            )
            # The yaml_block must be a strict substring of the cumulative file.
            self.assertIn(
                yaml_block,
                file_content,
                "yaml_block must appear in cumulative file",
            )
            # The yaml_block must NOT include the first section's content.
            self.assertNotIn(
                first_yaml_block,
                yaml_block,
                "append branch raw_payload must not contain the first section",
            )

    def test_create_path_raw_payload_equals_file_content(self) -> None:
        """create branch: raw_payload must equal the full file content after write.

        On the create branch yaml_block IS the entire file, so create + append
        branches share "just-written content" semantics — file content and
        yaml_block are identical here.
        """
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="rp-create", phase="build")
            report_path = phase_dir / "reviewer-report.md"

            captured = self._capture_emit(phase_dir, "eval00000001")
            self.assertGreater(len(captured), 0, "emit_event was never called")

            file_content = report_path.read_text(encoding="utf-8")
            create_payload = captured[0]
            self.assertIn("raw_payload", create_payload,
                          "create branch must emit raw_payload field")
            self.assertEqual(
                create_payload["raw_payload"],
                file_content,
                "create branch: raw_payload must equal full file content (yaml_block IS the full file)",
            )

    def test_pending_path_raw_payload_equals_file_content(self) -> None:
        """gate_pending: raw_payload must equal the pending template content."""
        controlled_eval_id = "pendingeval12345"
        captured: list = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            captured.append((event_type, payload))

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="rp-pending", phase="build")
            report_path = phase_dir / "reviewer-report.md"

            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_pending_reviewer_report(phase_dir, controlled_eval_id)

            self.assertGreater(len(captured), 0, "emit_event was never called")
            pending_emits = [(et, p) for et, p in captured
                             if et == "wicked.consensus.gate_pending"]
            self.assertGreater(len(pending_emits), 0, "gate_pending was never emitted")

            file_content = report_path.read_text(encoding="utf-8")
            _, payload = pending_emits[0]
            self.assertIn("raw_payload", payload,
                          "gate_pending must emit raw_payload field")
            self.assertEqual(
                payload["raw_payload"],
                file_content,
                "raw_payload must equal pending file content",
            )


if __name__ == "__main__":
    unittest.main()
