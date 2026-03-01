#!/usr/bin/env python3
"""Resolve local storage path for a domain.

Used by command prompts to avoid hardcoded ~/.something-wicked/ paths.
Prints the resolved path to stdout.

Usage:
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-delivery
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-search extracted
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _storage import get_local_path

if len(sys.argv) < 2:
    print("Usage: resolve_path.py <domain> [subpath...]", file=sys.stderr)
    sys.exit(1)

print(get_local_path(*sys.argv[1:]))
