"""Tests for cheatsheet_store.py

Covers:
- store / list / get round-trip
- store with invalid JSON -> error, exit 1
- get non-existent library -> {"found": false}
- list with search filter
- store returns success:false when DomainStore.create returns None
- update detection with diff reporting
- remove cheatsheet
- update-all listing
- staleness tracking (fetched_at metadata)
"""

import json
import sys
import types
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow import of cheatsheet_store from the same directory
# ---------------------------------------------------------------------------

_SMAHT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SMAHT_DIR))
sys.path.insert(0, str(_SMAHT_DIR.parent))  # scripts/

# We import the module under test. Because it constructs a module-level
# DomainStore at import time, we need to patch _domain_store before importing.


def _make_storage_mock(records=None):
    """Return a MagicMock that behaves like DomainStore."""
    sm = MagicMock()
    _store = list(records or [])

    def _create(source, data):
        _store.append(data)
        return data  # non-None = success

    def _list(source):
        return list(_store)

    def _delete(source, record_id):
        to_remove = [r for r in _store if r.get("id") == record_id]
        for r in to_remove:
            _store.remove(r)
        return True

    sm.create.side_effect = _create
    sm.list.side_effect = _list
    sm.delete.side_effect = _delete
    return sm, _store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_module(sm_mock):
    """Import (or reload) cheatsheet_store with the given DomainStore mock."""
    # Provide a fake _domain_store module so cheatsheet_store can import from it
    fake_storage = types.ModuleType("_domain_store")
    fake_storage.DomainStore = MagicMock(return_value=sm_mock)
    sys.modules["_domain_store"] = fake_storage

    import importlib
    import cheatsheet_store
    importlib.reload(cheatsheet_store)
    # Patch the module-level _sm directly after reload
    cheatsheet_store._sm = sm_mock
    return cheatsheet_store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCmdStore:
    def test_store_valid_json_returns_success_true(self, capsys):
        sm, _ = _make_storage_mock()
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "react"
        args.data = json.dumps({"key_apis": [{"name": "useState"}]})
        args.version_hint = "18.x"

        mod.cmd_store(args)

        out = json.loads(capsys.readouterr().out)
        assert out["success"] is True
        assert "id" in out

    def test_store_sets_library_from_args(self, capsys):
        sm, store = _make_storage_mock()
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "fastapi"
        args.data = json.dumps({})
        args.version_hint = None

        mod.cmd_store(args)

        assert store[0]["library"] == "fastapi"

    def test_store_invalid_json_prints_error_and_exits(self, capsys):
        sm, _ = _make_storage_mock()
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "react"
        args.data = "not-valid-json{"
        args.version_hint = None

        with pytest.raises(SystemExit) as exc_info:
            mod.cmd_store(args)

        assert exc_info.value.code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["success"] is False
        assert "Invalid JSON" in out["error"]

    def test_store_returns_success_false_when_create_returns_none(self, capsys):
        sm, _ = _make_storage_mock()
        sm.create.side_effect = None  # reset side_effect
        sm.create.return_value = None  # simulate store failure

        mod = _load_module(sm)

        args = MagicMock()
        args.library = "vue"
        args.data = json.dumps({"key_apis": []})
        args.version_hint = None

        mod.cmd_store(args)

        out = json.loads(capsys.readouterr().out)
        assert out["success"] is False
        assert "None" in out["error"] or "DomainStore" in out["error"]


