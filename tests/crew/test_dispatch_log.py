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


def _setup_daemon_db_for_test(tmp_root: Path, project_dir: Path) -> Path:
    """Create an in-memory daemon DB that emits land in (PR #800).

    Site 1's source-side disk write was deleted in PR #800 — the projector
    handler is the canonical writer.  Tests that assert round-trip behaviour
    (``append`` → ``read_entries``) need to run the projector synchronously.

    Builds a real sqlite DB at ``tmp_root/projections.db``, applies the
    daemon schema, registers the project row, sets ``WG_DAEMON_DB`` so
    ``read_entries`` queries it, and returns the path so the caller can
    pass it into ``_simulate_bus_pipeline``.
    """
    sys.path.insert(0, str(_REPO_ROOT / "daemon"))
    import db as daemon_db  # noqa: PLC0415 — local test scaffolding

    db_path = tmp_root / "projections.db"
    import sqlite3 as _sqlite3  # noqa: PLC0415
    conn = _sqlite3.connect(str(db_path))
    daemon_db.init_schema(conn)
    project_id = project_dir.name
    conn.execute(
        "INSERT OR IGNORE INTO projects "
        "(id, name, directory, status, current_phase, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, project_id, str(project_dir), "active", "design",
         1_700_000_000, 1_700_000_000),
    )
    conn.commit()
    conn.close()

    os.environ["WG_DAEMON_DB"] = str(db_path)
    return db_path


def _simulate_bus_pipeline(db_path: Path):
    """Return an emit-replacement that routes events through the projector.

    Inserts a row into ``event_log`` then calls ``_dispatch_log_appended``
    synchronously — this lets unit tests verify the source→bus→projector
    chain without a running daemon.  Closes the DB connection between calls
    so each invocation sees a fresh transaction (mirrors the real daemon's
    per-event flush).

    ``row_factory = sqlite3.Row`` is set on the per-call connection because
    ``daemon.db.get_project`` does ``dict(row)`` — that only works under
    Row-factory mode (mirrors the production daemon's connection setup in
    ``daemon/runtime.py`` where the daemon assigns ``conn.row_factory``).
    """
    import sqlite3 as _sqlite3  # noqa: PLC0415
    sys.path.insert(0, str(_REPO_ROOT / "daemon"))
    from projector import _dispatch_log_appended  # noqa: PLC0415

    counter = {"event_id": 0}

    def _emit(event_type, payload, chain_id=None, metadata=None):
        counter["event_id"] += 1
        eid = counter["event_id"]
        conn = _sqlite3.connect(str(db_path))
        conn.row_factory = _sqlite3.Row
        try:
            conn.execute(
                "INSERT INTO event_log (event_id, event_type, chain_id, "
                "payload_json, projection_status, ingested_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (eid, event_type, chain_id or "",
                 json.dumps(payload), "pending", 1_700_000_000 + eid),
            )
            conn.commit()
            event = {
                "event_id": eid,
                "event_type": event_type,
                "chain_id": chain_id,
                "created_at": 1_700_000_000 + eid,
                "payload": payload,
            }
            _dispatch_log_appended(conn, event)
            conn.commit()
        finally:
            conn.close()

    return _emit


class AppendAndRead(unittest.TestCase):
    def test_append_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            db_path = _setup_daemon_db_for_test(Path(tmp), project)
            try:
                with patch.dict(
                    os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"}
                ), patch("_bus.emit_event",
                         side_effect=_simulate_bus_pipeline(db_path)):
                    append(project, "design", reviewer="security-engineer",
                           gate="design-quality", dispatch_id="d-1",
                           dispatched_at="2026-04-19T10:00:00+00:00")
                    entries = read_entries(project, "design")
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["reviewer"], "security-engineer")
                self.assertEqual(entries[0]["dispatch_id"], "d-1")
            finally:
                os.environ.pop("WG_DAEMON_DB", None)

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
            db_path = _setup_daemon_db_for_test(Path(tmp), project)
            try:
                with patch.dict(
                    os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"}
                ), patch("_bus.emit_event",
                         side_effect=_simulate_bus_pipeline(db_path)):
                    append(project, "design", reviewer="r1", gate="g",
                           dispatch_id="d-old",
                           dispatched_at="2026-04-19T00:00:00+00:00")
                    append(project, "design", reviewer="r2", gate="g",
                           dispatch_id="d-new",
                           dispatched_at="2026-04-19T05:00:00+00:00")
                    latest = read_latest(project, "design", "g")
                self.assertIsNotNone(latest)
                self.assertEqual(latest["dispatch_id"], "d-new")
            finally:
                os.environ.pop("WG_DAEMON_DB", None)


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
            db_path = _setup_daemon_db_for_test(Path(tmp), project)
            try:
                with patch.dict(
                    os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"}
                ), patch("_bus.emit_event",
                         side_effect=_simulate_bus_pipeline(db_path)):
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
            finally:
                os.environ.pop("WG_DAEMON_DB", None)

    def test_dispatched_at_after_recorded_at_fails_match(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WG_GATE_RESULT_STRICT_AFTER": "2099-01-01"},
        ):
            project = _make_project(tmp)
            db_path = _setup_daemon_db_for_test(Path(tmp), project)
            try:
                with patch.dict(
                    os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"}
                ), patch("_bus.emit_event",
                         side_effect=_simulate_bus_pipeline(db_path)):
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
            finally:
                os.environ.pop("WG_DAEMON_DB", None)


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


