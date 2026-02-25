#!/usr/bin/env python3
"""
wicked-smaht v2: UserPromptSubmit hook.

Context replacement strategy — NOT accumulation:
1. Track content pressure (cumulative bytes, not just turns)
2. At MEDIUM pressure: advise compaction
3. At HIGH pressure: inject rich recovery briefing + compact directive
4. At CRITICAL pressure: insist on compaction before proceeding
5. After compaction: inject comprehensive recovery briefing from external state
   (condenser summary, mem, kanban, crew) so nothing is lost

The conversation is ephemeral. smaht's external state IS the source of truth.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add v2 scripts to path
scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(scripts_dir))

# Also add parent scripts for adapters
parent_scripts = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(parent_scripts))


def get_pressure_tracker():
    """Get pressure tracker, returns None if unavailable."""
    try:
        from context_pressure import PressureTracker
        return PressureTracker()
    except Exception:
        return None


def build_pressure_directive(level, pressure_kb: int, turn_count: int) -> str:
    """Build pressure-appropriate directive for Claude."""
    from context_pressure import PressureLevel

    if level == PressureLevel.MEDIUM:
        return (
            f"[Context pressure: {pressure_kb}KB ~MEDIUM, turn {turn_count}] "
            "Session has accumulated significant context. Consider saving key decisions "
            "with /wicked-mem:store and running /compact to free space."
        )
    elif level == PressureLevel.HIGH:
        return (
            f"[Context pressure: {pressure_kb}KB ~HIGH, turn {turn_count}] "
            "IMPORTANT: Context window is filling up. You MUST:\n"
            "1. Save any unsaved decisions/progress with /wicked-mem:store\n"
            "2. Run /compact to free context space\n"
            "Session state will be reconstructed from memory after compaction."
        )
    elif level == PressureLevel.CRITICAL:
        return (
            f"[Context pressure: {pressure_kb}KB ~CRITICAL, turn {turn_count}] "
            "MANDATORY: Context window is near capacity. Before doing ANYTHING else:\n"
            "1. Run /compact immediately\n"
            "Context will be rebuilt from session state after compaction. "
            "Do NOT proceed with the user's request until compaction is done."
        )
    return ""


def build_recovery_briefing(session_id: str) -> str:
    """Build comprehensive recovery briefing after compaction.

    Pulls from all external state stores to reconstruct what the
    conversation needs to continue seamlessly.
    """
    lines = ["## Session Recovery (post-compaction)", ""]

    # 1. Session summary from condenser (the ticket rail)
    try:
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        state = condenser.get_session_state()

        if state.get("current_task"):
            lines.append(f"**Current task**: {state['current_task']}")
        if state.get("topics"):
            lines.append(f"**Topics**: {', '.join(state['topics'][:8])}")
        if state.get("decisions"):
            lines.append(f"**Decisions**: {'; '.join(state['decisions'][:5])}")
        if state.get("active_constraints"):
            lines.append(f"**Constraints**: {'; '.join(state['active_constraints'][:5])}")
        if state.get("file_scope"):
            lines.append(f"**Active files**: {', '.join(state['file_scope'][-10:])}")
        if state.get("open_questions"):
            lines.append(f"**Open questions**: {'; '.join(state['open_questions'][:3])}")

        # Recent facts
        if state.get("facts"):
            facts_summary = state["facts"]
            if isinstance(facts_summary, dict) and facts_summary.get("count", 0) > 0:
                lines.append(f"**Facts extracted**: {facts_summary['count']}")

        lines.append("")

        # Condensed history (recent turns)
        history = condenser.get_condensed_history()
        if history and "(No summary yet)" not in history:
            # Cap history to keep recovery briefing focused
            history_lines = history.strip().split("\n")[:15]
            lines.extend(history_lines)
            lines.append("")

    except Exception as e:
        lines.append(f"(Session state partially unavailable: {str(e)[:50]})")
        lines.append("")

    lines.append("*Context was compacted. Above state reconstructed from session memory. "
                 "Use /wicked-mem:recall for past decisions, TaskList for active tasks.*")

    return "\n".join(lines)


def should_gather_context(prompt: str) -> bool:
    """Determine if we should gather context for this prompt."""
    if not prompt.strip():
        return False
    return True


async def gather_context(prompt: str, session_id: str) -> dict:
    """Gather context using v2 orchestrator."""
    try:
        from orchestrator import Orchestrator

        orchestrator = Orchestrator(session_id=session_id)
        result = await orchestrator.gather_context(prompt)

        return {
            "success": True,
            "path": result.path_used,
            "briefing": result.briefing,
            "latency_ms": result.latency_ms,
            "sources": result.sources_queried,
            "failed": result.sources_failed,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "briefing": "",
        }


def main():
    """Process user prompt and inject context."""
    # Read input from stdin
    try:
        input_data = json.loads(sys.stdin.read())
        prompt = input_data.get("prompt", "")
        session_id = input_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "default"))
    except Exception:
        print(json.dumps({"continue": True}))
        return

    if not prompt or not should_gather_context(prompt):
        print(json.dumps({"continue": True}))
        return

    # --- Pressure tracking ---
    tracker = get_pressure_tracker()
    pressure_directive = ""
    recovery_briefing = ""

    if tracker:
        from context_pressure import PressureLevel

        # Check for post-compaction recovery FIRST
        if tracker.was_just_compacted():
            recovery_briefing = build_recovery_briefing(session_id)

        # Record this turn's contribution (prompt size + estimated briefing)
        tracker.increment_turn(
            prompt_bytes=len(prompt.encode("utf-8", errors="replace")),
            briefing_bytes=0,  # updated after briefing is built
        )

        level = tracker.get_level()
        pressure_kb = tracker.get_pressure_kb()
        turn_count = tracker.get_turn_count()

        if level != PressureLevel.LOW:
            pressure_directive = build_pressure_directive(level, pressure_kb, turn_count)

    # --- Context gathering ---
    # At CRITICAL pressure, skip adapter queries to save time — just inject directive
    skip_gathering = False
    if tracker:
        level = tracker.get_level()
        if level == PressureLevel.CRITICAL and not recovery_briefing:
            skip_gathering = True

    if skip_gathering:
        briefing = ""
        path = "critical"
        sources = []
        failed = []
    else:
        result = asyncio.run(gather_context(prompt, session_id))
        if result["success"] and result.get("briefing"):
            briefing = result["briefing"]
            path = result["path"]
            sources = result.get("sources", [])
            failed = result.get("failed", [])
        else:
            briefing = ""
            path = "error"
            sources = result.get("sources", [])
            failed = result.get("failed", [])
            if result.get("error"):
                print(f"smaht: context assembly failed: {result['error']}", file=sys.stderr)

    # --- Budget enforcement ---
    if briefing:
        try:
            from budget_enforcer import BudgetEnforcer
            enforcer = BudgetEnforcer()
            briefing = enforcer.enforce(briefing, path)
        except Exception as e:
            print(f"smaht: budget enforcement failed: {e}", file=sys.stderr)
            char_budgets = {"hot": 400, "fast": 2000, "slow": 4000}
            max_chars = char_budgets.get(path, 2000) - 200
            briefing = briefing[:max_chars]

    # --- Compose final output ---
    parts = []

    # Recovery briefing takes priority (reconstructs context after compaction)
    if recovery_briefing:
        parts.append(recovery_briefing)

    # Normal briefing
    if briefing:
        parts.append(briefing)

    # Pressure directive (always last — it's the instruction to act)
    if pressure_directive:
        parts.append(pressure_directive)

    if not parts:
        # Nothing to inject — at least pass through any error context
        if failed:
            sanitized = f"Context sources failed: {', '.join(failed)}".replace('</system-reminder>', '')
            print(json.dumps({
                "additionalContext": f"<system-reminder>\n{sanitized}\n</system-reminder>",
                "continue": True
            }))
        else:
            print(json.dumps({"continue": True}))
        return

    # Build metadata header
    if tracker:
        level = tracker.get_level()
        pressure_kb = tracker.get_pressure_kb()
        turn_count = tracker.get_turn_count()
    else:
        level = None
        pressure_kb = 0
        turn_count = 0

    source_badge = ""
    if sources:
        source_badge = f"sources:{','.join(sources)}"
        if failed:
            source_badge += f"|failed:{','.join(failed)}"

    enforced_tokens = sum(len(p) for p in parts) // 4
    budget_tokens = {"hot": 100, "fast": 500, "slow": 1000, "critical": 0, "error": 500}.get(path, 500)

    level_str = level.value if level else "unknown"
    header = (
        f"<!-- wicked-smaht v2 | path={path} | {source_badge} "
        f"| tok:{enforced_tokens}/{budget_tokens} | turn={turn_count} "
        f"| pressure:{pressure_kb}KB/{level_str} -->"
    )

    combined = "\n\n".join(parts)
    sanitized = combined.replace('</system-reminder>', '')

    # Update pressure tracker with actual briefing size
    if tracker:
        tracker.add_content(len(sanitized.encode("utf-8", errors="replace")))

    output = {
        "additionalContext": f"<system-reminder>\n{header}\n{sanitized}\n</system-reminder>",
        "continue": True
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