class TestCmdList:
    def _stored_records(self):
        return [
            {"library": "react", "timestamp": "2026-01-01T00:00:00+00:00"},
            {"library": "fastapi", "timestamp": "2026-01-02T00:00:00+00:00"},
            {"library": "react-query", "timestamp": "2026-01-03T00:00:00+00:00"},
        ]

    def test_list_all_returns_all_records(self, capsys):
        sm, _ = _make_storage_mock(self._stored_records())
        mod = _load_module(sm)

        args = MagicMock()
        args.search = None
        mod.cmd_list(args)

        out = json.loads(capsys.readouterr().out)
        assert len(out) == 3

    def test_list_with_search_filter_returns_matching_records(self, capsys):
        sm, _ = _make_storage_mock(self._stored_records())
        mod = _load_module(sm)

        args = MagicMock()
        args.search = "react"
        mod.cmd_list(args)

        out = json.loads(capsys.readouterr().out)
        assert len(out) == 2
        libraries = [r["library"] for r in out]
        assert "react" in libraries
        assert "react-query" in libraries
        assert "fastapi" not in libraries

    def test_list_with_no_matches_returns_empty_list(self, capsys):
        sm, _ = _make_storage_mock(self._stored_records())
        mod = _load_module(sm)

        args = MagicMock()
        args.search = "django"
        mod.cmd_list(args)

        out = json.loads(capsys.readouterr().out)
        assert out == []

    def test_list_search_is_case_insensitive(self, capsys):
        sm, _ = _make_storage_mock(self._stored_records())
        mod = _load_module(sm)

        args = MagicMock()
        args.search = "REACT"
        mod.cmd_list(args)

        out = json.loads(capsys.readouterr().out)
        assert len(out) == 2


class TestCmdGet:
    def _stored_records(self):
        return [
            {"library": "react", "key_apis": [], "timestamp": "2026-01-01T00:00:00+00:00"},
            {"library": "react", "key_apis": [{"name": "useState"}], "timestamp": "2026-02-01T00:00:00+00:00"},
        ]

    def test_get_returns_most_recent_record(self, capsys):
        sm, _ = _make_storage_mock(self._stored_records())
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "react"
        mod.cmd_get(args)

        out = json.loads(capsys.readouterr().out)
        # Most recent = Feb 2026
        assert out["timestamp"] == "2026-02-01T00:00:00+00:00"
        assert out["library"] == "react"

    def test_get_nonexistent_library_returns_found_false(self, capsys):
        sm, _ = _make_storage_mock(self._stored_records())
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "nonexistent-library-xyz"
        mod.cmd_get(args)

        out = json.loads(capsys.readouterr().out)
        assert out == {"found": False}

    def test_get_is_case_insensitive(self, capsys):
        sm, _ = _make_storage_mock(self._stored_records())
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "REACT"
        mod.cmd_get(args)

        out = json.loads(capsys.readouterr().out)
        assert out.get("library") == "react"


class TestRoundTrip:
    def test_store_then_get_round_trip(self, capsys):
        """Store a record and retrieve it back via get."""
        sm, _ = _make_storage_mock()
        mod = _load_module(sm)

        payload = {
            "key_apis": [{"name": "useState", "example": "const [s, setS] = useState(0)"}],
            "common_patterns": [{"name": "hooks"}],
            "gotchas": ["Don't call hooks in loops"],
            "source_url": "https://react.dev",
        }

        store_args = MagicMock()
        store_args.library = "react"
        store_args.data = json.dumps(payload)
        store_args.version_hint = "18.x"
        mod.cmd_store(store_args)
        capsys.readouterr()  # discard store output

        get_args = MagicMock()
        get_args.library = "react"
        mod.cmd_get(get_args)

        out = json.loads(capsys.readouterr().out)
        assert out.get("library") == "react"
        assert out.get("version_hint") == "18.x"
        assert len(out.get("key_apis", [])) == 1
        assert out["key_apis"][0]["name"] == "useState"


