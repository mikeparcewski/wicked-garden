#!/usr/bin/env python3
"""
Task Evidence Validation — wicked-crew issue #253.

Validates that completed task descriptions include required evidence fields
at the appropriate level for the task's complexity score.

Usage:
    from evidence import validate_evidence, EVIDENCE_SCHEMA

    result = validate_evidence(task_description, complexity_score=3)
    # result = {valid: bool, missing: list[str], warnings: list[str]}

Evidence requirements by complexity tier:
    Low   (1-2): code_diff + test_results
    Medium (3-4): code_diff + test_results + verification
    High   (5+):  code_diff + test_results + verification + performance + assumptions
"""

import re
import sys
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Evidence schema — required fields per complexity tier
# ---------------------------------------------------------------------------
# Each tier describes what "complete" evidence looks like.
# Fields are detected via regex patterns in the task description text.
# Higher tiers are cumulative (medium = low + verification).

EVIDENCE_SCHEMA: Dict[str, Dict] = {
    "low": {
        "complexity_range": (1, 2),
        "required": [
            {
                "field": "test_results",
                "label": "Test results (e.g. '- Test: test_name — PASS/FAIL')",
                "patterns": [
                    r"\btest\b.*\b(pass|fail|passed|failed)\b",
                    r"\b(pass|fail|passed|failed)\b.*\btest\b",
                    r"- Test:.*—\s*(PASS|FAIL)",
                    r"\btests? (pass|fail|passing|failing)\b",
                    r"\bunit test\b",
                    r"\btest results?\b",
                ],
            },
            {
                "field": "code_diff",
                "label": "Code diff reference (e.g. '- Code diff: ...' or '- File: path — modified/created')",
                "patterns": [
                    r"\bcode diff\b",
                    r"- File:.*—\s*(modified|created|updated|deleted|added)",
                    r"\bchanged files?\b",
                    r"\bmodified\b.*\.(py|ts|js|go|rs|java|rb|tsx|jsx|cs|swift|kt)\b",
                    r"\.(py|ts|js|go|rs|java|rb|tsx|jsx|cs|swift|kt).*\b(modified|created|updated)\b",
                    r"\bpatch\b",
                    r"\bdiff\b.*\bline\b",
                ],
            },
        ],
        "warnings": [],
    },
    "medium": {
        "complexity_range": (3, 4),
        "required": [
            {
                "field": "test_results",
                "label": "Test results (e.g. '- Test: test_name — PASS/FAIL')",
                "patterns": [
                    r"\btest\b.*\b(pass|fail|passed|failed)\b",
                    r"\b(pass|fail|passed|failed)\b.*\btest\b",
                    r"- Test:.*—\s*(PASS|FAIL)",
                    r"\btests? (pass|fail|passing|failing)\b",
                    r"\bunit test\b",
                    r"\btest results?\b",
                ],
            },
            {
                "field": "code_diff",
                "label": "Code diff reference (e.g. '- Code diff: ...' or '- File: path — modified/created')",
                "patterns": [
                    r"\bcode diff\b",
                    r"- File:.*—\s*(modified|created|updated|deleted|added)",
                    r"\bchanged files?\b",
                    r"\bmodified\b.*\.(py|ts|js|go|rs|java|rb|tsx|jsx|cs|swift|kt)\b",
                    r"\.(py|ts|js|go|rs|java|rb|tsx|jsx|cs|swift|kt).*\b(modified|created|updated)\b",
                    r"\bpatch\b",
                    r"\bdiff\b.*\bline\b",
                ],
            },
            {
                "field": "verification",
                "label": "Verification step (e.g. '- Verification: curl ... returns 200' or command output)",
                "patterns": [
                    r"\bverif(y|ied|ication)\b",
                    r"- Verification:",
                    r"\bconfirmed\b.*\bworking\b",
                    r"\bmanually tested\b",
                    r"\bsmoke test\b",
                    r"\bchecked in\b.*\bstaging\b",
                    r"\bstaging\b.*\bconfirmed\b",
                    r"\bvalidated\b",
                    r"\bcurl\b.*\b(return|returns|returned)\b",
                    r"\bresponse\b.*\b(200|201|204)\b",
                ],
            },
        ],
        "warnings": [],
    },
    "high": {
        "complexity_range": (5, 7),
        "required": [
            {
                "field": "test_results",
                "label": "Test results (e.g. '- Test: test_name — PASS/FAIL')",
                "patterns": [
                    r"\btest\b.*\b(pass|fail|passed|failed)\b",
                    r"\b(pass|fail|passed|failed)\b.*\btest\b",
                    r"- Test:.*—\s*(PASS|FAIL)",
                    r"\btests? (pass|fail|passing|failing)\b",
                    r"\bunit test\b",
                    r"\btest results?\b",
                ],
            },
            {
                "field": "code_diff",
                "label": "Code diff reference (e.g. '- Code diff: ...' or '- File: path — modified/created')",
                "patterns": [
                    r"\bcode diff\b",
                    r"- File:.*—\s*(modified|created|updated|deleted|added)",
                    r"\bchanged files?\b",
                    r"\bmodified\b.*\.(py|ts|js|go|rs|java|rb|tsx|jsx|cs|swift|kt)\b",
                    r"\.(py|ts|js|go|rs|java|rb|tsx|jsx|cs|swift|kt).*\b(modified|created|updated)\b",
                    r"\bpatch\b",
                    r"\bdiff\b.*\bline\b",
                ],
            },
            {
                "field": "verification",
                "label": "Verification step (e.g. '- Verification: curl ... returns 200' or command output)",
                "patterns": [
                    r"\bverif(y|ied|ication)\b",
                    r"- Verification:",
                    r"\bconfirmed\b.*\bworking\b",
                    r"\bmanually tested\b",
                    r"\bsmoke test\b",
                    r"\bchecked in\b.*\bstaging\b",
                    r"\bstaging\b.*\bconfirmed\b",
                    r"\bvalidated\b",
                    r"\bcurl\b.*\b(return|returns|returned)\b",
                    r"\bresponse\b.*\b(200|201|204)\b",
                ],
            },
            {
                "field": "performance",
                "label": "Performance data (e.g. latency, throughput, benchmark results)",
                "patterns": [
                    r"\bperformance\b.*\b(test|metric|benchmark|result|data)\b",
                    r"- Performance:",
                    r"- Benchmark:",
                    r"\blatency\b",
                    r"\bthroughput\b",
                    r"\bp\d{2}\b.*\bms\b",
                    r"\brps\b",
                    r"\bops/sec\b",
                    r"\bbenchmark\b",
                    r"\bprofile\b.*\b(result|output|data)\b",
                    r"\bmetric(s)?\b.*\b(show|indicate|report)\b",
                    r"\bload test\b",
                ],
            },
            {
                "field": "assumptions",
                "label": "Documented assumptions (e.g. '## Assumptions' section or '- Assumption:')",
                "patterns": [
                    r"## Assumptions",
                    r"- Assumption:",
                    r"\bassuming\b",
                    r"\bassumptions?\b.*:",
                    r"\bprecondition\b",
                    r"\brequires?\b.*\bpre[-\s]?exist\b",
                ],
            },
        ],
        "warnings": [],
    },
}


