#!/usr/bin/env python3
"""migrate_legacy.py — legacy reference scans for /wicked-garden:setup.

Section 2.6 of the setup command needs to scan crew project directories
for legacy ``qe-evaluator`` strings in reeval and amendment logs. The
scan was inlined in markdown; this module exposes it as a callable +
CLI so the command body can stay slim.

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LEGACY_PATTERNS = (
    '"reviewer": "qe-evaluator"',
    '"trigger": "qe-evaluator:',
)
_TARGET_GLOBS = (
    "phases/*/reeval-log.jsonl",
    "phases/*/amendments.jsonl",
)


def scan_qe_evaluator_refs(projects_root: Path | None = None) -> list[str]:
    """Return the list of files that still contain legacy qe-evaluator refs."""
    root = projects_root or (
        Path.home() / ".something-wicked" / "wicked-garden" / "projects"
    )
    found: list[str] = []
    if not root.exists():
        return found
    for pattern in _TARGET_GLOBS:
        for f in root.glob("*/" + pattern):
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            if any(p in text for p in _LEGACY_PATTERNS):
                found.append(str(f))
    return found


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-root", default=None)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human text")
    args = parser.parse_args()
    root = Path(args.projects_root) if args.projects_root else None
    found = scan_qe_evaluator_refs(root)
    if args.json:
        json.dump({"status": "LEGACY_FOUND" if found else "CLEAN", "files": found},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("LEGACY_FOUND\n" if found else "CLEAN\n")
        for path in found:
            sys.stdout.write(path + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
