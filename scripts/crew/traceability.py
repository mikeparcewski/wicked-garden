#!/usr/bin/env python3
"""
Traceability Store — cross-phase traceability links with forward/reverse traversal.

Manages structured links between artifacts across crew phases (requirements,
design decisions, code, tests, evidence) using DomainStore for persistence.
Supports BFS-based forward and reverse graph traversal plus coverage reporting.

Usage (CLI):
    traceability.py create --source-id X --source-type requirement --target-id Y \
        --target-type design --link-type TRACES_TO --project P --created-by clarify
    traceability.py forward --source-id X --project P
    traceability.py reverse --target-id X --project P
    traceability.py coverage --project P
    traceability.py list --project P [--link-type TRACES_TO]
    traceability.py delete --project P [--source-id X]

Usage (Python):
    from traceability import create_link, forward_trace, reverse_trace, coverage_report
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Import DomainStore from parent scripts/ directory
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _domain_store import DomainStore

_ds = DomainStore("wicked-crew")

# Source name used in DomainStore for all traceability links
_SOURCE = "traceability"

# ---------------------------------------------------------------------------
# Valid link types
# ---------------------------------------------------------------------------

VALID_LINK_TYPES = frozenset({
    "TRACES_TO",          # requirement → design
    "IMPLEMENTED_BY",     # design → code
    "TESTED_BY",          # requirement/code → test scenario
    "VERIFIES",           # test result → requirement
    "SATISFIES",          # evidence → requirement
    "CONSENSUS_REVIEWED", # gate artifact → consensus report (multi-perspective review)
})

# Artifact types that represent "complete" coverage endpoints
_COVERAGE_ENDPOINTS = frozenset({"test_scenario", "evidence"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    """ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _all_links(project_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch all traceability links, optionally filtered by project."""
    links = _ds.list(_SOURCE)
    if project_id:
        links = [lnk for lnk in links if lnk.get("project_id") == project_id]
    return links


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_link(
    source_id: str,
    source_type: str,
    target_id: str,
    target_type: str,
    link_type: str,
    project_id: str,
    created_by: str,
) -> dict[str, Any]:
    """Create a traceability link between two artifacts.

    Args:
        source_id:   Identifier of the source artifact.
        source_type: Type of source (requirement, design, code, test_scenario, evidence).
        target_id:   Identifier of the target artifact.
        target_type: Type of target.
        link_type:   One of VALID_LINK_TYPES.
        project_id:  Crew project name.
        created_by:  Phase or agent that created this link.

    Returns:
        The created link record dict.

    Raises:
        ValueError: If link_type is not in VALID_LINK_TYPES.
    """
    if link_type not in VALID_LINK_TYPES:
        raise ValueError(
            f"Invalid link_type '{link_type}'. Must be one of: {', '.join(sorted(VALID_LINK_TYPES))}"
        )

    link_data: dict[str, Any] = {
        "id": f"link-{uuid.uuid4()}",
        "source_id": source_id,
        "source_type": source_type,
        "target_id": target_id,
        "target_type": target_type,
        "link_type": link_type,
        "project_id": project_id,
        "created_at": _now(),
        "created_by": created_by,
    }

    result = _ds.create(_SOURCE, link_data)
    return result if result else link_data


def get_links(
    source_id: str | None = None,
    target_id: str | None = None,
    link_type: str | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Query traceability links with optional filters.

    All filters are AND-combined. Omitted filters match everything.

    Returns:
        List of matching link records.
    """
    links = _all_links(project_id)

    if source_id:
        links = [lnk for lnk in links if lnk.get("source_id") == source_id]
    if target_id:
        links = [lnk for lnk in links if lnk.get("target_id") == target_id]
    if link_type:
        links = [lnk for lnk in links if lnk.get("link_type") == link_type]

    return links


def forward_trace(
    source_id: str,
    project_id: str,
) -> list[dict[str, Any]]:
    """Walk the link graph forward from source_id using BFS.

    Follows source_id → target_id edges, collecting all reachable links.
    For example: requirement → design → code → test → evidence.

    Returns:
        Ordered list of link records encountered during traversal.
    """
    all_links = _all_links(project_id)

    # Build adjacency: source_id → list of links
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for lnk in all_links:
        sid = lnk.get("source_id", "")
        adjacency.setdefault(sid, []).append(lnk)

    visited: set[str] = set()
    result: list[dict[str, Any]] = []
    queue: deque[str] = deque([source_id])

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        for lnk in adjacency.get(current, []):
            result.append(lnk)
            tid = lnk.get("target_id", "")
            if tid and tid not in visited:
                queue.append(tid)

    return result


def reverse_trace(
    target_id: str,
    project_id: str,
) -> list[dict[str, Any]]:
    """Walk the link graph backward from target_id using BFS.

    Follows target_id → source_id edges, collecting all reachable links.
    For example: evidence → test → code → design → requirement.

    Returns:
        Ordered list of link records encountered during traversal.
    """
    all_links = _all_links(project_id)

    # Build reverse adjacency: target_id → list of links
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for lnk in all_links:
        tid = lnk.get("target_id", "")
        adjacency.setdefault(tid, []).append(lnk)

    visited: set[str] = set()
    result: list[dict[str, Any]] = []
    queue: deque[str] = deque([target_id])

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        for lnk in adjacency.get(current, []):
            result.append(lnk)
            sid = lnk.get("source_id", "")
            if sid and sid not in visited:
                queue.append(sid)

    return result


def coverage_report(project_id: str) -> dict[str, Any]:
    """Generate a coverage report for all requirements in a project.

    Finds all artifacts of type "requirement" (appearing as source_type in any
    link) and checks whether each has a complete forward chain reaching at
    least one coverage endpoint (test_scenario or evidence).

    Returns:
        Dict with keys:
            - total_requirements: int
            - covered: list of {id, endpoints: [target_ids]}
            - gaps: list of {id, reached_types: [types reached but no endpoint]}
            - coverage_pct: float (0-100)
    """
    all_links = _all_links(project_id)

    # Discover all requirement IDs (anything that appears as source with type "requirement")
    requirement_ids: set[str] = set()
    for lnk in all_links:
        if lnk.get("source_type") == "requirement":
            requirement_ids.add(lnk["source_id"])

    if not requirement_ids:
        return {
            "total_requirements": 0,
            "covered": [],
            "gaps": [],
            "coverage_pct": 0.0,
        }

    # Build forward adjacency once
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for lnk in all_links:
        sid = lnk.get("source_id", "")
        adjacency.setdefault(sid, []).append(lnk)

    covered: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for req_id in sorted(requirement_ids):
        # BFS forward from this requirement
        visited: set[str] = set()
        endpoints: list[str] = []
        reached_types: set[str] = set()
        queue: deque[str] = deque([req_id])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            for lnk in adjacency.get(current, []):
                tt = lnk.get("target_type", "")
                tid = lnk.get("target_id", "")
                reached_types.add(tt)

                if tt in _COVERAGE_ENDPOINTS:
                    endpoints.append(tid)

                if tid and tid not in visited:
                    queue.append(tid)

        if endpoints:
            covered.append({"id": req_id, "endpoints": endpoints})
        else:
            gaps.append({"id": req_id, "reached_types": sorted(reached_types)})

    total = len(requirement_ids)
    pct = (len(covered) / total * 100.0) if total > 0 else 0.0

    return {
        "total_requirements": total,
        "covered": covered,
        "gaps": gaps,
        "coverage_pct": round(pct, 1),
    }


def delete_links(
    project_id: str | None = None,
    source_id: str | None = None,
) -> int:
    """Delete traceability links matching the given filters.

    At least one of project_id or source_id must be provided to prevent
    accidental deletion of all links.

    Returns:
        Number of links deleted.
    """
    if not project_id and not source_id:
        raise ValueError("At least one of project_id or source_id must be provided.")

    links = _all_links(project_id)

    if source_id:
        links = [lnk for lnk in links if lnk.get("source_id") == source_id]

    count = 0
    for lnk in links:
        link_id = lnk.get("id")
        if link_id and _ds.delete(_SOURCE, link_id):
            count += 1

    return count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="traceability.py",
        description="Cross-phase traceability link management for wicked-crew.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- create --
    p_create = sub.add_parser("create", help="Create a traceability link")
    p_create.add_argument("--source-id", required=True, help="Source artifact ID")
    p_create.add_argument("--source-type", required=True, help="Source artifact type")
    p_create.add_argument("--target-id", required=True, help="Target artifact ID")
    p_create.add_argument("--target-type", required=True, help="Target artifact type")
    p_create.add_argument(
        "--link-type", required=True,
        choices=sorted(VALID_LINK_TYPES),
        help="Relationship type",
    )
    p_create.add_argument("--project", required=True, help="Project ID")
    p_create.add_argument("--created-by", required=True, help="Phase or agent that created this link")

    # -- forward --
    p_fwd = sub.add_parser("forward", help="Walk forward trace from a source")
    p_fwd.add_argument("--source-id", required=True, help="Starting artifact ID")
    p_fwd.add_argument("--project", required=True, help="Project ID")

    # -- reverse --
    p_rev = sub.add_parser("reverse", help="Walk reverse trace from a target")
    p_rev.add_argument("--target-id", required=True, help="Starting artifact ID")
    p_rev.add_argument("--project", required=True, help="Project ID")

    # -- coverage --
    p_cov = sub.add_parser("coverage", help="Coverage report for a project")
    p_cov.add_argument("--project", required=True, help="Project ID")

    # -- list --
    p_list = sub.add_parser("list", help="List traceability links")
    p_list.add_argument("--project", required=True, help="Project ID")
    p_list.add_argument("--link-type", default=None, help="Filter by link type")
    p_list.add_argument("--source-id", default=None, help="Filter by source ID")
    p_list.add_argument("--target-id", default=None, help="Filter by target ID")

    # -- delete --
    p_del = sub.add_parser("delete", help="Delete traceability links")
    p_del.add_argument("--project", default=None, help="Project ID")
    p_del.add_argument("--source-id", default=None, help="Filter by source ID")

    return parser


def _run_cli(args: argparse.Namespace) -> None:
    """Dispatch CLI command and print JSON result to stdout."""
    result: Any

    if args.command == "create":
        try:
            result = create_link(
                source_id=args.source_id,
                source_type=args.source_type,
                target_id=args.target_id,
                target_type=args.target_type,
                link_type=args.link_type,
                project_id=args.project,
                created_by=args.created_by,
            )
        except ValueError as exc:
            result = {"error": str(exc)}

    elif args.command == "forward":
        result = forward_trace(source_id=args.source_id, project_id=args.project)

    elif args.command == "reverse":
        result = reverse_trace(target_id=args.target_id, project_id=args.project)

    elif args.command == "coverage":
        result = coverage_report(project_id=args.project)

    elif args.command == "list":
        result = get_links(
            source_id=args.source_id,
            target_id=args.target_id,
            link_type=args.link_type,
            project_id=args.project,
        )

    elif args.command == "delete":
        if not args.project and not args.source_id:
            result = {"error": "At least one of --project or --source-id is required."}
        else:
            try:
                count = delete_links(project_id=args.project, source_id=args.source_id)
                result = {"deleted": count}
            except ValueError as exc:
                result = {"error": str(exc)}

    else:
        result = {"error": f"Unknown command: {args.command}"}

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _run_cli(args)


if __name__ == "__main__":
    main()
