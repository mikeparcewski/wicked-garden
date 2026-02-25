#!/usr/bin/env python3
"""
Unit tests for wicked-smaht PreCompact hook.

Tests:
- Condenser state saved
- Hook returns {"continue": true}
- Graceful handling of missing session
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hook scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks" / "scripts"))
# Add v2 scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "v2"))

import pytest


class TestPreCompactHook:
    """Test PreCompact hook behavior."""

    def test_returns_continue_true(self):
        """Hook output must include continue: true."""
        import pre_compact
        # HistoryCondenser is imported inside main() from history_condenser module
        with patch.dict('os.environ', {'CLAUDE_SESSION_ID': 'test-session'}):
            with patch('history_condenser.HistoryCondenser') as MockCondenser:
                mock_instance = MagicMock()
                MockCondenser.return_value = mock_instance
                captured = StringIO()
                with patch('sys.stdin', StringIO('{}')):
                    with patch('sys.stdout', captured):
                        pre_compact.main()
                output = json.loads(captured.getvalue())
                assert output.get("continue") is True

    def test_saves_condenser_state(self):
        """Hook should call condenser.save() and persist_session_meta()."""
        import pre_compact
        with patch.dict('os.environ', {'CLAUDE_SESSION_ID': 'test-session'}):
            with patch('history_condenser.HistoryCondenser') as MockCondenser:
                mock_instance = MagicMock()
                MockCondenser.return_value = mock_instance
                with patch('sys.stdin', StringIO('{}')):
                    with patch('sys.stdout', StringIO()):
                        pre_compact.main()
                mock_instance.save.assert_called_once()
                mock_instance.persist_session_meta.assert_called_once()

    def test_handles_missing_session_gracefully(self):
        """Hook should not crash with empty/missing session ID."""
        import pre_compact
        with patch.dict('os.environ', {}, clear=True):
            with patch('history_condenser.HistoryCondenser') as MockCondenser:
                MockCondenser.side_effect = Exception("No session")
                captured = StringIO()
                with patch('sys.stdin', StringIO('{}')):
                    with patch('sys.stdout', captured):
                        pre_compact.main()
                output = json.loads(captured.getvalue())
                assert output.get("continue") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
