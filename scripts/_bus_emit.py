#!/usr/bin/env python3
"""
CLI wrapper for _bus.emit_event() — called from agent/command markdown via bash.

Usage:
    python3 scripts/_bus_emit.py <event_type> <payload_json> [--chain-id <id>]

Examples:
    python3 scripts/_bus_emit.py wicked.session.started '{"session_id":"abc","topic":"test"}'
    python3 scripts/_bus_emit.py wicked.phase.transitioned '{"project_id":"x"}' --chain-id x.root
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bus import emit_event


def main():
    if len(sys.argv) < 3:
        print("Usage: _bus_emit.py <event_type> <payload_json> [--chain-id <id>]", file=sys.stderr)
        sys.exit(1)

    event_type = sys.argv[1]
    try:
        payload = json.loads(sys.argv[2])
    except json.JSONDecodeError:
        print(f"Invalid JSON payload: {sys.argv[2]}", file=sys.stderr)
        sys.exit(1)

    chain_id = None
    if "--chain-id" in sys.argv:
        idx = sys.argv.index("--chain-id")
        if idx + 1 < len(sys.argv):
            chain_id = sys.argv[idx + 1]

    emit_event(event_type, payload, chain_id=chain_id)


if __name__ == "__main__":
    main()
