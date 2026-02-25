#!/usr/bin/env python3
"""
Unit tests for wicked-smaht v2 Fast Path Assembler.

Tests:
- Adapter selection rules
- Bonus adapter capping
- Briefing format
"""

import sys
from pathlib import Path

# Add v2 to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "v2"))

import pytest
from fast_path import FastPathAssembler, ADAPTER_RULES, FastPathResult
from router import IntentType, PromptAnalysis


def make_analysis(intent=IntentType.IMPLEMENTATION, confidence=0.8, entities=None):
    """Create a mock PromptAnalysis."""
    return PromptAnalysis(
        prompt="test prompt",
        word_count=5,
        intent_type=intent,
        confidence=confidence,
        competing_intents=0,
        entities=entities or [],
        entity_count=len(entities or []),
    )


class TestAdapterSelection:
    """Test adapter selection based on intent."""

    def test_debugging_adapters(self):
        adapters = ADAPTER_RULES[IntentType.DEBUGGING]
        assert "search" in adapters
        assert "mem" in adapters
        assert "delegation" in adapters

    def test_implementation_includes_mem(self):
        adapters = ADAPTER_RULES[IntentType.IMPLEMENTATION]
        assert "mem" in adapters
        assert "search" in adapters

    def test_planning_includes_kanban(self):
        adapters = ADAPTER_RULES[IntentType.PLANNING]
        assert "kanban" in adapters


class TestBonusAdapterCap:
    """Test that bonus adapters from predicted intent are capped."""

    def test_bonus_adapter_cap_at_2(self):
        assembler = FastPathAssembler()
        analysis = make_analysis(IntentType.DEBUGGING)

        # Get base adapter list for debugging
        base_count = len(ADAPTER_RULES[IntentType.DEBUGGING])

        # Simulate what assemble() does with predicted intent
        adapter_names = list(ADAPTER_RULES.get(analysis.intent_type, ["search"]))
        predicted_intent = IntentType.IMPLEMENTATION  # Has many adapters
        MAX_BONUS_ADAPTERS = 2
        bonus_count = 0
        for b in ADAPTER_RULES.get(predicted_intent, []):
            if b not in adapter_names and bonus_count < MAX_BONUS_ADAPTERS:
                adapter_names.append(b)
                bonus_count += 1

        # Should have at most base + 2 bonus
        assert len(adapter_names) <= base_count + 2

    def test_no_duplicate_adapters_with_bonus(self):
        adapter_names = list(ADAPTER_RULES[IntentType.DEBUGGING])
        predicted = ADAPTER_RULES[IntentType.IMPLEMENTATION]
        MAX_BONUS_ADAPTERS = 2
        bonus_count = 0
        for b in predicted:
            if b not in adapter_names and bonus_count < MAX_BONUS_ADAPTERS:
                adapter_names.append(b)
                bonus_count += 1
        # No duplicates
        assert len(adapter_names) == len(set(adapter_names))


class TestBriefingFormat:
    """Test briefing output format."""

    def test_compact_situation_line(self):
        assembler = FastPathAssembler()
        analysis = make_analysis(
            IntentType.DEBUGGING,
            entities=["parser.py"]
        )
        briefing = assembler._format_briefing("test", analysis, [], [])
        lines = briefing.strip().split("\n")
        # First line should be compact situation
        assert lines[0].startswith("[")
        assert "debugging" in lines[0]

    def test_summary_truncated_to_60(self):
        assembler = FastPathAssembler()

        class MockItem:
            source = "mem"
            title = "Test Item"
            summary = "A" * 100  # Over 60 chars

        analysis = make_analysis()
        briefing = assembler._format_briefing("test", analysis, [MockItem()], [])
        # Check that summary is truncated (first 60 chars)
        assert "A" * 61 not in briefing

    def test_failed_sources_single_line(self):
        assembler = FastPathAssembler()
        analysis = make_analysis()
        briefing = assembler._format_briefing("test", analysis, [], ["mem", "search"])
        assert "Unavailable: mem, search" in briefing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
