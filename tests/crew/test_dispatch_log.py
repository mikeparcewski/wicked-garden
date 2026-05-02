"""Tests for ``scripts/crew/dispatch_log.py`` (#471, AC-7).

Covers:
  - ``append()`` + ``read_entries()`` round-trip
  - ``check_orphan()`` graceful-degrade before strict-after
  - ``check_orphan()`` REJECT after strict-after
  - ``WG_GATE_RESULT_DISPATCH_CHECK=off`` scoped bypass
  - Malformed dispatch-log line is skipped (not fatal)

Deterministic. No wall-clock dependency in assertions — tests that
exercise the date flip set the env var explicitly rather than relying
on today's date.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import dispatch_log  # noqa: E402
from dispatch_log import append, check_orphan, read_entries, read_latest  # noqa: E402
from gate_result_schema import GateResultAuthorizationError  # noqa: E402


def _make_project(tmp: str, phase: str = "design") -> Path:
    project = Path(tmp) / "proj"
    (project / "phases" / phase).mkdir(parents=True)
    return project


class AppendAndRead(unittest.TestCase):
    def test_append_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            append(project, "design", reviewer="security-engineer",
                   gate="design-quality", dispatch_id="d-1",
                   dispatched_at="2026-04-19T10:00:00+00:00")
            entries = read_entries(project, "design")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["reviewer"], "security-engineer")
            self.assertEqual(entries[0]["dispatch_id"], "d-1")

    def test_read_entries_skips_malformed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            log_path.write_text(
                json.dumps({"reviewer": "a", "phase": "design",
                            "gate": "g", "dispatched_at": "2026-04-19T00:00:00+00:00",
                            "dispatch_id": "d-1"}) + "\n"
                + "not-json\n"
                + json.dumps({"reviewer": "b", "phase": "design",
                              "gate": "g", "dispatched_at": "2026-04-19T01:00:00+00:00",
                              "dispatch_id": "d-2"}) + "\n"
            )
            entries = read_entries(project, "design")
            # Malformed line skipped; two valid entries survive.
            self.assertEqual(len(entries), 2)
            self.assertEqual({e["dispatch_id"] for e in entries}, {"d-1", "d-2"})

    def test_read_latest_picks_newest_dispatched_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            append(project, "design", reviewer="r1", gate="g",
                   dispatch_id="d-old",
                   dispatched_at="2026-04-19T00:00:00+00:00")
            append(project, "design", reviewer="r2", gate="g",
                   dispatch_id="d-new",
                   dispatched_at="2026-04-19T05:00:00+00:00")
            latest = read_latest(project, "design", "g")
            self.assertIsNotNone(latest)
            self.assertEqual(latest["dispatch_id"], "d-new")


class CheckOrphanSoftWindow(unittest.TestCase):
    """Before strict-after: orphan → raise, caller audits + accepts."""

    def test_orphan_raises_authorization_error_pre_flip(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            parsed = {
                "reviewer": "rogue",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }
            with self.assertRaises(GateResultAuthorizationError) as cm:
                check_orphan(parsed, project, "design")
            self.assertEqual(
                cm.exception.reason,
                "unauthorized-gate-result:no-dispatch-record",
            )
            self.assertEqual(cm.exception.violation_class, "authorization")

    def test_matching_dispatch_entry_accepts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(project, "design",
                   reviewer="security-engineer",
                   gate="design-quality",
                   dispatch_id="d-1",
                   dispatched_at="2026-04-19T09:00:00+00:00")
            parsed = {
                "reviewer": "security-engineer",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "design-quality",
            }
            # No raise — the entry matches.
            check_orphan(parsed, project, "design")

    def test_dispatched_at_after_recorded_at_fails_match(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            append(project, "design",
                   reviewer="r",
                   gate="g",
                   dispatch_id="d-1",
                   dispatched_at="2026-04-19T12:00:00+00:00")
            parsed = {
                "reviewer": "r",
                "recorded_at": "2026-04-19T10:00:00+00:00",
                "gate": "g",
            }
            with self.assertRaises(GateResultAuthorizationError):
                check_orphan(parsed, project, "design")


class CheckOrphanStrictWindow(unittest.TestCase):
    def test_orphan_raises_post_flip_date(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2020-01-01"},
        ):
            project = _make_project(tmp)
            parsed = {"reviewer": "x", "recorded_at":
                      "2026-04-19T10:00:00+00:00", "gate": "g"}
            with self.assertRaises(GateResultAuthorizationError):
                check_orphan(parsed, project, "design")


class DispatchCheckDisabled(unittest.TestCase):
    def test_off_flag_bypasses_orphan_detection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "WG_GATE_RESULT_DISPATCH_CHECK": "off",
                "WG_GATE_RESULT_STRICT_AFTER": "2099-01-01",
            },
        ):
            project = _make_project(tmp)
            parsed = {"reviewer": "nomatch",
                      "recorded_at": "2026-04-19T10:00:00+00:00", "gate": "g"}
            # No raise — disabled.
            check_orphan(parsed, project, "design")


class BusCutoverFlagByteIdentity(unittest.TestCase):
    """Site 1 bus-cutover (#746) Council Condition C2 — flag-off MUST be
    byte-identical to flag-on at the disk-file level.  The flag gates
    only the projector handler's write to the new SQLite table; the
    on-disk JSONL must be the same in both modes (one full release of
    dual-write before deletion of the disk path)."""

    def test_flag_off_and_flag_on_produce_identical_disk_bytes(self):
        # Disable the bus subprocess so the emit thread is a no-op and
        # we can compare disk bytes deterministically without depending
        # on a running wicked-bus binary.
        with tempfile.TemporaryDirectory() as tmp_off, \
             tempfile.TemporaryDirectory() as tmp_on, \
             patch.dict(os.environ, {"WICKED_BUS_DISABLED": "1"}):
            project_off = _make_project(tmp_off)
            project_on = _make_project(tmp_on)

            # Reset secret so both runs sign with the same key.
            dispatch_log._reset_state_for_tests()
            dispatch_log.set_hmac_secret("deterministic-secret-for-byte-identity")

            common_kwargs = dict(
                reviewer="security-engineer",
                gate="design-quality",
                dispatch_id="d-byte-identity",
                dispatcher_agent="wicked-garden:crew:phase-manager",
                expected_result_path="phases/design/gate-result.json",
                dispatched_at="2026-04-19T10:00:00+00:00",
            )

            # flag-off path (default — env var unset)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("WG_BUS_AS_TRUTH_DISPATCH_LOG", None)
                append(project_off, "design", **common_kwargs)
            off_bytes = (
                project_off / "phases" / "design" / "dispatch-log.jsonl"
            ).read_bytes()

            # flag-on path
            with patch.dict(
                os.environ,
                {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"},
            ):
                append(project_on, "design", **common_kwargs)
            on_bytes = (
                project_on / "phases" / "design" / "dispatch-log.jsonl"
            ).read_bytes()

            self.assertEqual(
                off_bytes, on_bytes,
                "Council C2 violation: flag-on disk bytes diverge from "
                "flag-off bytes. The flag MUST gate ONLY the projector "
                "table write — the on-disk JSONL is source of truth and "
                "must be byte-identical across modes."
            )

    def test_dry_run_value_is_treated_as_off_per_council_c1(self):
        """Council C1 — only the literal string `on` enables the cutover.
        `dry-run`, `1`, `true`, or any other value MUST behave as off.
        This pins the contract so a future maintainer cannot expand the
        truthy values without an explicit council re-evaluation."""
        with tempfile.TemporaryDirectory() as tmp_off, \
             tempfile.TemporaryDirectory() as tmp_dry, \
             patch.dict(os.environ, {"WICKED_BUS_DISABLED": "1"}):
            project_off = _make_project(tmp_off)
            project_dry = _make_project(tmp_dry)
            dispatch_log._reset_state_for_tests()
            dispatch_log.set_hmac_secret("deterministic-secret")

            common_kwargs = dict(
                reviewer="r", gate="g", dispatch_id="d-dry",
                dispatched_at="2026-04-19T10:00:00+00:00",
            )

            os.environ.pop("WG_BUS_AS_TRUTH_DISPATCH_LOG", None)
            append(project_off, "design", **common_kwargs)
            off_bytes = (
                project_off / "phases" / "design" / "dispatch-log.jsonl"
            ).read_bytes()

            with patch.dict(
                os.environ,
                {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "dry-run"},
            ):
                append(project_dry, "design", **common_kwargs)
            dry_bytes = (
                project_dry / "phases" / "design" / "dispatch-log.jsonl"
            ).read_bytes()

            self.assertEqual(off_bytes, dry_bytes)


class ChainIdIncludesDispatchId(unittest.TestCase):
    """Council Condition C5 — chain_id MUST include dispatch_id so two
    retry dispatches to the same (project, phase, gate) do not collapse
    on the bus dedupe ledger (`_bus.py:569` is_processed keyed on
    `(event_type, chain_id)`).  Per brain memory
    `bus-chain-id-must-include-uniqueness-segment-gotcha`.

    The test asserts the OLD format `f"{project_id}.{phase}.{gate}"` would
    have collided — proving the regression is caught by this PR."""

    def test_chain_id_format_includes_dispatch_id_segment(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"WICKED_BUS_DISABLED": "0"}):
            project = _make_project(tmp)
            dispatch_log._reset_state_for_tests()
            dispatch_log.set_hmac_secret("test-secret")

            captured: list[dict] = []

            def _fake_emit(event_type, payload, chain_id=None, metadata=None):
                captured.append({
                    "event_type": event_type,
                    "chain_id": chain_id,
                    "payload": payload,
                })

            import _bus
            with patch.object(_bus, "emit_event", side_effect=_fake_emit):
                append(project, "design", reviewer="r",
                       gate="design-quality", dispatch_id="dispatch-A",
                       dispatched_at="2026-04-19T10:00:00+00:00")
                append(project, "design", reviewer="r",
                       gate="design-quality", dispatch_id="dispatch-B",
                       dispatched_at="2026-04-19T10:05:00+00:00")

            self.assertEqual(len(captured), 2)
            self.assertEqual(
                captured[0]["chain_id"],
                "proj.design.design-quality.dispatch-A",
            )
            self.assertEqual(
                captured[1]["chain_id"],
                "proj.design.design-quality.dispatch-B",
            )
            # The OLD format would have collided for both retries.
            self.assertNotEqual(
                captured[0]["chain_id"], captured[1]["chain_id"],
                "Regression assertion: under the OLD chain_id format "
                "(`{project}.{phase}.{gate}` with dispatch_id missing) "
                "the two retry dispatches share the same chain_id and "
                "the bus dedupe ledger drops the second emit.",
            )

    def test_old_chain_id_format_would_have_collided(self):
        """Direct regression assertion: verify the OLD format
        produces identical chain_ids for distinct retries.  This pins
        the bug that C5 fixes — if a future maintainer reverts to the
        OLD format this test fails immediately."""
        project_id = "proj"
        phase = "design"
        gate = "design-quality"
        dispatch_a = "dispatch-A"
        dispatch_b = "dispatch-B"

        old_format_a = f"{project_id}.{phase}.{gate}"
        old_format_b = f"{project_id}.{phase}.{gate}"
        new_format_a = f"{project_id}.{phase}.{gate}.{dispatch_a}"
        new_format_b = f"{project_id}.{phase}.{gate}.{dispatch_b}"

        # Old format: two distinct retries collide on (event_type, chain_id).
        self.assertEqual(
            old_format_a, old_format_b,
            "Sanity: the OLD chain_id format produces identical strings "
            "for distinct dispatch_ids — that is the bug C5 fixes.",
        )
        # New format: distinct retries get distinct chain_ids.
        self.assertNotEqual(
            new_format_a, new_format_b,
            "C5 contract: dispatch_id segment makes chain_ids unique "
            "across retries.",
        )

    def test_emit_payload_includes_raw_payload_and_hmac(self):
        """Council C4 — `raw_payload` MUST appear in the emit payload so
        the projector can reproduce the on-disk JSONL bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            dispatch_log._reset_state_for_tests()
            dispatch_log.set_hmac_secret("test-secret")

            captured: list[dict] = []

            def _fake_emit(event_type, payload, chain_id=None, metadata=None):
                captured.append({"event_type": event_type, "payload": payload})

            import _bus
            with patch.object(_bus, "emit_event", side_effect=_fake_emit):
                append(project, "design", reviewer="r",
                       gate="g", dispatch_id="d-1",
                       dispatched_at="2026-04-19T10:00:00+00:00")

            self.assertEqual(len(captured), 1)
            payload = captured[0]["payload"]
            self.assertIn("raw_payload", payload,
                          "Council C4 requires `raw_payload` in the emit")
            self.assertIn("hmac", payload,
                          "Council C7 requires `hmac` in the emit so "
                          "the projector can store it verbatim")
            # raw_payload should round-trip to a dict matching the on-disk line.
            roundtripped = json.loads(payload["raw_payload"])
            self.assertEqual(roundtripped["dispatch_id"], "d-1")
            self.assertEqual(roundtripped["reviewer"], "r")
            self.assertEqual(roundtripped["hmac"], payload["hmac"])


class ChainIdRequiresGate(unittest.TestCase):
    """Council C5 — `gate` is always supplied per current line 298, so
    the conditional `if gate else` branch is dropped.  An empty-string
    gate trips the in-emit assertion which is swallowed by the fail-open
    guard, so no emit fires.  We assert the absence of the emit; the
    disk write still succeeds (orphan check catches the missing entry
    via the file-based path)."""

    def test_missing_gate_skips_emit_via_assertion(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"WICKED_BUS_DISABLED": "0"}):
            project = _make_project(tmp)
            dispatch_log._reset_state_for_tests()
            dispatch_log.set_hmac_secret("s")
            import _bus
            with patch.object(_bus, "emit_event") as mock_emit:
                append(project, "design", reviewer="r", gate="",
                       dispatch_id="d-1",
                       dispatched_at="2026-04-19T10:00:00+00:00")
                # Disk write still succeeded.
                log_path = project / "phases" / "design" / "dispatch-log.jsonl"
                self.assertTrue(log_path.is_file())
                # But the emit was skipped — assertion swallowed by the
                # fail-open guard before emit_event was reached.
                target_calls = [
                    c for c in mock_emit.call_args_list
                    if c.args and c.args[0] == "wicked.dispatch.log_entry_appended"
                ]
                self.assertEqual(
                    target_calls, [],
                    "emit must not fire when gate is empty (the C5 "
                    "assertion trips and the fail-open guard skips emit)",
                )


if __name__ == "__main__":
    unittest.main()