def _get_tier(complexity_score: int) -> str:
    """Map complexity score to evidence tier name."""
    if complexity_score <= 0:
        return "low"  # Treat 0 as low — no evidence required but schema applies
    if complexity_score <= 2:
        return "low"
    if complexity_score <= 4:
        return "medium"
    return "high"


def _check_field(text: str, field_spec: dict) -> bool:
    """Return True if the field is detected in text."""
    for pattern in field_spec["patterns"]:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def validate_evidence(
    task_description: str,
    complexity_score: int,
) -> Dict:
    """Validate that a task description includes required evidence for the complexity level.

    Args:
        task_description: The full text of the task's completed description, including
                          ## Outcome, ## Evidence, ## Assumptions sections.
        complexity_score: The task's complexity score (0-7). Maps to tiers:
                          0-2 → low, 3-4 → medium, 5-7 → high

    Returns:
        dict with keys:
            valid (bool): True if all required fields are present
            missing (list[str]): Human-readable labels for missing required fields
            warnings (list[str]): Advisory warnings (non-blocking)
    """
    tier = _get_tier(complexity_score)
    schema = EVIDENCE_SCHEMA.get(tier, EVIDENCE_SCHEMA["low"])

    missing: List[str] = []
    warnings: List[str] = list(schema.get("warnings", []))

    for field_spec in schema["required"]:
        if not _check_field(task_description, field_spec):
            missing.append(field_spec["label"])

    # Always-advisory: suggest Assumptions section for any complexity >= 3
    if complexity_score >= 3:
        assumptions_present = re.search(
            r"## Assumptions|## Assumption|\bassumptions?\b.*:|assuming\b",
            task_description,
            re.IGNORECASE,
        )
        if not assumptions_present and not any("assumptions" in m.lower() for m in missing):
            warnings.append(
                "Consider documenting assumptions (## Assumptions section) "
                "for medium/high complexity tasks to help reviewers."
            )

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# CLI interface for ad-hoc validation
# ---------------------------------------------------------------------------

