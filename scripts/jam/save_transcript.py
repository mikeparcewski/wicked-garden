#!/usr/bin/env python3
"""
wicked-jam transcript persistence helper.

Called by facilitator and council agents after each session to store
individual persona contributions for later retrieval via jam.py.

Usage:
    save_transcript.py --session-id ID --entries '[{...}, ...]'

The --entries argument must be a JSON array of transcript entry objects.
Each entry schema:
    {
        "session_id": "...",
        "round": 1,
        "persona_name": "Technical Architect",
        "persona_type": "technical",   # technical | user | business | process | council
        "raw_text": "...",
        "timestamp": "...",            # ISO 8601 (auto-set if omitted)
        "entry_type": "perspective"    # perspective | synthesis | council_response
    }

Existing entries for the session are loaded, new entries are appended,
then the whole transcript is saved back via StorageManager.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_sm = None

VALID_ENTRY_TYPES = {"perspective", "synthesis", "council_response"}
VALID_PERSONA_TYPES = {"technical", "user", "business", "process", "council"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_entry(entry: dict, session_id: str) -> dict:
    """Fill defaults and validate a single transcript entry. Returns the normalised entry."""
    entry = dict(entry)

    # Enforce session_id
    entry["session_id"] = session_id

    # Default timestamp
    if not entry.get("timestamp"):
        entry["timestamp"] = _iso_now()

    # Default round
    if "round" not in entry:
        entry["round"] = 1

    # Validate entry_type
    etype = entry.get("entry_type", "")
    if etype not in VALID_ENTRY_TYPES:
        raise ValueError(
            f"Invalid entry_type {etype!r}. Must be one of: {sorted(VALID_ENTRY_TYPES)}"
        )

    # Validate persona_type (soft — unknown types are kept but warned)
    ptype = entry.get("persona_type", "")
    if ptype and ptype not in VALID_PERSONA_TYPES:
        print(
            f"Warning: unknown persona_type {ptype!r}. "
            f"Expected one of: {sorted(VALID_PERSONA_TYPES)}",
            file=sys.stderr,
        )

    # Require raw_text
    if not entry.get("raw_text", "").strip():
        raise ValueError("Entry is missing required field: raw_text")

    # Require persona_name
    if not entry.get("persona_name", "").strip():
        raise ValueError("Entry is missing required field: persona_name")

    return entry


def _get_sm():
    """Lazy DomainStore init — deferred to call time, not import time."""
    global _sm
    if _sm is None:
        from _domain_store import DomainStore
        _sm = DomainStore("wicked-jam")
    return _sm


def save_transcript_entries(session_id: str, new_entries: list) -> dict:
    """
    Append new_entries to the stored transcript for session_id.

    Returns a result dict with counts and any error.
    """
    if not session_id:
        return {"ok": False, "error": "session_id is required"}

    if not isinstance(new_entries, list) or not new_entries:
        return {"ok": False, "error": "entries must be a non-empty JSON array"}

    sm = _get_sm()

    # Load existing transcript (or start fresh)
    existing = sm.get("transcripts", session_id)
    existing_entries = existing.get("entries", []) if existing else []

    validated = []
    for i, entry in enumerate(new_entries):
        try:
            validated.append(_validate_entry(entry, session_id))
        except (ValueError, TypeError) as exc:
            return {"ok": False, "error": f"Entry #{i}: {exc}"}

    merged = existing_entries + validated
    transcript_doc = {"id": session_id, "session_id": session_id, "entries": merged}

    if existing:
        sm.update("transcripts", session_id, {"entries": merged})
    else:
        sm.create("transcripts", transcript_doc)

    return {
        "ok": True,
        "session_id": session_id,
        "entries_added": len(validated),
        "entries_total": len(merged),
    }


def main():
    parser = argparse.ArgumentParser(description="Persist jam transcript entries")
    parser.add_argument("--session-id", required=True, help="Brainstorm session ID")
    parser.add_argument(
        "--entries",
        required=True,
        help="JSON array of transcript entry objects",
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    try:
        entries = json.loads(args.entries)
    except json.JSONDecodeError as exc:
        result = {"ok": False, "error": f"Invalid JSON in --entries: {exc}"}
        print(json.dumps(result, indent=2) if getattr(args, "json", False) else result["error"])
        sys.exit(1)

    result = save_transcript_entries(session_id=args.session_id, new_entries=entries)

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
    else:
        if result.get("ok"):
            added = result["entries_added"]
            total = result["entries_total"]
            print(f"Saved {added} transcript {'entry' if added == 1 else 'entries'} "
                  f"(total: {total}) for session: {args.session_id}")
        else:
            print(f"Error: {result.get('error', 'unknown error')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
