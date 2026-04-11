"""Task completion evidence validation for wicked-crew.

Validates that task completion descriptions include the required evidence fields
for the given complexity level. Used by the reviewer agent and acceptance gates.

Evidence complexity levels:
  low (1-2):    code_diff + test_results
  medium (3-4): code_diff + test_results + verification
  high (5+):    code_diff + test_results + verification + performance

Usage as module:
  from evidence import validate_evidence, EVIDENCE_SCHEMA

Usage as CLI:
  echo "task_description" | python evidence.py --complexity 3
"""

import argparse
import re
import sys

# Schema: per-complexity-tier required evidence fields and their detection patterns
EVIDENCE_SCHEMA = {
    "low": {
        "complexity_range": (1, 2),
        "required": ["code_diff", "test_results"],
    },
    "medium": {
        "complexity_range": (3, 4),
        "required": ["code_diff", "test_results", "verification"],
    },
    "high": {
        "complexity_range": (5, 10),
        "required": ["code_diff", "test_results", "verification", "performance"],
    },
}

# Detection patterns for each evidence field
_PATTERNS = {
    "code_diff": re.compile(
        r"(code diff|diff:|changed:|modified:|added:|created:)",
        re.IGNORECASE,
    ),
    "test_results": re.compile(
        r"(test:|tests?/|\.py —|PASS|FAIL|test_\w+|pytest|unittest)",
        re.IGNORECASE,
    ),
    "verification": re.compile(
        r"(verification:|verified:|verify:|curl |http|endpoint|response|200|checked)",
        re.IGNORECASE,
    ),
    "performance": re.compile(
        r"(performance:|benchmark:|p\d{2,3} latency|ops/sec|rps|throughput|latency|ms |metric)",
        re.IGNORECASE,
    ),
}

_MISSING_MESSAGES = {
    "code_diff": "Missing code diff evidence (add 'Code diff:' line describing changes)",
    "test_results": "Missing test results evidence (add 'Test:' line showing test pass/fail)",
    "verification": "Missing verification evidence (add 'Verification:' line with a manual check)",
    "performance": "Missing performance evidence (add 'Performance:' or 'Benchmark:' metrics)",
}


def _get_tier(complexity_score: int) -> str:
    for tier, schema in EVIDENCE_SCHEMA.items():
        low, high = schema["complexity_range"]
        if low <= complexity_score <= high:
            return tier
    return "high"


def validate_evidence(task_description: str, complexity_score: int = 1) -> dict:
    """Validate task completion evidence against complexity-level requirements.

    Args:
        task_description: Markdown task description including Evidence section.
        complexity_score: Integer complexity score (1-10).

    Returns:
        dict with keys:
            valid (bool): True if all required evidence is present.
            missing (list[str]): Human-readable descriptions of missing fields.
            warnings (list[str]): Non-blocking recommendations.
            tier (str): The complexity tier used (low/medium/high).
    """
    tier = _get_tier(complexity_score)
    required = EVIDENCE_SCHEMA[tier]["required"]

    missing = []
    warnings = []

    for field in required:
        pattern = _PATTERNS[field]
        if not pattern.search(task_description):
            missing.append(_MISSING_MESSAGES[field])

    # Non-blocking: warn if no ## Evidence section at all
    if "## Evidence" not in task_description and "## Outcome" not in task_description:
        warnings.append(
            "No '## Evidence' or '## Outcome' section found — structured evidence sections improve reviewability"
        )

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "warnings": warnings,
        "tier": tier,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate task completion evidence")
    parser.add_argument(
        "--complexity",
        type=int,
        default=1,
        help="Complexity score 1-10 (default: 1)",
    )
    parser.add_argument(
        "--task-desc",
        help="Task description string (default: read from stdin)",
    )
    args = parser.parse_args()

    if args.task_desc:
        task_desc = args.task_desc
    else:
        task_desc = sys.stdin.read()

    result = validate_evidence(task_desc, args.complexity)

    import json
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
