#!/usr/bin/env python3
"""
wicked-smaht v2: Main Orchestrator

Entry point for the tiered hybrid context management system.

Usage:
    orchestrator.py gather <prompt> [--session <id>] [--json]
    orchestrator.py route <prompt> [--json]
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from router import Router, PathDecision, RouterDecision
from fast_path import FastPathAssembler, FastPathResult
from slow_path import SlowPathAssembler, SlowPathResult
from history_condenser import HistoryCondenser


@dataclass
class ContextResult:
    """Result from context gathering."""
    path_used: str
    briefing: str
    sources_queried: list[str]
    sources_failed: list[str]
    latency_ms: int
    routing_reason: str


class Orchestrator:
    """Main orchestrator for wicked-smaht v2."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.condenser = HistoryCondenser(session_id)
        # Seed router with session topics for proper novelty detection
        session_topics = self.condenser.summary.topics
        self.router = Router(session_topics=session_topics)
        self.fast_path = FastPathAssembler()
        self.slow_path = SlowPathAssembler()

    async def gather_context(self, prompt: str) -> ContextResult:
        """Gather context for a prompt using tiered hybrid approach."""
        import time
        start_time = time.time()

        # Route the prompt
        decision = self.router.route(prompt)

        # Execute appropriate path with error handling
        try:
            if decision.path == PathDecision.HOT:
                # Hot path: session state only, no adapter queries
                state = self.condenser.get_session_state()
                briefing = self._format_hot_briefing(state)
                path_used = "hot"
                sources_queried = ["session_state"]
                sources_failed = []
            elif decision.path == PathDecision.FAST:
                result = await self.fast_path.assemble(prompt, decision.analysis)
                path_used = "fast"
                briefing = result.briefing
                sources_queried = result.sources_queried
                sources_failed = result.sources_failed
            else:
                result = await self.slow_path.assemble(prompt, decision.analysis, self.condenser)
                path_used = "slow"
                briefing = result.briefing
                sources_queried = result.sources_queried
                sources_failed = result.sources_failed
        except Exception as e:
            # Fallback on path execution failure
            path_used = decision.path.value
            briefing = f"# Context Briefing (error)\n\n*Context assembly failed: {e}*\n\nProceeding without enriched context."
            sources_queried = []
            sources_failed = ["assembly"]

        # Update session with entities
        self.router.update_session_topics(decision.analysis.entities)

        total_latency = int((time.time() - start_time) * 1000)

        return ContextResult(
            path_used=path_used,
            briefing=briefing,
            sources_queried=sources_queried,
            sources_failed=sources_failed,
            latency_ms=total_latency,
            routing_reason=decision.reason,
        )

    def _format_hot_briefing(self, state: dict) -> str:
        """Format minimal briefing from session state for hot path.

        Only includes the working state (current task, constraints, file scope).
        No adapter queries, no history dump — just the ticket rail.
        """
        lines = []
        if state.get("current_task"):
            lines.append(f"**Current task**: {state['current_task']}")
        if state.get("decisions"):
            lines.append(f"**Recent decisions**: {'; '.join(state['decisions'][-2:])}")
        if state.get("active_constraints"):
            lines.append(f"**Constraints**: {'; '.join(state['active_constraints'][-3:])}")
        if state.get("file_scope"):
            lines.append(f"**Active files**: {', '.join(state['file_scope'][-5:])}")
        return "\n".join(lines) if lines else "(Session state empty — new session)"

    def add_turn(self, user_msg: str, assistant_msg: str, tools_used: list[str] = None):
        """Record a turn in session history."""
        self.condenser.add_turn(user_msg, assistant_msg, tools_used)


def main():
    """CLI for orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="wicked-smaht v2 orchestrator")
    parser.add_argument("command", choices=["gather", "route"], help="Command to run")
    parser.add_argument("prompt", nargs="?", help="User prompt")
    parser.add_argument("--session", default="default", help="Session ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.prompt:
        # Read from stdin
        args.prompt = sys.stdin.read().strip()

    if not args.prompt:
        print("Error: No prompt provided", file=sys.stderr)
        sys.exit(1)

    if args.command == "route":
        # Just route, don't gather
        router = Router()
        decision = router.route(args.prompt)

        if args.json:
            print(json.dumps({
                "path": decision.path.value,
                "reason": decision.reason,
                "analysis": {
                    "intent": decision.analysis.intent_type.value,
                    "confidence": decision.analysis.confidence,
                    "word_count": decision.analysis.word_count,
                    "entity_count": decision.analysis.entity_count,
                    "entities": decision.analysis.entities,
                }
            }, indent=2))
        else:
            print(f"Path: {decision.path.value}")
            print(f"Reason: {decision.reason}")
            print(f"Intent: {decision.analysis.intent_type.value} ({decision.analysis.confidence:.2f})")

    elif args.command == "gather":
        # Full context gathering
        orchestrator = Orchestrator(session_id=args.session)
        result = asyncio.run(orchestrator.gather_context(args.prompt))

        if args.json:
            print(json.dumps({
                "path_used": result.path_used,
                "latency_ms": result.latency_ms,
                "routing_reason": result.routing_reason,
                "sources_queried": result.sources_queried,
                "sources_failed": result.sources_failed,
                "briefing": result.briefing,
            }, indent=2))
        else:
            print(f"Path: {result.path_used}")
            print(f"Latency: {result.latency_ms}ms")
            print(f"Reason: {result.routing_reason}")
            print(f"Sources: {result.sources_queried}")
            if result.sources_failed:
                print(f"Failed: {result.sources_failed}")
            print()
            print(result.briefing)


if __name__ == "__main__":
    main()