def main():
    """CLI: validate evidence from stdin or a file."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Validate task completion evidence for wicked-crew"
    )
    parser.add_argument("--complexity", type=int, default=2,
                        help="Complexity score 0-7 (default: 2)")
    parser.add_argument("--file", type=str, default=None,
                        help="Path to task description file (default: read from stdin)")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    result = validate_evidence(text, args.complexity)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASS" if result["valid"] else "FAIL"
        print(f"Evidence validation: {status}")
        if result["missing"]:
            print("Missing required fields:")
            for m in result["missing"]:
                print(f"  - {m}")
        if result["warnings"]:
            print("Warnings:")
            for w in result["warnings"]:
                print(f"  - {w}")


# ---------------------------------------------------------------------------
# Test evidence validation — QE crew integration
# ---------------------------------------------------------------------------
# Validates that a test task's artifact list satisfies evidence requirements
# for its change type (ui, api, or both/integration).
#
# Evidence taxonomy (canonical source: skills/qe/qe-strategy/refs/test-type-taxonomy.md):
#   UI:  requires at least one "image" artifact (screenshot)
#   API: requires one "api_request" AND one "api_response" artifact
#   Both (integration): requires all of the above
#
# Usage (import):
#   from evidence import validate_test_evidence
#   result = validate_test_evidence(task.artifacts, "ui")
#   # result = {valid: bool, missing: list[str], present: list[str]}
#
# Usage (CLI — extension of main() below):
#   python3 evidence.py --validate-test --artifacts '[{"type":"image","path":"..."}]' --test-type ui

# Artifact type matching — maps evidence requirement names to accepted artifact types
# NOTE: Keep in sync with EVIDENCE_TAXONOMY in scripts/crew/test_task_factory.py
_TEST_EVIDENCE_REQUIREMENTS: Dict[str, Dict] = {
    "ui": {
        "screenshot": {
            "label": "screenshot",
            "accepted_types": {"image", "screenshot"},
        },
    },
    "api": {
        "request_payload": {
            "label": "request_payload",
            "accepted_types": {"api_request", "request"},
        },
        "response_payload": {
            "label": "response_payload",
            "accepted_types": {"api_response", "response"},
        },
    },
}


def validate_test_evidence(task_artifacts: list, test_type: str) -> Dict:
    """Validate that a test task has required evidence for its test_type.

    Checks artifact types against the canonical evidence taxonomy. Optional
    artifacts (visual_diff, response_timing) do not affect validity.

    Args:
        task_artifacts: list of artifact dicts from kanban task record.
            Each artifact dict has at minimum: {"type": str, "name": str}
            and optionally "path" and/or "content" fields.
        test_type: "ui", "api", or "both" (integration requires all)

    Returns:
        dict with keys:
            valid (bool): True if all required artifacts are present
            missing (list[str]): Human-readable labels for missing required artifacts
            present (list[str]): Human-readable labels for satisfied requirements
    """
    if test_type not in ("ui", "api", "both"):
        return {
            "valid": False,
            "missing": [f"Unknown test_type '{test_type}' — expected 'ui', 'api', or 'both'"],
            "present": [],
        }

    # Build the set of requirements based on test_type
    requirements: Dict[str, Dict] = {}
    if test_type in ("ui", "both"):
        requirements.update(_TEST_EVIDENCE_REQUIREMENTS["ui"])
    if test_type in ("api", "both"):
        requirements.update(_TEST_EVIDENCE_REQUIREMENTS["api"])

    # Collect all artifact types present in the task
    artifact_types: List[str] = []
    for artifact in task_artifacts:
        artifact_type = artifact.get("type", "").lower().strip()
        if artifact_type:
            artifact_types.append(artifact_type)

    # Check each requirement
    missing: List[str] = []
    present: List[str] = []

    for req_name, req_spec in requirements.items():
        accepted = req_spec["accepted_types"]
        satisfied = any(atype in accepted for atype in artifact_types)
        if satisfied:
            present.append(req_spec["label"])
        else:
            missing.append(req_spec["label"])

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "present": present,
    }


if __name__ == "__main__":
    main()