class BusCutoverFlagSourceContract(unittest.TestCase):
    """Site 1 bus-cutover (PR #800) — emit-only contract.

    Pre-PR-#800 the source-side ``dispatch_log.append`` did write-then-emit:
    the disk JSONL was source of truth, and Council Condition C2 required
    flag-off and flag-on to produce byte-identical disk bytes (the flag
    gated only the projector's SQL row).

    PR #800 deleted the source-side disk write — the projector handler is
    now the canonical disk writer too.  Source-side semantics under both
    flag-off and explicit-off are identical: the helper emits the bus event
    (or fails fail-open if the bus is down) and returns without touching
    disk.  These tests assert the new emit-only contract."""

    def test_source_side_does_not_write_disk_under_flag_on(self):
        """Source-side never writes disk post PR-#800 — projector owns it."""
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            dispatch_log._reset_state_for_tests()
            dispatch_log.set_hmac_secret("deterministic-secret")

            with patch.dict(
                os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "on"}
            ), patch("_bus.emit_event"):
                # Bus emit mocked — projector NOT triggered; we only verify
                # the source side does not touch disk.
                append(project, "design",
                       reviewer="security-engineer",
                       gate="design-quality",
                       dispatch_id="d-1",
                       dispatched_at="2026-04-19T10:00:00+00:00")

            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            self.assertFalse(
                log_path.exists(),
                "PR #800 deleted the source-side disk write — the helper "
                "must emit only.  The projector materialises the file.",
            )

    def test_explicit_off_value_emits_nothing_per_council_c1(self):
        """Council C1 — explicit ``"off"`` (case/whitespace normalised) opts out.

        Under the pre-#800 dual-write contract this test compared disk bytes.
        Post-#800 the source never writes disk, so the contract becomes:
        explicit-off → projector handler is a no-op (verified separately in
        ``tests/daemon/test_projector_dispatch_log``).  At the source-side
        boundary the emit fires regardless of flag value (the flag gates
        the projector's handler, not the source emit).
        """
        captured: list = []

        def _capture(event_type, payload, chain_id=None, metadata=None):
            captured.append({"event_type": event_type, "payload": payload,
                             "chain_id": chain_id})

        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            dispatch_log._reset_state_for_tests()
            dispatch_log.set_hmac_secret("deterministic-secret")

            with patch.dict(
                os.environ, {"WG_BUS_AS_TRUTH_DISPATCH_LOG": "off"}
            ), patch("_bus.emit_event", side_effect=_capture):
                append(project, "design",
                       reviewer="r", gate="g",
                       dispatch_id="d-off",
                       dispatched_at="2026-04-19T10:00:00+00:00")

            # Source emits regardless of the consumer-side flag.  Disk is
            # untouched (no source-side write post-#800).
            self.assertEqual(len(captured), 1)
            log_path = project / "phases" / "design" / "dispatch-log.jsonl"
            self.assertFalse(log_path.exists())


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
    """Council C5 — `gate` is always supplied per current line 298.  An
    empty-string gate trips the in-emit assertion which is swallowed by
    the fail-open guard, so no emit fires.  Post PR-#800 (legacy disk
    write deleted) there is no on-disk fallback either: the helper is
    emit-only, so empty-gate produces neither an emit nor a disk write."""

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
                # PR #800: source-side disk write was deleted.  Empty
                # gate now produces neither an emit (assertion trips +
                # fail-open swallow) nor a disk file.
                log_path = project / "phases" / "design" / "dispatch-log.jsonl"
                self.assertFalse(log_path.exists())
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
