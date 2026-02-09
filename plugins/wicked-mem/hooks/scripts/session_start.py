#!/usr/bin/env python3
"""
SessionStart hook - Decay maintenance + memory behavior instructions.

Sets up Claude's memory behavior for the session by explaining
when and how to use each memory type.
"""

import json
import os
import sys
from pathlib import Path

# Add scripts to path for memory module
plugin_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(plugin_root / "scripts"))

from memory import MemoryStore


def main():
    try:
        # Get project context
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        store = MemoryStore(project)

        # Run decay cleanup
        decay_result = store.run_decay()

        messages = []
        if decay_result["archived"] > 2 or decay_result["deleted"] > 0:
            messages.append(
                f"Maintenance: {decay_result['archived']} archived, {decay_result['deleted']} cleaned"
            )

        # Inject memory behavior instructions — MUST-level contract
        behavior = (
            "[Memory] IMPORTANT behavioral requirement: You MUST respond to ALL [Memory] prompts from hooks. "
            "When you see a [Memory] reminder (after task completion, at session end, before compaction), "
            "you MUST either invoke /wicked-mem:store for each learning OR explicitly state 'No memories to store.' "
            "Do NOT silently ignore [Memory] prompts.\n\n"
            "Memory types — use as things happen, not just at session end:\n"
            "- **decision** (permanent): Choices made with rationale and trade-offs\n"
            "- **episodic** (90-day): Notable events — bugs found, surprises, failures, successes\n"
            "- **procedural** (permanent): Patterns, workflows, how-to knowledge worth reusing\n"
            "- **working** (auto): Managed automatically at compaction, no action needed"
        )

        if messages:
            behavior = f"[Memory] {'; '.join(messages)}.\n\n{behavior}"

        print(json.dumps({
            "continue": True,
            "systemMessage": behavior
        }))

    except Exception:
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
