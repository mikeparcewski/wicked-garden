#!/usr/bin/env python3
"""
Unit tests for wicked-smaht SubagentStart hook.

Tests:
- Output format is valid JSON with correct structure
- Orientation metadata is compact (under token budget)
- Graceful fallback when no context available
- Crew context extraction
- Session pointer extraction
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hooks/scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks" / "scripts"))

import pytest


class TestGetCrewContext:
    """Test _get_crew_context function."""

    def test_no_crew_dir(self, tmp_path):
        """Returns empty dict when crew directory doesn't exist."""
        from subagent_start import _get_crew_context
        with patch("subagent_start.Path.home", return_value=tmp_path):
            result = _get_crew_context()
            assert result == {}

    def test_finds_active_project(self, tmp_path):
        """Returns context from most recently modified project."""
        from subagent_start import _get_crew_context
        crew_dir = tmp_path / ".something-wicked" / "wicked-crew" / "projects"
        proj_dir = crew_dir / "test-project"
        proj_dir.mkdir(parents=True)
        proj_json = proj_dir / "project.json"
        proj_json.write_text(json.dumps({
            "name": "test-project",
            "current_phase": "build",
            "signals_detected": ["security", "performance"],
        }))

        with patch("subagent_start.Path.home", return_value=tmp_path):
            result = _get_crew_context()
            assert result["project"] == "test-project"
            assert result["phase"] == "build"
            assert "security" in result["signals"]

    def test_ignores_completed_projects(self, tmp_path):
        """Ignores projects with no current_phase."""
        from subagent_start import _get_crew_context
        crew_dir = tmp_path / ".something-wicked" / "wicked-crew" / "projects"
        proj_dir = crew_dir / "done-project"
        proj_dir.mkdir(parents=True)
        proj_json = proj_dir / "project.json"
        proj_json.write_text(json.dumps({
            "name": "done-project",
            "current_phase": "",
        }))

        with patch("subagent_start.Path.home", return_value=tmp_path):
            result = _get_crew_context()
            assert result == {}

    def test_handles_corrupt_json(self, tmp_path):
        """Gracefully handles corrupt project.json."""
        from subagent_start import _get_crew_context
        crew_dir = tmp_path / ".something-wicked" / "wicked-crew" / "projects"
        proj_dir = crew_dir / "corrupt"
        proj_dir.mkdir(parents=True)
        (proj_dir / "project.json").write_text("not json")

        with patch("subagent_start.Path.home", return_value=tmp_path):
            result = _get_crew_context()
            assert result == {}

    def test_ignores_stale_projects(self, tmp_path):
        """Ignores projects not modified within MAX_PROJECT_AGE_SECONDS."""
        import time
        from subagent_start import _get_crew_context, MAX_PROJECT_AGE_SECONDS
        crew_dir = tmp_path / ".something-wicked" / "wicked-crew" / "projects"
        proj_dir = crew_dir / "stale-project"
        proj_dir.mkdir(parents=True)
        proj_json = proj_dir / "project.json"
        proj_json.write_text(json.dumps({
            "name": "stale-project",
            "current_phase": "build",
            "signals_detected": [],
        }))
        # Set mtime to 3 hours ago (beyond the 2-hour cap)
        old_time = time.time() - (MAX_PROJECT_AGE_SECONDS + 3600)
        os.utime(proj_json, (old_time, old_time))

        with patch("subagent_start.Path.home", return_value=tmp_path):
            result = _get_crew_context()
            assert result == {}


class TestGetSessionPointers:
    """Test _get_session_pointers function."""

    def test_returns_empty_on_import_failure(self):
        """Gracefully returns empty when HistoryCondenser unavailable."""
        from subagent_start import _get_session_pointers
        with patch.dict(sys.modules, {"history_condenser": None}):
            result = _get_session_pointers("test-session")
            assert result == {}

    def test_truncates_current_task(self):
        """Current task is truncated to 120 chars."""
        from subagent_start import _get_session_pointers
        mock_condenser = MagicMock()
        mock_condenser.get_session_state.return_value = {
            "current_task": "x" * 200,
            "topics": [],
            "file_scope": [],
        }
        with patch("history_condenser.HistoryCondenser", return_value=mock_condenser, create=True):
            result = _get_session_pointers("test")
            assert len(result.get("current_task", "")) <= 120

    def test_limits_topics_to_five(self):
        """Topics list is limited to 5 items."""
        from subagent_start import _get_session_pointers
        mock_condenser = MagicMock()
        mock_condenser.get_session_state.return_value = {
            "current_task": "",
            "topics": ["a", "b", "c", "d", "e", "f", "g"],
            "file_scope": [],
        }
        with patch("history_condenser.HistoryCondenser", return_value=mock_condenser, create=True):
            result = _get_session_pointers("test")
            assert len(result.get("topics", [])) <= 5

    def test_limits_files_to_five(self):
        """Active files list is limited to 5 items."""
        from subagent_start import _get_session_pointers
        mock_condenser = MagicMock()
        mock_condenser.get_session_state.return_value = {
            "current_task": "",
            "topics": [],
            "file_scope": [f"file{i}.py" for i in range(10)],
        }
        with patch("history_condenser.HistoryCondenser", return_value=mock_condenser, create=True):
            result = _get_session_pointers("test")
            assert len(result.get("active_files", [])) <= 5


