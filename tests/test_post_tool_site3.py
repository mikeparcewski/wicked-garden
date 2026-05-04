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

    def test_pending_report_does_not_write_disk_directly(self) -> None:
        """Site 3 emit-only contract (PR #799).

        Pre-PR-#799 the source-side helper wrote the file synchronously even
        when the bus flag was off.  After legacy direct-write deletion the
        helper is emit-only — the projector handler ``_consensus_gate_pending``
        materialises the file from the bus event.  This test asserts the new
        contract: the source NEVER touches disk; absence of the file when
        the daemon is not running is the correct behaviour.
        """
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="proj2", phase="review")

            # Patch _bus.emit_event so the helper does NOT need a running bus.
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "off"}), \
                 patch("_bus.emit_event"):
                post_tool._write_pending_reviewer_report(phase_dir, "any-eval-id")

            report_path = phase_dir / "reviewer-report.md"
            self.assertFalse(
                report_path.exists(),
                "PR #799 deleted the source-side disk write; the helper must "
                "NOT touch disk — the projector materialises the file from "
                "the bus event.",
            )


# ---------------------------------------------------------------------------
# 3. Write-then-emit invariant
# ---------------------------------------------------------------------------

class TestEmitOnlyContract(unittest.TestCase):
    """Site 3 emit-only contract (PR #799).

    Pre-PR-#799 the source-side helpers did write-then-emit: the file
    must exist on disk when the bus emit fires (Sites 1+2 invariant).
    PR #799 deleted the source-side disk writes — the projector handler
    ``_consensus_gate_completed`` is now the canonical writer AND owns
    the create-vs-append branch decision (it reads disk state at
    projection time, eliminating the source/projector race).

    The new contract: source-side helpers emit ONLY.  The file appears
    when the daemon's projector materialises it from the bus event.
    These tests assert that contract directly.
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

    def test_create_call_emits_without_writing_disk(self) -> None:
        """First call to _write_reviewer_report emits but does not write disk."""
        emits: List[dict] = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            emits.append({"event_type": event_type, "payload": payload})

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="projA", phase="build")
            report_path = phase_dir / "reviewer-report.md"

            cr = self._build_mock_consensus_result("aaaa0000bbbb1111")
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_reviewer_report(
                    phase_dir, "approved", cr, "aaaa0000bbbb1111"
                )

            self.assertFalse(
                report_path.exists(),
                "PR #799 emit-only contract: source must NOT write disk",
            )
            self.assertEqual(len(emits), 1, "expected exactly one bus emit")
            self.assertEqual(
                emits[0]["event_type"], "wicked.consensus.gate_completed"
            )

    def test_append_call_emits_without_mutating_existing_disk_file(self) -> None:
        """A pre-existing reviewer-report.md is NOT mutated by the source.

        The projector handles the append path now — the source emits the
        new section and returns.  Pre-PR-#799 the source rewrote the file
        in-place; that behaviour is gone.
        """
        emits: List[dict] = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            emits.append({"event_type": event_type, "payload": payload})

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="projB", phase="build")
            report_path = phase_dir / "reviewer-report.md"

            seed = "# Existing report from independent reviewer\n"
            report_path.write_text(seed, encoding="utf-8")

            cr = self._build_mock_consensus_result("cccc2222dddd3333")
            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_reviewer_report(
                    phase_dir, "conditional", cr, "cccc2222dddd3333"
                )

            # Source must NOT have touched the seeded file.
            self.assertEqual(report_path.read_text(encoding="utf-8"), seed)
            self.assertEqual(len(emits), 1, "expected exactly one bus emit")

    def test_pending_call_emits_without_writing_disk(self) -> None:
        """_write_pending_reviewer_report emits but does not write disk."""
        emits: List[dict] = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            emits.append({"event_type": event_type, "payload": payload})

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="projC", phase="design")
            report_path = phase_dir / "reviewer-report.md"

            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_pending_reviewer_report(
                    phase_dir, "eeee4444ffff5555"
                )

            self.assertFalse(
                report_path.exists(),
                "PR #799 emit-only contract: source must NOT write disk",
            )
            self.assertEqual(len(emits), 1)
            self.assertEqual(
                emits[0]["event_type"], "wicked.consensus.gate_pending"
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

    def test_consecutive_emits_carry_per_section_yaml_block_payloads(self) -> None:
        """Per-section payload contract (#770) post PR-#799 (emit-only).

        Each call to ``_write_reviewer_report`` carries its own yaml_block
        as raw_payload — the projector concatenates them into the
        cumulative file.  Verify per-section semantics without comparing
        to disk (the source never writes; the projector does).

        eval_id is in the bus payload metadata + chain_id, not in the
        yaml_block bytes (the YAML output documents the consensus result
        without the bus-level eval_id discriminator), so we verify the
        eval_id at the payload level instead.
        """
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="rp-append", phase="build")

            captured1 = self._capture_emit(phase_dir, "eval00000001")
            captured2 = self._capture_emit(phase_dir, "eval00000002")
            self.assertEqual(len(captured1), 1)
            self.assertEqual(len(captured2), 1)

            self.assertEqual(captured1[0]["eval_id"], "eval00000001")
            self.assertEqual(captured2[0]["eval_id"], "eval00000002")

            payload1 = captured1[0]["raw_payload"]
            payload2 = captured2[0]["raw_payload"]
            self.assertIsInstance(payload1, str)
            self.assertIsInstance(payload2, str)
            # Both yaml_blocks are valid, non-empty per-section bytes.
            self.assertIn("---", payload1)
            self.assertIn("---", payload2)
            self.assertIn("verdict:", payload1)
            self.assertIn("verdict:", payload2)

    def test_create_path_raw_payload_is_yaml_block_string(self) -> None:
        """create branch: raw_payload is the source-built yaml_block string."""
        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="rp-create", phase="build")

            captured = self._capture_emit(phase_dir, "eval00000001")
            self.assertEqual(len(captured), 1)

            payload = captured[0]
            self.assertIn("raw_payload", payload,
                          "create branch must emit raw_payload field")
            self.assertIsInstance(payload["raw_payload"], str)
            # raw_payload should look like a YAML frontmatter block (the
            # post_tool _build_reviewer_report_yaml output).
            self.assertIn("---", payload["raw_payload"])
            self.assertIn("verdict:", payload["raw_payload"])
            # eval_id is at the bus-payload metadata level, not embedded
            # in the YAML body.
            self.assertEqual(payload["eval_id"], "eval00000001")

    def test_pending_path_raw_payload_is_pending_template(self) -> None:
        """gate_pending: raw_payload is the pending-template string."""
        controlled_eval_id = "pendingeval12345"
        captured: list = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            captured.append((event_type, payload))

        with tempfile.TemporaryDirectory() as tmp:
            phase_dir = _make_phase_dir(Path(tmp), project="rp-pending", phase="build")

            with patch.dict(os.environ, {"WG_BUS_AS_TRUTH_REVIEWER_REPORT": "on"}), \
                 patch("_bus.emit_event", side_effect=_capture):
                post_tool._write_pending_reviewer_report(phase_dir, controlled_eval_id)

            self.assertEqual(len(captured), 1)
            event_type, payload = captured[0]
            self.assertEqual(event_type, "wicked.consensus.gate_pending")
            self.assertIn("raw_payload", payload)
            # The pending template renders into the raw_payload string.
            # Source helper substitutes _now_iso() into the template; we
            # only verify the shape (non-empty + recognisable marker), not
            # the timestamp value.
            self.assertIsInstance(payload["raw_payload"], str)
            self.assertGreater(len(payload["raw_payload"]), 20,
                               "pending template must produce non-trivial bytes")


if __name__ == "__main__":
    unittest.main()
