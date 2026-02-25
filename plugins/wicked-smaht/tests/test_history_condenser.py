#!/usr/bin/env python3
"""
Unit tests for wicked-smaht v2 History Condenser.

Tests:
- Turn storage and retrieval
- Session summary updates
- Topic/decision/preference extraction
- Compression output format
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add v2 to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "v2"))

import pytest
from history_condenser import HistoryCondenser, Turn, SessionSummary


@pytest.fixture
def temp_session_dir():
    """Create a temporary session directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the session directory
        with patch.object(HistoryCondenser, '__init__', lambda self, sid: None):
            condenser = HistoryCondenser.__new__(HistoryCondenser)
            condenser.session_id = "test"
            condenser.session_dir = Path(tmpdir)
            condenser.session_dir.mkdir(parents=True, exist_ok=True)
            condenser.summary = SessionSummary()
            condenser.turn_buffer = []
            condenser.fact_extractor = None
            condenser.lane_tracker = None
            condenser._memory_promoter = None
            yield condenser


class TestTurnManagement:
    """Test turn storage and retrieval."""

    def test_add_turn(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.turn_buffer = []

        # Mock save to avoid file operations
        condenser.save = lambda: None

        condenser.add_turn("Hello", "Hi there!")
        assert len(condenser.turn_buffer) == 1
        assert condenser.turn_buffer[0].user == "Hello"

    def test_turn_buffer_limit(self, temp_session_dir):
        condenser = temp_session_dir
        from collections import deque
        condenser.turn_buffer = deque(maxlen=5)
        condenser.save = lambda: None

        # Add 7 turns
        for i in range(7):
            condenser.add_turn(f"User {i}", f"Assistant {i}")

        # Should only keep last 5
        assert len(condenser.turn_buffer) == 5
        assert condenser.turn_buffer[0].user == "User 2"

    def test_get_last_turn(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.turn_buffer = []
        condenser.save = lambda: None

        assert condenser.get_last_turn() is None

        condenser.add_turn("First", "Response 1")
        condenser.add_turn("Second", "Response 2")

        last = condenser.get_last_turn()
        assert last.user == "Second"


class TestTopicExtraction:
    """Test topic extraction from turns."""

    def test_extract_file_topics(self, temp_session_dir):
        condenser = temp_session_dir
        topics = condenser._extract_topics("Let's work on parser.py and lexer.py")
        assert "parser.py" in topics
        assert "lexer.py" in topics

    def test_extract_concept_topics(self, temp_session_dir):
        condenser = temp_session_dir
        topics = condenser._extract_topics("We need better caching and authentication")
        assert "caching" in topics
        assert "authentication" in topics


class TestDecisionExtraction:
    """Test decision extraction from turns."""

    def test_extract_decision_lets_use(self, temp_session_dir):
        condenser = temp_session_dir
        turn = Turn(
            user="What should we use?",
            assistant="Let's use Redis for caching."
        )
        decisions = condenser._extract_decisions(turn)
        assert len(decisions) > 0
        assert any("redis" in d.lower() for d in decisions)

    def test_extract_decision_decided_on(self, temp_session_dir):
        condenser = temp_session_dir
        turn = Turn(
            user="Which approach?",
            assistant="We decided on the hybrid approach."
        )
        decisions = condenser._extract_decisions(turn)
        assert len(decisions) > 0


class TestPreferenceExtraction:
    """Test preference extraction from user messages."""

    def test_extract_preference_prefer(self, temp_session_dir):
        condenser = temp_session_dir
        prefs = condenser._extract_preferences("I prefer simple solutions")
        assert any("simple" in p.lower() for p in prefs)

    def test_extract_preference_keep_it(self, temp_session_dir):
        condenser = temp_session_dir
        prefs = condenser._extract_preferences("Keep it minimal please")
        assert any("minimal" in p.lower() for p in prefs)


class TestCondensedOutput:
    """Test condensed history output format."""

    def test_condensed_history_format(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.summary = SessionSummary(
            topics=["caching", "auth"],
            decisions=["Use Redis"],
        )
        condenser.turn_buffer = [
            Turn(user="Add caching", assistant="Sure, let me add caching"),
        ]

        output = condenser.get_condensed_history()

        assert "## Session Context" in output
        assert "### Summary" in output
        assert "caching" in output
        assert "### Recent Turns" in output

    def test_empty_summary_output(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.summary = SessionSummary()
        condenser.turn_buffer = []

        output = condenser.get_condensed_history()
        assert "No summary yet" in output or "Session Context" in output


class TestTurnCondensation:
    """Test individual turn compression."""

    def test_condense_code_response(self, temp_session_dir):
        condenser = temp_session_dir
        turn = Turn(
            user="Show me the code",
            assistant="Here's the code:\n```python\nprint('hello')\n```"
        )
        condensed = condenser._condense_turn(turn)
        assert "Provided code" in condensed

    def test_condense_question_response(self, temp_session_dir):
        condenser = temp_session_dir
        turn = Turn(
            user="Add feature",
            assistant="What kind of feature?"
        )
        condensed = condenser._condense_turn(turn)
        assert "clarifying question" in condensed.lower()

    def test_condense_long_user_message(self, temp_session_dir):
        condenser = temp_session_dir
        long_msg = "A" * 200
        turn = Turn(user=long_msg, assistant="OK")
        condensed = condenser._condense_turn(turn)
        assert "..." in condensed  # Should be truncated


class TestSessionState:
    """Test session state retrieval."""

    def test_get_session_state(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.summary = SessionSummary(
            topics=["cache"],
            decisions=["Use Redis"],
        )
        condenser.turn_buffer = [Turn(user="test", assistant="test")]

        state = condenser.get_session_state()

        assert state["session_id"] == "test"
        assert state["turn_count"] == 1
        assert "cache" in state["topics"]
        assert state["has_decisions"] is True


class TestStripSystemReminders:
    """Test system-reminder stripping."""

    def test_strip_single_reminder(self):
        text = "before <system-reminder>secret</system-reminder> after"
        result = HistoryCondenser._strip_system_reminders(text)
        assert "secret" not in result
        assert "before" in result
        assert "after" in result

    def test_strip_multiple_reminders(self):
        text = "a <system-reminder>1</system-reminder> b <system-reminder>2</system-reminder> c"
        result = HistoryCondenser._strip_system_reminders(text)
        assert "1" not in result
        assert "2" not in result
        assert "a" in result
        assert "c" in result

    def test_strip_multiline_reminder(self):
        text = "before\n<system-reminder>\nline1\nline2\n</system-reminder>\nafter"
        result = HistoryCondenser._strip_system_reminders(text)
        assert "line1" not in result
        assert "after" in result

    def test_no_reminders_unchanged(self):
        text = "just plain text"
        result = HistoryCondenser._strip_system_reminders(text)
        assert result == text

    def test_add_turn_strips_reminders(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.turn_buffer = []
        condenser.save = lambda: None
        condenser.add_turn(
            "user msg",
            "response <system-reminder>injected</system-reminder> end"
        )
        assert "injected" not in condenser.turn_buffer[0].assistant
        assert "end" in condenser.turn_buffer[0].assistant


class TestUpdateFromPrompt:
    """Test update_from_prompt for populating session state from prompt only."""

    def test_extracts_topics(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.update_from_prompt("Let's work on parser.py and lexer.py")
        assert "parser.py" in condenser.summary.topics
        assert "lexer.py" in condenser.summary.topics

    def test_extracts_task(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.update_from_prompt("I'm working on fixing the auth bug")
        assert "auth" in condenser.summary.current_task.lower() or \
               "fixing" in condenser.summary.current_task.lower()

    def test_persists_to_disk(self):
        """update_from_prompt should call save()."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(HistoryCondenser, '__init__', lambda self, sid: None):
                condenser = HistoryCondenser.__new__(HistoryCondenser)
                condenser.session_id = "test"
                condenser.session_dir = Path(tmpdir)
                condenser.session_dir.mkdir(parents=True, exist_ok=True)
                condenser.summary = SessionSummary()
                condenser.turn_buffer = []
                condenser.fact_extractor = None
                condenser.lane_tracker = None
                condenser._memory_promoter = None
                condenser.update_from_prompt("Work on cache.py")
                # Should have persisted summary.json
                assert (Path(tmpdir) / "summary.json").exists()

    def test_does_not_add_to_turn_buffer(self, temp_session_dir):
        condenser = temp_session_dir
        condenser.save = lambda: None
        condenser.update_from_prompt("Some prompt")
        assert len(condenser.turn_buffer) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
