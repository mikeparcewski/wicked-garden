# Test Evidence Requirements

QE artifact requirements per test type. Used by the evidence-validation skill
when validating test task completion (distinct from task description validation).

Test task validation checks the task's **artifact list** (not the description
text) against required artifact types.

---

## Test Task Artifact Validation

### Input

```json
{
  "task_artifacts": [
    {"type": "image", "name": "login-screenshot.png", "path": "..."},
    {"type": "api_request", "name": "auth-request.json"}
  ],
  "test_type": "ui|api|both"
}
```

### Output

```json
{
  "valid": true|false,
  "missing": ["label for missing artifact", ...],
  "present": ["label for satisfied requirement", ...]
}
```

---

## Requirements Table

### UI Test Tasks

| Requirement | Required | Accepted artifact types |
|-------------|----------|------------------------|
| screenshot | Yes | `image`, `screenshot` |
| visual_diff | No (optional) | `image`, `visual_diff` |

**Validation**: At least one artifact with type `image` or `screenshot` must
be present. `visual_diff` and other optional types do not affect validity.

---

### API Test Tasks

| Requirement | Required | Accepted artifact types |
|-------------|----------|------------------------|
| request_payload | Yes | `api_request`, `request` |
| response_payload | Yes | `api_response`, `response` |
| response_timing | No (optional) | any timing artifact |

**Validation**: At least one artifact with type `api_request` or `request`
AND at least one with type `api_response` or `response` must both be present.
Both are required — missing either one fails validation.

---

### Both / Integration

For tasks originally created with `change_type == "both"`, two separate tasks
are created at factory time (one `ui`, one `api`). Validate each task
independently using its own `test_type`.

If you encounter a task with `test_type == "both"` (should not happen with
current factory), require ALL artifact types: screenshot/image, api_request/request,
AND api_response/response.

---

## Error Cases

| Input | Result |
|-------|--------|
| Unknown `test_type` | `valid: false`, `missing: ["Unknown test_type '...' — expected 'ui', 'api', or 'both'"]` |
| Empty artifact list with required fields | `valid: false`, `missing: [all required labels]` |

---

## Artifact Type Matching Rules

1. Extract the `type` field from each artifact dict
2. Lowercase and strip whitespace
3. Check membership in the accepted types set for each requirement
4. Optional artifacts are not checked — their absence does not affect validity

---

## Relationship to Task Description Validation

Test task artifact validation is SEPARATE from task description evidence
validation (see [Evidence Schema](evidence-schema.md)):

| Validation type | Input | What is checked |
|-----------------|-------|-----------------|
| Task description | Description text | Natural language indicators of test_results, code_diff, etc. |
| Test task artifacts | Artifact list | Structured artifact types (image, api_request, etc.) |

Both validations may apply to the same test task. A task must pass both to
be considered complete.

---

## Cross-References

- Evidence taxonomy (factory side): [Test Evidence Taxonomy](../../test-task-factory/refs/test-evidence-taxonomy.md)
- Task description validation: [Evidence Schema](evidence-schema.md)
- Factory skill: [Test Task Factory](../../test-task-factory/SKILL.md)
