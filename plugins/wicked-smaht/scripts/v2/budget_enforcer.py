#!/usr/bin/env python3
"""
wicked-smaht v2: Budget Enforcer

Intelligent token budget enforcement using relevance-based item selection.

Two phases:
1. PRE-FORMAT (smart): Select highest-relevance items within budget allocation
2. POST-FORMAT (safety net): Hard character cap if formatting produces over-budget output

Budget per path:
  HOT:  100 tokens → 400 chars
  FAST: 500 tokens → 2000 chars
  SLOW: 1000 tokens → 4000 chars
"""

import re


# Per-item character estimates for budget allocation
ITEM_CHAR_ESTIMATE = 80  # "- **title**: summary" line
EXCERPT_CHAR_ESTIMATE = 60  # "  > excerpt" line
SECTION_HEADER_ESTIMATE = 30  # "### Source Name\n"
SITUATION_ESTIMATE = 60  # "[intent | entities]"

# Source priority (higher = keep longer when cutting)
SOURCE_PRIORITY = {
    "mem": 10,       # Highest — past decisions/context
    "search": 9,     # Code context
    "kanban": 7,     # Active tasks
    "crew": 6,       # Project state
    "context7": 4,   # External docs
    "jam": 3,        # Brainstorms
    "startah": 2,    # Available CLIs
    "delegation": 1, # Suggestions — lowest
}


class BudgetEnforcer:
    """Enforce token budget on context briefings using intelligent selection."""

    CHAR_BUDGETS = {"hot": 400, "fast": 2000, "slow": 4000}
    OVERHEAD = 200  # system-reminder wrapper + HTML comment header (variable but bounded)

    def select_items(self, items_by_source: dict, path: str, reserved_chars: int = 0) -> dict:
        """Select highest-value items that fit within the path's budget.

        Args:
            items_by_source: dict of source_name -> list of ContextItems
            path: "hot", "fast", or "slow"
            reserved_chars: chars already used by situation/history sections

        Returns:
            Filtered items_by_source with only the best items within budget.
        """
        budget = self.CHAR_BUDGETS.get(path, 2000) - self.OVERHEAD - reserved_chars

        # Flatten all items with source info and relevance
        scored_items = []
        for source, items in items_by_source.items():
            if not items:
                continue
            source_priority = SOURCE_PRIORITY.get(source, 0)
            for item in items:
                relevance = getattr(item, 'relevance', 0.5)
                # Combined score: relevance weighted + source priority bonus
                score = relevance + (source_priority * 0.05)
                char_cost = ITEM_CHAR_ESTIMATE
                if getattr(item, 'excerpt', ''):
                    char_cost += EXCERPT_CHAR_ESTIMATE
                scored_items.append({
                    'source': source,
                    'item': item,
                    'score': score,
                    'cost': char_cost,
                })

        # Sort by score descending
        scored_items.sort(key=lambda x: x['score'], reverse=True)

        # Greedily select items within budget
        selected = {}
        chars_used = 0
        sources_seen = set()
        for entry in scored_items:
            source = entry['source']
            cost = entry['cost']
            # Account for section header if this is the first item from this source
            if source not in sources_seen:
                cost += SECTION_HEADER_ESTIMATE
            if chars_used + cost > budget:
                continue
            if source not in selected:
                selected[source] = []
                sources_seen.add(source)
            selected[source].append(entry['item'])
            chars_used += cost

        return selected

    def enforce(self, briefing: str, path: str) -> str:
        """Hard character cap on formatted briefing (safety net).

        Returns briefing unchanged if within budget. Never raises.
        """
        budget = self.CHAR_BUDGETS.get(path, 2000) - self.OVERHEAD
        if len(briefing) <= budget:
            return briefing
        try:
            return self._truncate(briefing, budget)
        except Exception:
            return briefing[:budget]

    def _truncate(self, text: str, budget: int) -> str:
        """Safety-net truncation for already-formatted text."""
        result = text

        # 1. Remove excerpts (> lines)
        result = re.sub(r'  > .+\n?', '', result)
        if len(result) <= budget:
            return result

        # 2. Remove Suggestion section
        result = re.sub(r'\n## Suggestion\n.*?(?=\n## |\Z)', '', result, flags=re.DOTALL)
        if len(result) <= budget:
            return result

        # 3. Truncate Session History to 3 lines
        def truncate_history(m):
            lines = m.group(0).split('\n')
            return '\n'.join(lines[:4])
        result = re.sub(r'## Session History\n(?:.*\n?)*?(?=\n## |\Z)', truncate_history, result)
        if len(result) <= budget:
            return result

        # 4. Remove lower-priority source sections
        for source in ['Delegation Hints', 'Available CLIs', 'Brainstorms', 'External Docs', 'Project State']:
            result = re.sub(rf'\n### {source}\n.*?(?=\n### |\n## |\Z)', '', result, flags=re.DOTALL)
            if len(result) <= budget:
                return result

        # 5. Hard slice
        return result[:budget]

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count from text length."""
        return len(text) // 4
