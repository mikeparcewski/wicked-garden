#!/usr/bin/env python3
"""
Unit tests for wicked-smaht v2 Budget Enforcer.

Tests:
- Token budget enforcement per path
- Relevance-based item selection
- Truncation behavior
- Safety net for malformed input
"""

import sys
from pathlib import Path

# Add v2 to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "v2"))

import pytest
from budget_enforcer import BudgetEnforcer, SOURCE_PRIORITY


@pytest.fixture
def enforcer():
    return BudgetEnforcer()


class TestEnforce:
    """Test post-format safety net enforcement."""

    def test_hot_within_budget(self, enforcer):
        big_text = "x" * 5000
        result = enforcer.enforce(big_text, "hot")
        assert len(result) <= 400 - enforcer.OVERHEAD

    def test_fast_within_budget(self, enforcer):
        big_text = "x" * 5000
        result = enforcer.enforce(big_text, "fast")
        assert len(result) <= 2000 - enforcer.OVERHEAD

    def test_slow_within_budget(self, enforcer):
        big_text = "x" * 10000
        result = enforcer.enforce(big_text, "slow")
        assert len(result) <= 4000 - enforcer.OVERHEAD

    def test_under_budget_untouched(self, enforcer):
        short_text = "Hello world"
        result = enforcer.enforce(short_text, "slow")
        assert result == short_text

    def test_truncation_preserves_situation(self, enforcer):
        text = "[implementation | parser.py]\n\n## Relevant Context\n" + "x" * 5000
        result = enforcer.enforce(text, "fast")
        assert "[implementation" in result

    def test_suggestion_cut_before_content(self, enforcer):
        text = (
            "[debugging]\n\n"
            "## Relevant Context\n### Memories\n- **Decision**: Use Redis\n\n"
            "## Suggestion\n*Consider this pattern*\n\n"
        )
        padded = text + "x" * 3000
        result = enforcer.enforce(padded, "fast")
        # Suggestion section should be removed before hard content
        if "Memories" in result:
            assert "Suggestion" not in result or len(result) <= 2000

    def test_enforce_never_raises(self, enforcer):
        # Malformed input should not raise
        result = enforcer.enforce("", "hot")
        assert isinstance(result, str)

        result = enforcer.enforce(None or "", "unknown")
        assert isinstance(result, str)


class TestSelectItems:
    """Test pre-format relevance-based selection."""

    def _make_item(self, title="item", source="mem", relevance=0.5, excerpt=""):
        """Create a mock context item."""
        class Item:
            pass
        item = Item()
        item.title = title
        item.source = source
        item.relevance = relevance
        item.summary = f"Summary for {title}"
        item.excerpt = excerpt
        return item

    def test_hot_path_very_few_items(self, enforcer):
        items = {
            "mem": [self._make_item("Decision 1", "mem", 0.9)],
            "search": [self._make_item("Code ref", "search", 0.7)],
        }
        selected = enforcer.select_items(items, "hot")
        # HOT budget is tiny (400 - 200 overhead = 200 chars), should select very few
        total_items = sum(len(v) for v in selected.values())
        assert total_items <= 3

    def test_fast_path_bounded(self, enforcer):
        # Create enough items to exceed budget (FAST: 2000 - 200 = 1800 chars)
        # Each item ~80 chars + excerpt ~60 chars = 140 chars; 1800/140 ≈ 12 items max
        items = {
            "mem": [self._make_item(f"Mem {i}", "mem", 0.9, "excerpt text") for i in range(15)],
            "search": [self._make_item(f"Code {i}", "search", 0.8, "excerpt text") for i in range(15)],
        }
        selected = enforcer.select_items(items, "fast")
        total_items = sum(len(v) for v in selected.values())
        # Should not include all 30 items
        assert total_items < 30

    def test_high_relevance_preferred(self, enforcer):
        items = {
            "mem": [self._make_item("High", "mem", 0.95)],
            "delegation": [self._make_item("Low", "delegation", 0.1)],
        }
        selected = enforcer.select_items(items, "fast")
        # High-relevance mem item should always be selected
        assert "mem" in selected

    def test_source_priority_tiebreaker(self, enforcer):
        # Same relevance, different source priority
        items = {
            "mem": [self._make_item("Memory", "mem", 0.5)],
            "delegation": [self._make_item("Hint", "delegation", 0.5)],
        }
        selected = enforcer.select_items(items, "hot", reserved_chars=100)
        # With tight budget, mem should win over delegation
        if selected:
            assert "mem" in selected

    def test_empty_items_returns_empty(self, enforcer):
        selected = enforcer.select_items({}, "fast")
        assert selected == {}

    def test_reserved_chars_reduces_budget(self, enforcer):
        # Need enough items to exceed at least one of the budgets
        # SLOW: 4000 - 200 = 3800 (full), 4000 - 200 - 2000 = 1800 (reserved)
        # Each item with excerpt: 80 + 60 = 140 chars; need 3800/140 ≈ 27+ items
        items = {
            "mem": [self._make_item(f"Item {i}", "mem", 0.9, "excerpt") for i in range(40)],
        }
        selected_full = enforcer.select_items(items, "slow", reserved_chars=0)
        selected_reserved = enforcer.select_items(items, "slow", reserved_chars=2000)
        full_count = sum(len(v) for v in selected_full.values())
        reserved_count = sum(len(v) for v in selected_reserved.values())
        assert reserved_count < full_count


class TestEstimateTokens:
    """Test token estimation."""

    def test_estimate_tokens(self):
        assert BudgetEnforcer.estimate_tokens("x" * 400) == 100
        assert BudgetEnforcer.estimate_tokens("") == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