class TestUpdateDetection:
    def test_store_new_library_reports_updated_false(self, capsys):
        sm, _ = _make_storage_mock()
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "react"
        args.data = json.dumps({"key_apis": [{"name": "useState"}]})
        args.version_hint = None

        mod.cmd_store(args)

        out = json.loads(capsys.readouterr().out)
        assert out["updated"] is False

    def test_store_existing_library_reports_updated_true_with_diff(self, capsys):
        existing = [{
            "id": "old-id",
            "library": "react",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "key_apis": [{"name": "useState"}],
            "common_patterns": [],
            "gotchas": [],
        }]
        sm, _ = _make_storage_mock(existing)
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "react"
        args.data = json.dumps({
            "key_apis": [{"name": "useState"}, {"name": "useEffect"}],
            "common_patterns": [],
            "gotchas": ["Watch out for stale closures"],
        })
        args.version_hint = None

        mod.cmd_store(args)

        out = json.loads(capsys.readouterr().out)
        assert out["updated"] is True
        assert out["diff"]["has_changes"] is True
        assert "useEffect" in out["diff"]["changes"]["key_apis"]["added"]
        assert "Watch out for stale closures" in out["diff"]["changes"]["gotchas"]["added"]

    def test_store_sets_fetched_at_and_last_updated(self, capsys):
        existing = [{
            "id": "old-id",
            "library": "react",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "key_apis": [],
            "common_patterns": [],
            "gotchas": [],
        }]
        sm, store = _make_storage_mock(existing)
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "react"
        args.data = json.dumps({"key_apis": []})
        args.version_hint = None

        mod.cmd_store(args)
        capsys.readouterr()

        # The stored record should have fetched_at and last_updated
        stored = [r for r in store if r.get("library") == "react"]
        assert len(stored) >= 1
        latest = stored[-1]
        assert "fetched_at" in latest
        assert "last_updated" in latest
        assert "previous_fetched_at" in latest


class TestCmdRemove:
    def test_remove_existing_library_succeeds(self, capsys):
        records = [{"id": "abc", "library": "react", "timestamp": "2026-01-01T00:00:00+00:00"}]
        sm, _ = _make_storage_mock(records)
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "react"
        mod.cmd_remove(args)

        out = json.loads(capsys.readouterr().out)
        assert out["success"] is True
        assert out["removed"] == 1

    def test_remove_nonexistent_library_exits_with_error(self, capsys):
        sm, _ = _make_storage_mock()
        mod = _load_module(sm)

        args = MagicMock()
        args.library = "nonexistent"

        with pytest.raises(SystemExit) as exc_info:
            mod.cmd_remove(args)

        assert exc_info.value.code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["success"] is False


class TestCmdUpdateAll:
    def test_update_all_returns_unique_libraries(self, capsys):
        records = [
            {"library": "react", "timestamp": "2026-01-01T00:00:00+00:00",
             "fetched_at": "2026-01-01T00:00:00+00:00", "version_hint": "18.x"},
            {"library": "react", "timestamp": "2026-02-01T00:00:00+00:00",
             "fetched_at": "2026-02-01T00:00:00+00:00", "version_hint": "18.x"},
            {"library": "fastapi", "timestamp": "2026-01-15T00:00:00+00:00",
             "fetched_at": "2026-01-15T00:00:00+00:00"},
        ]
        sm, _ = _make_storage_mock(records)
        mod = _load_module(sm)

        args = MagicMock()
        mod.cmd_update_all(args)

        out = json.loads(capsys.readouterr().out)
        assert out["count"] == 2
        libs = [l["library"] for l in out["libraries"]]
        assert "react" in libs
        assert "fastapi" in libs


class TestDiffCheatsheets:
    def test_no_changes_detected(self):
        sm, _ = _make_storage_mock()
        mod = _load_module(sm)

        old = {"key_apis": [{"name": "a"}], "common_patterns": [{"name": "p"}], "gotchas": ["g"]}
        new = {"key_apis": [{"name": "a"}], "common_patterns": [{"name": "p"}], "gotchas": ["g"]}

        changes, has_changes = mod._diff_cheatsheets(old, new)
        assert has_changes is False
        assert changes == {}

    def test_added_and_removed_apis(self):
        sm, _ = _make_storage_mock()
        mod = _load_module(sm)

        old = {"key_apis": [{"name": "a"}, {"name": "b"}], "common_patterns": [], "gotchas": []}
        new = {"key_apis": [{"name": "b"}, {"name": "c"}], "common_patterns": [], "gotchas": []}

        changes, has_changes = mod._diff_cheatsheets(old, new)
        assert has_changes is True
        assert "a" in changes["key_apis"]["removed"]
        assert "c" in changes["key_apis"]["added"]
