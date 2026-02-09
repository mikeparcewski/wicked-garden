#!/usr/bin/env python3
"""
wicked-smaht v2: Slow Path Assembler

Comprehensive context assembly for complex requests.
Target latency: 2-4s

Strategy:
1. Query ALL adapters in parallel with longer timeouts
2. Gather condensed history
3. Format comprehensive briefing with detailed context
4. Pattern-based compression (no external LLM calls)

Key difference from fast path:
- Longer adapter timeout (2s vs 500ms)
- All adapters queried (not just intent-specific)
- More items per source (10 vs 5)
- Richer formatting with history context
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add parent to path for adapter imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from history_condenser import HistoryCondenser
from router import PromptAnalysis


@dataclass
class SlowPathResult:
    """Result from slow path assembly."""
    briefing: str
    sources_queried: list[str]
    sources_failed: list[str]
    latency_ms: int


class SlowPathAssembler:
    """Comprehensive pattern-based context assembly."""

    def __init__(self):
        self.adapters = self._load_adapters()

    def _load_adapters(self) -> dict:
        """Load available adapters."""
        adapters = {}
        try:
            from adapters import mem_adapter, search_adapter, kanban_adapter, jam_adapter, crew_adapter, context7_adapter
            adapters["mem"] = mem_adapter
            adapters["search"] = search_adapter
            adapters["kanban"] = kanban_adapter
            adapters["jam"] = jam_adapter
            adapters["crew"] = crew_adapter
            adapters["context7"] = context7_adapter
        except ImportError as e:
            print(f"Warning: Could not load adapters: {e}", file=sys.stderr)
        return adapters

    async def assemble(
        self,
        prompt: str,
        analysis: PromptAnalysis,
        condenser: HistoryCondenser,
        timeout: float = 5.0
    ) -> SlowPathResult:
        """Assemble comprehensive context using pattern-based rules."""
        import time
        start_time = time.time()

        # Query ALL adapters in parallel with longer timeout
        adapter_timeout = min(2.0, timeout / 2)  # 2s per adapter max
        tasks = {}
        for name, adapter in self.adapters.items():
            tasks[name] = self._query_adapter(name, prompt, timeout=adapter_timeout)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Collect raw data - differentiate empty from failed
        all_items = {}
        sources_queried = []
        sources_failed = []

        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                sources_failed.append(name)
                all_items[name] = []
            else:
                sources_queried.append(name)
                all_items[name] = result if result else []

        # Get history context
        condensed_history = condenser.get_condensed_history()
        last_turn = condenser.get_last_turn()

        # Format comprehensive briefing
        briefing = self._format_briefing(
            prompt, analysis, all_items, condensed_history, last_turn, sources_failed
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return SlowPathResult(
            briefing=briefing,
            sources_queried=sources_queried,
            sources_failed=sources_failed,
            latency_ms=latency_ms,
        )

    async def _query_adapter(self, name: str, prompt: str, timeout: float = 2.0):
        """Query a single adapter with timeout."""
        adapter = self.adapters.get(name)
        if not adapter:
            return []

        try:
            return await asyncio.wait_for(
                adapter.query(prompt),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise Exception(f"{name} adapter timeout")
        except Exception as e:
            raise Exception(f"{name} adapter failed: {e}")

    def _format_briefing(
        self,
        prompt: str,
        analysis: PromptAnalysis,
        items_by_source: dict,
        condensed_history: str,
        last_turn,
        sources_failed: list[str]
    ) -> str:
        """Format comprehensive briefing with all available context."""
        lines = [
            "# Context Briefing",
            "",
        ]

        # Situation
        lines.extend([
            "## Situation",
            f"**Intent**: {analysis.intent_type.value} (confidence: {analysis.confidence:.2f})",
        ])

        if analysis.entities:
            lines.append(f"**Entities**: {', '.join(analysis.entities[:10])}")

        if analysis.is_compound:
            lines.append("**Note**: Multi-part request detected")

        if analysis.requires_history:
            lines.append("**Note**: References conversation history")

        lines.append("")

        # Last turn context (if available)
        if last_turn:
            lines.extend([
                "## Recent Context",
                f"**Last user message**: {last_turn.user[:150]}...",
                f"**Last response**: {last_turn.assistant[:200]}...",
                "",
            ])

        # Condensed history (if non-empty)
        if condensed_history and condensed_history.strip():
            lines.extend([
                "## Session History",
                condensed_history,
                "",
            ])

        # Source-specific context
        source_labels = {
            "mem": "Memories",
            "search": "Code & Docs",
            "kanban": "Tasks",
            "jam": "Brainstorms",
            "crew": "Project State",
            "context7": "External Docs",
        }

        has_context = any(items for items in items_by_source.values())
        if has_context:
            lines.append("## Relevant Context")
            lines.append("")

            for source, items in items_by_source.items():
                if not items:
                    continue

                label = source_labels.get(source, source)
                lines.append(f"### {label}")

                for item in items[:10]:  # Max 10 per source in slow path
                    # Safe attribute access with fallbacks
                    title = getattr(item, 'title', str(item)[:50])
                    summary = getattr(item, 'summary', '')
                    excerpt = getattr(item, 'excerpt', '')
                    relevance = getattr(item, 'relevance', 0.0)

                    # More detailed output in slow path
                    if relevance > 0:
                        lines.append(f"- **{title}** (relevance: {relevance:.2f})")
                    else:
                        lines.append(f"- **{title}**")

                    if summary:
                        lines.append(f"  {summary[:200]}")

                    if excerpt:
                        # Include more excerpt in slow path
                        excerpt_clean = excerpt[:400].replace("\n", " ").strip()
                        if excerpt_clean:
                            lines.append(f"  > {excerpt_clean}")

                lines.append("")

        # Considerations based on analysis
        considerations = self._derive_considerations(analysis, items_by_source)
        if considerations:
            lines.append("## Considerations")
            for consideration in considerations:
                lines.append(f"- {consideration}")
            lines.append("")

        # Uncertainties
        uncertainties = []
        if sources_failed:
            uncertainties.append(f"Unavailable sources: {', '.join(sources_failed)}")
        if analysis.confidence < 0.7:
            uncertainties.append(f"Intent confidence is moderate ({analysis.confidence:.2f})")
        if analysis.competing_intents > 0:
            uncertainties.append(f"{analysis.competing_intents} competing intent(s) detected")
        if analysis.is_novel:
            uncertainties.append("Topic appears novel (not seen in session)")

        if uncertainties:
            lines.append("## Uncertainties")
            for u in uncertainties:
                lines.append(f"- {u}")
            lines.append("")

        return "\n".join(lines)

    def _derive_considerations(
        self,
        analysis: PromptAnalysis,
        items_by_source: dict
    ) -> list[str]:
        """Derive considerations from analysis and context."""
        considerations = []

        # Intent-specific considerations
        if analysis.intent_type.value == "planning":
            considerations.append("Planning request - consider trade-offs and alternatives")

        if analysis.intent_type.value == "debugging":
            # Look for related memories or past issues
            mem_items = items_by_source.get("mem", [])
            if mem_items:
                considerations.append("Past memories may contain relevant solutions")

        if analysis.intent_type.value == "implementation":
            # Check for existing patterns in search
            search_items = items_by_source.get("search", [])
            if search_items:
                considerations.append("Existing code patterns found - consider consistency")

            # Check kanban for related tasks
            kanban_items = items_by_source.get("kanban", [])
            if kanban_items:
                considerations.append("Related tasks exist - check for conflicts or dependencies")

        if analysis.is_compound:
            considerations.append("Multi-part request - may need sequential handling")

        if analysis.entity_count > 5:
            considerations.append(f"Many entities referenced ({analysis.entity_count}) - ensure comprehensive coverage")

        return considerations


async def main():
    """CLI for testing slow path."""
    if len(sys.argv) < 2:
        print("Usage: slow_path.py <prompt> [session_id]")
        sys.exit(1)

    prompt = sys.argv[1]
    session_id = sys.argv[2] if len(sys.argv) > 2 else "test-session"

    from router import Router
    router = Router()
    decision = router.route(prompt)

    condenser = HistoryCondenser(session_id)
    assembler = SlowPathAssembler()

    result = await assembler.assemble(prompt, decision.analysis, condenser)

    print(f"Latency: {result.latency_ms}ms")
    print(f"Sources: {result.sources_queried}")
    print(f"Failed: {result.sources_failed}")
    print()
    print(result.briefing)


if __name__ == "__main__":
    asyncio.run(main())
