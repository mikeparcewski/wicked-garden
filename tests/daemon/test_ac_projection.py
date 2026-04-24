#!/usr/bin/env python3
"""
Tests for daemon AC projection (v8-PR-5 #591).

Covers:
  wicked.ac.declared  → row inserted into acceptance_criteria
  wicked.ac.evidence_linked → row inserted into ac_evidence
  Idempotent replay — same event twice yields identical row state
  ac_coverage_summary — counts linked / unlinked
  FK integrity — evidence_linked for unknown AC is logged-not-raised

Run with: pytest tests/daemon/test_ac_projection.py
"""
import sqlite3
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import daemon.db as db
from daemon.projector import project_event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_conn() -> sqlite3.Connection:
    conn = db.connect(":memory:")
    db.init_schema(conn)
    return conn


def _seed_project(conn: sqlite3.Connection, project_id: str = "proj-1") -> None:
    db.upsert_project(conn, project_id, {
        "name": project_id,
        "status": "active",
        "created_at": 1_700_000_000,
        "updated_at": 1_700_000_000,
    })


def _ac_declared_event(
    project_id: str,
    ac_id: str,
    statement: str = "Test statement",
    verification: str | None = None,
    ts: int = 1_700_001_000,
) -> dict:
    return {
        "event_type": "wicked.ac.declared",
        "created_at": ts,
        "payload": {
            "project_id": project_id,
            "ac_id": ac_id,
            "statement": statement,
            "verification": verification,
        },
    }


def _ac_evidence_linked_event(
    project_id: str,
    ac_id: str,
    evidence_ref: str,
    evidence_type: str | None = None,
    ts: int = 1_700_002_000,
) -> dict:
    return {
        "event_type": "wicked.ac.evidence_linked",
        "created_at": ts,
        "payload": {
            "project_id": project_id,
            "ac_id": ac_id,
            "evidence_ref": evidence_ref,
            "evidence_type": evidence_type,
        },
    }


# ---------------------------------------------------------------------------
# wicked.ac.declared
# ---------------------------------------------------------------------------

class TestACDeclared(unittest.TestCase):

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_project(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_declared_event_inserts_row(self):
        event = _ac_declared_event("proj-1", "AC-3", "User can log in")
        status = project_event(self.conn, event)
        self.assertEqual(status, "applied")
        rows = db.list_acs(self.conn, "proj-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ac_id"], "AC-3")
        self.assertEqual(rows[0]["statement"], "User can log in")

    def test_declared_idempotent_replay(self):
        """Projecting the same event twice yields one row with same state."""
        event = _ac_declared_event("proj-1", "AC-3", "User can log in")
        project_event(self.conn, event)
        project_event(self.conn, event)
        rows = db.list_acs(self.conn, "proj-1")
        self.assertEqual(len(rows), 1)

    def test_declared_updates_statement_on_replay(self):
        """Re-emitting with a corrected statement updates the row."""
        project_event(self.conn, _ac_declared_event("proj-1", "AC-3", "Old statement"))
        project_event(self.conn, _ac_declared_event("proj-1", "AC-3", "Corrected statement"))
        rows = db.list_acs(self.conn, "proj-1")
        self.assertEqual(rows[0]["statement"], "Corrected statement")

    def test_declared_missing_project_id_is_ignored(self):
        event = {
            "event_type": "wicked.ac.declared",
            "created_at": 1_700_001_000,
            "payload": {"ac_id": "AC-3", "statement": "No project"},
        }
        status = project_event(self.conn, event)
        # Handler returns ignored (via _require logging) — projector wraps as error
        # if exception, but here it returns from handler normally → applied|ignored
        # What matters: no crash, and no AC row inserted.
        rows = db.list_acs(self.conn, "proj-1")
        self.assertEqual(len(rows), 0)

    def test_declared_missing_ac_id_is_ignored(self):
        event = {
            "event_type": "wicked.ac.declared",
            "created_at": 1_700_001_000,
            "payload": {"project_id": "proj-1", "statement": "Missing id"},
        }
        project_event(self.conn, event)
        rows = db.list_acs(self.conn, "proj-1")
        self.assertEqual(len(rows), 0)

    def test_declared_with_verification_field(self):
        event = _ac_declared_event(
            "proj-1", "AC-5", "Timeout check", verification="check_acceptance_criteria"
        )
        project_event(self.conn, event)
        rows = db.list_acs(self.conn, "proj-1")
        self.assertEqual(rows[0]["verification"], "check_acceptance_criteria")

    def test_multiple_acs_for_same_project(self):
        for i in range(1, 4):
            project_event(self.conn, _ac_declared_event("proj-1", f"AC-{i}", f"Stmt {i}"))
        rows = db.list_acs(self.conn, "proj-1")
        self.assertEqual(len(rows), 3)


# ---------------------------------------------------------------------------
# wicked.ac.evidence_linked
# ---------------------------------------------------------------------------

