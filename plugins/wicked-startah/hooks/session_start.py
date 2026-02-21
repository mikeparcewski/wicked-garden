#!/usr/bin/env python3
"""SessionStart: Silent startup with AGENTS.md detection."""
import json
import sys
from pathlib import Path


def main():
    try:
        sys.stdin.read()  # consume input

        # Detect AGENTS.md for cross-tool compatibility
        cwd = Path.cwd()
        agents_md = cwd / "AGENTS.md"

        if agents_md.exists():
            claude_md = cwd / "CLAUDE.md"
            if claude_md.exists():
                msg = (
                    "AGENTS.md detected — loading cross-tool agent instructions "
                    "alongside CLAUDE.md. CLAUDE.md takes precedence on conflicts."
                )
            else:
                msg = (
                    "AGENTS.md detected — loading cross-tool agent instructions. "
                    "No CLAUDE.md found; using AGENTS.md as primary project context."
                )
            print(json.dumps({
                "continue": True,
                "message": f"<system-reminder>{msg}</system-reminder>"
            }))
        else:
            # Silent startup - no annoying setup nags
            print(json.dumps({"continue": True}))
    except Exception as e:
        print(f"Error in wicked-startah session_start hook: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
