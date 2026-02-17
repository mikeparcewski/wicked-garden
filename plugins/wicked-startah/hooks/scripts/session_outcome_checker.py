#!/usr/bin/env python3
"""
Stop hook (async): File GitHub issues for tool failures and task mismatches.

Reads pending_issues.jsonl and mismatches.jsonl from the session state
directory, composes issues using templates, and files them via `gh issue create`.
Caps at 3 issues per session to prevent noise. Always exits 0.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


MAX_ISSUES_PER_SESSION = 3
GH_DETECT_TIMEOUT = 5
GH_CREATE_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _sanitize_session_id(raw: str) -> str:
    """Strip path separators and traversal sequences from session ID."""
    sanitized = raw.replace("/", "_").replace("\\", "_").replace("..", "_")
    return sanitized if sanitized else "default"


def get_session_dir(session_id: str) -> Path:
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    return Path(tmpdir) / "wicked-issue-reporter" / _sanitize_session_id(session_id)


def read_jsonl(path: Path) -> list:
    """Read a JSONL file; return list of parsed objects. Skip bad lines."""
    records = []
    if not path.exists():
        return records
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(f"[session_outcome_checker] bad JSONL line in {path}: {exc}", file=sys.stderr)
    except OSError as exc:
        print(f"[session_outcome_checker] cannot read {path}: {exc}", file=sys.stderr)
    return records


# ---------------------------------------------------------------------------
# Repo detection
# ---------------------------------------------------------------------------

def detect_repo() -> Optional[str]:
    """Return 'owner/repo' string from gh CLI, or None on failure."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True,
            text=True,
            timeout=GH_DETECT_TIMEOUT,
        )
        if result.returncode == 0:
            repo = result.stdout.strip()
            if repo:
                return repo
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"[session_outcome_checker] gh repo detect failed: {exc}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Issue composition
# ---------------------------------------------------------------------------

def _short(session_id: str) -> str:
    """Return first 8 chars of session id for display."""
    return session_id[:8]


def compose_tool_failure_issue(record: dict, session_id: str) -> tuple[str, str, str]:
    """Return (title, body, label) for a tool-failure record."""
    tool = record.get("tool", "unknown")
    count = record.get("count", 1)
    last_error = str(record.get("last_error", ""))[:500]
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session_short = _short(session_id)

    title = f"[Auto] Tool failure: {tool} ({count}x) in session {session_short}"
    label = "bug"
    body = f"""\
**Reported by**: Claude Code auto-reporter
**Session**: {session_id}
**Date**: {date}

## Tool Failure Pattern

Tool `{tool}` failed {count} times during this session.

### Last Error
```
{last_error}
```

### Acceptance Criteria
- [ ] Root cause identified
- [ ] Fix verified with test
- [ ] No regression in related functionality

### Desired Outcome
Tool `{tool}` should execute successfully under these conditions.
"""
    return title, body, label


def compose_mismatch_issue(record: dict, session_id: str) -> tuple[str, str, str]:
    """Return (title, body, label) for a task-mismatch record."""
    subject = str(record.get("subject", "unknown task"))
    subject_short = subject[:60] + ("..." if len(subject) > 60 else "")
    signal = record.get("signal", "unknown")
    detail = str(record.get("detail", ""))
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session_short = _short(session_id)

    title = f"[Auto] Unmet outcome: {subject_short} in session {session_short}"
    label = "gap"
    body = f"""\
**Reported by**: Claude Code auto-reporter
**Session**: {session_id}
**Date**: {date}

## Unmet Outcome

Task "{subject}" was marked completed but showed signals of incomplete work.

### Signal Detected
{signal}: {detail}

### Acceptance Criteria
- [ ] Outcome verified against original intent
- [ ] Gap addressed or documented
- [ ] Related workflows checked

### Desired Outcome
Task should fully achieve its stated objective before being marked complete.
"""
    return title, body, label


