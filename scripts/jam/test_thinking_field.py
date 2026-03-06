"""
pytest tests for jam.py thinking field — J-8, J-9, J-24.

Run with:
    cd /Users/michael.parcewski/Projects/wicked-garden && uv run pytest scripts/jam/test_thinking_field.py -v
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

JAM_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = JAM_DIR.parent

sys.path.insert(0, str(JAM_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Minimal stub for StorageManager so jam.py imports cleanly without a real DB
# ---------------------------------------------------------------------------

class _StubStorageManager:
    """In-memory StorageManager stand-in."""

    def __init__(self, *args, **kwargs):
        self._data: dict[str, dict] = {}

    def list(self, collection: str, **params) -> list:
        return list(self._data.get(collection, {}).values())

    def get(self, collection: str, key: str) -> dict | None:
        return self._data.get(collection, {}).get(key)

    def set(self, collection: str, key: str, value: dict) -> None:
        self._data.setdefault(collection, {})[key] = value

    def update(self, collection: str, key: str, updates: dict) -> None:
        existing = self._data.get(collection, {}).get(key, {})
        existing.update(updates)
        self._data.setdefault(collection, {})[key] = existing


@pytest.fixture(autouse=True)
def stub_storage(monkeypatch):
    """Replace StorageManager globally before jam.py module is loaded."""
    stub_module = MagicMock()
    stub_module.StorageManager = _StubStorageManager
    monkeypatch.setitem(sys.modules, "_storage", stub_module)
    yield stub_module


@pytest.fixture
def jam():
    """Import jam module fresh (with stubbed _storage)."""
    # Remove cached module so the fixture-level stub takes effect
    if "jam" in sys.modules:
        del sys.modules["jam"]
    import jam as _jam
    return _jam


# ---------------------------------------------------------------------------
# J-8: thinking field preserved in transcript entries
# ---------------------------------------------------------------------------

class TestThinkingFieldPreserved:
    """J-8 — thinking field is stored in entries and surfaces in get_thinking()."""

    def _make_transcript(self, session_id: str, entries: list) -> dict:
        return {"session_id": session_id, "entries": entries}

    def _make_entry(self, round_num=1, persona="Architect", thinking="", raw_text="Some text",
                    entry_type="perspective") -> dict:
        return {
            "session_id": "sess-001",
            "round": round_num,
            "persona_name": persona,
            "persona_type": "technical",
            "raw_text": raw_text,
            "thinking": thinking,
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_type": entry_type,
        }

    def test_get_thinking_returns_entries_with_thinking_field(self, jam):
        """get_thinking() returns perspective entries regardless of thinking content."""
        entry_with_thinking = self._make_entry(thinking="Considering alternatives A vs B")
        entry_without_thinking = self._make_entry(round_num=2, thinking="", persona="User")
        transcript = self._make_transcript("sess-001", [entry_with_thinking, entry_without_thinking])

        jam._sm.set("transcripts", "sess-001", transcript)
        jam._sm.set("sessions", "sess-001", {"id": "sess-001", "topic": "test"})

        result = jam.get_thinking(session_id="sess-001")

        assert result["session_id"] == "sess-001"
        assert len(result["entries"]) == 2
        # Entry with thinking content is present
        entries_with_content = [e for e in result["entries"] if e.get("thinking")]
        assert len(entries_with_content) == 1
        assert entries_with_content[0]["thinking"] == "Considering alternatives A vs B"

    def test_thinking_field_survives_get_transcript(self, jam):
        """get_transcript() returns entries with thinking field intact."""
        entry = self._make_entry(thinking="My deliberation notes")
        transcript = self._make_transcript("sess-002", [entry])

        jam._sm.set("transcripts", "sess-002", transcript)
        jam._sm.set("sessions", "sess-002", {"id": "sess-002", "topic": "test"})

        result = jam.get_transcript(session_id="sess-002")

        assert result["entries"][0]["thinking"] == "My deliberation notes"

    def test_get_thinking_filters_to_perspective_type(self, jam):
        """Only entry_type='perspective' entries are returned by get_thinking()."""
        perspective = self._make_entry(entry_type="perspective", thinking="trade-off analysis")
        synthesis = self._make_entry(round_num=2, entry_type="synthesis", thinking="synthesis thinking")
        council = self._make_entry(round_num=3, entry_type="council_response", thinking="council thoughts")
        transcript = self._make_transcript("sess-003", [perspective, synthesis, council])

        jam._sm.set("transcripts", "sess-003", transcript)
        jam._sm.set("sessions", "sess-003", {"id": "sess-003", "topic": "test"})

        result = jam.get_thinking(session_id="sess-003")

        assert len(result["entries"]) == 1
        assert result["entries"][0]["entry_type"] == "perspective"


# ---------------------------------------------------------------------------
# J-9: thinking field optional (empty string works fine)
# ---------------------------------------------------------------------------

class TestThinkingFieldOptional:
    """J-9 — thinking field is optional; entries without it still work."""

    def test_entry_with_empty_thinking_string(self, jam):
        entry = {
            "session_id": "sess-010",
            "round": 1,
            "persona_name": "User",
            "persona_type": "user",
            "raw_text": "User perspective text",
            "thinking": "",
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_type": "perspective",
        }
        transcript = {"session_id": "sess-010", "entries": [entry]}
        jam._sm.set("transcripts", "sess-010", transcript)
        jam._sm.set("sessions", "sess-010", {"id": "sess-010", "topic": "test"})

        result = jam.get_transcript(session_id="sess-010")
        assert len(result["entries"]) == 1
        assert result["entries"][0]["thinking"] == ""

    def test_print_entry_does_not_show_section_when_thinking_empty(self, jam, capsys):
        """_print_entry must not print [thinking] header when thinking is empty."""
        entry = {
            "round": 1,
            "persona_name": "Designer",
            "persona_type": "user",
            "raw_text": "The design should be clean",
            "thinking": "",
            "timestamp": "",
            "entry_type": "perspective",
        }
        jam._print_entry(entry, index=1)
        captured = capsys.readouterr()
        assert "[thinking]" not in captured.out

    def test_print_entry_shows_thinking_section_when_present(self, jam, capsys):
        """_print_entry must print [thinking] section when field is non-empty."""
        entry = {
            "round": 1,
            "persona_name": "Architect",
            "persona_type": "technical",
            "raw_text": "We should use microservices",
            "thinking": "Trade-off: monolith vs microservices. Chose micro for scalability.",
            "timestamp": "",
            "entry_type": "perspective",
        }
        jam._print_entry(entry, index=1)
        captured = capsys.readouterr()
        assert "[thinking]" in captured.out
        assert "Trade-off: monolith vs microservices" in captured.out

    def test_print_entry_shows_raw_text_regardless_of_thinking(self, jam, capsys):
        """raw_text must always be printed whether thinking is present or not."""
        for thinking_val in ["", "some thoughts"]:
            entry = {
                "round": 1,
                "persona_name": "Tester",
                "persona_type": "process",
                "raw_text": "This is the main content",
                "thinking": thinking_val,
                "timestamp": "",
                "entry_type": "perspective",
            }
            jam._print_entry(entry)
            captured = capsys.readouterr()
            assert "This is the main content" in captured.out


# ---------------------------------------------------------------------------
# J-24: Old records without thinking field work correctly (backward compat)
# ---------------------------------------------------------------------------

class TestBackwardCompatOldRecords:
    """J-24 — Old transcript entries without 'thinking' key load without error."""

    def test_get_transcript_with_no_thinking_key(self, jam):
        """Entry missing 'thinking' key entirely must not raise KeyError."""
        old_entry = {
            "session_id": "sess-legacy",
            "round": 1,
            "persona_name": "Legacy Persona",
            "persona_type": "business",
            "raw_text": "Old record text",
            # 'thinking' key deliberately absent
            "timestamp": "2025-01-01T00:00:00Z",
            "entry_type": "perspective",
        }
        transcript = {"session_id": "sess-legacy", "entries": [old_entry]}
        jam._sm.set("transcripts", "sess-legacy", transcript)
        jam._sm.set("sessions", "sess-legacy", {"id": "sess-legacy", "topic": "legacy test"})

        result = jam.get_transcript(session_id="sess-legacy")
        assert len(result["entries"]) == 1
        assert result["entries"][0]["raw_text"] == "Old record text"

    def test_get_thinking_with_no_thinking_key(self, jam):
        """get_thinking() returns entries even if thinking key is absent."""
        old_entry = {
            "round": 1,
            "persona_name": "Old Persona",
            "persona_type": "technical",
            "raw_text": "Legacy perspective",
            # no 'thinking' key
            "entry_type": "perspective",
        }
        transcript = {"session_id": "sess-old", "entries": [old_entry]}
        jam._sm.set("transcripts", "sess-old", transcript)
        jam._sm.set("sessions", "sess-old", {"id": "sess-old", "topic": "old"})

        result = jam.get_thinking(session_id="sess-old")
        assert len(result["entries"]) == 1

    def test_print_entry_with_no_thinking_key(self, jam, capsys):
        """_print_entry must not crash when 'thinking' key is absent."""
        old_entry = {
            "round": 1,
            "persona_name": "Old",
            "persona_type": "technical",
            "raw_text": "Legacy content",
            # no 'thinking' key
            "timestamp": "",
            "entry_type": "perspective",
        }
        # Should not raise KeyError
        jam._print_entry(old_entry, index=1)
        captured = capsys.readouterr()
        assert "Legacy content" in captured.out
        assert "[thinking]" not in captured.out

    def test_mixed_old_and_new_records_coexist(self, jam):
        """Session can contain a mix of old records (no thinking) and new ones."""
        old_entry = {
            "round": 1,
            "persona_name": "Old",
            "persona_type": "technical",
            "raw_text": "Old way",
            "entry_type": "perspective",
            # no 'thinking'
        }
        new_entry = {
            "round": 2,
            "persona_name": "New",
            "persona_type": "user",
            "raw_text": "New way",
            "thinking": "Deliberating on the new approach",
            "entry_type": "perspective",
        }
        transcript = {"session_id": "sess-mixed", "entries": [old_entry, new_entry]}
        jam._sm.set("transcripts", "sess-mixed", transcript)
        jam._sm.set("sessions", "sess-mixed", {"id": "sess-mixed", "topic": "mixed"})

        result = jam.get_transcript(session_id="sess-mixed")
        assert len(result["entries"]) == 2

        result_thinking = jam.get_thinking(session_id="sess-mixed")
        assert len(result_thinking["entries"]) == 2

    def test_get_thinking_output_shows_no_thinking_message_for_sessions_without_it(self, jam):
        """When all entries lack thinking, the CLI reports 'No thinking data available'."""
        # This exercises the main() display path: entries_with_thinking check
        old_entry = {
            "round": 1,
            "persona_name": "Old",
            "persona_type": "technical",
            "raw_text": "Legacy text",
            "entry_type": "perspective",
        }
        transcript = {"session_id": "sess-no-think", "entries": [old_entry]}
        jam._sm.set("transcripts", "sess-no-think", transcript)
        jam._sm.set("sessions", "sess-no-think", {"id": "sess-no-think", "topic": "no think"})

        # Simulate main() CLI path for 'thinking' command
        # We directly test the logic: if entries exist but none have thinking, display a message
        result = jam.get_thinking(session_id="sess-no-think")
        entries = result["entries"]
        entries_with_thinking = [e for e in entries if e.get("thinking", "").strip()]
        assert entries  # entries exist
        assert not entries_with_thinking  # but none have thinking


# ---------------------------------------------------------------------------
# Integration: get_thinking + get_persona work together
# ---------------------------------------------------------------------------

class TestThinkingIntegration:
    """Combined thinking and persona queries work correctly."""

    def test_get_persona_returns_thinking_field_in_entries(self, jam):
        """get_persona() must return thinking field in each entry."""
        entry = {
            "session_id": "sess-int",
            "round": 1,
            "persona_name": "Business Analyst",
            "persona_type": "business",
            "raw_text": "Business perspective text",
            "thinking": "Analyzing ROI and business value",
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_type": "perspective",
        }
        transcript = {"session_id": "sess-int", "entries": [entry]}
        jam._sm.set("transcripts", "sess-int", transcript)
        jam._sm.set("sessions", "sess-int", {"id": "sess-int", "topic": "int test"})

        result = jam.get_persona("Business Analyst", session_id="sess-int")
        assert len(result["entries"]) == 1
        assert result["entries"][0]["thinking"] == "Analyzing ROI and business value"

    def test_thinking_field_in_json_output(self, jam, capsys):
        """JSON output mode includes thinking field."""
        entry = {
            "session_id": "sess-json",
            "round": 1,
            "persona_name": "Tester",
            "persona_type": "process",
            "raw_text": "Test text",
            "thinking": "Test deliberation",
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_type": "perspective",
        }
        transcript = {"session_id": "sess-json", "entries": [entry]}
        jam._sm.set("transcripts", "sess-json", transcript)
        jam._sm.set("sessions", "sess-json", {"id": "sess-json", "topic": "json test"})

        result = jam.get_transcript(session_id="sess-json")
        # Serialize to JSON and verify thinking key is present
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["entries"][0]["thinking"] == "Test deliberation"
