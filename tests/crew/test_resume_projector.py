"""Unit tests for scripts/crew/resume_projector.py (#734).

Covers:
    * build_snapshot — empty DB, missing project, fully populated
    * write_snapshot — atomic write, no temp leakage on crash
    * read_snapshot — missing / corrupt / well-formed
    * verify_snapshot — match, diverged, missing on-disk

Stdlib + unittest only; provisions a real SQLite DB matching daemon/db.py
schema rather than mocking, because mocking sqlite3 hides driver-level
bugs that the projector hits in production.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Add scripts/ (NOT scripts/crew/) so `from crew.X import` works as a
# package import. tests/crew/conftest.py applies the same setup under
# pytest; this block keeps unittest working too. Do NOT insert
# scripts/crew/ at index 0 — it shadows the crew/ package namespace and
# breaks sibling tests in the same process (see conftest docstring).
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from crew import resume_projector as rp  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _init_projector_schema(db_path: Path) -> None:
    """Create the minimal projector schema this module reads from.

    Mirrors the relevant subset of daemon/db.py — projects, phases,
    event_log, tasks. Other tables (council_*, ac_*, hook_*, etc.) are
    not read by resume_projector and are omitted to keep the fixture
    small.
    """
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE projects (
            id                  TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            workspace           TEXT,
            directory           TEXT,
            archetype           TEXT,
            complexity_score    REAL,
            rigor_tier          TEXT,
            current_phase       TEXT NOT NULL DEFAULT '',
            status              TEXT NOT NULL DEFAULT 'active',
            chain_id            TEXT,
            yolo_revoked_count  INTEGER NOT NULL DEFAULT 0,
            last_revoke_reason  TEXT,
            created_at          INTEGER NOT NULL,
            updated_at          INTEGER NOT NULL
        );
        CREATE TABLE phases (
            project_id          TEXT NOT NULL,
            phase               TEXT NOT NULL,
            state               TEXT NOT NULL DEFAULT 'pending',
            gate_score          REAL,
            gate_verdict        TEXT,
            gate_reviewer       TEXT,
            started_at          INTEGER,
            terminal_at         INTEGER,
            rework_iterations   INTEGER NOT NULL DEFAULT 0,
            updated_at          INTEGER NOT NULL,
            PRIMARY KEY (project_id, phase)
        );
        CREATE TABLE event_log (
            event_id            INTEGER PRIMARY KEY,
            event_type          TEXT NOT NULL,
            chain_id            TEXT,
            payload_json        TEXT NOT NULL,
            projection_status   TEXT NOT NULL,
            error_message       TEXT,
            ingested_at         INTEGER NOT NULL
        );
        CREATE TABLE tasks (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            subject     TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'pending',
            chain_id    TEXT,
            event_type  TEXT,
            metadata    TEXT,
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _seed_project(
    db_path: Path,
    project_id: str = "demo-proj",
    current_phase: str = "build",
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO projects
           (id, name, archetype, complexity_score, rigor_tier,
            current_phase, status, chain_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, "Demo Project", "code-repo", 7, "full",
         current_phase, "active", f"{project_id}.root", 1700000000, 1700001000),
    )
    conn.execute(
        """INSERT INTO phases
           (project_id, phase, state, gate_score, gate_verdict, gate_reviewer,
            started_at, terminal_at, rework_iterations, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, "clarify", "approved", 0.85, "APPROVE", "rev-1",
         1700000100, 1700000200, 0, 1700000200),
    )
    conn.execute(
        """INSERT INTO phases
           (project_id, phase, state, gate_score, gate_verdict, gate_reviewer,
            started_at, terminal_at, rework_iterations, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, "design", "approved", 0.78, "APPROVE", "rev-2",
         1700000300, 1700000400, 1, 1700000400),
    )
    conn.execute(
        """INSERT INTO phases
           (project_id, phase, state, updated_at)
           VALUES (?, ?, ?, ?)""",
        (project_id, current_phase, "in_progress", 1700001000),
    )
    # Two gate-decided events.
    conn.execute(
        """INSERT INTO event_log
           (event_id, event_type, chain_id, payload_json,
            projection_status, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (1, "wicked.gate.decided", f"{project_id}.clarify",
         json.dumps({"phase": "clarify", "result": "APPROVE",
                     "score": 0.85, "min_score": 0.7, "reviewer": "rev-1"}),
         "applied", 1700000200),
    )
    conn.execute(
        """INSERT INTO event_log
           (event_id, event_type, chain_id, payload_json,
            projection_status, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (2, "wicked.gate.decided", f"{project_id}.design",
         json.dumps({"phase": "design", "result": "APPROVE",
                     "score": 0.78, "min_score": 0.7, "reviewer": "rev-2"}),
         "applied", 1700000400),
    )
    # An unrelated event for a sibling project — must NOT bleed in.
    conn.execute(
        """INSERT INTO event_log
           (event_id, event_type, chain_id, payload_json,
            projection_status, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (3, "wicked.gate.decided", "other-proj.clarify",
         json.dumps({"phase": "clarify", "result": "REJECT", "score": 0.4}),
         "applied", 1700000500),
    )
    # Active task on this project + a completed task that shouldn't count.
    conn.execute(
        """INSERT INTO tasks
           (id, session_id, status, chain_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("t1", "sess-1", "in_progress", f"{project_id}.build", 1700001000, 1700001100),
    )
    conn.execute(
        """INSERT INTO tasks
           (id, session_id, status, chain_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("t2", "sess-1", "completed", f"{project_id}.clarify", 1700000100, 1700000200),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# build_snapshot
# ---------------------------------------------------------------------------

class TestBuildSnapshot(unittest.TestCase):
    def test_missing_db_returns_empty_with_unavailable_flag(self):
        snap = rp.build_snapshot("anything", db_path="/nonexistent/path/projections.db")
        self.assertEqual(snap["schema_version"], rp.SCHEMA_VERSION)
        self.assertEqual(snap["project_id"], "anything")
        self.assertFalse(snap["projector_available"])
        self.assertIsNone(snap["project"])
        self.assertEqual(snap["phases"], [])
        self.assertEqual(snap["gate_history"], [])
        self.assertEqual(snap["active_tasks_count"], 0)
        self.assertIsNone(snap["last_event"])

    def test_unknown_project_returns_empty_but_db_available(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            snap = rp.build_snapshot("ghost", db_path=str(db))
            self.assertTrue(snap["projector_available"])
            self.assertIsNone(snap["project"])
            self.assertEqual(snap["phases"], [])
            self.assertEqual(snap["gate_history"], [])

    def test_populated_project_round_trip(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            _seed_project(db, project_id="demo-proj", current_phase="build")
            snap = rp.build_snapshot("demo-proj", db_path=str(db))

            self.assertTrue(snap["projector_available"])
            self.assertEqual(snap["project"]["name"], "Demo Project")
            self.assertEqual(snap["project"]["archetype"], "code-repo")
            self.assertEqual(snap["project"]["current_phase"], "build")

            phases_by_name = {p["phase"]: p for p in snap["phases"]}
            self.assertIn("clarify", phases_by_name)
            self.assertIn("design", phases_by_name)
            self.assertIn("build", phases_by_name)
            self.assertEqual(phases_by_name["clarify"]["gate_verdict"], "APPROVE")
            self.assertEqual(phases_by_name["design"]["rework_iterations"], 1)

            self.assertEqual(len(snap["gate_history"]), 2)
            self.assertEqual(snap["gate_history"][0]["phase"], "clarify")
            self.assertEqual(snap["gate_history"][0]["verdict"], "APPROVE")
            self.assertEqual(snap["gate_history"][1]["phase"], "design")

            # Sibling project's events must not leak in.
            for entry in snap["gate_history"]:
                self.assertTrue(entry["chain_id"].startswith("demo-proj."))

            self.assertEqual(snap["active_tasks_count"], 1)  # t1, not t2
            self.assertEqual(snap["last_event"]["event_id"], 2)
            self.assertIn("dispatch_log", snap["pointers"])
            self.assertEqual(
                snap["pointers"]["dispatch_log"],
                "phases/build/dispatch-log.jsonl",
            )

    def test_underscore_in_project_id_does_not_match_unrelated(self):
        """LIKE wildcard escape regression: ``test_proj`` MUST NOT match ``testxproj``.

        SQLite ``LIKE`` treats ``_`` as a single-character wildcard, so an
        unescaped ``test_proj.%`` would match ``testxproj.clarify``. This
        test seeds two sibling projects whose ids differ only by the
        underscore being literal vs. a wildcard match, and verifies the
        snapshot for ``test_proj`` does not see ``testxproj``'s events.
        """
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            conn = sqlite3.connect(str(db))
            # Real project: literal underscore.
            conn.execute(
                """INSERT INTO projects (id, name, current_phase, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                ("test_proj", "Underscore Project", "build", 1, 1),
            )
            # Sibling that LIKE wildcards would falsely match without ESCAPE.
            conn.execute(
                """INSERT INTO projects (id, name, current_phase, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                ("testxproj", "Wildcard Confusion", "design", 2, 2),
            )
            # An event on the SIBLING — must not bleed into test_proj's snapshot.
            conn.execute(
                """INSERT INTO event_log
                   (event_id, event_type, chain_id, payload_json,
                    projection_status, ingested_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (1, "wicked.gate.decided", "testxproj.clarify",
                 json.dumps({"phase": "clarify", "result": "REJECT"}),
                 "applied", 1700000100),
            )
            # Active task on the SIBLING.
            conn.execute(
                """INSERT INTO tasks (id, session_id, status, chain_id,
                                       created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("t-bleed", "s", "in_progress", "testxproj.build", 1, 1),
            )
            conn.commit()
            conn.close()

            snap = rp.build_snapshot("test_proj", db_path=str(db))
            self.assertEqual(
                snap["gate_history"], [],
                "LIKE wildcard escape failed: sibling project's events bled in",
            )
            self.assertEqual(
                snap["active_tasks_count"], 0,
                "LIKE wildcard escape failed: sibling project's tasks bled in",
            )
            self.assertIsNone(
                snap["last_event"],
                "LIKE wildcard escape failed: sibling project's events bled in",
            )

    def test_pointers_skip_phase_template_when_no_current_phase(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            # Seed project with empty current_phase.
            conn = sqlite3.connect(str(db))
            conn.execute(
                """INSERT INTO projects
                   (id, name, current_phase, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                ("nophase", "No Phase", "", 1, 1),
            )
            conn.commit()
            conn.close()
            snap = rp.build_snapshot("nophase", db_path=str(db))
            self.assertIn("process_plan", snap["pointers"])  # always present
            self.assertNotIn("dispatch_log", snap["pointers"])  # phase-templated, skipped


# ---------------------------------------------------------------------------
# write_snapshot + read_snapshot
# ---------------------------------------------------------------------------

class TestWriteAndRead(unittest.TestCase):
    def test_atomic_write_and_round_trip(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            _seed_project(db)
            project_dir = Path(tmp) / "projects" / "demo-proj"
            written = rp.write_snapshot("demo-proj", project_dir, db_path=str(db))
            self.assertTrue(written.is_file())
            self.assertEqual(written.name, "resume.json")

            loaded = rp.read_snapshot(project_dir)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["project_id"], "demo-proj")
            self.assertEqual(loaded["active_tasks_count"], 1)

            # No leftover temp files in the project dir.
            leftover = [p.name for p in project_dir.iterdir()
                        if p.name.startswith(".resume.json.")]
            self.assertEqual(leftover, [], f"temp leak: {leftover}")

    def test_read_snapshot_missing_returns_none(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(rp.read_snapshot(Path(tmp)))

    def test_read_snapshot_corrupt_returns_none(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "resume.json").write_text("{ not valid json", encoding="utf-8")
            self.assertIsNone(rp.read_snapshot(project_dir))


# ---------------------------------------------------------------------------
# verify_snapshot
# ---------------------------------------------------------------------------

class TestVerifySnapshot(unittest.TestCase):
    def test_verify_missing_snapshot(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            _seed_project(db)
            ok, reason = rp.verify_snapshot(
                "demo-proj", Path(tmp) / "no-snapshot-here", db_path=str(db)
            )
            self.assertFalse(ok)
            self.assertIn("no on-disk snapshot", reason)

    def test_verify_match(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            _seed_project(db)
            project_dir = Path(tmp) / "demo-proj"
            rp.write_snapshot("demo-proj", project_dir, db_path=str(db))
            ok, reason = rp.verify_snapshot("demo-proj", project_dir, db_path=str(db))
            self.assertTrue(ok, f"expected match, got: {reason!r}")
            self.assertEqual(reason, "")

    def test_verify_diverged_after_db_mutation(self):
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            _seed_project(db)
            project_dir = Path(tmp) / "demo-proj"
            rp.write_snapshot("demo-proj", project_dir, db_path=str(db))

            # Mutate the projector — adds a new gate event.
            conn = sqlite3.connect(str(db))
            conn.execute(
                """INSERT INTO event_log
                   (event_id, event_type, chain_id, payload_json,
                    projection_status, ingested_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (10, "wicked.gate.decided", "demo-proj.build",
                 json.dumps({"phase": "build", "result": "CONDITIONAL",
                             "score": 0.65, "min_score": 0.7}),
                 "applied", 1700002000),
            )
            conn.commit()
            conn.close()

            ok, reason = rp.verify_snapshot("demo-proj", project_dir, db_path=str(db))
            self.assertFalse(ok)
            self.assertIn("diverges", reason)
            self.assertIn("gate_history", reason)

    def test_verify_does_not_silently_overwrite(self):
        """Critical contract — verify must NEVER auto-rewrite on divergence."""
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "projections.db"
            _init_projector_schema(db)
            _seed_project(db)
            project_dir = Path(tmp) / "demo-proj"
            rp.write_snapshot("demo-proj", project_dir, db_path=str(db))

            original_bytes = (project_dir / "resume.json").read_bytes()

            # Mutate the projector so verify fails.
            conn = sqlite3.connect(str(db))
            conn.execute(
                """INSERT INTO event_log
                   (event_id, event_type, chain_id, payload_json,
                    projection_status, ingested_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (11, "wicked.gate.decided", "demo-proj.build",
                 json.dumps({"phase": "build", "result": "REJECT", "score": 0.2}),
                 "applied", 1700003000),
            )
            conn.commit()
            conn.close()

            ok, _ = rp.verify_snapshot("demo-proj", project_dir, db_path=str(db))
            self.assertFalse(ok)
            # On-disk MUST be unchanged.
            self.assertEqual(
                (project_dir / "resume.json").read_bytes(),
                original_bytes,
                "verify_snapshot silently rewrote on-disk — contract violation",
            )


if __name__ == "__main__":
    unittest.main()
