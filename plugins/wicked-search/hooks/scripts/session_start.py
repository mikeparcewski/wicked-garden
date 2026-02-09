#!/usr/bin/env python3
"""SessionStart hook: Check index status and freshness."""
import json
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_index_dir() -> Path:
    """Get the index storage directory."""
    return Path.home() / ".something-wicked" / "wicked-search"


def get_path_hash(path: str) -> str:
    """Generate a hash for the project path.

    Must match unified_search.py's _path_hash() method: MD5[:12]
    """
    return hashlib.md5(path.encode()).hexdigest()[:12]


def get_repo_path() -> str:
    """Get current repository path."""
    return os.environ.get('PWD', os.getcwd())


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as 'X ago'."""
    now = datetime.now(timezone.utc)
    delta = now - dt

    if delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h ago"
    elif delta.seconds >= 60:
        return f"{delta.seconds // 60}m ago"
    else:
        return "just now"


def check_index_status(repo_path: str):
    """Check if index exists and get its status."""
    index_dir = get_index_dir()
    path_hash = get_path_hash(repo_path)

    jsonl_path = index_dir / f"{path_hash}.jsonl"
    meta_path = index_dir / f"{path_hash}_meta.json"

    if not jsonl_path.exists():
        return None

    # Get basic stats
    stat = jsonl_path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    size_kb = stat.st_size / 1024

    # Count symbols (lines in jsonl)
    try:
        with open(jsonl_path, 'r') as f:
            symbol_count = sum(1 for _ in f)
    except Exception:
        symbol_count = 0

    # Check metadata for more details
    doc_count = 0
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            doc_count = len(meta.get("documents", []))
        except Exception:
            pass

    return {
        "symbol_count": symbol_count,
        "doc_count": doc_count,
        "size_kb": round(size_kb, 1),
        "modified": modified,
        "time_ago": format_time_ago(modified)
    }


def main():
    try:
        sys.stdin.read()  # consume input
    except IOError:
        pass

    repo_path = get_repo_path()
    status = check_index_status(repo_path)

    result = {"continue": True}

    if status:
        total_indexed = status['symbol_count'] + status['doc_count']
        msg = f"[Search] {total_indexed:,} code/docs indexed"
        msg += f" ({status['symbol_count']:,} symbols)"
        msg += f" - {status['time_ago']}"
        result["systemMessage"] = msg
    else:
        result["systemMessage"] = "[Search] No index. Run /wicked-search:index . to create"

    print(json.dumps(result))


if __name__ == "__main__":
    main()