class TestACEvidenceLinked(unittest.TestCase):

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_project(self.conn)
        # Pre-declare AC-1 so FK constraint is satisfied
        project_event(self.conn, _ac_declared_event("proj-1", "AC-1", "User logs in"))

    def tearDown(self) -> None:
        self.conn.close()

    def test_evidence_linked_inserts_row(self):
        event = _ac_evidence_linked_event("proj-1", "AC-1", "tests/test_login.py")
        status = project_event(self.conn, event)
        self.assertEqual(status, "applied")
        evidence = db.get_ac_evidence(self.conn, "proj-1", "AC-1")
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["evidence_ref"], "tests/test_login.py")

    def test_evidence_type_inferred_for_test_path(self):
        event = _ac_evidence_linked_event("proj-1", "AC-1", "tests/test_login.py")
        project_event(self.conn, event)
        evidence = db.get_ac_evidence(self.conn, "proj-1", "AC-1")
        self.assertEqual(evidence[0]["evidence_type"], "test")

    def test_evidence_type_inferred_for_issue_ref(self):
        event = _ac_evidence_linked_event("proj-1", "AC-1", "#612")
        project_event(self.conn, event)
        evidence = db.get_ac_evidence(self.conn, "proj-1", "AC-1")
        self.assertEqual(evidence[0]["evidence_type"], "issue")

    def test_evidence_type_explicit_overrides_infer(self):
        event = _ac_evidence_linked_event("proj-1", "AC-1", "#612", evidence_type="check")
        project_event(self.conn, event)
        evidence = db.get_ac_evidence(self.conn, "proj-1", "AC-1")
        self.assertEqual(evidence[0]["evidence_type"], "check")

    def test_evidence_linked_idempotent(self):
        """Same (project_id, ac_id, evidence_ref) twice → one row."""
        event = _ac_evidence_linked_event("proj-1", "AC-1", "tests/test_login.py")
        project_event(self.conn, event)
        project_event(self.conn, event)
        evidence = db.get_ac_evidence(self.conn, "proj-1", "AC-1")
        self.assertEqual(len(evidence), 1)

    def test_evidence_for_unknown_ac_does_not_raise(self):
        """FK violation on unknown AC is caught; no crash, no evidence row."""
        event = _ac_evidence_linked_event("proj-1", "AC-999", "tests/test_missing.py")
        # Should not raise; handler logs a warning and returns
        try:
            status = project_event(self.conn, event)
        except Exception as exc:
            self.fail(f"project_event raised unexpectedly: {exc}")
        evidence = db.get_ac_evidence(self.conn, "proj-1", "AC-999")
        self.assertEqual(len(evidence), 0)

    def test_multiple_evidence_for_one_ac(self):
        for ref in ("tests/test_login.py", "#101", "check:ac_coverage"):
            project_event(self.conn, _ac_evidence_linked_event("proj-1", "AC-1", ref))
        evidence = db.get_ac_evidence(self.conn, "proj-1", "AC-1")
        self.assertEqual(len(evidence), 3)


# ---------------------------------------------------------------------------
# ac_coverage_summary
# ---------------------------------------------------------------------------

class TestACCoverageSummary(unittest.TestCase):

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_project(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_empty_project(self):
        summary = db.ac_coverage_summary(self.conn, "proj-1")
        self.assertEqual(summary, {"total": 0, "linked": 0, "unlinked": 0})

    def test_all_unlinked(self):
        for i in range(1, 4):
            project_event(self.conn, _ac_declared_event("proj-1", f"AC-{i}", f"S{i}"))
        summary = db.ac_coverage_summary(self.conn, "proj-1")
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["linked"], 0)
        self.assertEqual(summary["unlinked"], 3)

    def test_partial_linked(self):
        for i in range(1, 4):
            project_event(self.conn, _ac_declared_event("proj-1", f"AC-{i}", f"S{i}"))
        # Link only AC-1
        project_event(self.conn, _ac_evidence_linked_event("proj-1", "AC-1", "tests/t.py"))
        summary = db.ac_coverage_summary(self.conn, "proj-1")
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["linked"], 1)
        self.assertEqual(summary["unlinked"], 2)

    def test_all_linked(self):
        for i in range(1, 4):
            project_event(self.conn, _ac_declared_event("proj-1", f"AC-{i}", f"S{i}"))
            project_event(self.conn, _ac_evidence_linked_event("proj-1", f"AC-{i}", f"tests/t{i}.py"))
        summary = db.ac_coverage_summary(self.conn, "proj-1")
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["linked"], 3)
        self.assertEqual(summary["unlinked"], 0)

    def test_multiple_evidence_does_not_inflate_linked_count(self):
        """AC with 3 evidence refs counts as 1 linked, not 3."""
        project_event(self.conn, _ac_declared_event("proj-1", "AC-1", "S"))
        for ref in ("tests/a.py", "tests/b.py", "#42"):
            project_event(self.conn, _ac_evidence_linked_event("proj-1", "AC-1", ref))
        summary = db.ac_coverage_summary(self.conn, "proj-1")
        self.assertEqual(summary["linked"], 1)


if __name__ == "__main__":
    unittest.main()
