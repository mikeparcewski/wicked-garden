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
            else:
                sources_queried.append(name)
                if result:
                    all_items[name] = result

        # Get history context
        condensed_history = condenser.get_condensed_history()
        last_turn = condenser.get_last_turn()

        # Cap condensed history at source to prevent budget overrun
        # History producer (summary + lanes + facts + turns) grows unbounded
        MAX_HISTORY_CHARS = 1200  # ~300 tokens max for session history
        if condensed_history and len(condensed_history) > MAX_HISTORY_CHARS:
            condensed_history = condensed_history[:MAX_HISTORY_CHARS].rsplit('\n', 1)[0]

        # Intelligent selection: pick highest-relevance items within budget
        # Reserve chars for situation + history + recent context
        reserved = 600  # situation + last turn + capped session history
        try:
            from budget_enforcer import BudgetEnforcer
            enforcer = BudgetEnforcer()
            selected_items = enforcer.select_items(all_items, "slow", reserved_chars=reserved)
        except Exception:
            selected_items = all_items  # Fallback: use all

        # Format comprehensive briefing
        briefing = self._format_briefing(
            prompt, analysis, selected_items, condensed_history, last_turn, sources_failed
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
        # Compact situation line
        entities_str = f" | {', '.join(analysis.entities[:3])}" if analysis.entities else ""
        notes = []
        if analysis.is_compound:
            notes.append("multi-part")
        if analysis.requires_history:
            notes.append("refs history")
        notes_str = f" | {', '.join(notes)}" if notes else ""
        lines = [
            f"[{analysis.intent_type.value}{entities_str}{notes_str}]",
            "",
        ]

        # Last turn context (if available, with system-reminder stripping)
        if last_turn:
            import re as _re
            clean_assistant = _re.sub(
                r'<system-reminder>.*?</system-reminder>', '',
                last_turn.assistant or '', flags=_re.DOTALL
            ).strip()
            lines.extend([
                "## Recent Context",
                f"**Last**: {last_turn.user[:100]}",
                f"**Response**: {clean_assistant[:150]}",
                "",
            ])

        # Condensed history (only if non-empty and has real content)
        if condensed_history and "(No summary yet)" not in condensed_history and condensed_history.strip():
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
            "startah": "Available CLIs",
            "delegation": "Delegation Hints",
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

                for item in items[:5]:  # Max 5 per source
                    # Safe attribute access with fallbacks
                    title = getattr(item, 'title', str(item)[:50])
                    summary = getattr(item, 'summary', '')
                    excerpt = getattr(item, 'excerpt', '')

                    lines.append(f"- **{title}**")

                    if summary:
                        lines.append(f"  {summary[:100]}")

                    if excerpt:
                        excerpt_clean = excerpt[:100].replace("\n", " ").strip()
                        if excerpt_clean:
                            lines.append(f"  > {excerpt_clean}")

                lines.append("")

        # Note failures (single line, no section header — only for actual source failures)
        if sources_failed:
            lines.append(f"Unavailable: {', '.join(sources_failed)}")
            lines.append("")

        return "\n".join(lines)



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
