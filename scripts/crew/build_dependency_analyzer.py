#!/usr/bin/env python3
"""
Build Dependency Analyzer — wicked-crew issue #252.

Analyzes a list of build tasks and groups them into parallel batches based
on file overlap detection. Tasks that share file references should not run
in parallel (risk of merge conflicts); tasks with no overlap can run concurrently.

Output format:
    [
      {"batch": 1, "tasks": ["task-id-1", "task-id-2"], "parallel": true},
      {"batch": 2, "tasks": ["task-id-3"], "parallel": false}
    ]

Usage:
    # From JSON file
    python3 build_dependency_analyzer.py --tasks-file tasks.json --max-parallelism 3

    # From stdin (pipe TaskList JSON output)
    echo '[{"id":"1","subject":"Build: ...","description":"..."}]' | \
        python3 build_dependency_analyzer.py --stdin

    # Python API
    from build_dependency_analyzer import analyze_dependencies
    batches = analyze_dependencies(tasks, max_parallelism=3)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# File reference extraction
# ---------------------------------------------------------------------------

# Patterns that suggest a file path in task text
_FILE_PATH_RE = re.compile(
    r"(?:"
    r"(?:[a-zA-Z0-9_\-./]+/[a-zA-Z0-9_\-./]+\.[a-zA-Z]{1,10})"   # path/to/file.ext
    r"|"
    r"(?:[a-zA-Z0-9_\-]+\.[a-zA-Z]{1,10})"                         # file.ext (at word boundary)
    r")",
    re.IGNORECASE,
)

# Extensions that are meaningful for conflict analysis (source code / config)
_MEANINGFUL_EXTENSIONS = {
    "py", "ts", "js", "go", "rs", "java", "rb", "tsx", "jsx", "cs", "swift", "kt",
    "c", "cpp", "h", "hpp", "json", "yaml", "yml", "toml", "tf", "hcl",
    "sql", "sh", "bash", "zsh", "md",
}

# Generic words that look like file references but aren't
_FILE_STOPWORDS = {
    "e.g", "i.e", "etc", "vs", "ex", "cf", "inc", "no", "ok", "id",
}


def extract_file_references(text: str) -> Set[str]:
    """Extract file path references from task subject + description text.

    Returns a set of normalized file path strings. Only includes paths with
    meaningful extensions to avoid false positives on common words.
    """
    refs: Set[str] = set()

    for match in _FILE_PATH_RE.finditer(text):
        candidate = match.group(0).lower().strip("./")

        # Must have a known extension
        ext = candidate.rsplit(".", 1)[-1] if "." in candidate else ""
        if ext not in _MEANINGFUL_EXTENSIONS:
            continue

        # Skip stopwords
        if candidate in _FILE_STOPWORDS:
            continue

        # Skip short stems (e.g., "v1.0", "no.1") — require stem >= 3 chars
        stem = candidate.rsplit(".", 1)[0] if "." in candidate else candidate
        if len(stem) < 3:
            continue

        # Normalize: strip leading/trailing slashes, lowercase
        normalized = candidate.strip("/")
        if normalized:
            refs.add(normalized)

    return refs


def _task_files(task: Dict) -> Set[str]:
    """Extract file references from a task dict."""
    text = task.get("subject", "") + " " + task.get("description", "")
    return extract_file_references(text)


# ---------------------------------------------------------------------------
# Dependency analysis
# ---------------------------------------------------------------------------

def _tasks_conflict(files_a: Set[str], files_b: Set[str], strict: bool = False) -> bool:
    """Return True if two tasks share file references.

    In normal mode, checks for exact file path overlap.
    In strict mode, also checks for shared parent directories (indirect deps).
    """
    if not files_a or not files_b:
        return False
    # Direct overlap
    if files_a & files_b:
        return True
    if not strict:
        return False
    # Strict: check shared parent directories (indirect dependency)
    dirs_a = {str(Path(f).parent) for f in files_a if "/" in f}
    dirs_b = {str(Path(f).parent) for f in files_b if "/" in f}
    return bool(dirs_a & dirs_b)


def analyze_dependencies(
    tasks: List[Dict],
    max_parallelism: int = 3,
    strict: bool = False,
) -> List[Dict]:
    """Analyze task dependencies and group into parallel/sequential batches.

    Algorithm:
    1. Extract file references for each task
    2. Build conflict graph: edge between tasks that share file references
    3. Greedily pack tasks into parallel batches:
       - A task can join the current batch if it does NOT conflict with any
         task already in the batch AND the batch has capacity (max_parallelism)
       - Otherwise it starts the next batch (sequential relative to previous)

    Args:
        tasks: List of task dicts with at least 'id', 'subject', 'description' keys.
        max_parallelism: Maximum number of tasks in a single parallel batch (default: 3).
        strict: If True, tasks sharing a parent directory are also considered conflicting.
                This prevents parallel dispatch when indirect file dependencies exist.

    Returns:
        List of batch dicts: {batch: int, tasks: list[str], parallel: bool}
        Tasks are represented by their 'id' field.
    """
    if not tasks:
        return []

    # Pre-compute file references for all tasks
    task_files: Dict[str, Set[str]] = {
        task["id"]: _task_files(task) for task in tasks
    }

    batches: List[Dict] = []
    current_batch_ids: List[str] = []
    current_batch_files: Set[str] = set()
    batch_num = 1

    def flush_batch():
        nonlocal batch_num, current_batch_ids, current_batch_files
        if current_batch_ids:
            batches.append({
                "batch": batch_num,
                "tasks": list(current_batch_ids),
                "parallel": len(current_batch_ids) > 1,
            })
            batch_num += 1
            current_batch_ids = []
            current_batch_files = set()

    for task in tasks:
        task_id = task["id"]
        files = task_files[task_id]

        # Check if this task conflicts with the current batch
        conflicts_with_batch = _tasks_conflict(files, current_batch_files, strict=strict)
        batch_full = len(current_batch_ids) >= max_parallelism

        if conflicts_with_batch or batch_full:
            # Start a new batch
            flush_batch()

        current_batch_ids.append(task_id)
        current_batch_files |= files

    # Flush the last batch
    flush_batch()

    return batches


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze build task dependencies for parallel execution"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--tasks-file",
        type=Path,
        default=None,
        help="Path to JSON file containing task list",
    )
    group.add_argument(
        "--stdin",
        action="store_true",
        help="Read task list JSON from stdin",
    )
    parser.add_argument(
        "--max-parallelism",
        type=int,
        default=3,
        help="Maximum tasks per parallel batch (default: 3)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict isolation: block parallel dispatch when tasks share parent directories",
    )
    args = parser.parse_args()

    # Load tasks
    if args.stdin:
        raw = sys.stdin.read()
    elif args.tasks_file:
        raw = args.tasks_file.read_text()
    else:
        parser.error("Provide --tasks-file or --stdin")
        return

    try:
        tasks = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(tasks, list):
        print("Error: input must be a JSON array of task objects", file=sys.stderr)
        sys.exit(1)

    batches = analyze_dependencies(tasks, max_parallelism=args.max_parallelism, strict=args.strict)

    indent = 2 if args.pretty else None
    print(json.dumps(batches, indent=indent))

    # Summary to stderr
    parallel_count = sum(1 for b in batches if b["parallel"])
    sequential_count = len(batches) - parallel_count
    print(
        f"[dependency-analyzer] {len(tasks)} tasks → {len(batches)} batches "
        f"({parallel_count} parallel, {sequential_count} sequential)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
