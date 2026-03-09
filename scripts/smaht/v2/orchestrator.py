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
import time
from dataclasses import dataclass
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
    items_pre_loaded: int = 0


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
        start_time = time.time()

        # Route the prompt
        decision = self.router.route(prompt)

        # Update condenser from prompt (populates session state for HOT path and future turns)
        self.condenser.update_from_prompt(
            prompt,
            intent_type=decision.analysis.intent_type.value
        )

        # Get intent prediction for bonus adapters
        predicted_intent = self.router.predict_next_intent()

        # Execute appropriate path with error handling
        items_pre_loaded = 0
        adapter_timings: Optional[dict] = None
        try:
            if decision.path == PathDecision.HOT:
                # Hot path: session state only, no adapter queries (AC-1.6)
                state = self.condenser.get_session_state()
                briefing = self._format_hot_briefing(state)
                path_used = "hot"
                sources_queried = ["session_state"]
                sources_failed = []
                # No adapter timings for HOT path
            elif decision.path == PathDecision.FAST:
                result = await self.fast_path.assemble(prompt, decision.analysis, predicted_intent)
                path_used = "fast"
                briefing = result.briefing
                sources_queried = result.sources_queried
                sources_failed = result.sources_failed
                items_pre_loaded = len(sources_queried)
                adapter_timings = result.adapter_timings
            else:
                result = await self.slow_path.assemble(prompt, decision.analysis, self.condenser)
                path_used = "slow"
                briefing = result.briefing
                sources_queried = result.sources_queried
                sources_failed = result.sources_failed
                items_pre_loaded = len(sources_queried)
                adapter_timings = result.adapter_timings
        except Exception as e:
            # Fallback on path execution failure
            path_used = decision.path.value
            briefing = f"# Context Briefing (error)\n\n*Context assembly failed: {e}*\n\nProceeding without enriched context."
            sources_queried = []
            sources_failed = ["assembly"]

        # Update session with entities and record intent for prediction
        self.router.update_session_topics(decision.analysis.entities)
        self.router.record_intent(decision.analysis.intent_type)

        # Track session metrics (adapter_timings=None for HOT path and error path)
        self._update_metrics(items_pre_loaded, adapter_timings=adapter_timings)

        total_latency = int((time.time() - start_time) * 1000)

        return ContextResult(
            path_used=path_used,
            briefing=briefing,
            sources_queried=sources_queried,
            sources_failed=sources_failed,
            latency_ms=total_latency,
            routing_reason=decision.reason,
            items_pre_loaded=items_pre_loaded,
        )

    def _format_hot_briefing(self, state: dict) -> str:
        """Format minimal briefing from session state for hot path.

        Only includes the working state (current task, constraints, file scope).
        No adapter queries, no history dump — just the ticket rail.
        """
        lines = []
        if state.get("current_task"):
            lines.append(f"**Current task**: {state['current_task'][:120]}")
        if state.get("decisions"):
            decisions_str = '; '.join(state['decisions'][-2:])[:200]
            lines.append(f"**Recent decisions**: {decisions_str}")
        if state.get("active_constraints"):
            constraints_str = '; '.join(state['active_constraints'][-3:])[:200]
            lines.append(f"**Constraints**: {constraints_str}")
        if state.get("file_scope"):
            files_str = ', '.join(state['file_scope'][-5:])[:150]
            lines.append(f"**Active files**: {files_str}")
        return "\n".join(lines) if lines else "(Session state empty — new session)"

    def _update_metrics(self, items_pre_loaded: int, adapter_timings: "dict | None" = None):
        """Update session-level metrics for turn savings + per-adapter timing (AC-2.1)."""
        metrics_path = self.condenser.session_dir / "metrics.json"
        try:
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text())
            else:
                metrics = {
                    "items_pre_loaded": 0,
                    "queries_made": 0,
                    "estimated_turns_saved": 0,
                    "adapter_timings": {},
                }

            metrics.setdefault("adapter_timings", {})
            metrics["items_pre_loaded"] += items_pre_loaded
            metrics["queries_made"] += 1
            # Rough estimate: each pre-loaded source saves ~1.5 manual lookups
            metrics["estimated_turns_saved"] = round(metrics["items_pre_loaded"] * 1.5)

            if adapter_timings:
                for name, data in adapter_timings.items():
                    acc = metrics["adapter_timings"].setdefault(name, {
                        "total_ms": 0, "call_count": 0, "avg_ms": 0.0,
                        "cache_hits": 0, "failures": 0,
                    })
                    acc["total_ms"] += data.get("total_ms", 0)
                    acc["call_count"] += data.get("call_count", 0)
                    acc["cache_hits"] += data.get("cache_hits", 0)
                    acc["failures"] += data.get("failures", 0)
                    # Guard against division-by-zero when only cache hits exist (Gap G-3)
                    if acc["call_count"] > 0:
                        acc["avg_ms"] = round(acc["total_ms"] / acc["call_count"], 1)

            self.condenser._atomic_write(metrics_path, json.dumps(metrics, indent=2))
        except Exception:
            pass  # Metrics are nice-to-have, never block (AC-2.4)

    def get_session_metrics(self) -> dict:
        """Get accumulated session metrics for /debug display."""
        metrics_path = self.condenser.session_dir / "metrics.json"
        try:
            if metrics_path.exists():
                return json.loads(metrics_path.read_text())
        except Exception:
            pass  # fail open: metrics unavailable, return defaults
        return {"items_pre_loaded": 0, "queries_made": 0, "estimated_turns_saved": 0, "adapter_timings": {}}

    def add_turn(self, user_msg: str, assistant_msg: str, tools_used: list[str] = None, intent_type: str = ""):
        """Record a turn in session history."""
        self.condenser.add_turn(user_msg, assistant_msg, tools_used, intent_type=intent_type)

    def gather_context_sync(self, prompt: str) -> "ContextResult":
        """Synchronous bridge for hook invocation.

        Safe because Claude Code hook scripts run in fresh subprocesses — there is
        no running asyncio event loop when the hook starts. Uses asyncio.run() as
        the canonical stdlib-safe entry point.

        Defensive: if a running loop is detected (e.g. future executor model),
        falls back to run_coroutine_threadsafe rather than crashing.

        See architecture.md — Async Bridge Design for full rationale.
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Unexpected running loop (future Claude Code executor variant).
            # Delegate to the existing loop via a thread-safe future.
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self.gather_context(prompt), loop
            )
            return future.result(timeout=10)

        return asyncio.run(self.gather_context(prompt))


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
