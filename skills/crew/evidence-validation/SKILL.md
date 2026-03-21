---
name: evidence-validation
description: |
  Validates that completed task descriptions include required evidence fields
  at the appropriate level for the task's complexity score. Three tiers (low,
  medium, high) map to complexity ranges 1-2, 3-4, 5-7.

  Use when: "validate evidence", "check task completion", "evidence required",
  "missing evidence", "evidence schema", "task description review",
  or validating a TaskUpdate description before marking complete.
---

# Evidence Validation Skill

Check that a task description has required evidence before marking complete.

## Output Format

```json
{
  "valid": true|false,
  "missing": ["Human-readable label for missing field", ...],
  "warnings": ["Advisory warning (non-blocking)", ...]
}
```

## Tier Mapping

| Complexity | Tier | Required Fields |
|------------|------|-----------------|
| 0-2 | low | test_results + code_diff |
| 3-4 | medium | test_results + code_diff + verification |
| 5-7 | high | test_results + code_diff + verification + performance + assumptions |

Tiers are cumulative: high = medium + performance + assumptions.

## Validation Process

1. Map complexity score to tier (0 → low, 1-2 → low, 3-4 → medium, 5-7 → high)
2. For each required field in the tier, check the task description text for
   natural language presence (see [Evidence Schema](refs/evidence-schema.md))
3. If field is NOT detected → add its label to `missing`
4. Collect `warnings` for advisory items
5. Set `valid = true` only when `missing` is empty

## Advisory: Assumptions Warning

For any complexity >= 3, if no assumptions are detected, add this warning
(non-blocking, does not affect `valid`):

> "Consider documenting assumptions (## Assumptions section) for medium/high
> complexity tasks to help reviewers."

This warning is suppressed if `assumptions` is already in `missing` (i.e.,
high-tier tasks where it is required).

## Detection Approach

Each field is detected by scanning the task description for natural language
indicators. Detection is text analysis — look for the patterns described in
[Evidence Schema](refs/evidence-schema.md). A single indicator match is
sufficient to mark a field as present.

Detection is case-insensitive.

## Quick Reference — Field Labels (for missing list)

| Field | Label used in `missing` |
|-------|------------------------|
| test_results | `"Test results (e.g. '- Test: test_name — PASS/FAIL')"` |
| code_diff | `"Code diff reference (e.g. '- Code diff: ...' or '- File: path — modified/created')"` |
| verification | `"Verification step (e.g. '- Verification: curl ... returns 200' or command output)"` |
| performance | `"Performance data (e.g. latency, throughput, benchmark results)"` |
| assumptions | `"Documented assumptions (e.g. '## Assumptions' section or '- Assumption:')"` |

## Standard Task Description Format

Well-structured task descriptions follow this format:

```markdown
{original task description}

## Outcome
{what was accomplished}

## Evidence
- Test: {test name} — PASS/FAIL
- File: {path} — modified/created/deleted
- Verification: {command + output}
- Performance: {metric} (complexity >= 5 only)
- Benchmark: {tool + result} (complexity >= 5 only)

## Assumptions
- {assumption 1}
```

See [Evidence Schema](refs/evidence-schema.md) for full detection patterns
and [Test Evidence Requirements](refs/test-evidence-requirements.md) for
QE artifact requirements per test type.

## AC-Evidence Mapping

When a task description includes an `## Acceptance Criteria` section (AC-4.5), validation must confirm that each listed AC has a **corresponding evidence entry** — not just that evidence fields are present anywhere in the description.

### Mapping Process

1. **Extract ACs**: Parse the `## Acceptance Criteria` section. Each `- [ ] AC-N:` or `- AC-N:` line is a criterion that requires evidence.
2. **Extract evidence entries**: Parse the `## Evidence` section. Each `- AC-N:` line is a candidate match.
3. **Match by label**: For each AC, check whether an evidence entry with the same label exists (e.g., `AC-1` in criteria → `AC-1:` in evidence). Label matching is case-insensitive.
4. **Validate entry quality**: A matching entry is only valid if it references a concrete artifact — a file path, test name, command output excerpt, diff, or screenshot. Bare assertions ("it works", "verified", "done") are not sufficient.

### Validation Result

If any AC is missing a matching evidence entry, add to `missing`:

> `"AC-N evidence: {criterion text} — no matching evidence entry found"`

If an evidence entry exists but contains only an assertion without artifact reference, add to `warnings`:

> `"AC-N evidence is vague: '{entry text}' — provide file path, test output, or diff"`

AC-evidence mapping is performed **in addition to** the tier-based field checks. A task can pass tier validation (evidence fields present) but still fail AC-evidence mapping if individual criteria lack coverage.
