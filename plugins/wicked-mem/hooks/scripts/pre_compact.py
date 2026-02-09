#!/usr/bin/env python3
"""
PreCompact hook - Save working memory and prompt for learning extraction.

Two jobs:
1. Automatically save a working memory snapshot (context preservation)
2. Prompt Claude to store any decisions/episodic/procedural memories
   that haven't been captured yet
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add scripts to path
plugin_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(plugin_root / "scripts"))

from memory import MemoryStore, MemoryType, Scope, Importance


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}

    # Auto-save working memory (context snapshot before compression)
    context = input_data.get("context", "")
    if context and len(context) > 100:
        try:
            project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
            session_id = os.environ.get("CLAUDE_SESSION_ID") or f"sess_{uuid.uuid4().hex[:8]}"
            store = MemoryStore(project)

            # Take last 2000 chars as working context (most recent = most relevant)
            working_context = context[-2000:] if len(context) > 2000 else context

            store.store(
                title=f"Working context - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                content=working_context,
                type=MemoryType.WORKING,
                summary="Session context preserved before compaction",
                context="Auto-saved before context compression",
                importance=Importance.LOW,
                scope=Scope.PROJECT,
                source="hook:pre_compact",
                session_id=session_id,
            )
        except Exception as e:
            print(f"[wicked-mem] pre_compact snapshot error: {e}", file=sys.stderr)

    # Directive prompt — analyze work in progress before context is lost
    print(json.dumps({
        "continue": True,
        "systemMessage": (
            "[Memory] REQUIRED: Context is about to compress. Run TaskList to check completed and in-progress tasks. "
            "Store any decisions, discoveries, or reusable patterns from this work NOW with /wicked-mem:store "
            "before context is lost. If nothing worth storing, state 'No memories to store.'"
        )
    }))


if __name__ == "__main__":
    main()
