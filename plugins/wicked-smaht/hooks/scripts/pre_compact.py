#!/usr/bin/env python3
"""
wicked-smaht: PreCompact hook.
Saves condenser state before conversation compaction so session
context survives the window reset.
"""
import json
import os
import sys
from pathlib import Path

V2_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(V2_SCRIPTS_DIR))


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}

    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")

    try:
        from history_condenser import HistoryCondenser
        condenser = HistoryCondenser(session_id)
        condenser.save()
        condenser.persist_session_meta()
    except Exception as e:
        print(f"smaht: pre-compact save failed: {e}", file=sys.stderr)

    # Always continue — never block compaction
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
