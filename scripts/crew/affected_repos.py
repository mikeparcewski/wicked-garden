#!/usr/bin/env python3
"""affected_repos.py — Render the optional `affected_repos` advisory line (#722).

Surfaces the OPTIONAL ``affected_repos`` field from a project's
``process-plan.json`` as a single human-readable line. This is the read
side of the multi-repo *advisory* surface added by issue #722 — the
write side is the field on the existing process-plan, populated by the
facilitator (or the user directly editing the plan).

There is intentionally no DAG, no merge-order validator, no worktree
provisioning, no cross-repo evidence aggregation. Those belong to a
sibling v9 plugin (``wicked-garden-monorepo``); see
``docs/v9/sibling-plugin-monorepo.md`` for the full design brief and
demand criteria for when that plugin should actually get built.

Usage:
    affected_repos.py render --plan path/to/process-plan.json
    affected_repos.py render --project-dir path/to/project
    affected_repos.py json   --plan path/to/process-plan.json

Behaviour:
  - When ``affected_repos`` is missing, empty, or malformed, the CLI
    prints NOTHING and exits 0. Callers can pipe the output directly
    into the briefing / status template — silence means "skip this
    section." This keeps the surface backward-compatible: existing
    projects that never set the field show no new line.
  - When the field is present and non-empty, the CLI prints exactly:

        Affected repos: foo, bar (advisory — see docs/v9/sibling-plugin-monorepo.md)

    The repo names are rendered in the order they appear in the plan
    (no sorting — the facilitator's order may carry signal).

Stdlib-only. Cross-platform (no shell features). Fail-open: any read or
parse error is swallowed and the script exits 0 with no output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# Doc pointer kept as a module constant so the test can assert the line
# text without re-deriving the URL. R3: no magic strings in callers.
ADVISORY_DOC = "docs/v9/sibling-plugin-monorepo.md"
ADVISORY_LINE_PREFIX = "Affected repos:"
ADVISORY_LINE_SUFFIX = f"(advisory — see {ADVISORY_DOC})"


# ---------------------------------------------------------------------------
# Public API — pure functions, no I/O. Easy to test without fixtures.
# ---------------------------------------------------------------------------

def extract_affected_repos(plan: dict) -> List[str]:
    """Return the cleaned ``affected_repos`` list from *plan*.

    Defensive parser: accepts only the documented shape (list of
    non-empty strings). Anything else returns an empty list — the field
    is advisory and never blocks. Validation of malformed shapes is the
    job of ``scripts/crew/validate_plan.py``; this function exists to
    *render* what's there, not to police it.
    """
    if not isinstance(plan, dict):
        return []
    raw = plan.get("affected_repos")
    if not isinstance(raw, list):
        return []
    cleaned: List[str] = []
    for entry in raw:
        if isinstance(entry, str) and entry.strip():
            cleaned.append(entry.strip())
    return cleaned


def render_line(repos: List[str]) -> str:
    """Render the advisory line. Empty list → empty string (skip)."""
    if not repos:
        return ""
    names = ", ".join(repos)
    return f"{ADVISORY_LINE_PREFIX} {names} {ADVISORY_LINE_SUFFIX}"


def render_from_plan(plan: dict) -> str:
    """Convenience: extract + render in one call."""
    return render_line(extract_affected_repos(plan))


# ---------------------------------------------------------------------------
# I/O — guarded so the CLI is fail-open
# ---------------------------------------------------------------------------

def _resolve_plan_path(plan_path: Optional[Path], project_dir: Optional[Path]) -> Optional[Path]:
    """Pick the plan file path. ``plan_path`` wins over ``project_dir``."""
    if plan_path is not None:
        return plan_path
    if project_dir is not None:
        return project_dir / "process-plan.json"
    return None


def _load_plan(path: Path) -> Optional[dict]:
    """Read and parse the plan file. Returns None on any error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_source_args(p: argparse.ArgumentParser) -> None:
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--plan",
        type=Path,
        help="Path to process-plan.json (preferred when the caller already knows it).",
    )
    src.add_argument(
        "--project-dir",
        type=Path,
        help="Project directory; resolves to <dir>/process-plan.json.",
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the optional affected_repos advisory line (#722).",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    render_parser = sub.add_parser(
        "render",
        help="Print the human-readable advisory line, or nothing when unset.",
    )
    _add_source_args(render_parser)

    json_parser = sub.add_parser(
        "json",
        help="Print {\"affected_repos\": [...]} as JSON for programmatic callers.",
    )
    _add_source_args(json_parser)

    args = parser.parse_args(argv)

    path = _resolve_plan_path(getattr(args, "plan", None), getattr(args, "project_dir", None))
    if path is None:
        # argparse's mutually_exclusive_group(required=True) should
        # prevent this, but defence-in-depth: stay silent rather than
        # crashing the briefing when called from a shell pipeline.
        return 0

    plan = _load_plan(path)
    if plan is None:
        # Plan missing or unparseable. The advisory line is purely
        # additive — never escalate this to an error that breaks
        # crew:status / smaht:briefing rendering.
        return 0

    repos = extract_affected_repos(plan)

    if args.action == "render":
        line = render_line(repos)
        if line:
            sys.stdout.write(line + "\n")
        return 0

    if args.action == "json":
        sys.stdout.write(json.dumps({"affected_repos": repos}) + "\n")
        return 0

    return 0  # pragma: no cover — argparse rejects unknown actions earlier


if __name__ == "__main__":
    sys.exit(main())
