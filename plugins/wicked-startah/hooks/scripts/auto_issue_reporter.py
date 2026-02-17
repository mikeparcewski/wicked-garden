#!/usr/bin/env python3
"""
PostToolUseFailure + PostToolUse(TaskUpdate) hook: Auto issue reporter.

Handles two event types in a single script, determined by payload shape:
  - PostToolUseFailure: `tool_error` key present → failure counting + threshold alerts
  - PostToolUse(TaskUpdate): `tool_name == "TaskUpdate"`, no `tool_error` → mismatch detection

Never blocks — always prints {"continue": true} and exits cleanly.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# --- Configuration -----------------------------------------------------------

DEFAULT_THRESHOLD = 3
MISMATCH_SIGNALS = ["failed", "not working", "broken", "error", "couldn't", "unable", "blocked"]
SESSION_DIR_MAX_AGE_HOURS = 48


# --- Helpers -----------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_session_id(raw: str) -> str:
    """Strip path separators and traversal sequences from session ID."""
    sanitized = raw.replace("/", "_").replace("\\", "_").replace("..", "_")
    return sanitized if sanitized else "default"


def _session_dir() -> Path:
    """Return (and create) the per-session state directory."""
    tmpdir = os.environ.get("TMPDIR", "/tmp").rstrip("/")
    session_id = _sanitize_session_id(os.environ.get("CLAUDE_SESSION_ID", "default"))
    path = Path(tmpdir) / "wicked-issue-reporter" / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parent_dir() -> Path:
    """Return the parent directory that holds all session dirs."""
    tmpdir = os.environ.get("TMPDIR", "/tmp").rstrip("/")
    return Path(tmpdir) / "wicked-issue-reporter"


def _load_failure_counts(session_dir: Path) -> dict:
    """Load failure_counts.json; return empty structure on any error."""
    counts_file = session_dir / "failure_counts.json"
    try:
        data = json.loads(counts_file.read_text())
        if "counts" not in data:
            data["counts"] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return {"counts": {}, "last_updated": _now_iso()}


def _save_failure_counts(session_dir: Path, data: dict) -> None:
    """Save failure_counts.json, updating last_updated timestamp."""
    data["last_updated"] = _now_iso()
    counts_file = session_dir / "failure_counts.json"
    counts_file.write_text(json.dumps(data, indent=2))


def _prune_stale_sessions(parent_dir: Path, flag_file: Path) -> None:
    """Delete session dirs whose failure_counts.json is >48h old.

    Only runs once per session (gate: flag_file existence).
    Skips dirs that cannot be read.
    """
    if flag_file.exists():
        return  # Already pruned this session

    # Write flag immediately to prevent concurrent runs
    try:
        flag_file.write_text(_now_iso())
    except OSError:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_DIR_MAX_AGE_HOURS)

    try:
        for entry in parent_dir.iterdir():
            if not entry.is_dir():
                continue
            counts_file = entry / "failure_counts.json"
            try:
                data = json.loads(counts_file.read_text())
                last_updated_str = data.get("last_updated", "")
                last_updated = datetime.fromisoformat(last_updated_str)
                # Normalize to UTC if naive
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=timezone.utc)
                if last_updated < cutoff:
                    # Remove contents then directory
                    for child in entry.iterdir():
                        try:
                            child.unlink()
                        except OSError:
                            pass
                    try:
                        entry.rmdir()
                    except OSError:
                        pass
            except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
                # Can't read — skip silently
                continue
    except OSError:
        pass


def _append_jsonl(path: Path, record: dict) -> None:
    """Append a JSON record as a single line to a .jsonl file."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# --- Event handlers ----------------------------------------------------------

def _handle_failure(payload: dict) -> dict:
    """PostToolUseFailure path: count failures, trigger issue queue at threshold."""
    tool_name = payload.get("tool_name", "unknown")
    tool_error = payload.get("tool_error", "") or payload.get("tool_use_error", "")
    session_id = _sanitize_session_id(os.environ.get("CLAUDE_SESSION_ID", "default"))

    sdir = _session_dir()
    parent = _parent_dir()
    prune_flag = sdir / ".pruned"

    # Prune stale sessions on first PostToolUseFailure of this session
    try:
        _prune_stale_sessions(parent, prune_flag)
    except Exception:
        pass

    try:
        threshold = int(os.environ.get("WICKED_ISSUE_THRESHOLD", str(DEFAULT_THRESHOLD)))
    except (ValueError, TypeError):
        threshold = DEFAULT_THRESHOLD

    # Load, increment, save
    counts_data = _load_failure_counts(sdir)
    counts = counts_data["counts"]
    counts[tool_name] = counts.get(tool_name, 0) + 1
    current_count = counts[tool_name]
    try:
        _save_failure_counts(sdir, counts_data)
    except OSError:
        pass  # Permission error — continue without persisting count

    # Threshold check
    if current_count >= threshold:
        record = {
            "type": "tool_failure",
            "tool": tool_name,
            "count": current_count,
            "last_error": str(tool_error)[:500],  # cap length
            "session_id": session_id,
            "ts": _now_iso(),
        }
        try:
            _append_jsonl(sdir / "pending_issues.jsonl", record)
        except OSError:
            pass

        # Reset counter so next threshold cycle starts fresh
        counts[tool_name] = 0
        try:
            _save_failure_counts(sdir, counts_data)
        except OSError:
            pass

        return {
            "continue": True,
            "systemMessage": (
                f"[Issue Reporter] {current_count} {tool_name} failures — issue queued."
            ),
        }

    return {"continue": True}


def _handle_task_update(payload: dict) -> dict:
    """PostToolUse(TaskUpdate) path: detect completion mismatch signals."""
    tool_input = payload.get("tool_input", {})

    # Only care about completions
    if tool_input.get("status") != "completed":
        return {"continue": True}

    # Gather text fields to inspect
    subject = tool_input.get("subject", "") or ""
    description = tool_input.get("description", "") or ""
    task_id = tool_input.get("taskId", "") or ""

    combined = (subject + " " + description).lower()

    found_signal = None
    for signal in MISMATCH_SIGNALS:
        if signal in combined:
            found_signal = signal
            break

    if found_signal:
        record = {
            "type": "task_mismatch",
            "task_id": task_id,
            "subject": subject[:200],
            "signal": found_signal,
            "detail": description[:300],
            "ts": _now_iso(),
        }
        try:
            sdir = _session_dir()
            _append_jsonl(sdir / "mismatches.jsonl", record)
        except OSError:
            pass

    return {"continue": True}


# --- Main --------------------------------------------------------------------

def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError, ValueError):
        payload = {}

    try:
        tool_name = payload.get("tool_name", "")
        has_error = "tool_error" in payload or "tool_use_error" in payload

        if has_error:
            result = _handle_failure(payload)
        elif tool_name == "TaskUpdate":
            result = _handle_task_update(payload)
        else:
            result = {"continue": True}
    except Exception:
        result = {"continue": True}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
