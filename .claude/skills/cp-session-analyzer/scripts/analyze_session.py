#!/usr/bin/env python3
"""
Post-session analysis of control plane errors in Claude Code transcripts.

Parses a JSONL transcript, finds CP error patterns, groups by domain/source/code,
deduplicates against existing GitHub issues, and optionally auto-files new issues.

Usage:
    python3 analyze_session.py <transcript_path>
    python3 analyze_session.py <transcript_path> --auto-file --repo mikeparcewski/wicked-garden

Exit codes:
    0 - No CP errors found
    1 - CP errors found (regardless of filing)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Actual _do_request format:
# [wicked-garden] Control plane HTTP 400 for POST http://…/api/v1/data/memory/memories/create: Bad Request
# Captures: code, method, domain (from URL path), source (from URL path), reason
RE_CP_HTTP_URL = re.compile(
    r"\[wicked-garden\]\s*Control plane HTTP\s*(\d{3})"
    r"\s+for\s+\w+\s+"               # "for POST "
    r"https?://[^/]+/api/v\d+/data/"  # base URL up to /data/
    r"([^/]+)/([^/]+)/[^:]*"          # domain/source/verb
    r"(?::\s*(.+))?"                  # optional ": reason"
)

# Fallback: same prefix without URL parsing (e.g. truncated messages)
RE_CP_HTTP_BARE = re.compile(
    r"\[wicked-garden\]\s*Control plane HTTP\s*(\d{3})"
    r"(?::\s*(.+))?"
)

# Broader fallback: "CP rejected" or "CP error" with optional HTTP code
RE_CP_GENERIC = re.compile(
    r"(?:CP rejected|CP error)(?:\s*(?:HTTP\s*)?(\d{3}))?"
    r"(?::\s*(.+))?"
    , re.IGNORECASE
)

# Domain extraction from source paths like "scripts/crew/phase_manager.py"
RE_DOMAIN_PATH = re.compile(r"scripts/([a-z_-]+)/")


# ---------------------------------------------------------------------------
# Error extraction
# ---------------------------------------------------------------------------

def _extract_timestamp(entry: Dict[str, Any]) -> Optional[str]:
    """Try to pull a timestamp from the JSONL entry."""
    for key in ("timestamp", "ts", "time", "created_at"):
        val = entry.get(key)
        if val:
            return str(val)
    return None


def _search_text(text: str, line_number: int, timestamp: Optional[str]) -> List[Dict]:
    """Search a block of text for CP error patterns."""
    hits: List[Dict] = []

    # Try the URL-based pattern first (extracts domain/source from URL path)
    for m in RE_CP_HTTP_URL.finditer(text):
        code = int(m.group(1))
        domain = m.group(2).strip()
        source = m.group(3).strip()
        message = (m.group(4) or "").strip()
        hits.append({
            "domain": domain,
            "source": source,
            "code": code,
            "message": message,
            "timestamp": timestamp,
            "line_number": line_number,
        })

    # Fall back to bare pattern (no URL in message)
    if not hits:
        for m in RE_CP_HTTP_BARE.finditer(text):
            code = int(m.group(1))
            message = (m.group(2) or "").strip()
            hits.append({
                "domain": "unknown",
                "source": "unknown",
                "code": code,
                "message": message,
                "timestamp": timestamp,
                "line_number": line_number,
            })

    # Only use the generic pattern if neither specific pattern matched
    if not hits:
        for m in RE_CP_GENERIC.finditer(text):
            code = int(m.group(1)) if m.group(1) else 0
            message = (m.group(2) or "").strip()
            hits.append({
                "domain": "unknown",
                "source": "unknown",
                "code": code,
                "message": message,
                "timestamp": timestamp,
                "line_number": line_number,
            })

    return hits


def _extract_from_entry(entry: Dict[str, Any], line_number: int) -> List[Dict]:
    """Extract CP errors from a single JSONL entry."""
    errors: List[Dict] = []
    ts = _extract_timestamp(entry)

    # Check stderr
    stderr = entry.get("stderr", "")
    if isinstance(stderr, str) and stderr:
        errors.extend(_search_text(stderr, line_number, ts))

    # Check content (may be string or list of blocks)
    content = entry.get("content", "")
    if isinstance(content, str) and content:
        errors.extend(_search_text(content, line_number, ts))
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "") or block.get("content", "")
                if text:
                    errors.extend(_search_text(str(text), line_number, ts))
            elif isinstance(block, str):
                errors.extend(_search_text(block, line_number, ts))

    # Check tool_error in PostToolUseFailure entries
    hook_event = entry.get("hook_event_name", "")
    tool_error = entry.get("tool_error", "")
    if hook_event == "PostToolUseFailure" and tool_error:
        errors.extend(_search_text(str(tool_error), line_number, ts))

    # Check nested result/error fields
    for nested_key in ("result", "error", "output", "message"):
        val = entry.get(nested_key)
        if isinstance(val, str) and val:
            errors.extend(_search_text(val, line_number, ts))
        elif isinstance(val, dict):
            for subval in val.values():
                if isinstance(subval, str):
                    errors.extend(_search_text(subval, line_number, ts))

    return errors


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _group_key(err: Dict) -> str:
    return f"{err['domain']}/{err['source']}/{err['code']}"


def group_errors(errors: List[Dict]) -> Dict[str, Dict]:
    """Group errors by domain/source/code."""
    groups: Dict[str, Dict] = {}
    for err in errors:
        key = _group_key(err)
        if key not in groups:
            groups[key] = {
                "count": 0,
                "first_seen": err.get("timestamp"),
                "last_seen": err.get("timestamp"),
                "sample_message": err.get("message", ""),
                "domain": err["domain"],
                "source": err["source"],
                "code": err["code"],
            }
        groups[key]["count"] += 1
        ts = err.get("timestamp")
        if ts:
            if not groups[key]["first_seen"] or ts < groups[key]["first_seen"]:
                groups[key]["first_seen"] = ts
            if not groups[key]["last_seen"] or ts > groups[key]["last_seen"]:
                groups[key]["last_seen"] = ts
    return groups


# ---------------------------------------------------------------------------
# GitHub deduplication
# ---------------------------------------------------------------------------

def _gh_available() -> bool:
    """Check if the gh CLI is on PATH."""
    return shutil.which("gh") is not None


def find_existing_issues(groups: Dict[str, Dict], repo: str) -> List[Dict]:
    """Search for existing GH issues matching each error group."""
    if not _gh_available():
        print("[warn] gh CLI not found -- skipping issue dedup", file=sys.stderr)
        return []

    existing: List[Dict] = []
    for key, info in groups.items():
        domain = info["domain"]
        source = info["source"]
        search_term = f"CP error {domain}/{source}"
        try:
            result = subprocess.run(
                [
                    "gh", "issue", "list",
                    "--repo", repo,
                    "--search", search_term,
                    "--json", "number,title",
                    "--limit", "5",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                issues = json.loads(result.stdout)
                for issue in issues:
                    existing.append({
                        "number": issue["number"],
                        "title": issue["title"],
                        "matched_group": key,
                    })
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            print(f"[warn] gh search failed for '{search_term}': {exc}", file=sys.stderr)

    return existing


# ---------------------------------------------------------------------------
# Issue filing
# ---------------------------------------------------------------------------

def file_issues(
    new_groups: Dict[str, Dict],
    repo: str,
) -> List[Dict]:
    """File GH issues for new (non-duplicate) error groups."""
    if not _gh_available():
        print("[warn] gh CLI not found -- skipping issue filing", file=sys.stderr)
        return []

    filed: List[Dict] = []
    for key, info in new_groups.items():
        title = f"CP Error: {info['domain']}/{info['source']} HTTP {info['code']}"
        body_lines = [
            f"## CP Error Report",
            f"",
            f"**Group**: `{key}`",
            f"**Occurrences**: {info['count']}",
            f"**First seen**: {info.get('first_seen', 'N/A')}",
            f"**Last seen**: {info.get('last_seen', 'N/A')}",
            f"**Sample message**: {info.get('sample_message', 'N/A')}",
            f"",
            f"## Context",
            f"",
            f"- **Domain**: {info['domain']}",
            f"- **Source script**: {info['source']}",
            f"- **HTTP status**: {info['code']}",
            f"",
            f"Detected by `cp-session-analyzer` from transcript analysis.",
            f"",
            f"## Suggested Investigation",
            f"",
            f"1. Check `scripts/{info['domain']}/{info['source']}` for the failing CP call",
            f"2. Verify control plane endpoint availability",
            f"3. Check StorageManager fallback behavior",
        ]
        body = "\n".join(body_lines)

        try:
            result = subprocess.run(
                [
                    "gh", "issue", "create",
                    "--repo", repo,
                    "--title", title,
                    "--body", body,
                    "--label", "bug,cp-error",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                # gh prints the issue URL on success
                issue_url = result.stdout.strip()
                filed.append({
                    "group_key": key,
                    "title": title,
                    "url": issue_url,
                })
                print(f"[filed] {title} -> {issue_url}", file=sys.stderr)
            else:
                print(
                    f"[error] Failed to file issue for {key}: {result.stderr.strip()}",
                    file=sys.stderr,
                )
        except (subprocess.TimeoutExpired, OSError) as exc:
            print(f"[error] gh issue create failed for {key}: {exc}", file=sys.stderr)

    return filed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyze_transcript(path: str) -> Tuple[List[Dict], int]:
    """Parse transcript and return (errors, total_lines)."""
    errors: List[Dict] = []
    total_lines = 0

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            total_lines = line_number
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            errors.extend(_extract_from_entry(entry, line_number))

    return errors, total_lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a Claude Code transcript for CP error patterns.",
    )
    parser.add_argument(
        "transcript_path",
        help="Path to the JSONL transcript file",
    )
    parser.add_argument(
        "--auto-file",
        action="store_true",
        help="Automatically file GitHub issues for new error groups",
    )
    parser.add_argument(
        "--repo",
        default="mikeparcewski/wicked-garden",
        help="GitHub repo (OWNER/REPO) for issue operations (default: mikeparcewski/wicked-garden)",
    )

    args = parser.parse_args()

    # Validate transcript path
    transcript = Path(args.transcript_path)
    if not transcript.is_file():
        print(f"Error: transcript not found: {transcript}", file=sys.stderr)
        return 1

    # Parse
    errors, total_lines = analyze_transcript(str(transcript))

    if not errors:
        report = {
            "transcript": str(transcript),
            "total_lines": total_lines,
            "total_errors": 0,
            "errors": [],
            "grouped": {},
            "existing_issues": [],
            "new_issues": [],
        }
        print(json.dumps(report, indent=2))
        return 0

    # Group
    grouped = group_errors(errors)

    # Deduplicate against existing issues
    existing = find_existing_issues(grouped, args.repo)
    existing_group_keys = {e["matched_group"] for e in existing}

    # Determine new groups (not covered by existing issues)
    new_groups = {k: v for k, v in grouped.items() if k not in existing_group_keys}

    # Build report
    new_issues_list = [
        {
            "group_key": k,
            "title": f"CP Error: {v['domain']}/{v['source']} HTTP {v['code']}",
            "count": v["count"],
        }
        for k, v in new_groups.items()
    ]

    report = {
        "transcript": str(transcript),
        "total_lines": total_lines,
        "total_errors": len(errors),
        "errors": errors,
        "grouped": {
            k: {
                "count": v["count"],
                "first_seen": v["first_seen"],
                "last_seen": v["last_seen"],
                "sample_message": v["sample_message"],
            }
            for k, v in grouped.items()
        },
        "existing_issues": existing,
        "new_issues": new_issues_list,
    }

    # Auto-file if requested
    filed = []
    if args.auto_file and new_groups:
        filed = file_issues(new_groups, args.repo)
        report["filed_issues"] = filed

    print(json.dumps(report, indent=2))

    # Exit 1 if errors were found
    return 1


if __name__ == "__main__":
    sys.exit(main())
