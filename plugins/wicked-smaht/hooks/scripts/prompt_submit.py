#!/usr/bin/env python3
"""
wicked-smaht v2: UserPromptSubmit hook.

Uses tiered hybrid context management:
- Fast path for simple, clear requests (<1s)
- Slow path for complex/ambiguous requests (2-4s)
- Context budget warnings when sessions run long
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# Add v2 scripts to path
scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(scripts_dir))

# Also add parent scripts for adapters
parent_scripts = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(parent_scripts))


# Turn-based context budget thresholds
CONTEXT_WARNING_TURN = 30
CONTEXT_CRITICAL_TURN = 50


def get_turn_tracker_path() -> Path:
    """Get path to smaht turn tracker (per-session)."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    return Path(tempfile.gettempdir()) / f"wicked-smaht-turns-{session_id}"


def increment_and_check_turns() -> tuple:
    """Increment turn count and return (count, warning_message_or_None)."""
    tracker = get_turn_tracker_path()
    try:
        count = int(tracker.read_text().strip()) + 1
    except (FileNotFoundError, ValueError):
        count = 1
    tracker.write_text(str(count))

    if count >= CONTEXT_CRITICAL_TURN:
        return count, (
            "[Context] Session is very long (~{} turns). "
            "Context window likely filling up. Consider: "
            "1) Saving progress with /wicked-mem:store, "
            "2) Starting a fresh session for remaining work.".format(count)
        )
    elif count >= CONTEXT_WARNING_TURN:
        return count, (
            "[Context] Long session (~{} turns). "
            "Consider summarizing key decisions with /wicked-mem:store "
            "to preserve progress if context runs low.".format(count)
        )
    return count, None


def should_gather_context(prompt: str) -> bool:
    """Determine if we should gather context for this prompt."""
    # Skip very short prompts
    if len(prompt.strip()) < 5:
        return False

    # Skip slash commands (they have their own context)
    if prompt.strip().startswith("/"):
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
        prompt = input_data.get("user_prompt", "")
        session_id = input_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "default"))
    except Exception:
        print(json.dumps({"continue": True}))
        return

    # Check if we should gather context
    if not prompt or not should_gather_context(prompt):
        print(json.dumps({"continue": True}))
        return

    # Check context budget
    turn_count, context_warning = increment_and_check_turns()

    # Gather context
    result = asyncio.run(gather_context(prompt, session_id))

    if not result["success"] or not result["briefing"]:
        # Even without briefing, emit context warning if needed
        if context_warning:
            print(json.dumps({
                "continue": True,
                "message": f"<system-reminder>\n{context_warning}\n</system-reminder>"
            }))
        else:
            print(json.dumps({"continue": True}))
        return

    # Format output
    briefing = result["briefing"]
    path = result["path"]
    latency = result["latency_ms"]

    # Add metadata header
    header = f"<!-- wicked-smaht v2 | path={path} | latency={latency}ms | turn={turn_count} -->"

    # Append context warning if applicable
    if context_warning:
        briefing += f"\n\n{context_warning}"

    output = {
        "continue": True,
        "message": f"<system-reminder>\n{header}\n{briefing}\n</system-reminder>"
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
