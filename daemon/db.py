"""SQLite schema, connection management, and per-table CRUD for the v8 projection daemon."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase state machine import (v8-PR-3 #590).
# The scripts/crew directory is not on sys.path by default when daemon/db.py
# is imported standalone (e.g. from tests).  Add it if needed so that
# phase_state can be resolved without requiring callers to set PYTHONPATH.
# ---------------------------------------------------------------------------
_SCRIPTS_CREW = Path(__file__).resolve().parents[1] / "scripts" / "crew"
if str(_SCRIPTS_CREW) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_CREW))

_DEFAULT_DB_PATH = Path.home() / ".something-wicked" / "wicked-garden-daemon" / "projections.db"
_ENV_DB_KEY = "WG_DAEMON_DB"

_BUS_SOURCE_DEFAULT = "wicked-bus"
_STATUS_ACTIVE = "active"
_PRUNE_KEEP_DEFAULT = 10_000

_PROJECTION_STATUS_APPLIED = "applied"
_PROJECTION_STATUS_IGNORED = "ignored"
_PROJECTION_STATUS_ERROR = "error"


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open the projections DB; set WAL mode and foreign keys. Caller is responsible for closing."""
    resolved = path or os.environ.get(_ENV_DB_KEY) or str(_DEFAULT_DB_PATH)
    db_path = Path(resolved)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes idempotently; safe to call on every startup.

    Also runs the phase-state migration (v8-PR-3 #590) exactly once via the
    _migrations table, mapping any legacy ``completed`` rows to ``approved``
    (AC-linked evidence present) or ``skipped`` (no evidence).

    Council tables (v8-PR-4 #594) are projection-exception: POST /council
    originates data rather than projecting from bus events.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
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

        CREATE INDEX IF NOT EXISTS idx_projects_status
            ON projects(status);

        CREATE INDEX IF NOT EXISTS idx_projects_updated
            ON projects(updated_at DESC);

        CREATE TABLE IF NOT EXISTS phases (
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
            PRIMARY KEY (project_id, phase),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_phases_project
            ON phases(project_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS cursor (
            bus_source      TEXT PRIMARY KEY,
            cursor_id       TEXT NOT NULL,
            last_event_id   INTEGER NOT NULL DEFAULT 0,
            acked_at        INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS event_log (
            event_id            INTEGER PRIMARY KEY,
            event_type          TEXT NOT NULL,
            chain_id            TEXT,
            payload_json        TEXT NOT NULL,
            projection_status   TEXT NOT NULL,
            error_message       TEXT,
            ingested_at         INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_event_log_type
            ON event_log(event_type, event_id DESC);

        -- Site 1 of bus-cutover (#746): projection target for
        -- wicked.dispatch.log_entry_appended events.  Written by
        -- daemon/projector.py::_dispatch_log_appended ONLY when
        -- WG_BUS_AS_TRUTH_DISPATCH_LOG=on; otherwise the handler is a
        -- registered no-op that returns _APPLIED (event projected, table
        -- untouched).  Disk file at phases/{phase}/dispatch-log.jsonl
        -- remains the source of truth during dual-write — see
        -- docs/v9/bus-cutover-staging-plan.md.
        --
        -- dispatched_at note: stored as INTEGER epoch seconds even though
        -- the event payload carries an ISO-8601 string.  The handler
        -- normalises the string at insertion time so range queries
        -- (`WHERE dispatched_at BETWEEN ...`) avoid ISO comparison gymnastics.
        --
        -- FK + ON DELETE CASCADE (#754): event_id REFERENCES event_log so
        -- retention/cleanup workflows that prune event_log rows do not leak
        -- orphan projection rows.  PRAGMA foreign_keys=ON is set in connect()
        -- (every connection); without it SQLite parses but does not enforce
        -- the FK.  Cutover Sites 2-5's projection tables MUST follow this
        -- pattern — staging plan §5 names FK + WARN as REQUIRED.
        --
        -- Migration note (#754): if a developer's local DB created this table
        -- before this PR landed (no FK), CREATE TABLE IF NOT EXISTS will skip
        -- and the table stays FK-less.  Detection helper:
        -- `_dispatch_log_entries_has_event_id_fk()` below; recreation only
        -- happens when the table is empty, otherwise the developer is asked
        -- to manually re-create.  No destructive auto-migration ships.
        CREATE TABLE IF NOT EXISTS dispatch_log_entries (
            event_id              INTEGER PRIMARY KEY,
            project_id            TEXT NOT NULL,
            phase                 TEXT NOT NULL,
            gate                  TEXT NOT NULL,
            reviewer              TEXT NOT NULL,
            dispatch_id           TEXT NOT NULL,
            dispatcher_agent      TEXT NOT NULL,
            expected_result_path  TEXT NOT NULL,
            dispatched_at         INTEGER NOT NULL,
            hmac                  TEXT,
            hmac_present          INTEGER NOT NULL DEFAULT 0,
            raw_payload           TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_log(event_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dispatch_log_entries_lookup
            ON dispatch_log_entries(project_id, phase, gate, dispatched_at DESC);

        -- Site 2 of bus-cutover (#746): two projection tables for the
        -- consensus emit pair.  Per Council Condition C6 these are
        -- INTENTIONALLY SEPARATE tables (not one shared schema) — the two
        -- handlers will diverge (different required-key sets, different
        -- conditional-emit semantics) so co-locating them would force a
        -- premature abstraction.
        --
        -- Both tables follow the Site 1 pattern:
        --   * INTEGER PRIMARY KEY on event_id (one row per bus event)
        --   * raw_payload TEXT NOT NULL (canonical on-disk JSON for replay)
        --   * created_at stored as INTEGER epoch seconds
        --   * FK + ON DELETE CASCADE on event_id → event_log so retention
        --     prunes do not leak orphan projection rows (#754 contract)
        --
        -- Migration helpers `_consensus_reports_has_event_id_fk()` and
        -- `_consensus_evidence_has_event_id_fk()` plus the two
        -- `_run_migration` invocations below mirror the dispatch-log
        -- pattern so a developer who somehow created these tables
        -- pre-#746 (e.g. via a partial test fixture) gets the FK
        -- backfilled when the table is empty.
        CREATE TABLE IF NOT EXISTS consensus_reports (
            event_id              INTEGER PRIMARY KEY,
            project_id            TEXT NOT NULL,
            phase                 TEXT NOT NULL,
            decision              TEXT NOT NULL,
            confidence            REAL,
            agreement_ratio       REAL,
            participants          INTEGER,
            rounds                INTEGER,
            created_at            INTEGER NOT NULL,
            raw_payload           TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_log(event_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_consensus_reports_lookup
            ON consensus_reports(project_id, phase, created_at DESC);

        CREATE TABLE IF NOT EXISTS consensus_evidence (
            event_id              INTEGER PRIMARY KEY,
            project_id            TEXT NOT NULL,
            phase                 TEXT NOT NULL,
            result                TEXT NOT NULL,
            reason                TEXT,
            consensus_confidence  REAL,
            agreement_ratio       REAL,
            participants          INTEGER,
            created_at            INTEGER NOT NULL,
            raw_payload           TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_log(event_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_consensus_evidence_lookup
            ON consensus_evidence(project_id, phase, created_at DESC);

        CREATE TABLE IF NOT EXISTS tasks (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            subject     TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'in_progress', 'completed')),
            chain_id    TEXT,
            event_type  TEXT,
            metadata    TEXT,
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_session
            ON tasks(session_id, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON tasks(status);

        CREATE INDEX IF NOT EXISTS idx_tasks_chain
            ON tasks(chain_id);

        -- Migration tracking (v8-PR-3 #590): each row records one idempotent
        -- migration that has been applied.  Re-running init_schema is a no-op
        -- once the migration row exists.
        CREATE TABLE IF NOT EXISTS _migrations (
            name        TEXT PRIMARY KEY,
            applied_at  INTEGER NOT NULL
        );

        -- Stream 1 — #594 v8-PR-4: council sessions + votes
        CREATE TABLE IF NOT EXISTS council_sessions (
            id                  TEXT PRIMARY KEY,
            topic               TEXT NOT NULL,
            question            TEXT NOT NULL,
            started_at          INTEGER NOT NULL,
            completed_at        INTEGER,
            synthesized_verdict TEXT,
            agreement_ratio     REAL,
            hitl_paused         INTEGER NOT NULL DEFAULT 0,
            hitl_rule_id        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_council_sessions_started
            ON council_sessions(started_at DESC);

        CREATE INDEX IF NOT EXISTS idx_council_sessions_verdict
            ON council_sessions(synthesized_verdict);

        CREATE INDEX IF NOT EXISTS idx_council_sessions_hitl_rule
            ON council_sessions(hitl_rule_id);

        CREATE TABLE IF NOT EXISTS council_votes (
            session_id      TEXT NOT NULL,
            model           TEXT NOT NULL,
            verdict         TEXT,
            confidence      REAL,
            rationale       TEXT,
            raw_response    TEXT,
            latency_ms      INTEGER,
            emitted_at      INTEGER NOT NULL,
            PRIMARY KEY (session_id, model),
            FOREIGN KEY (session_id) REFERENCES council_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_council_votes_session
            ON council_votes(session_id);

        -- AC structured records (v8-PR-5 #591): typed acceptance criteria rows.
        -- Projected from wicked.ac.declared bus events (read-only principle per
        -- Decision #6 — ACs are NOT mutated via HTTP; only bus events write here).
        CREATE TABLE IF NOT EXISTS acceptance_criteria (
            project_id      TEXT NOT NULL,
            ac_id           TEXT NOT NULL,
            statement       TEXT NOT NULL DEFAULT '',
            verification    TEXT,
            created_at      INTEGER NOT NULL,
            PRIMARY KEY (project_id, ac_id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_ac_project
            ON acceptance_criteria(project_id);

        -- AC evidence map (v8-PR-5 #591): each row links one evidence reference
        -- (file path, test ID, issue ref, check name) to an AC.
        -- Projected from wicked.ac.evidence_linked bus events.
        CREATE TABLE IF NOT EXISTS ac_evidence (
            project_id      TEXT NOT NULL,
            ac_id           TEXT NOT NULL,
            evidence_ref    TEXT NOT NULL,
            evidence_type   TEXT NOT NULL DEFAULT 'unknown',
            created_at      INTEGER NOT NULL,
            PRIMARY KEY (project_id, ac_id, evidence_ref),
            FOREIGN KEY (project_id, ac_id)
                REFERENCES acceptance_criteria(project_id, ac_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_ac_evidence_project_ac
            ON ac_evidence(project_id, ac_id);

        -- Test dispatch audit table (v8-PR-7 #595): each row records one
        -- wicked-testing skill dispatch attempt.
        --
        -- MUTATION CARVE-OUT from PR-1 decision #6 (daemon read-only):
        -- test dispatches are *originated* here (not projected from bus events)
        -- because the daemon decides when to fire based on phase detection.
        -- The read-only principle still applies to all projection tables.
        -- This is the third explicit write path after council (PR-4) and event
        -- ingestion (PR-2).  Documented in daemon/test_dispatch.py module
        -- docstring.
        CREATE TABLE IF NOT EXISTS test_dispatches (
            dispatch_id     TEXT PRIMARY KEY,
            session_id      TEXT NOT NULL,
            project_id      TEXT NOT NULL,
            phase           TEXT NOT NULL,
            skill           TEXT NOT NULL,
            verdict         TEXT NOT NULL,
            evidence_path   TEXT,
            latency_ms      INTEGER NOT NULL DEFAULT 0,
            emitted_at      INTEGER NOT NULL,
            notes           TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_test_dispatches_project
            ON test_dispatches(project_id, emitted_at DESC);

        CREATE INDEX IF NOT EXISTS idx_test_dispatches_phase_skill
            ON test_dispatches(project_id, phase, skill, emitted_at DESC);

        CREATE INDEX IF NOT EXISTS idx_test_dispatches_verdict
            ON test_dispatches(verdict);

        -- Hook subscription registry (v8-PR-8 #592): typed hook subscribers.
        --
        -- MUTATION CARVE-OUT from PR-1 decision #6 (daemon read-only):
        -- Subscriptions are originated by the daemon (via registration sweep at
        -- startup or direct db calls from operators).  This is the fourth explicit
        -- write path after council (PR-4), event ingestion (PR-2), and test
        -- dispatch (PR-7).  HTTP toggle (POST /subscriptions/<id>/toggle) is a
        -- bounded write exception for operator control — documented in
        -- daemon/hook_dispatch.py and docs/evidence/pr-v8-8/contract-check.md.
        -- Creation of subscriptions is NOT exposed over HTTP; only file-config
        -- or direct DB calls may register them.
        CREATE TABLE IF NOT EXISTS hook_subscriptions (
            subscription_id TEXT PRIMARY KEY,
            filter_pattern  TEXT NOT NULL,
            debounce_rule   TEXT,
            handler_path    TEXT NOT NULL,
            enabled         INTEGER NOT NULL DEFAULT 1,
            created_at      INTEGER NOT NULL,
            updated_at      INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_hook_subscriptions_filter
            ON hook_subscriptions(filter_pattern, enabled);

        -- Hook invocation audit log (v8-PR-8 #592): one row per subscriber dispatch
        -- attempt, including debounced and filtered-out outcomes.
        -- Per-invocation stdout_digest / stderr_digest are capped at 1000 chars.
        --
        -- B1 fix (#624): debounce_key stores the composite dedup key computed at
        -- dispatch time (e.g. "phase-boundary:sub-1:proj-1:build").  Debounce
        -- queries filter by this column rather than constructing a fake composite
        -- event_type value that was never stored in the original implementation.
        CREATE TABLE IF NOT EXISTS hook_invocations (
            invocation_id   TEXT PRIMARY KEY,
            subscription_id TEXT NOT NULL,
            event_id        INTEGER NOT NULL,
            event_type      TEXT NOT NULL,
            verdict         TEXT NOT NULL,
            debounce_key    TEXT,
            stdout_digest   TEXT,
            stderr_digest   TEXT,
            latency_ms      INTEGER NOT NULL,
            emitted_at      INTEGER NOT NULL,
            FOREIGN KEY (subscription_id)
                REFERENCES hook_subscriptions(subscription_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_hook_invocations_event_type
            ON hook_invocations(event_type, emitted_at DESC);

        CREATE INDEX IF NOT EXISTS idx_hook_invocations_subscription
            ON hook_invocations(subscription_id, emitted_at DESC);

        CREATE INDEX IF NOT EXISTS idx_hook_invocations_debounce_key
            ON hook_invocations(debounce_key);
    """)
    conn.commit()

    # Run one-time migrations registered above.
    _run_migration(conn, "phase_state_completed_to_canonical",
                   _migrate_phase_state_completed_to_canonical)
    # B1 fix (#624): add debounce_key column to existing hook_invocations tables
    # that were created before this column was introduced.
    _run_migration(conn, "hook_invocations_add_debounce_key",
                   _migrate_hook_invocations_add_debounce_key)
    # #754: rebuild dispatch_log_entries with FK + ON DELETE CASCADE on
    # event_id when a pre-#754 schema is detected and the table is empty.
    # Non-empty tables are left alone with a logger.warning so the developer
    # can decide how to migrate; we never silently drop projection rows.
    _run_migration(conn, "dispatch_log_entries_add_event_id_fk",
                   _migrate_dispatch_log_entries_add_event_id_fk)
    # Site 2 of bus-cutover (#746): mirror the dispatch-log FK migration for
    # the two consensus projection tables.  No pre-#746 DBs have these tables
    # today, but the migration pattern is the contract — a future developer
    # who creates the tables via a test fixture or a partial init must get
    # the FK backfilled the next time init_schema runs.
    _run_migration(conn, "consensus_reports_add_event_id_fk",
                   _migrate_consensus_reports_add_event_id_fk)
    _run_migration(conn, "consensus_evidence_add_event_id_fk",
                   _migrate_consensus_evidence_add_event_id_fk)


# ---------------------------------------------------------------------------
# Migration helpers (v8-PR-3 #590)
# ---------------------------------------------------------------------------

def _run_migration(
    conn: sqlite3.Connection,
    name: str,
    fn: "Callable[[sqlite3.Connection], None]",
) -> None:
    """Apply *fn* exactly once, guarded by a _migrations row.

    Idempotent: if the migration row already exists the function is not called.
    The row is written inside the same transaction as the migration body so
    partial migrations cannot produce a committed row without committed data.
    """
    from typing import Callable  # local import avoids circular at module level

    row = conn.execute(
        "SELECT name FROM _migrations WHERE name = ?", (name,)
    ).fetchone()
    if row is not None:
        return  # already applied
    fn(conn)
    conn.execute(
        "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
        (name, int(time.time())),
    )
    conn.commit()


def _migrate_phase_state_completed_to_canonical(conn: sqlite3.Connection) -> None:
    """Map legacy ``completed`` phase rows to canonical states.

    Mapping rule (v8-PR-3 #590):
    - gate_score IS NOT NULL or gate_verdict IS NOT NULL → ``approved``
      (AC-linked evidence present from a prior gate decision)
    - otherwise → ``skipped``
      (no gate evidence; treat as a no-gate-required skip)

    This migration targets the daemon ``phases`` table only.  The
    phase_manager.py JSON file store is unaffected.
    """
    now = int(time.time())
    rows = conn.execute(
        "SELECT project_id, phase, gate_score, gate_verdict "
        "FROM phases WHERE state = 'completed'"
    ).fetchall()
    for row in rows:
        project_id = row[0]
        phase = row[1]
        has_evidence = (row[2] is not None) or (row[3] is not None)
        new_state = "approved" if has_evidence else "skipped"
        conn.execute(
            "UPDATE phases SET state = ?, updated_at = ? "
            "WHERE project_id = ? AND phase = ? AND state = 'completed'",
            (new_state, now, project_id, phase),
        )
    # Commit is handled by _run_migration after the migration row is written.


def _migrate_hook_invocations_add_debounce_key(conn: sqlite3.Connection) -> None:
    """Add the ``debounce_key`` column to hook_invocations if it does not exist.

    B1 fix (#624): hook_invocations tables created before this migration lack
    the ``debounce_key`` column that ``append_hook_invocation`` now writes.
    ALTER TABLE ADD COLUMN is idempotent-safe via the _migrations guard.
    Existing rows get NULL for debounce_key, which is correct — they predate
    the fix and would not have had a key stored anyway.
    """
    # Only add the column when hook_invocations exists (it may not on fresh DBs
    # that went through CREATE TABLE IF NOT EXISTS with the column already present).
    cols_info = conn.execute("PRAGMA table_info(hook_invocations)").fetchall()
    col_names = {r[1] for r in cols_info}
    if "debounce_key" not in col_names:
        conn.execute("ALTER TABLE hook_invocations ADD COLUMN debounce_key TEXT")
    # Commit is handled by _run_migration after the migration row is written.


def _dispatch_log_entries_has_event_id_fk(conn: sqlite3.Connection) -> bool:
    """Return True iff dispatch_log_entries has the FK on event_id → event_log.

    SQLite reports FKs through ``PRAGMA foreign_key_list(<table>)``.  Each row
    has columns (id, seq, table, from, to, on_update, on_delete, match).  We
    look for one where ``from`` is ``event_id``, ``table`` is ``event_log``,
    and ``on_delete`` is ``CASCADE`` — the exact contract from #754.
    """
    rows = conn.execute("PRAGMA foreign_key_list(dispatch_log_entries)").fetchall()
    for r in rows:
        # Tuple form to stay row_factory-agnostic in tests.
        from_col = r["from"] if hasattr(r, "keys") else r[3]
        ref_table = r["table"] if hasattr(r, "keys") else r[2]
        on_delete = r["on_delete"] if hasattr(r, "keys") else r[6]
        if from_col == "event_id" and ref_table == "event_log" and on_delete == "CASCADE":
            return True
    return False


def _migrate_dispatch_log_entries_add_event_id_fk(conn: sqlite3.Connection) -> None:
    """Backfill the event_id FK on dispatch_log_entries for pre-#754 DBs.

    Why this exists (#754): PR #751 created ``dispatch_log_entries`` without
    an explicit FK on ``event_id``.  CREATE TABLE IF NOT EXISTS in
    ``init_schema`` will not modify a pre-existing table, so a developer who
    ran the daemon between #751 and #754 has an FK-less table that will leak
    orphan rows when ``event_log`` is pruned.

    SQLite cannot ADD a FOREIGN KEY via ALTER TABLE; the canonical fix is the
    "rename / recreate / copy / drop" dance.  We refuse to ship that as a
    silent destructive auto-migration:

      * If the table is empty → safe to DROP and recreate.  Do it.
      * If the table is non-empty → emit a `logger.warning` with the recovery
        steps and leave the table alone.  Future writes still go in; they
        just lack FK enforcement until the developer migrates manually.

    The fresh-DB path also hits this migration — the FK already exists, so
    the function is a no-op.  We use the existence check to keep the
    _migrations row idempotent across both paths.
    """
    # Skip when the table does not exist yet (defensive; init_schema runs
    # CREATE TABLE IF NOT EXISTS above so this should not happen, but a
    # partially initialised DB should not crash the migration.)
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'dispatch_log_entries'"
    ).fetchone()
    if table_exists is None:
        return

    if _dispatch_log_entries_has_event_id_fk(conn):
        return  # already migrated (fresh DB or prior run)

    row_count_row = conn.execute(
        "SELECT COUNT(*) FROM dispatch_log_entries"
    ).fetchone()
    row_count = row_count_row[0] if row_count_row else 0
    if row_count > 0:
        logger.warning(
            "daemon/db.py: dispatch_log_entries has %d row(s) and is missing "
            "the event_id → event_log FK (#754). Auto-migration skipped to "
            "avoid silent data loss. To migrate manually: BEGIN; CREATE TABLE "
            "dispatch_log_entries_new (... FOREIGN KEY (event_id) REFERENCES "
            "event_log(event_id) ON DELETE CASCADE); INSERT INTO "
            "dispatch_log_entries_new SELECT * FROM dispatch_log_entries; "
            "DROP TABLE dispatch_log_entries; ALTER TABLE "
            "dispatch_log_entries_new RENAME TO dispatch_log_entries; COMMIT;",
            row_count,
        )
        return

    # Empty table → safe to recreate with the FK in place.  Schema kept in
    # lockstep with the CREATE TABLE block above so the two paths converge.
    conn.execute("DROP TABLE dispatch_log_entries")
    conn.execute(
        """
        CREATE TABLE dispatch_log_entries (
            event_id              INTEGER PRIMARY KEY,
            project_id            TEXT NOT NULL,
            phase                 TEXT NOT NULL,
            gate                  TEXT NOT NULL,
            reviewer              TEXT NOT NULL,
            dispatch_id           TEXT NOT NULL,
            dispatcher_agent      TEXT NOT NULL,
            expected_result_path  TEXT NOT NULL,
            dispatched_at         INTEGER NOT NULL,
            hmac                  TEXT,
            hmac_present          INTEGER NOT NULL DEFAULT 0,
            raw_payload           TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_log(event_id) ON DELETE CASCADE
        )
        """
    )
    # Re-create the lookup index that init_schema declares (idempotent).
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dispatch_log_entries_lookup "
        "ON dispatch_log_entries(project_id, phase, gate, dispatched_at DESC)"
    )
    # Commit handled by _run_migration after the migration row is written.


# ---------------------------------------------------------------------------
# Site 2 of bus-cutover (#746) — FK detection + backfill for the two
# consensus projection tables.  Both helpers are direct analogues of the
# dispatch-log helper above; the duplication is deliberate per Council
# Condition C8 (DO NOT extract a base class at N=2).
# ---------------------------------------------------------------------------


def _consensus_reports_has_event_id_fk(conn: sqlite3.Connection) -> bool:
    """Return True iff consensus_reports has the FK on event_id → event_log.

    Mirrors `_dispatch_log_entries_has_event_id_fk` (#754).  The contract is
    identical: one row in PRAGMA foreign_key_list with from='event_id',
    table='event_log', on_delete='CASCADE'.
    """
    rows = conn.execute("PRAGMA foreign_key_list(consensus_reports)").fetchall()
    for r in rows:
        from_col = r["from"] if hasattr(r, "keys") else r[3]
        ref_table = r["table"] if hasattr(r, "keys") else r[2]
        on_delete = r["on_delete"] if hasattr(r, "keys") else r[6]
        if from_col == "event_id" and ref_table == "event_log" and on_delete == "CASCADE":
            return True
    return False


def _consensus_evidence_has_event_id_fk(conn: sqlite3.Connection) -> bool:
    """Return True iff consensus_evidence has the FK on event_id → event_log."""
    rows = conn.execute("PRAGMA foreign_key_list(consensus_evidence)").fetchall()
    for r in rows:
        from_col = r["from"] if hasattr(r, "keys") else r[3]
        ref_table = r["table"] if hasattr(r, "keys") else r[2]
        on_delete = r["on_delete"] if hasattr(r, "keys") else r[6]
        if from_col == "event_id" and ref_table == "event_log" and on_delete == "CASCADE":
            return True
    return False


def _migrate_consensus_reports_add_event_id_fk(conn: sqlite3.Connection) -> None:
    """Backfill the event_id FK on consensus_reports for any pre-#746 DBs.

    No production DBs have this table today (Site 2 ships it for the first
    time), but the migration pattern is the contract per Council Condition
    C6 — Sites 3-5 will add their own projection tables and inherit this
    same pattern, and a developer who creates the table via a test fixture
    today and then upgrades must NOT lose the FK.

    Same safety rule as the dispatch-log migration: empty table → recreate
    with FK; non-empty table → WARN + leave alone (no destructive
    auto-migration).
    """
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'consensus_reports'"
    ).fetchone()
    if table_exists is None:
        return

    if _consensus_reports_has_event_id_fk(conn):
        return

    row_count_row = conn.execute(
        "SELECT COUNT(*) FROM consensus_reports"
    ).fetchone()
    row_count = row_count_row[0] if row_count_row else 0
    if row_count > 0:
        logger.warning(
            "daemon/db.py: consensus_reports has %d row(s) and is missing "
            "the event_id → event_log FK (#746). Auto-migration skipped to "
            "avoid silent data loss. To migrate manually: BEGIN; CREATE TABLE "
            "consensus_reports_new (... FOREIGN KEY (event_id) REFERENCES "
            "event_log(event_id) ON DELETE CASCADE); INSERT INTO "
            "consensus_reports_new SELECT * FROM consensus_reports; "
            "DROP TABLE consensus_reports; ALTER TABLE "
            "consensus_reports_new RENAME TO consensus_reports; COMMIT;",
            row_count,
        )
        return

    conn.execute("DROP TABLE consensus_reports")
    conn.execute(
        """
        CREATE TABLE consensus_reports (
            event_id              INTEGER PRIMARY KEY,
            project_id            TEXT NOT NULL,
            phase                 TEXT NOT NULL,
            decision              TEXT NOT NULL,
            confidence            REAL,
            agreement_ratio       REAL,
            participants          INTEGER,
            rounds                INTEGER,
            created_at            INTEGER NOT NULL,
            raw_payload           TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_log(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consensus_reports_lookup "
        "ON consensus_reports(project_id, phase, created_at DESC)"
    )


def _migrate_consensus_evidence_add_event_id_fk(conn: sqlite3.Connection) -> None:
    """Backfill the event_id FK on consensus_evidence (mirror of the report
    migration above).  See `_migrate_consensus_reports_add_event_id_fk` for
    the contract — they are intentional twins per Council Condition C8 (no
    base-class extraction at N=2).
    """
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'consensus_evidence'"
    ).fetchone()
    if table_exists is None:
        return

    if _consensus_evidence_has_event_id_fk(conn):
        return

    row_count_row = conn.execute(
        "SELECT COUNT(*) FROM consensus_evidence"
    ).fetchone()
    row_count = row_count_row[0] if row_count_row else 0
    if row_count > 0:
        logger.warning(
            "daemon/db.py: consensus_evidence has %d row(s) and is missing "
            "the event_id → event_log FK (#746). Auto-migration skipped to "
            "avoid silent data loss. To migrate manually: BEGIN; CREATE TABLE "
            "consensus_evidence_new (... FOREIGN KEY (event_id) REFERENCES "
            "event_log(event_id) ON DELETE CASCADE); INSERT INTO "
            "consensus_evidence_new SELECT * FROM consensus_evidence; "
            "DROP TABLE consensus_evidence; ALTER TABLE "
            "consensus_evidence_new RENAME TO consensus_evidence; COMMIT;",
            row_count,
        )
        return

    conn.execute("DROP TABLE consensus_evidence")
    conn.execute(
        """
        CREATE TABLE consensus_evidence (
            event_id              INTEGER PRIMARY KEY,
            project_id            TEXT NOT NULL,
            phase                 TEXT NOT NULL,
            result                TEXT NOT NULL,
            reason                TEXT,
            consensus_confidence  REAL,
            agreement_ratio       REAL,
            participants          INTEGER,
            created_at            INTEGER NOT NULL,
            raw_payload           TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_log(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consensus_evidence_lookup "
        "ON consensus_evidence(project_id, phase, created_at DESC)"
    )



def upsert_project(conn: sqlite3.Connection, project_id: str, fields: dict[str, Any]) -> None:
    """Insert or update a project row; missing keys preserve existing column values."""
    now = int(time.time())
    fields = dict(fields)
    fields.setdefault("updated_at", now)

    # Columns that can be updated after creation (never overwrite id or created_at).
    mutable_cols = [
        "name", "workspace", "directory", "archetype",
        "complexity_score", "rigor_tier", "current_phase", "status",
        "chain_id", "yolo_revoked_count", "last_revoke_reason", "updated_at",
    ]

    # For a brand-new row: require name (NOT NULL in schema). INSERT OR IGNORE leaves
    # an existing row untouched; the UPDATE below then applies the supplied fields.
    if "name" in fields:
        created_at = fields.get("created_at", now)
        # Collect all supplied columns for the initial insert.
        ins_cols: list[str] = ["id", "created_at"]
        ins_vals: list[Any] = [project_id, created_at]
        for col in mutable_cols:
            if col in fields:
                ins_cols.append(col)
                ins_vals.append(fields[col])
        placeholders = ", ".join("?" for _ in ins_cols)
        conn.execute(
            f"INSERT OR IGNORE INTO projects ({', '.join(ins_cols)}) VALUES ({placeholders})",
            ins_vals,
        )

    # Apply all supplied mutable fields as an in-place update so partial calls
    # (e.g. only archetype) update the existing row without touching other columns.
    # Touch-null semantic (#589 coordination item #7): for columns that must never
    # regress to NULL when a richer value already exists, use COALESCE so that a
    # None/null payload value is silently ignored on the row.
    _PRESERVE_NONNULL = frozenset({"name", "archetype"})
    update_cols = [c for c in mutable_cols if c in fields]
    if update_cols:
        set_parts = []
        for c in update_cols:
            if c in _PRESERVE_NONNULL:
                set_parts.append(f"{c} = COALESCE(?, {c})")
            else:
                set_parts.append(f"{c} = ?")
        set_clause = ", ".join(set_parts)
        conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            [fields[c] for c in update_cols] + [project_id],
        )

    conn.commit()


def upsert_phase(
    conn: sqlite3.Connection,
    project_id: str,
    phase: str,
    fields: dict[str, Any],
) -> None:
    """Insert or update a phase row — vocabulary check only, no graph enforcement.

    SEMANTIC SPLIT (#614, epic #679 brainstorm decision D1):
    For graph-enforced UPDATEs callers should use ``transition_phase()`` from
    ``daemon._internal`` instead.  This function exists for INSERTs (creating a
    row at the target state directly from an event with no prior state to
    validate against) and for paths where graph enforcement is intentionally
    bypassed (e.g. recovery, rollback, replay, or backfill migrations).

    Behaviour
    ---------
    - Missing keys in ``fields`` preserve existing column values.
    - When ``fields`` contains a ``state`` key the value is checked against the
      canonical PhaseState **vocabulary**: banned values (``"completed"``) and
      unknown strings raise ``phase_state.InvalidTransition``.
    - The function does **not** read the current row to verify that the
      requested move is graph-legal.  ``upsert_phase(state="approved")``
      succeeds even when the current row is ``pending`` — by design, so an
      INSERT can establish any canonical target state in a single call.

    The previous docstring claimed transition-graph validation was performed
    here; that was load-bearingly inaccurate (#614 root cause) and led the
    review of v8-PR-3 to assume an enforcement guarantee that did not exist.

    Callers in ``projector.py`` use named constants from ``phase_state.PhaseState``
    so a typo or new banned value is caught at import time rather than at runtime.
    """
    from phase_state import InvalidTransition, PhaseState, BANNED_STATES  # type: ignore[import]

    now = int(time.time())
    fields = dict(fields)
    fields.setdefault("updated_at", now)

    # Validate the requested state vocabulary before touching the DB.
    # NOTE: this is a vocabulary check (banned / unknown values rejected) — it
    # is NOT a graph-path enforcement check.  See module ``daemon._internal``
    # for ``transition_phase()`` which adds graph enforcement on top.
    if "state" in fields:
        requested_state = fields["state"]
        # Reject banned states immediately (R2: no silent failures).
        if str(requested_state) in BANNED_STATES:
            raise InvalidTransition(
                f"upsert_phase: attempted to write banned state {requested_state!r} "
                f"for ({project_id!r}, {phase!r}). "
                "Run phase_state_migration.py to clean up existing rows."
            )
        # Coerce to PhaseState to catch unknown values early.
        try:
            PhaseState(str(requested_state))
        except ValueError as exc:
            raise InvalidTransition(
                f"upsert_phase: unknown state {requested_state!r} for ({project_id!r}, {phase!r}). "
                f"Valid states: {sorted(PhaseState)}"
            ) from exc

    # Columns that can be set after (project_id, phase) PK is established.
    mutable_cols = [
        "state", "gate_score", "gate_verdict", "gate_reviewer",
        "started_at", "terminal_at", "rework_iterations", "updated_at",
    ]

    # Ensure the row exists; schema defaults cover state/rework_iterations.
    ins_cols: list[str] = ["project_id", "phase"]
    ins_vals: list[Any] = [project_id, phase]
    for col in mutable_cols:
        if col in fields:
            ins_cols.append(col)
            ins_vals.append(fields[col])
    placeholders = ", ".join("?" for _ in ins_cols)
    conn.execute(
        f"INSERT OR IGNORE INTO phases ({', '.join(ins_cols)}) VALUES ({placeholders})",
        ins_vals,
    )

    # Apply supplied mutable fields to the (possibly pre-existing) row.
    update_cols = [c for c in mutable_cols if c in fields]
    if update_cols:
        set_clause = ", ".join(f"{c} = ?" for c in update_cols)
        conn.execute(
            f"UPDATE phases SET {set_clause} WHERE project_id = ? AND phase = ?",
            [fields[c] for c in update_cols] + [project_id, phase],
        )

    conn.commit()


def get_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any] | None:
    """Return a project row as a dict, or None if not found."""
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return dict(row) if row else None


def list_projects(
    conn: sqlite3.Connection,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return projects ordered by updated_at DESC; optionally filtered by status."""
    if status is not None:
        rows = conn.execute(
            "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_phases(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    """Return all phases for a project ordered by started_at NULLS LAST."""
    rows = conn.execute(
        "SELECT * FROM phases WHERE project_id = ? ORDER BY started_at ASC NULLS LAST",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_phase(
    conn: sqlite3.Connection,
    project_id: str,
    phase: str,
) -> dict[str, Any] | None:
    """Return a phase row as a dict, or None if not found.

    Used by ``daemon._internal.transition_phase`` to read the current state
    before validating a graph-legal UPDATE (#614).
    """
    row = conn.execute(
        "SELECT * FROM phases WHERE project_id = ? AND phase = ?",
        (project_id, phase),
    ).fetchone()
    return dict(row) if row else None


def get_cursor(
    conn: sqlite3.Connection,
    bus_source: str = _BUS_SOURCE_DEFAULT,
) -> dict[str, Any] | None:
    """Return the cursor row for bus_source, or None if not yet registered."""
    row = conn.execute(
        "SELECT * FROM cursor WHERE bus_source = ?", (bus_source,)
    ).fetchone()
    return dict(row) if row else None


def set_cursor(
    conn: sqlite3.Connection,
    bus_source: str,
    cursor_id: str,
    last_event_id: int,
) -> None:
    """Upsert the bus cursor; updates last_event_id and acked_at."""
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO cursor (bus_source, cursor_id, last_event_id, acked_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(bus_source) DO UPDATE SET
            cursor_id     = excluded.cursor_id,
            last_event_id = excluded.last_event_id,
            acked_at      = excluded.acked_at
        """,
        (bus_source, cursor_id, last_event_id, now),
    )
    conn.commit()


def append_event_log(
    conn: sqlite3.Connection,
    event_id: int,
    event_type: str,
    chain_id: str | None,
    payload: dict[str, Any],
    projection_status: str,
    error_message: str | None = None,
) -> None:
    """Append one event to the audit log; silently replaces on duplicate event_id."""
    now = int(time.time())
    payload_json = json.dumps(payload, separators=(",", ":"))
    conn.execute(
        """
        INSERT OR REPLACE INTO event_log
            (event_id, event_type, chain_id, payload_json, projection_status, error_message, ingested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, event_type, chain_id, payload_json, projection_status, error_message, now),
    )
    conn.commit()


def list_events(
    conn: sqlite3.Connection,
    since: int = 0,
    limit: int = 100,
    event_type_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """Return event_log rows with event_id > since, ordered by event_id ASC, LIMIT.

    Optionally filter to event_type values that start with event_type_prefix.
    Used by server.py's /events endpoint (#589, coordination item #1).
    """
    if event_type_prefix is not None:
        rows = conn.execute(
            """
            SELECT * FROM event_log
            WHERE event_id > ? AND event_type LIKE ?
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (since, event_type_prefix + "%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM event_log
            WHERE event_id > ?
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def prune_event_log(conn: sqlite3.Connection, keep_last: int = _PRUNE_KEEP_DEFAULT) -> int:
    """Delete oldest event_log rows beyond keep_last; returns the count deleted."""
    cursor = conn.execute(
        "SELECT MIN(event_id) FROM (SELECT event_id FROM event_log ORDER BY event_id DESC LIMIT ?)",
        (keep_last,),
    )
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return 0
    cutoff_id: int = row[0]
    result = conn.execute(
        "DELETE FROM event_log WHERE event_id < ?", (cutoff_id,)
    )
    conn.commit()
    return result.rowcount


# ---------------------------------------------------------------------------
# Task CRUD (Stream 1 — #596 v8-PR-2)
# ---------------------------------------------------------------------------
# Tasks are projected from bus events (wicked.task.created / .updated /
# .completed).  The daemon is READ-ONLY from the task side — Claude's native
# TaskList remains the primary writer; the daemon projects over it.

_VALID_TASK_STATUSES: frozenset[str] = frozenset({"pending", "in_progress", "completed"})
_TASK_MUTABLE_COLS: tuple[str, ...] = (
    "subject", "status", "chain_id", "event_type", "metadata", "updated_at",
)


def upsert_task(conn: sqlite3.Connection, task_id: str, fields: dict[str, Any]) -> None:
    """Insert or update a task row; missing keys preserve existing column values.

    ``fields`` keys that map to mutable columns are applied via INSERT OR IGNORE
    (to establish the row) followed by an UPDATE (to apply deltas).  The
    ``id``, ``session_id``, and ``created_at`` columns are immutable after
    creation; supply them on the initial call.

    Callers may pass ``metadata`` as a dict — it is JSON-serialised before
    storage so the column stays TEXT.
    """
    now = int(time.time())
    fields = dict(fields)
    fields.setdefault("updated_at", now)

    # Serialise metadata dict → TEXT so the column stays TEXT in SQLite.
    if isinstance(fields.get("metadata"), dict):
        fields["metadata"] = json.dumps(fields["metadata"], separators=(",", ":"))

    session_id = fields.get("session_id", "")
    subject = fields.get("subject", "")
    created_at = fields.get("created_at", now)

    # Bootstrap the row so subsequent UPDATE has a target.
    ins_cols: list[str] = ["id", "session_id", "subject", "created_at"]
    ins_vals: list[Any] = [task_id, session_id, subject, created_at]
    for col in _TASK_MUTABLE_COLS:
        if col in fields:
            ins_cols.append(col)
            ins_vals.append(fields[col])
    placeholders = ", ".join("?" for _ in ins_cols)
    conn.execute(
        f"INSERT OR IGNORE INTO tasks ({', '.join(ins_cols)}) VALUES ({placeholders})",
        ins_vals,
    )

    # Apply mutable-column deltas to the (possibly pre-existing) row.
    update_cols = [c for c in _TASK_MUTABLE_COLS if c in fields]
    if update_cols:
        set_clause = ", ".join(f"{c} = ?" for c in update_cols)
        conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?",
            [fields[c] for c in update_cols] + [task_id],
        )

    conn.commit()


def get_task(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    """Return a task row as a dict (metadata deserialised to dict), or None."""
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    _deserialize_task_metadata(result)
    return result


def list_tasks(
    conn: sqlite3.Connection,
    session_id: str | None = None,
    status_filter: str | None = None,
    chain_id_filter: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return task rows ordered by updated_at DESC.

    All filter args are optional and combinable.  An empty result is []
    rather than None.  ``limit`` is capped at 500 (R5: no unbounded reads).
    """
    _MAX_LIMIT = 500
    limit = min(limit, _MAX_LIMIT)

    clauses: list[str] = []
    params: list[Any] = []

    if session_id is not None:
        clauses.append("session_id = ?")
        params.append(session_id)
    if status_filter is not None:
        clauses.append("status = ?")
        params.append(status_filter)
    if chain_id_filter is not None:
        clauses.append("chain_id = ?")
        params.append(chain_id_filter)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM tasks {where} ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        _deserialize_task_metadata(d)
        result.append(d)
    return result


def _deserialize_task_metadata(task_dict: dict[str, Any]) -> None:
    """Deserialise the ``metadata`` column from TEXT to dict in-place.

    Silently leaves the field as-is if parsing fails — the caller gets the raw
    string rather than a crash.  Per R4: swallowed only because metadata is
    optional/enrichment and the row is still usable without it.
    """
    raw = task_dict.get("metadata")
    if isinstance(raw, str):
        try:
            task_dict["metadata"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass  # leave as raw string — callers treat metadata as best-effort


# ---------------------------------------------------------------------------
# Council CRUD (Stream 1 — #594 v8-PR-4)
# ---------------------------------------------------------------------------
# Council sessions fan out to N LLM CLIs in parallel; each model's raw
# response is persisted as a vote row.  The daemon is the authoritative store
# for council results — unlike the projection tables, council sessions are
# *originated* here (the one explicit write-path added per the carve-out
# from PR-1 decision #6, documented in daemon/council.py and the PR body).

_MAX_LIST_COUNCIL_SESSIONS: int = 200


def insert_council_session(
    conn: sqlite3.Connection,
    session_id: str,
    topic: str,
    question: str,
    started_at: int | None = None,
) -> None:
    """Insert a new council session row; idempotent via INSERT OR IGNORE.

    ``started_at`` defaults to the current epoch when omitted.
    """
    ts = started_at if started_at is not None else int(time.time())
    conn.execute(
        """
        INSERT OR IGNORE INTO council_sessions
            (id, topic, question, started_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, topic, question, ts),
    )
    conn.commit()


def upsert_council_vote(
    conn: sqlite3.Connection,
    session_id: str,
    model: str,
    verdict: str | None,
    confidence: float | None,
    rationale: str,
    raw_response: str,
    latency_ms: int,
    emitted_at: int | None = None,
) -> None:
    """Insert or replace a vote row for (session_id, model).

    Replacing allows a retry to overwrite a previous timeout/unavailable row
    while preserving all other votes in the session.
    """
    ts = emitted_at if emitted_at is not None else int(time.time())
    conn.execute(
        """
        INSERT OR REPLACE INTO council_votes
            (session_id, model, verdict, confidence, rationale, raw_response,
             latency_ms, emitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, model, verdict, confidence, rationale, raw_response,
         latency_ms, ts),
    )
    conn.commit()


def complete_council_session(
    conn: sqlite3.Connection,
    session_id: str,
    synthesized_verdict: str | None,
    agreement_ratio: float | None,
    hitl_paused: bool,
    hitl_rule_id: str | None,
    completed_at: int | None = None,
) -> None:
    """Mark a council session as completed with synthesis results."""
    ts = completed_at if completed_at is not None else int(time.time())
    conn.execute(
        """
        UPDATE council_sessions
        SET completed_at        = ?,
            synthesized_verdict = ?,
            agreement_ratio     = ?,
            hitl_paused         = ?,
            hitl_rule_id        = ?
        WHERE id = ?
        """,
        (ts, synthesized_verdict, agreement_ratio,
         1 if hitl_paused else 0, hitl_rule_id, session_id),
    )
    conn.commit()


def get_council_session(
    conn: sqlite3.Connection,
    session_id: str,
) -> dict[str, Any] | None:
    """Return a council_sessions row as a dict, or None if not found."""
    row = conn.execute(
        "SELECT * FROM council_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return dict(row) if row else None


def list_council_sessions(
    conn: sqlite3.Connection,
    topic_prefix: str | None = None,
    since: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return council sessions ordered by started_at DESC.

    ``topic_prefix`` filters to rows whose topic starts with the given string.
    ``since`` is an epoch lower bound on ``started_at`` (inclusive).
    ``limit`` is capped at _MAX_LIST_COUNCIL_SESSIONS (R5: no unbounded reads).
    """
    limit = min(limit, _MAX_LIST_COUNCIL_SESSIONS)
    if topic_prefix is not None:
        rows = conn.execute(
            """
            SELECT * FROM council_sessions
            WHERE started_at >= ? AND topic LIKE ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (since, topic_prefix + "%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM council_sessions
            WHERE started_at >= ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def list_council_votes(
    conn: sqlite3.Connection,
    session_id: str,
) -> list[dict[str, Any]]:
    """Return all vote rows for a council session."""
    rows = conn.execute(
        "SELECT * FROM council_votes WHERE session_id = ? ORDER BY emitted_at ASC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Acceptance-criteria CRUD (v8-PR-5 #591)
# ---------------------------------------------------------------------------
# Projected from wicked.ac.declared / wicked.ac.evidence_linked bus events.
# All writes are through bus-event projections — no HTTP write paths exist
# for these tables (Decision #6 read-only principle, carve-out documented in
# PR-4 only covers POST /council).

_MAX_LIST_ACS: int = 500
_MAX_LIST_AC_EVIDENCE: int = 1_000

# Evidence type inference: maps evidence_ref prefix patterns to a type label.
_EVIDENCE_TYPE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("tests/", "test"),
    ("test_", "test"),
    ("http", "url"),
    ("#", "issue"),
    ("gh#", "issue"),
    ("check:", "check"),
)

_DEFAULT_EVIDENCE_TYPE = "file"


def _infer_evidence_type(evidence_ref: str) -> str:
    """Infer an evidence_type label from the reference string.

    This is a hint for display purposes, not a gate condition.
    """
    low = evidence_ref.lstrip().lower()
    for prefix, label in _EVIDENCE_TYPE_PATTERNS:
        if low.startswith(prefix):
            return label
    return _DEFAULT_EVIDENCE_TYPE


def upsert_ac(
    conn: sqlite3.Connection,
    project_id: str,
    ac_id: str,
    statement: str,
    verification: str | None = None,
    created_at: int | None = None,
) -> None:
    """Insert or update an acceptance_criteria row.

    UPSERT semantics: re-projecting the same wicked.ac.declared event is
    idempotent.  ``statement`` is updated on conflict so a re-emitted event
    can correct a previously declared statement.
    """
    ts = created_at if created_at is not None else int(time.time())
    conn.execute(
        """
        INSERT INTO acceptance_criteria
            (project_id, ac_id, statement, verification, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(project_id, ac_id) DO UPDATE SET
            statement    = excluded.statement,
            verification = COALESCE(excluded.verification, verification)
        """,
        (project_id, ac_id, statement, verification, ts),
    )
    conn.commit()


def add_ac_evidence(
    conn: sqlite3.Connection,
    project_id: str,
    ac_id: str,
    evidence_ref: str,
    evidence_type: str | None = None,
    created_at: int | None = None,
) -> None:
    """Insert an ac_evidence row; idempotent on (project_id, ac_id, evidence_ref).

    ``evidence_type`` is inferred from ``evidence_ref`` when omitted.
    The FK (project_id, ac_id) requires the AC to exist first; callers must
    project wicked.ac.declared before wicked.ac.evidence_linked.
    """
    ts = created_at if created_at is not None else int(time.time())
    ev_type = evidence_type or _infer_evidence_type(evidence_ref)
    conn.execute(
        """
        INSERT OR IGNORE INTO ac_evidence
            (project_id, ac_id, evidence_ref, evidence_type, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, ac_id, evidence_ref, ev_type, ts),
    )
    conn.commit()


def list_acs(
    conn: sqlite3.Connection,
    project_id: str,
) -> list[dict[str, Any]]:
    """Return all acceptance_criteria rows for a project.

    Capped at _MAX_LIST_ACS (R5: no unbounded reads).
    """
    rows = conn.execute(
        """
        SELECT * FROM acceptance_criteria
        WHERE project_id = ?
        ORDER BY ac_id ASC
        LIMIT ?
        """,
        (project_id, _MAX_LIST_ACS),
    ).fetchall()
    return [dict(r) for r in rows]


def get_ac_evidence(
    conn: sqlite3.Connection,
    project_id: str,
    ac_id: str,
) -> list[dict[str, Any]]:
    """Return ac_evidence rows for a single (project_id, ac_id) pair.

    Capped at _MAX_LIST_AC_EVIDENCE (R5: no unbounded reads).
    """
    rows = conn.execute(
        """
        SELECT * FROM ac_evidence
        WHERE project_id = ? AND ac_id = ?
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (project_id, ac_id, _MAX_LIST_AC_EVIDENCE),
    ).fetchall()
    return [dict(r) for r in rows]


def ac_coverage_summary(
    conn: sqlite3.Connection,
    project_id: str,
) -> dict[str, int]:
    """Return counts {total, linked, unlinked} for a project's ACs.

    ``linked`` = ACs that have at least one ac_evidence row.
    ``unlinked`` = ACs with no evidence yet.
    """
    total_row = conn.execute(
        "SELECT COUNT(*) FROM acceptance_criteria WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    total: int = total_row[0] if total_row else 0

    linked_row = conn.execute(
        """
        SELECT COUNT(DISTINCT ac_id) FROM ac_evidence
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    linked: int = linked_row[0] if linked_row else 0

    return {"total": total, "linked": linked, "unlinked": total - linked}


# ---------------------------------------------------------------------------
# Hook subscription CRUD (v8-PR-8 #592)
# ---------------------------------------------------------------------------
# Subscriptions are originated by the daemon (registration sweep at startup or
# operator direct-db calls).  They are NOT created via HTTP — only toggled.
# This is the 4th explicit write path, documented in daemon/hook_dispatch.py
# and docs/evidence/pr-v8-8/contract-check.md.

_MAX_LIST_SUBSCRIPTIONS: int = 500
_MAX_LIST_INVOCATIONS: int = 1_000

#: Digest length for handler stdout/stderr captured in hook_invocations.
_INVOCATION_DIGEST_LENGTH: int = 1_000


def upsert_hook_subscription(
    conn: sqlite3.Connection,
    subscription_id: str,
    filter_pattern: str,
    handler_path: str,
    debounce_rule: dict | None = None,
    enabled: bool = True,
    created_at: int | None = None,
) -> None:
    """Insert or update a hook_subscriptions row.

    Idempotent: re-registering the same subscription_id updates the filter,
    handler, and debounce rule while preserving created_at.

    ``debounce_rule`` is JSON-serialised to TEXT when provided.
    """
    now = int(time.time())
    ts = created_at if created_at is not None else now
    debounce_json: str | None = (
        json.dumps(debounce_rule, separators=(",", ":")) if debounce_rule is not None else None
    )
    conn.execute(
        """
        INSERT INTO hook_subscriptions
            (subscription_id, filter_pattern, handler_path, debounce_rule,
             enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(subscription_id) DO UPDATE SET
            filter_pattern = excluded.filter_pattern,
            handler_path   = excluded.handler_path,
            debounce_rule  = excluded.debounce_rule,
            enabled        = excluded.enabled,
            updated_at     = excluded.updated_at
        """,
        (subscription_id, filter_pattern, handler_path, debounce_json,
         1 if enabled else 0, ts, now),
    )
    conn.commit()


def get_hook_subscription(
    conn: sqlite3.Connection,
    subscription_id: str,
) -> dict[str, Any] | None:
    """Return a hook_subscriptions row as a dict, or None if not found.

    ``debounce_rule`` is deserialised from JSON to a dict (or None).
    """
    row = conn.execute(
        "SELECT * FROM hook_subscriptions WHERE subscription_id = ?",
        (subscription_id,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    _deserialize_debounce_rule(result)
    return result


def list_hook_subscriptions(
    conn: sqlite3.Connection,
    enabled_only: bool = False,
) -> list[dict[str, Any]]:
    """Return hook_subscriptions rows ordered by created_at ASC.

    ``enabled_only=True`` filters to rows with enabled=1.
    Capped at _MAX_LIST_SUBSCRIPTIONS (R5: no unbounded reads).
    """
    if enabled_only:
        rows = conn.execute(
            """
            SELECT * FROM hook_subscriptions
            WHERE enabled = 1
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (_MAX_LIST_SUBSCRIPTIONS,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM hook_subscriptions
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (_MAX_LIST_SUBSCRIPTIONS,),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        _deserialize_debounce_rule(d)
        result.append(d)
    return result


def toggle_hook_subscription(
    conn: sqlite3.Connection,
    subscription_id: str,
    enabled: bool,
) -> bool:
    """Toggle a subscription's enabled flag.  Returns True if a row was updated."""
    now = int(time.time())
    cursor = conn.execute(
        "UPDATE hook_subscriptions SET enabled = ?, updated_at = ? WHERE subscription_id = ?",
        (1 if enabled else 0, now, subscription_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def append_hook_invocation(
    conn: sqlite3.Connection,
    invocation_id: str,
    subscription_id: str,
    event_id: int,
    event_type: str,
    verdict: str,
    latency_ms: int,
    stdout_digest: str | None = None,
    stderr_digest: str | None = None,
    emitted_at: int | None = None,
    debounce_key: str | None = None,
) -> None:
    """Append one hook invocation audit row.

    ``stdout_digest`` and ``stderr_digest`` are automatically truncated to
    _INVOCATION_DIGEST_LENGTH characters if longer (R5: no unbounded storage).
    Idempotent via INSERT OR IGNORE — re-recording the same invocation_id is a no-op.

    ``debounce_key`` (B1 fix #624): stores the composite dedup key computed at
    dispatch time so future debounce lookups can query by this column instead of
    constructing a fake composite event_type that was never stored.
    """
    ts = emitted_at if emitted_at is not None else int(time.time())
    # Truncate digests to bounded length (R5: no unbounded storage).
    if stdout_digest and len(stdout_digest) > _INVOCATION_DIGEST_LENGTH:
        stdout_digest = stdout_digest[:_INVOCATION_DIGEST_LENGTH]
    if stderr_digest and len(stderr_digest) > _INVOCATION_DIGEST_LENGTH:
        stderr_digest = stderr_digest[:_INVOCATION_DIGEST_LENGTH]
    conn.execute(
        """
        INSERT OR IGNORE INTO hook_invocations
            (invocation_id, subscription_id, event_id, event_type,
             verdict, debounce_key, stdout_digest, stderr_digest, latency_ms, emitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (invocation_id, subscription_id, event_id, event_type,
         verdict, debounce_key, stdout_digest, stderr_digest, latency_ms, ts),
    )
    conn.commit()


def list_hook_invocations(
    conn: sqlite3.Connection,
    subscription_id: str,
    since: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return hook_invocations for a subscription ordered by emitted_at DESC.

    ``since`` is an epoch lower bound on emitted_at (inclusive).
    ``limit`` is capped at _MAX_LIST_INVOCATIONS (R5: no unbounded reads).
    """
    limit = min(limit, _MAX_LIST_INVOCATIONS)
    rows = conn.execute(
        """
        SELECT * FROM hook_invocations
        WHERE subscription_id = ? AND emitted_at >= ?
        ORDER BY emitted_at DESC
        LIMIT ?
        """,
        (subscription_id, since, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _deserialize_debounce_rule(sub_dict: dict[str, Any]) -> None:
    """Deserialise the ``debounce_rule`` column from TEXT to dict in-place.

    Silently leaves the field as None if the column is NULL or parsing fails.
    Per R4: swallowed only because debounce_rule is optional metadata and the
    row is still usable without it.
    """
    raw = sub_dict.get("debounce_rule")
    if isinstance(raw, str):
        try:
            sub_dict["debounce_rule"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            sub_dict["debounce_rule"] = None  # leave as None — caller treats as no-rule
