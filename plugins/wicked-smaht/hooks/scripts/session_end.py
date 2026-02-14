#!/usr/bin/env python3
"""
wicked-smaht v2: Stop hook.

Persists session metadata for cross-session recall.
Runs async so it doesn't block the user on exit.
"""

import json
import os
import sys
from pathlib import Path

# Add v2 scripts to path
scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "v2"
sys.path.insert(0, str(scripts_dir))


def main():
    """Persist session state on session end."""
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        input_data = {}

    session_id = input_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "default"))

    try:
        from history_condenser import HistoryCondenser

        condenser = HistoryCondenser(session_id)
        condenser.persist_session_meta()
    except ImportError:
        pass
    except Exception as e:
        print(f"smaht: session persist failed: {e}", file=sys.stderr)

    # Always return ok — never block session exit
    print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
