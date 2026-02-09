#!/usr/bin/env python3
"""
Stop hook - Run memory decay and prompt for session reflection.

Decay maintenance is the only script logic needed.
Memory extraction intelligence lives in the prompt.
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
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        hook_input = {}

    messages = []

    # Run decay maintenance
    try:
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        store = MemoryStore(project)
        result = store.run_decay()
        if result["archived"] > 0 or result["deleted"] > 0:
            messages.append(f"Decay: {result['archived']} archived, {result['deleted']} cleaned")
    except Exception as e:
        print(f"[wicked-mem] decay error: {e}", file=sys.stderr)

    # Directive prompt — analyze completed work, not vague reflection
    reflection = (
        "[Memory] REQUIRED: Session ending. Run TaskList to review completed tasks from this session. "
        "For each completed task, evaluate: did it produce a decision, gotcha, or reusable pattern? "
        "Store each learning with /wicked-mem:store (type: decision, procedural, or episodic). "
        "If no tasks completed or no learnings found, state 'No memories to store.' Do NOT skip silently."
    )

    if messages:
        reflection = f"[Memory] {'; '.join(messages)}. {reflection}"

    print(json.dumps({"systemMessage": reflection}))
    sys.exit(0)


if __name__ == "__main__":
    main()