class TestMainOutput:
    """Test the main() function output format."""

    def test_output_is_valid_json(self, tmp_path):
        """Output must be valid JSON."""
        from subagent_start import main
        with patch("subagent_start._get_crew_context", return_value={}), \
             patch("subagent_start._get_session_pointers", return_value={}), \
             patch("sys.stdin", MagicMock(read=lambda: "{}")), \
             patch("builtins.print") as mock_print:
            main()
            output = mock_print.call_args[0][0]
            parsed = json.loads(output)
            assert "continue" in parsed
            assert parsed["continue"] is True

    def test_no_context_returns_continue_only(self):
        """When no context available, returns minimal continue response."""
        from subagent_start import main
        with patch("subagent_start._get_crew_context", return_value={}), \
             patch("subagent_start._get_session_pointers", return_value={}), \
             patch("sys.stdin", MagicMock(read=lambda: "{}")), \
             patch("builtins.print") as mock_print:
            main()
            output = json.loads(mock_print.call_args[0][0])
            assert "hookSpecificOutput" not in output

    def test_with_context_returns_hook_output(self):
        """When context is available, returns hookSpecificOutput."""
        from subagent_start import main
        crew = {"project": "test-proj", "phase": "build", "signals": ["security"]}
        session = {"current_task": "Fix the bug", "topics": ["auth"]}
        with patch("subagent_start._get_crew_context", return_value=crew), \
             patch("subagent_start._get_session_pointers", return_value=session), \
             patch("sys.stdin", MagicMock(read=lambda: "{}")), \
             patch("builtins.print") as mock_print:
            main()
            output = json.loads(mock_print.call_args[0][0])
            assert "hookSpecificOutput" in output
            hook_output = output["hookSpecificOutput"]
            assert hook_output["hookEventName"] == "SubagentStart"
            context = hook_output["additionalContext"]
            assert "test-proj" in context
            assert "build" in context
            assert "Fix the bug" in context

    def test_context_is_compact(self):
        """Orientation metadata should be under 500 chars (~125 tokens)."""
        from subagent_start import main
        crew = {"project": "my-long-project-name", "phase": "build", "signals": ["security", "performance", "data"]}
        session = {
            "current_task": "Implement authentication flow with JWT tokens",
            "topics": ["auth", "jwt", "security", "middleware", "express"],
            "active_files": ["src/auth.py", "src/middleware.py", "tests/test_auth.py", "config.py", "README.md"],
        }
        with patch("subagent_start._get_crew_context", return_value=crew), \
             patch("subagent_start._get_session_pointers", return_value=session), \
             patch("sys.stdin", MagicMock(read=lambda: "{}")), \
             patch("builtins.print") as mock_print:
            main()
            output = json.loads(mock_print.call_args[0][0])
            context = output["hookSpecificOutput"]["additionalContext"]
            # Should be well under 500 chars
            assert len(context) < 500, f"Context too large: {len(context)} chars"

    def test_handles_stdin_error(self):
        """Gracefully handles stdin read failure."""
        from subagent_start import main
        with patch("subagent_start._get_crew_context", return_value={}), \
             patch("subagent_start._get_session_pointers", return_value={}), \
             patch("sys.stdin", MagicMock(read=MagicMock(side_effect=Exception("stdin error")))), \
             patch("builtins.print") as mock_print:
            main()
            output = json.loads(mock_print.call_args[0][0])
            assert output["continue"] is True


class TestEnsureSubagentHook:
    """Test _ensure_subagent_hook auto-installation."""

    def test_creates_settings_local_when_missing(self, tmp_path):
        """Creates .claude/settings.local.json with SubagentStart hook."""
        from session_start import _ensure_subagent_hook
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        with patch("session_start.Path.cwd", return_value=tmp_path):
            _ensure_subagent_hook()
        local_settings = claude_dir / "settings.local.json"
        assert local_settings.exists()
        data = json.loads(local_settings.read_text())
        assert "SubagentStart" in data["hooks"]
        assert data["hooks"]["SubagentStart"][0]["matcher"] == "*"

    def test_skips_when_already_in_settings_json(self, tmp_path):
        """Doesn't create settings.local.json if settings.json has SubagentStart."""
        from session_start import _ensure_subagent_hook
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        settings.write_text(json.dumps({
            "hooks": {"SubagentStart": [{"matcher": "*", "hooks": []}]}
        }))
        with patch("session_start.Path.cwd", return_value=tmp_path):
            _ensure_subagent_hook()
        assert not (claude_dir / "settings.local.json").exists()

    def test_skips_when_no_claude_dir(self, tmp_path):
        """Does nothing when .claude/ directory doesn't exist."""
        from session_start import _ensure_subagent_hook
        with patch("session_start.Path.cwd", return_value=tmp_path):
            _ensure_subagent_hook()
        assert not (tmp_path / ".claude" / "settings.local.json").exists()

    def test_merges_with_existing_local_settings(self, tmp_path):
        """Preserves existing settings.local.json content."""
        from session_start import _ensure_subagent_hook
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        local_settings = claude_dir / "settings.local.json"
        local_settings.write_text(json.dumps({
            "hooks": {"PostToolUse": [{"matcher": "Write", "hooks": []}]},
            "someOtherKey": True,
        }))
        with patch("session_start.Path.cwd", return_value=tmp_path):
            _ensure_subagent_hook()
        data = json.loads(local_settings.read_text())
        assert "SubagentStart" in data["hooks"]
        assert "PostToolUse" in data["hooks"]  # Preserved
        assert data["someOtherKey"] is True  # Preserved

    def test_skips_corrupt_local_settings(self, tmp_path):
        """Does not overwrite corrupt settings.local.json."""
        from session_start import _ensure_subagent_hook
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        local_settings = claude_dir / "settings.local.json"
        local_settings.write_text("not valid json {{{")
        with patch("session_start.Path.cwd", return_value=tmp_path):
            _ensure_subagent_hook()
        # File should be untouched
        assert local_settings.read_text() == "not valid json {{{"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
