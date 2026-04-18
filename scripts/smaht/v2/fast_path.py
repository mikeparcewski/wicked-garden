#!/usr/bin/env python3
"""
wicked-smaht v2: Fast Path Assembler

Pattern-based context assembly without LLM reasoning.
Target latency: <1s

Strategy:
1. Get intent from router analysis
2. Select adapters based on intent type
3. Query adapters in parallel
4. Format directly into briefing
"""

import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Add parent to path for adapter imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from router import IntentType, PromptAnalysis
from adapter_registry import AdapterRegistry, timed_query, CACHE_BYPASS


# Adapter selection rules by intent
# "domain" is the DomainStore adapter — queries crew projects and jam sessions
ADAPTER_RULES = {
    IntentType.DEBUGGING: ["domain", "brain", "delegation"],
    IntentType.IMPLEMENTATION: ["domain", "brain", "context7", "tools", "delegation"],
    IntentType.PLANNING: ["domain", "events", "delegation"],
    IntentType.RESEARCH: ["domain", "brain", "events", "context7", "tools", "delegation"],
    IntentType.REVIEW: ["domain", "brain", "events", "delegation"],
    IntentType.GENERAL: ["domain", "delegation"],
}


@dataclass
class FastPathResult:
    """Result from fast path assembly."""
    briefing: str
    sources_queried: list[str]
    sources_failed: list[str]
    latency_ms: int
    adapter_timings: dict = field(default_factory=dict)


