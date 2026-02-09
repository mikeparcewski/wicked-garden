#!/usr/bin/env python3
"""
{{event}} hook for {{plugin_name}}.

Exit codes:
  0 - Success, continue
  2 - Blocking error (message sent to Claude)
  Other - Non-blocking error (logged)
"""

import sys
import json
import os


def main():
    """Main hook execution."""
    # Read hook data from stdin
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    # Get hook context
    tool = data.get('tool', '')
    arguments = data.get('arguments', {})
    context = data.get('context', {})

    # Hook logic here
    # Example: Block dangerous commands
    if tool == 'Bash':
        command = arguments.get('command', '')

        # Check for dangerous patterns
        dangerous_patterns = [
            'rm -rf /',
            'curl | bash',
            'wget | sh',
            '> /dev/sda'
        ]

        for pattern in dangerous_patterns:
            if pattern in command:
                print(f"Blocked dangerous command: {pattern}")
                sys.exit(2)  # Block execution

    # Allow execution
    sys.exit(0)


if __name__ == "__main__":
    main()
