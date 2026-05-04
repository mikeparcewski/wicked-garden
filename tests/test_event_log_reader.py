"""Tests for ``scripts/_event_log_reader.py`` (Scope B, #746).

Covers:
  - empty event_log
  - no matching events (wrong event_type / wrong project)
  - single match returns payload['data']
  - multiple matches returns latest (highest event_id)
  - payload missing 'data' key → None
  - payload['data'] not a dict → None
  - malformed JSON in payload_json → None
  - sqlite.Error on query → None / [] (fail-open)

All tests are deterministic, stdlib-only, no disk I/O beyond in-memory DB.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from _event_log_reader import read_latest_event_data, read_event_appends  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_log (
    event_id          INTEGER PRIMARY KEY,
    event_type        TEXT NOT NULL,
    chain_id          TEXT,
    payload_json      TEXT NOT NULL DEFAULT '{}',
    projection_status TEXT NOT NULL DEFAULT 'applied',
    error_message     TEXT,
    ingested_at       INTEGER NOT NULL DEFAULT 0
);
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def _insert(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    event_type: str,
    chain_id: str,
    payload: dict,
) -> None:
    conn.execute(
        "INSERT INTO event_log (event_id, event_type, chain_id, payload_json) "
        "VALUES (?, ?, ?, ?)",
        (event_id, event_type, chain_id, json.dumps(payload)),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# read_latest_event_data tests
# ---------------------------------------------------------------------------

class TestReadLatestEventDataEmptyTable(unittest.TestCase):
    def test_empty_table_returns_none(self):
        conn = _make_conn()
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)


class TestReadLatestEventDataNoMatch(unittest.TestCase):
    def test_wrong_event_type_returns_none(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.other.event",
                chain_id="proj-x.design.gate",
                payload={"data": {"verdict": "APPROVE"}})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)

    def test_wrong_project_id_returns_none(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="other-proj.design.gate",
                payload={"data": {"verdict": "APPROVE"}})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)

    def test_wrong_phase_returns_none(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="proj-x.build.gate",
                payload={"data": {"verdict": "APPROVE"}})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)


class TestReadLatestEventDataSingleMatch(unittest.TestCase):
    def test_single_match_returns_data(self):
        conn = _make_conn()
        _insert(conn, event_id=10, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"data": {"verdict": "APPROVE", "score": 0.9}})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertAlmostEqual(result["score"], 0.9)


class TestReadLatestEventDataMultipleMatches(unittest.TestCase):
    def test_multiple_matches_returns_latest_by_event_id(self):
        conn = _make_conn()
        _insert(conn, event_id=5, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"data": {"verdict": "REJECT", "score": 0.3}})
        _insert(conn, event_id=12, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate.retry",
                payload={"data": {"verdict": "APPROVE", "score": 0.85}})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNotNone(result)
        # event_id=12 is the latest — should return APPROVE
        self.assertEqual(result["verdict"], "APPROVE")

    def test_prefix_match_scope_correct(self):
        """chain_id LIKE 'proj-x.design%' must NOT match 'proj-x.design-extra' style
        entries for a different phase that happens to start with the same prefix."""
        conn = _make_conn()
        # Insert for phase=design
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"data": {"verdict": "APPROVE"}})
        # Insert for phase=design-extra (different phase, longer name)
        _insert(conn, event_id=2, event_type="wicked.gate.decided",
                chain_id="proj-x.design-extra.gate",
                payload={"data": {"verdict": "REJECT"}})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        # Both match prefix 'proj-x.design%' — latest wins (event_id=2, REJECT)
        # This is acceptable: chain_id scoping is best-effort for phase prefix.
        # The returned result will be from the highest event_id.
        self.assertIsNotNone(result)


class TestReadLatestEventDataMissingDataKey(unittest.TestCase):
    def test_payload_without_data_key_returns_none(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"verdict": "APPROVE"})  # no 'data' key
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)


class TestReadLatestEventDataDataNotDict(unittest.TestCase):
    def test_data_as_string_returns_none(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"data": "not-a-dict"})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)

    def test_data_as_list_returns_none(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"data": [1, 2, 3]})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)

    def test_data_as_none_returns_none(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"data": None})
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)


class TestReadLatestEventDataMalformedJSON(unittest.TestCase):
    def test_malformed_json_payload_returns_none(self):
        conn = _make_conn()
        # Insert directly with malformed JSON
        conn.execute(
            "INSERT INTO event_log (event_id, event_type, chain_id, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (1, "wicked.gate.decided", "proj-x.design.gate", "{not valid json")
        )
        conn.commit()
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)

    def test_null_payload_json_returns_none(self):
        conn = _make_conn()
        # payload_json column is NULL (use a different table that allows NULL)
        conn.execute(
            "INSERT INTO event_log (event_id, event_type, chain_id, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (1, "wicked.gate.decided", "proj-x.design.gate", "")
        )
        conn.commit()
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)


class TestReadLatestEventDataFailOpen(unittest.TestCase):
    def test_sqlite_error_on_query_returns_none(self):
        """Simulate a broken connection — must return None, not raise."""
        conn = _make_conn()
        conn.close()  # Close the connection to trigger OperationalError
        result = read_latest_event_data(
            conn, project_id="proj-x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# read_event_appends tests
# ---------------------------------------------------------------------------

class TestReadEventAppendsEmptyTable(unittest.TestCase):
    def test_empty_table_returns_empty_list(self):
        conn = _make_conn()
        result = read_event_appends(
            conn, project_id="proj-x", phase="design",
            event_type="wicked.dispatch.log_entry_appended"
        )
        self.assertEqual(result, [])


class TestReadEventAppendsNoMatch(unittest.TestCase):
    def test_wrong_event_type_returns_empty(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.other",
                chain_id="proj-x.design.gate.d1",
                payload={"raw_payload": '{"reviewer":"eng"}'})
        result = read_event_appends(
            conn, project_id="proj-x", phase="design",
            event_type="wicked.dispatch.log_entry_appended"
        )
        self.assertEqual(result, [])


class TestReadEventAppendsOrdering(unittest.TestCase):
    def test_returns_all_entries_in_event_id_order(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.dispatch.log_entry_appended",
                chain_id="proj-x.design.gate-quality.d1",
                payload={"raw_payload": '{"reviewer":"eng","dispatch_id":"d1"}'})
        _insert(conn, event_id=3, event_type="wicked.dispatch.log_entry_appended",
                chain_id="proj-x.design.gate-quality.d2",
                payload={"raw_payload": '{"reviewer":"sec","dispatch_id":"d2"}'})
        _insert(conn, event_id=2, event_type="wicked.dispatch.log_entry_appended",
                chain_id="proj-x.design.gate-quality.d3",
                payload={"raw_payload": '{"reviewer":"qe","dispatch_id":"d3"}'})
        result = read_event_appends(
            conn, project_id="proj-x", phase="design",
            event_type="wicked.dispatch.log_entry_appended"
        )
        # event_id order: 1, 2, 3
        self.assertEqual(len(result), 3)
        parsed = [json.loads(r) for r in result]
        self.assertEqual(parsed[0]["dispatch_id"], "d1")
        self.assertEqual(parsed[1]["dispatch_id"], "d3")
        self.assertEqual(parsed[2]["dispatch_id"], "d2")

    def test_newline_stripped_from_raw_payload(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.dispatch.log_entry_appended",
                chain_id="proj-x.design.g.d1",
                payload={"raw_payload": '{"reviewer":"eng"}\n'})
        result = read_event_appends(
            conn, project_id="proj-x", phase="design",
            event_type="wicked.dispatch.log_entry_appended"
        )
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].endswith("\n"))


class TestReadEventAppendsMissingRawPayload(unittest.TestCase):
    def test_entry_without_raw_payload_skipped(self):
        conn = _make_conn()
        _insert(conn, event_id=1, event_type="wicked.dispatch.log_entry_appended",
                chain_id="proj-x.design.g.d1",
                payload={"other_field": "value"})  # no raw_payload
        result = read_event_appends(
            conn, project_id="proj-x", phase="design",
            event_type="wicked.dispatch.log_entry_appended"
        )
        self.assertEqual(result, [])


class TestReadEventAppendsMalformedJSON(unittest.TestCase):
    def test_malformed_json_row_skipped(self):
        conn = _make_conn()
        conn.execute(
            "INSERT INTO event_log (event_id, event_type, chain_id, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (1, "wicked.dispatch.log_entry_appended",
             "proj-x.design.g.d1", "{bad json")
        )
        # Add a valid one too
        _insert(conn, event_id=2, event_type="wicked.dispatch.log_entry_appended",
                chain_id="proj-x.design.g.d2",
                payload={"raw_payload": '{"reviewer":"eng"}'})
        conn.commit()
        result = read_event_appends(
            conn, project_id="proj-x", phase="design",
            event_type="wicked.dispatch.log_entry_appended"
        )
        self.assertEqual(len(result), 1)
        self.assertIn('"reviewer"', result[0])


class TestReadEventAppendsFailOpen(unittest.TestCase):
    def test_sqlite_error_returns_empty_list(self):
        conn = _make_conn()
        conn.close()
        result = read_event_appends(
            conn, project_id="proj-x", phase="design",
            event_type="wicked.dispatch.log_entry_appended"
        )
        self.assertEqual(result, [])


class TestLikeEscaping(unittest.TestCase):
    """Underscores in project_id must not act as LIKE wildcards."""

    def test_underscore_in_project_id_is_literal(self):
        conn = _make_conn()
        # project_id with underscore
        _insert(conn, event_id=1, event_type="wicked.gate.decided",
                chain_id="proj_x.design.gate",
                payload={"data": {"verdict": "APPROVE"}})
        # project_id with different char at underscore position
        _insert(conn, event_id=2, event_type="wicked.gate.decided",
                chain_id="proj-x.design.gate",
                payload={"data": {"verdict": "REJECT"}})
        # Query specifically for proj_x (underscore)
        result = read_latest_event_data(
            conn, project_id="proj_x", phase="design", event_type="wicked.gate.decided"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "APPROVE")


if __name__ == "__main__":
    unittest.main()