class FastPathAssembler:
    """Pattern-based context assembly."""

    def __init__(self):
        self._registry = AdapterRegistry()

    async def assemble(self, prompt: str, analysis: PromptAnalysis,
                       predicted_intent: 'IntentType | None' = None) -> FastPathResult:
        """Assemble context using pattern-based rules."""
        start_time = time.time()

        # Check session state for context-dependent prompts.
        # Pass prompt so topic-overlap detection can surface relevant prior decisions.
        session_summary = self._get_session_summary(prompt)

        # Get adapters for this intent
        adapter_names = list(ADAPTER_RULES.get(analysis.intent_type, ["domain", "delegation"]))

        # If we have a predicted next intent, add bonus adapters (capped at 2)
        MAX_BONUS_ADAPTERS = 2
        if predicted_intent:
            bonus = ADAPTER_RULES.get(predicted_intent, [])
            bonus_count = 0
            for b in bonus:
                if b not in adapter_names and bonus_count < MAX_BONUS_ADAPTERS:
                    adapter_names.append(b)
                    bonus_count += 1

        # Within-call deduplication cache and timing accumulator (AC-1.1, AC-2.1)
        _call_cache: dict[str, list] = {}
        _timing_acc: dict[str, dict] = {}

        # Query adapters in parallel
        adapters_for_call = self._registry.get(adapter_names)
        tasks = []
        queried = []
        for name in adapter_names:
            if name in adapters_for_call:
                tasks.append(self._query_adapter(
                    adapters_for_call[name], name, prompt, _call_cache, _timing_acc))
                queried.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect items by source and track failures
        items_by_source = {}
        sources_queried = []
        sources_failed = []

        for name, result in zip(queried, results):
            if isinstance(result, Exception):
                sources_failed.append(name)
            else:
                sources_queried.append(name)
                if result:
                    items_by_source[name] = result[:10]

        # Intelligent selection: pick highest-relevance items within budget
        try:
            from budget_enforcer import BudgetEnforcer
            enforcer = BudgetEnforcer()
            selected = enforcer.select_items(items_by_source, "fast", reserved_chars=80)
        except Exception:
            selected = items_by_source  # Fallback: use all

        # Flatten for formatting
        all_items = []
        for items in selected.values():
            all_items.extend(items)

        # Extract active constraints from session summary (constraints only)
        active_constraints = []
        if session_summary:
            for line in session_summary.split("\n"):
                if "Constraints" in line or "constraints" in line:
                    # Strip markdown bold markers, extract the constraint text
                    constraint_text = line.split(":", 1)[-1].strip().strip("**").strip()
                    if constraint_text:
                        active_constraints = constraint_text.split("; ")
                    break

        # Format briefing
        briefing = self._format_briefing(prompt, analysis, all_items, active_constraints, sources_failed)

        latency_ms = int((time.time() - start_time) * 1000)

        return FastPathResult(
            briefing=briefing,
            sources_queried=sources_queried,
            sources_failed=sources_failed,
            latency_ms=latency_ms,
            adapter_timings=_timing_acc,
        )

    async def _query_adapter(
        self,
        adapter,
        name: str,
        prompt: str,
        call_cache: dict,
        timing_acc: dict,
        timeout: float = 0.5,
    ) -> list:
        """Query a single adapter via timed_query (handles cache, timing, bypass)."""
        return await timed_query(
            adapter, name, prompt, timeout,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=CACHE_BYPASS,
        )

    def _format_briefing(
        self,
        prompt: str,
        analysis: PromptAnalysis,
        items: list,
        active_constraints: list[str],
        failed_sources: list[str],
    ) -> str:
        """Format items into a compact authoritative briefing.

        Does not re-emit session history or last turn — those are already in
        Claude's context window. Only surfaces what is NOT already visible.
        """
        # Situation line (1 line)
        entities_str = f" | {', '.join(analysis.entities[:3])}" if analysis.entities else ""
        lines = [f"[{analysis.intent_type.value}{entities_str}]"]

        # Active constraints (user-stated rules that persist across turns)
        if active_constraints:
            lines.append(f"**Constraints:** {'; '.join(active_constraints)}")

        # Separate CLIs from knowledge items
        tools_items = [i for i in items if getattr(i, 'source', '') == "tools"]
        knowledge_items = [i for i in items if getattr(i, 'source', '') != "tools"]

        if knowledge_items:
            lines.append("")
            lines.append("**Relevant knowledge:**")
            for item in knowledge_items[:5]:  # Max 5 knowledge items on fast path
                title = getattr(item, 'title', str(item)[:50])
                snippet = getattr(item, 'summary', '') or getattr(item, 'excerpt', '')
                if snippet:
                    snippet = snippet[:70].replace("\n", " ").strip()
                    lines.append(f"- **{title}**: {snippet}")
                else:
                    lines.append(f"- **{title}**")

        if tools_items:
            cli_names = []
            for t in tools_items[:4]:
                name = getattr(t, 'title', '').replace(' available', '').split()[0]
                if name:
                    cli_names.append(name)
            if cli_names:
                lines.append("")
                lines.append(f"**Available CLIs:** {', '.join(cli_names)}")

        if failed_sources:
            lines.append(f"Unavailable: {', '.join(failed_sources)}")

        return "\n".join(lines)

    def _get_session_summary(self, prompt: str = "") -> str:
        """Build a lightweight session context summary for the fast path.

        Returns a short string (current task + last 2-3 decisions) if the
        session has established context, or empty string for new sessions.
        When a prompt is provided, also checks whether the prompt's topics
        overlap with session decision topics and surfaces those decisions first.
        Designed to keep the fast path context-aware without adapter queries.
        """
        try:
            from history_condenser import HistoryCondenser
            import os
            session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
            condenser = HistoryCondenser(session_id)
            state = condenser.get_session_state()

            parts = []
            if state.get("current_task"):
                parts.append(f"**Current task**: {state['current_task'][:120]}")

            decisions = state.get("decisions", [])
            if decisions:
                # When we have a prompt, check if any session topics overlap
                # with prompt terms to surface the most relevant past decisions first.
                if prompt and state.get("topics"):
                    prompt_words = set(prompt.lower().split())
                    session_topics = set(t.lower() for t in state["topics"])
                    topic_overlap = prompt_words & session_topics
                    if topic_overlap:
                        # Topic match: flag it so the user knows prior context applies
                        overlap_str = ", ".join(sorted(topic_overlap)[:3])
                        parts.append(f"**Prior context on**: {overlap_str}")

                recent = decisions[-3:]
                parts.append(f"**Recent decisions**: {'; '.join(recent)[:200]}")

            if state.get("file_scope"):
                files = state["file_scope"][-5:]
                parts.append(f"**Active files**: {', '.join(files)[:150]}")

            return "\n".join(parts)
        except Exception:
            return ""

    def _generate_suggestion(self, analysis: PromptAnalysis, items: list) -> str:
        """Generate at most one proactive suggestion based on context patterns."""
        # Check for relevant past decisions in memory items
        mem_items = [i for i in items if getattr(i, 'source', '') == 'mem']
        for item in mem_items:
            title = getattr(item, 'title', '')
            relevance = getattr(item, 'relevance', 0)
            if relevance > 0.6 and 'decision' in title.lower():
                return f"Related past decision found: {title[:80]}"

        # Check for delegation hints
        delegation_items = [i for i in items if getattr(i, 'source', '') == 'delegation']
        if delegation_items and analysis.confidence > 0.7:
            hint = delegation_items[0]
            title = getattr(hint, 'title', '')
            if title:
                return f"Consider delegating: {title[:80]}"

        return ""


async def main():
    """CLI for testing fast path."""
    import json

    if len(sys.argv) < 2:
        print("Usage: fast_path.py <prompt>")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])

    # Create mock analysis
    from router import Router
    router = Router()
    decision = router.route(prompt)

    assembler = FastPathAssembler()
    result = await assembler.assemble(prompt, decision.analysis)

    print(f"Latency: {result.latency_ms}ms")
    print(f"Sources: {result.sources_queried}")
    print(f"Failed: {result.sources_failed}")
    print()
    print(result.briefing)


if __name__ == "__main__":
    asyncio.run(main())
