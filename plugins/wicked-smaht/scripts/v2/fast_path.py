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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add parent to path for adapter imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from router import IntentType, PromptAnalysis


# Adapter selection rules by intent
ADAPTER_RULES = {
    IntentType.DEBUGGING: ["search", "mem", "delegation"],
    IntentType.IMPLEMENTATION: ["search", "mem", "kanban", "context7", "startah", "delegation"],
    IntentType.PLANNING: ["kanban", "crew", "jam", "delegation"],
    IntentType.RESEARCH: ["search", "mem", "context7", "startah", "delegation"],
    IntentType.REVIEW: ["search", "kanban", "delegation"],
    IntentType.GENERAL: ["search", "delegation"],
}


@dataclass
class FastPathResult:
    """Result from fast path assembly."""
    briefing: str
    sources_queried: list[str]
    sources_failed: list[str]
    latency_ms: int


class FastPathAssembler:
    """Pattern-based context assembly."""

    def __init__(self):
        self.adapters = self._load_adapters()

    def _load_adapters(self) -> dict:
        """Load available adapters individually for graceful degradation."""
        adapters = {}
        adapter_modules = {
            "mem": "mem_adapter",
            "search": "search_adapter",
            "kanban": "kanban_adapter",
            "jam": "jam_adapter",
            "crew": "crew_adapter",
            "context7": "context7_adapter",
            "startah": "startah_adapter",
            "delegation": "delegation_adapter",
        }
        for name, module_name in adapter_modules.items():
            try:
                mod = __import__(f"adapters.{module_name}", fromlist=[module_name])
                adapters[name] = mod
            except ImportError as e:
                print(f"smaht: adapter '{name}' unavailable: {e}", file=sys.stderr)
        return adapters

    async def assemble(self, prompt: str, analysis: PromptAnalysis,
                       predicted_intent: 'IntentType | None' = None) -> FastPathResult:
        """Assemble context using pattern-based rules."""
        import time
        start_time = time.time()

        # Get adapters for this intent
        adapter_names = list(ADAPTER_RULES.get(analysis.intent_type, ["search"]))

        # If we have a predicted next intent, add bonus adapters from that intent's rules
        if predicted_intent:
            bonus = ADAPTER_RULES.get(predicted_intent, [])
            for b in bonus:
                if b not in adapter_names:
                    adapter_names.append(b)

        # Query adapters in parallel
        tasks = []
        queried = []
        for name in adapter_names:
            if name in self.adapters:
                tasks.append(self._query_adapter(name, prompt))
                queried.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect items and track failures - differentiate empty from failed
        all_items = []
        sources_queried = []
        sources_failed = []

        for name, result in zip(queried, results):
            if isinstance(result, Exception):
                sources_failed.append(name)
            else:
                # Successfully queried (even if empty)
                sources_queried.append(name)
                if result:
                    all_items.extend(result[:10])  # Cap per source

        # Format briefing
        briefing = self._format_briefing(prompt, analysis, all_items, sources_failed)

        latency_ms = int((time.time() - start_time) * 1000)

        return FastPathResult(
            briefing=briefing,
            sources_queried=sources_queried,
            sources_failed=sources_failed,
            latency_ms=latency_ms,
        )

    async def _query_adapter(self, name: str, prompt: str, timeout: float = 0.5):
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
        items: list,
        failed_sources: list[str]
    ) -> str:
        """Format items into a simple briefing."""
        lines = [
            "# Context Briefing (fast)",
            "",
            "## Situation",
            f"**Intent**: {analysis.intent_type.value} (confidence: {analysis.confidence:.2f})",
        ]

        if analysis.entities:
            lines.append(f"**Entities**: {', '.join(analysis.entities[:5])}")

        lines.append("")

        # Group items by source (with safe attribute access)
        by_source: dict[str, list] = {}
        for item in items:
            source = getattr(item, 'source', 'unknown')
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(item)

        # Format each source
        source_labels = {
            "mem": "Memories",
            "search": "Code & Docs",
            "kanban": "Tasks",
            "jam": "Brainstorms",
            "crew": "Project State",
            "context7": "External Docs",
            "startah": "Available CLIs",
            "delegation": "Delegation Hints",
        }

        if by_source:
            lines.append("## Relevant Context")
            lines.append("")

            for source, source_items in by_source.items():
                label = source_labels.get(source, source)
                lines.append(f"### {label}")

                for item in source_items[:5]:  # Max 5 per source
                    # Safe attribute access with fallbacks
                    title = getattr(item, 'title', str(item)[:50])
                    summary = getattr(item, 'summary', '')[:100]
                    lines.append(f"- **{title}**: {summary}")

                lines.append("")

        # Proactive suggestion (max 1 per turn)
        suggestion = self._generate_suggestion(analysis, items)
        if suggestion:
            lines.append("## Suggestion")
            lines.append(f"*{suggestion}*")
            lines.append("")

        # Note failures
        if failed_sources:
            lines.append("## Uncertainties")
            lines.append(f"*Unavailable sources: {', '.join(failed_sources)}*")
            lines.append("")

        return "\n".join(lines)

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
