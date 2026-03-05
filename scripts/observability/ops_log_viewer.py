#!/usr/bin/env python3
"""
ops_log_viewer.py — View the wicked-garden operational log for a session.

Reads $TMPDIR/wicked-ops-{session_id}.jsonl and formats output.

Usage:
    python3 ops_log_viewer.py [--tail N] [--level LEVEL] [--json] [--session ID]

Flags:
    --tail N       Show only the last N entries (after filtering)
    --level LEVEL  Show only entries at LEVEL or more verbose (normal|verbose|debug)
    --json         Output raw JSONL lines instead of human-readable format
    --session ID   Read from $TMPDIR/wicked-ops-{ID}.jsonl instead of current session
"""

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

# Level hierarchy: lower rank = coarser (less verbose), higher rank = finer (more verbose)
_LEVELS = {"normal": 0, "verbose": 1, "debug": 2}


def _get_session_id() -> str:
    """Sanitize CLAUDE_SESSION_ID for use in filenames."""
    raw = os.environ.get("CLAUDE_SESSION_ID", "")
    if not raw:
        return ""
    safe = re.sub(r"[^a-zA-Z0-9\-_]", "_", raw)
    return safe or ""


def _find_log_file(session_id: str | None) -> Path | None:
    """Resolve the ops log file path.

    Resolution order:
    1. --session flag (explicit session ID)
    2. CLAUDE_SESSION_ID env var
    3. Glob $TMPDIR/wicked-ops-*.jsonl — most recently modified if multiple
    """
    tmpdir = os.environ.get("TMPDIR", "/tmp")

    if session_id:
        return Path(tmpdir) / f"wicked-ops-{session_id}.jsonl"

    env_sid = _get_session_id()
    if env_sid:
        candidate = Path(tmpdir) / f"wicked-ops-{env_sid}.jsonl"
        if candidate.exists():
            return candidate

    # Glob for any ops log in TMPDIR
    pattern = str(Path(tmpdir) / "wicked-ops-*.jsonl")
    matches = glob.glob(pattern)
    if not matches:
        return None
    if len(matches) == 1:
        return Path(matches[0])
    # Multiple files: pick most recently modified
    matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return Path(matches[0])


def _format_summary(entry: dict) -> str:
    """Build a compact summary string from a log entry."""
    parts = []

    if not entry.get("ok", True):
        parts.append("FAIL")

    ms = entry.get("ms")
    if ms is not None:
        parts.append(f"ms={ms}")

    detail = entry.get("detail")
    if detail and isinstance(detail, dict):
        shown = 0
        for k, v in detail.items():
            if shown >= 3:
                break
            v_str = str(v)
            if len(v_str) > 40:
                v_str = v_str[:37] + "..."
            parts.append(f"{k}={v_str}")
            shown += 1

    return "  ".join(parts)


def _format_human(entry: dict) -> str:
    """Format a log entry as a human-readable line.

    Format: {time}  [{level:7}]  {domain:<12}  {event:<24}  {summary}
    """
    ts = entry.get("ts", "")
    # Extract HH:MM:SS.mmm from ISO-8601 timestamp
    time_str = ""
    if ts:
        # ts looks like: 2026-03-05T14:23:01.123456Z
        try:
            t_part = ts.split("T")[1].rstrip("Z")
            # Keep HH:MM:SS.mmm (first 12 chars including millis)
            time_str = t_part[:12]
        except (IndexError, AttributeError):
            time_str = ts[:12]

    level = entry.get("level", "")
    domain = entry.get("domain", "")
    event = entry.get("event", "")
    summary = _format_summary(entry)

    level_col = f"[{level:<7}]"
    domain_col = f"{domain:<12}"
    event_col = f"{event:<24}"

    line = f"{time_str}  {level_col}  {domain_col}  {event_col}"
    if summary:
        line += f"  {summary}"
    return line


def _no_file_message(session_id: str | None) -> str:
    """Return the standard 'no log file' message."""
    lines = [
        "No log file found for this session.",
        "To enable operational logging, the plugin logs automatically to:",
        "  $TMPDIR/wicked-ops-{session_id}.jsonl",
        "Run /wicked-garden:observability:debug to check the current log level.",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="View wicked-garden operational logs for a session."
    )
    parser.add_argument("--tail", type=int, default=None, metavar="N",
                        help="Show only the last N entries (after filtering)")
    parser.add_argument("--level", type=str, default=None, metavar="LEVEL",
                        help="Show only entries at this level or more verbose (normal|verbose|debug)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSONL lines")
    parser.add_argument("--session", type=str, default=None, metavar="ID",
                        help="Read from $TMPDIR/wicked-ops-{ID}.jsonl")
    args = parser.parse_args()

    log_path = _find_log_file(args.session)

    if log_path is None or not log_path.exists():
        print(_no_file_message(args.session))
        return 0

    # Determine minimum level rank for display filtering
    # --level verbose shows verbose(1) and debug(2); --level normal shows all
    min_rank: int | None = None
    if args.level:
        level_lower = args.level.strip().lower()
        if level_lower not in _LEVELS:
            print(f"Error: invalid level {args.level!r}. Must be one of: normal, verbose, debug",
                  file=sys.stderr)
            return 1
        min_rank = _LEVELS[level_lower]

    # Read and parse JSONL lines
    entries = []
    try:
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append((line, entry))
                except (json.JSONDecodeError, ValueError):
                    # Skip corrupt/truncated lines silently
                    continue
    except OSError as exc:
        print(f"Error reading log file: {exc}", file=sys.stderr)
        return 1

    # Apply level filter
    if min_rank is not None:
        entries = [
            (raw, e) for raw, e in entries
            if _LEVELS.get(e.get("level", ""), 2) >= min_rank
        ]

    # Apply tail
    if args.tail is not None and args.tail > 0:
        entries = entries[-args.tail:]

    # Output
    for raw, entry in entries:
        if args.json:
            print(raw)
        else:
            print(_format_human(entry))

    return 0


if __name__ == "__main__":
    sys.exit(main())
