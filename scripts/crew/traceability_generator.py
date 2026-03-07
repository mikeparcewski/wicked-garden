#!/usr/bin/env python3
"""
Traceability Generator — wicked-crew issue #255.

Reads test-strategy deliverables from phases/test-strategy/ and maps
acceptance criteria to completed build tasks via TaskList metadata.

Outputs phases/build/traceability-matrix.md as a markdown table:
  Criterion ID | Description | Test File/Scenario | Build Task | Status

Usage:
    python3 traceability_generator.py --phases-dir phases/ --output phases/build/traceability-matrix.md
    python3 traceability_generator.py --phases-dir phases/ --project my-project --dry-run
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Acceptance criteria extraction
# ---------------------------------------------------------------------------

_AC_TABLE_ROW_RE = re.compile(
    r"\|\s*(?P<id>AC-\d+|[A-Z]{1,4}-\d+|\d+)\s*\|"
    r"\s*(?P<desc>[^|]+)\s*\|"
    r"\s*(?P<test>[^|]*)\s*\|",
    re.IGNORECASE,
)

_AC_LIST_RE = re.compile(
    r"[-*]\s+(?:\*\*)?(?P<id>AC-\d+|[A-Z]{1,4}-\d+)(?:\*\*)?\s*[:\-]\s*(?P<desc>.+)",
    re.IGNORECASE,
)

_AC_HEADER_RE = re.compile(
    r"(?:acceptance criteria|success criteria|test scenarios?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_acceptance_criteria(text: str) -> List[Dict]:
    """Extract acceptance criteria from markdown text.

    Supports:
    - Table rows: | ID | Description | Test File |
    - List items: - AC-001: Description

    Returns list of {id, description, test_file} dicts.
    """
    criteria = []
    seen_ids = set()

    # Try table format first (more structured)
    for match in _AC_TABLE_ROW_RE.finditer(text):
        ac_id = match.group("id").strip()
        desc = match.group("desc").strip()
        test_file = match.group("test").strip() if match.group("test") else ""

        # Skip header rows
        if "criterion" in desc.lower() or "description" in desc.lower():
            continue

        if ac_id not in seen_ids and desc:
            seen_ids.add(ac_id)
            criteria.append({
                "id": ac_id,
                "description": desc,
                "test_file": test_file,
            })

    # Fall back to list format
    if not criteria:
        for match in _AC_LIST_RE.finditer(text):
            ac_id = match.group("id").strip()
            desc = match.group("desc").strip()

            if ac_id not in seen_ids and desc:
                seen_ids.add(ac_id)
                criteria.append({
                    "id": ac_id,
                    "description": desc,
                    "test_file": "",
                })

    return criteria


def read_test_strategy(phases_dir: Path) -> List[Dict]:
    """Read all markdown files in phases/test-strategy/ and extract criteria."""
    strategy_dir = phases_dir / "test-strategy"
    if not strategy_dir.exists():
        # Try legacy qe/ directory
        strategy_dir = phases_dir / "qe"

    if not strategy_dir.exists():
        return []

    all_criteria = []
    for md_file in sorted(strategy_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="replace")
        criteria = extract_acceptance_criteria(text)
        for c in criteria:
            c["source_file"] = str(md_file.name)
        all_criteria.extend(criteria)

    return all_criteria


# ---------------------------------------------------------------------------
# Task mapping
# ---------------------------------------------------------------------------

def _load_task_list_from_env() -> List[Dict]:
    """Try to load task list from environment (CLAUDE_TASK_LIST_JSON) or return empty."""
    raw = os.environ.get("CLAUDE_TASK_LIST_JSON", "")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass  # fail open: returns []
    return []


def _find_tasks_for_criterion(criterion: Dict, tasks: List[Dict]) -> Optional[Dict]:
    """Find a task that mentions the criterion ID or related keywords."""
    ac_id = criterion["id"].lower()
    desc_words = set(criterion["description"].lower().split())

    best_task = None
    best_score = 0

    for task in tasks:
        subject = task.get("subject", "").lower()
        description = task.get("description", "").lower()
        full_text = subject + " " + description

        score = 0
        if ac_id in full_text:
            score += 3
        # Word overlap with criterion description
        task_words = set(full_text.split())
        overlap = desc_words & task_words
        meaningful_overlap = {w for w in overlap if len(w) > 3}
        score += len(meaningful_overlap) * 0.5

        if score > best_score:
            best_score = score
            best_task = task

    return best_task if best_score > 0 else None


def map_criteria_to_tasks(
    criteria: List[Dict],
    tasks: List[Dict],
) -> List[Dict]:
    """Map each criterion to its best-matching task."""
    rows = []
    for criterion in criteria:
        task = _find_tasks_for_criterion(criterion, tasks)
        rows.append({
            "criterion_id": criterion["id"],
            "description": criterion["description"],
            "test_file": criterion.get("test_file", ""),
            "build_task": task.get("subject", "—") if task else "—",
            "status": task.get("status", "pending") if task else "not started",
            "source_file": criterion.get("source_file", ""),
        })
    return rows


# ---------------------------------------------------------------------------
# Matrix output
# ---------------------------------------------------------------------------

def render_matrix(rows: List[Dict], project: Optional[str] = None) -> str:
    """Render the traceability matrix as a markdown table."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    project_line = f"**Project**: {project}\n" if project else ""

    header = f"""# Traceability Matrix

{project_line}**Generated**: {now}

Maps test-strategy acceptance criteria to build phase tasks.

| Criterion ID | Description | Test File/Scenario | Build Task | Status |
|---|---|---|---|---|
"""

    def _escape(s: str) -> str:
        return s.replace("|", "\\|").replace("\n", " ").strip()

    body_lines = []
    for row in rows:
        status = row["status"]
        # Normalize status display
        if status in ("completed",):
            status_display = "completed"
        elif status in ("in_progress",):
            status_display = "in progress"
        elif status in ("pending",):
            status_display = "pending"
        else:
            status_display = status or "not started"

        line = (
            f"| {_escape(row['criterion_id'])} "
            f"| {_escape(row['description'])} "
            f"| {_escape(row['test_file'] or '—')} "
            f"| {_escape(row['build_task'])} "
            f"| {status_display} |"
        )
        body_lines.append(line)

    if not body_lines:
        body_lines.append("| — | No criteria found | — | — | — |")

    return header + "\n".join(body_lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a traceability matrix from test-strategy criteria and build tasks"
    )
    parser.add_argument(
        "--phases-dir",
        type=Path,
        default=Path("phases"),
        help="Path to the phases/ directory (default: phases/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: {phases-dir}/build/traceability-matrix.md)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Project name to include in the matrix header",
    )
    parser.add_argument(
        "--tasks-json",
        type=str,
        default=None,
        help="JSON string of task list (from TaskList output). If not provided, uses empty list.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the matrix to stdout without writing to file",
    )
    args = parser.parse_args()

    # Resolve output path
    output_path = args.output
    if output_path is None:
        output_path = args.phases_dir / "build" / "traceability-matrix.md"

    # Load test-strategy criteria
    criteria = read_test_strategy(args.phases_dir)
    if not criteria:
        print(
            f"[traceability] No acceptance criteria found in {args.phases_dir / 'test-strategy'}",
            file=sys.stderr,
        )

    # Load tasks
    tasks: List[Dict] = []
    if args.tasks_json:
        try:
            tasks = json.loads(args.tasks_json)
        except json.JSONDecodeError as e:
            print(f"[traceability] Warning: could not parse --tasks-json: {e}", file=sys.stderr)
    else:
        tasks = _load_task_list_from_env()

    # Map criteria to tasks
    rows = map_criteria_to_tasks(criteria, tasks)

    # Render matrix
    matrix = render_matrix(rows, project=args.project)

    if args.dry_run:
        print(matrix)
        print(
            f"[traceability] Dry run: {len(criteria)} criteria found, "
            f"{sum(1 for r in rows if r['build_task'] != '—')} mapped to tasks",
            file=sys.stderr,
        )
        return

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(matrix, encoding="utf-8")
    print(
        f"[traceability] Wrote {len(rows)} criteria to {output_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
