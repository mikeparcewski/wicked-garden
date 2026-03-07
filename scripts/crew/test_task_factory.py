#!/usr/bin/env python3
"""
Test Task Factory — wicked-crew QE integration.

Produces test task creation parameters from a detected change type and
implementation task subject. The model reads this JSON and executes the
TaskCreate and TaskUpdate calls — the script does NOT call TaskCreate itself.

Usage:
    python3 test_task_factory.py --change-type ui --impl-subject "Implement login form" --project "my-project"
    python3 test_task_factory.py --change-type api --impl-subject "Add auth endpoint" --project "auth-service" --json
    python3 test_task_factory.py --change-type both --impl-subject "Integrate payment flow" --project "checkout"

Output:
    JSON with test_tasks list. Each entry has subject, description, and metadata
    ready to be passed to TaskCreate. For "both" change type, two tasks are returned.
    For "unknown", an empty list is returned with a warning.

Evidence taxonomy (from architecture.md Section C):
    UI:  requires screenshot; optional visual_diff
    API: requires request_payload + response_payload; optional response_timing
    Both: requires all of the above
"""

import argparse
import json
import re
import sys
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Evidence taxonomy — source of truth
# See also: skills/qe/qe-strategy/refs/test-type-taxonomy.md
# ---------------------------------------------------------------------------

EVIDENCE_TAXONOMY = {
    "ui": {
        "test_category": "visual",
        "evidence_required": ["screenshot"],
        "evidence_optional": ["visual_diff"],
        "description_template": (
            "Visual test task for implementation: '{impl_description}'.\n\n"
            "Required evidence before completion:\n"
            "- screenshot: At least one screenshot of the rendered UI change "
            "(file path in phases/test/evidence/ or inline base64)\n"
            "- visual_diff: Optional but recommended — diff image showing before/after\n\n"
            "Collect evidence using:\n"
            "- Browser screenshot via Read tool or browser automation\n"
            "- Store screenshot at: phases/test/evidence/{safe_name}-screenshot.png\n\n"
            "Run validate_test_evidence([artifacts], 'ui') before marking this task complete.\n"
            "Task cannot be marked complete without at least one screenshot artifact."
        ),
    },
    "api": {
        "test_category": "endpoint",
        "evidence_required": ["request_payload", "response_payload"],
        "evidence_optional": ["response_timing"],
        "description_template": (
            "Endpoint test task for implementation: '{impl_description}'.\n\n"
            "Required evidence before completion:\n"
            "- request_payload: HTTP request body + headers (method, URL, headers, body)\n"
            "- response_payload: HTTP response body + status code\n"
            "- response_timing: Optional — response time in milliseconds\n\n"
            "Collect evidence using:\n"
            "- curl or httpie to call the endpoint\n"
            "- Store as kanban artifacts via add-artifact command\n"
            "- Request artifact type: api_request\n"
            "- Response artifact type: api_response\n\n"
            "Run validate_test_evidence([artifacts], 'api') before marking this task complete.\n"
            "Task cannot be marked complete without both request_payload and response_payload."
        ),
    },
}


# ---------------------------------------------------------------------------
# Phase prefix stripping
# ---------------------------------------------------------------------------

# Matches "Phase: " at the start
PHASE_PREFIX_PATTERN = re.compile(
    r"^(?:build|clarify|design|ideate|test-strategy|test|review|implement)\s*:\s*",
    re.IGNORECASE,
)


def _strip_phase_prefix(subject: str, project: str) -> str:
    """
    Strip the phase prefix and optional project name from an impl task subject.

    Examples:
        "Build: my-project - Implement login form" → "Implement login form"
        "Build: Implement login form" → "Implement login form"
        "Implement login form" → "Implement login form" (no-op)
    """
    # Strip "Phase: " prefix first
    stripped = PHASE_PREFIX_PATTERN.sub("", subject).strip()

    # After stripping phase prefix, the remaining text may be:
    #   "my-project - Implement login form"  (when project name is present)
    #   "Implement login form"               (when no project name follows)
    #
    # Strip "project-name - " if it appears at the start of the remainder
    if stripped and " - " in stripped:
        parts = stripped.split(" - ", 1)
        # If the first part matches the project name (case-insensitive), strip it
        if parts[0].strip().lower() == project.strip().lower():
            return parts[1].strip()

    return stripped


def _make_safe_name(text: str) -> str:
    """Convert text to a safe filename fragment."""
    safe = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return safe.strip("-")[:50]


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_test_tasks(
    change_type: str,
    impl_subject: str,
    project: str,
) -> Dict:
    """
    Generate test task creation parameters for a given change type.

    Args:
        change_type: "ui", "api", "both", or "unknown"
        impl_subject: The implementation task's subject (will be stripped of phase prefix)
        project: The project name

    Returns:
        dict with:
            test_tasks: list of task creation parameter dicts
            warning: optional string (present when change_type is "unknown")
    """
    # Strip phase prefix from impl subject for clean test task names
    impl_description = _strip_phase_prefix(impl_subject, project)
    safe_name = _make_safe_name(impl_description)

    if change_type == "unknown":
        return {
            "test_tasks": [],
            "suppressed": True,
            "warning": (
                f"change_type is 'unknown' — no test tasks created for '{impl_description}'. "
                "No UI or API files were detected. If this task touches UI or API code, "
                "re-run change_type_detector.py with the correct file paths."
            ),
        }

    if change_type not in ("ui", "api", "both"):
        return {
            "test_tasks": [],
            "suppressed": True,
            "warning": f"Unrecognized change_type '{change_type}' — no test tasks created.",
        }

    types_to_create = ["ui", "api"] if change_type == "both" else [change_type]
    test_tasks = []

    for test_type in types_to_create:
        taxonomy = EVIDENCE_TAXONOMY[test_type]
        test_category = taxonomy["test_category"]
        evidence_required = taxonomy["evidence_required"]
        evidence_optional = taxonomy["evidence_optional"]

        # Build subject using naming convention from architecture doc:
        # Test: {project-name} - {impl description} ({test_category})
        subject = f"Test: {project} - {impl_description} ({test_category})"

        # Fill description template
        description = taxonomy["description_template"].format(
            impl_description=impl_description,
            safe_name=safe_name,
        )

        task = {
            "subject": subject,
            "description": description,
            "metadata": {
                "initiative": project,
                "priority": "P1",
                "assigned_to": "acceptance-test-executor",
                "test_type": test_type,
                "evidence_required": evidence_required,
                "evidence_optional": evidence_optional,
                "impl_subject": impl_subject,
            },
        }
        test_tasks.append(task)

    return {"test_tasks": test_tasks}


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate test task creation parameters for QE integration"
    )
    parser.add_argument(
        "--change-type",
        required=True,
        choices=["ui", "api", "both", "unknown"],
        help="Change type detected by change_type_detector.py",
    )
    parser.add_argument(
        "--impl-subject",
        required=True,
        help="Implementation task subject (phase prefix will be stripped)",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project name (used in test task subject and initiative metadata)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (always true in practice; kept for CLI consistency)",
    )

    args = parser.parse_args()

    result = create_test_tasks(
        change_type=args.change_type,
        impl_subject=args.impl_subject,
        project=args.project,
    )

    # Always output JSON — this script is a data producer for model consumption
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
