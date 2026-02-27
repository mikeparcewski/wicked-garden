#!/usr/bin/env python3
"""
PreCompact hook — wicked-garden memory snapshot before context compression.

Port of wicked-mem's pre_compact.py with updated import paths.

Two jobs:
1. Automatically save a working memory snapshot (context preservation)
2. Prompt Claude to store any decisions/episodic/procedural memories
   that haven't been captured yet before context is lost

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add shared scripts directory to path
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


def _save_working_memory_snapshot(context: str, project: str, session_id: str) -> None:
    """Save a working memory snapshot via the mem domain MemoryStore."""
    try:
        from mem.memory import MemoryStore, MemoryType, Scope, Importance

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
        print(f"[wicked-garden] pre_compact snapshot error: {e}", file=sys.stderr)


def main():
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        input_data = {}

    context = input_data.get("context", "")
    if context and len(context) > 100:
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        session_id = os.environ.get("CLAUDE_SESSION_ID") or f"sess_{uuid.uuid4().hex[:8]}"
        _save_working_memory_snapshot(context, project, session_id)

    print(json.dumps({
        "continue": True,
        "systemMessage": (
            "[Memory] REQUIRED: Context is about to compress. "
            "Run TaskList to check completed and in-progress tasks. "
            "Store any decisions, discoveries, or reusable patterns from this work NOW "
            "with /wicked-garden:mem:store before context is lost. "
            "If nothing worth storing, state 'No memories to store.'"
        ),
    }))


if __name__ == "__main__":
    main()
