#!/usr/bin/env python3
"""
Unit tests for wicked-smaht v2 Slow Path Assembler.

Tests:
- Format output correctness
- System-reminder stripping
- Empty section suppression
"""

import sys
from pathlib import Path

# Add v2 to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "v2"))

import pytest
from slow_path import SlowPathAssembler
from router import IntentType, PromptAnalysis


def make_analysis(intent=IntentType.IMPLEMENTATION, entities=None):
    return PromptAnalysis(
        prompt="test",
        word_count=5,
        intent_type=intent,
        confidence=0.8,
        competing_intents=0,
        entities=entities or [],
        entity_count=len(entities or []),
        is_compound=False,
        requires_history=False,
    )


class MockTurn:
    def __init__(self, user="test", assistant="response"):
        self.user = user
        self.assistant = assistant


class TestSlowPathFormat:
    """Test slow path briefing format."""

    def test_no_considerations_section(self):
        assembler = SlowPathAssembler()
        analysis = make_analysis()
        briefing = assembler._format_briefing(
            "test", analysis, {}, "", None, []
        )
        assert "## Considerations" not in briefing

    def test_no_empty_session_history(self):
        assembler = SlowPathAssembler()
        analysis = make_analysis()
        # "(No summary yet)" should be suppressed
        briefing = assembler._format_briefing(
            "test", analysis, {}, "(No summary yet)", None, []
        )
        assert "## Session History" not in briefing

    def test_empty_history_suppressed(self):
        assembler = SlowPathAssembler()
        analysis = make_analysis()
        briefing = assembler._format_briefing(
            "test", analysis, {}, "", None, []
        )
        assert "## Session History" not in briefing

    def test_last_turn_stripped_of_reminders(self):
        assembler = SlowPathAssembler()
        analysis = make_analysis()
        last_turn = MockTurn(
            user="test prompt",
            assistant="response <system-reminder>secret</system-reminder> end"
        )
        briefing = assembler._format_briefing(
            "test", analysis, {}, "", last_turn, []
        )
        assert "secret" not in briefing
        assert "system-reminder" not in briefing

    def test_excerpt_truncated_to_100(self):
        assembler = SlowPathAssembler()
        analysis = make_analysis()

        class MockItem:
            title = "Test"
            summary = "Summary"
            excerpt = "E" * 200

        items = {"mem": [MockItem()]}
        briefing = assembler._format_briefing(
            "test", analysis, items, "", None, []
        )
        # Excerpt should be truncated
        assert "E" * 101 not in briefing

    def test_compact_situation_with_notes(self):
        assembler = SlowPathAssembler()
        analysis = make_analysis()
        analysis.is_compound = True
        analysis.requires_history = True
        briefing = assembler._format_briefing(
            "test", analysis, {}, "", None, []
        )
        assert "multi-part" in briefing
        assert "refs history" in briefing

    def test_failed_sources_single_line(self):
        assembler = SlowPathAssembler()
        analysis = make_analysis()
        briefing = assembler._format_briefing(
            "test", analysis, {}, "", None, ["mem", "search"]
        )
        assert "Unavailable: mem, search" in briefing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