def compose_issue(record: dict, session_id: str) -> tuple[str, str, str]:
    """Dispatch to the correct template based on record type."""
    record_type = record.get("type", "tool_failure")
    if record_type == "task_mismatch":
        return compose_mismatch_issue(record, session_id)
    return compose_tool_failure_issue(record, session_id)


# ---------------------------------------------------------------------------
# Filing helpers
# ---------------------------------------------------------------------------

def write_unfiled(record: dict, title: str, body: str, label: str,
                  session_id: str, index: int) -> None:
    """Write an unfiled issue record to the local fallback queue."""
    unfiled_dir = Path.home() / ".something-wicked" / "wicked-startah" / "unfiled-issues"
    try:
        unfiled_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "title": title,
            "body": body,
            "label": label,
            "source_session": session_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        out_path = unfiled_dir / f"{session_id}-{index}.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"[session_outcome_checker] unfiled issue saved: {out_path}", file=sys.stderr)
    except OSError as exc:
        print(f"[session_outcome_checker] failed to write unfiled issue: {exc}", file=sys.stderr)


def file_issue(repo: str, title: str, body: str, label: str) -> Optional[str]:
    """
    File a GitHub issue. Returns the issue URL on success, None on failure.
    Uses --body-file to safely handle multiline body text.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix="wicked-issue-")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--repo", repo,
                "--title", title,
                "--body-file", tmp_path,
                "--label", label,
            ],
            capture_output=True,
            text=True,
            timeout=GH_CREATE_TIMEOUT,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            return url if url else None
        print(
            f"[session_outcome_checker] gh issue create failed (rc={result.returncode}): "
            f"{result.stderr.strip()[:300]}",
            file=sys.stderr,
        )
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"[session_outcome_checker] gh issue create error: {exc}", file=sys.stderr)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Consume stdin (Stop hook payload — not used directly)
    try:
        sys.stdin.read()
    except Exception:
        pass

    session_id = _sanitize_session_id(os.environ.get("CLAUDE_SESSION_ID", "") or "default")

    session_dir = get_session_dir(session_id)

    # Nothing to do if no session directory
    if not session_dir.exists():
        sys.exit(0)

    # Read both data sources
    pending_issues = read_jsonl(session_dir / "pending_issues.jsonl")
    mismatches = read_jsonl(session_dir / "mismatches.jsonl")

    all_records = pending_issues + mismatches

    if not all_records:
        # Clean session — remove the empty dir and exit
        try:
            shutil.rmtree(session_dir)
        except OSError as exc:
            print(f"[session_outcome_checker] cleanup error: {exc}", file=sys.stderr)
        sys.exit(0)

    # Cap total issues to avoid spamming the repo
    capped_records = all_records[:MAX_ISSUES_PER_SESSION]
    if len(all_records) > MAX_ISSUES_PER_SESSION:
        print(
            f"[session_outcome_checker] capping at {MAX_ISSUES_PER_SESSION} issues "
            f"({len(all_records)} total records)",
            file=sys.stderr,
        )

    repo = detect_repo()
    if not repo:
        print("[session_outcome_checker] no repo detected; all issues go to unfiled queue", file=sys.stderr)

    for index, record in enumerate(capped_records):
        try:
            title, body, label = compose_issue(record, session_id)
        except Exception as exc:
            print(f"[session_outcome_checker] failed to compose issue #{index}: {exc}", file=sys.stderr)
            continue

        if repo:
            url = file_issue(repo, title, body, label)
            if url:
                print(f"[session_outcome_checker] filed issue: {url}", file=sys.stderr)
            else:
                write_unfiled(record, title, body, label, session_id, index)
        else:
            write_unfiled(record, title, body, label, session_id, index)

    # Cleanup session directory
    try:
        shutil.rmtree(session_dir)
    except OSError as exc:
        print(f"[session_outcome_checker] cleanup error: {exc}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
