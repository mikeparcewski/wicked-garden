#!/usr/bin/env python3
"""SessionStart: Silent startup - no nag messages."""
import json
import sys

def main():
    try:
        sys.stdin.read()  # consume input
        # Silent startup - no annoying setup nags
        print(json.dumps({"continue": True}))
    except Exception:
        print(json.dumps({"continue": True}))

if __name__ == "__main__":
    main()
