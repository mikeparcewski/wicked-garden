# Test Evidence Taxonomy

Canonical evidence requirements per test type. Used to populate task metadata
and validate test task completion. Source of truth for both the factory skill
and evidence-validation skill.

---

## Evidence Requirements by Test Type

### UI (visual tests)

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| screenshot | Yes | `evidence_required` | At least one rendered screenshot of the UI change |
| visual_diff | No | `evidence_optional` | Before/after diff image |

**Metadata values**:
```json
{
  "test_type": "ui",
  "test_category": "visual",
  "evidence_required": ["screenshot"],
  "evidence_optional": ["visual_diff"]
}
```

**Accepted artifact types for validation**:
- screenshot: `image`, `screenshot`
- visual_diff: `image`, `visual_diff`

---

### API (endpoint tests)

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| request_payload | Yes | `evidence_required` | HTTP request: method, URL, headers, body |
| response_payload | Yes | `evidence_required` | HTTP response: status code + body |
| response_timing | No | `evidence_optional` | Response time in milliseconds |

**Metadata values**:
```json
{
  "test_type": "api",
  "test_category": "endpoint",
  "evidence_required": ["request_payload", "response_payload"],
  "evidence_optional": ["response_timing"]
}
```

**Accepted artifact types for validation**:
- request_payload: `api_request`, `request`
- response_payload: `api_response`, `response`
- response_timing: any timing artifact

---

### Both (integration tests)

When `change_type == "both"`, two separate tasks are created — one using the
UI taxonomy and one using the API taxonomy. There is no merged "both" task type.

Each task carries only its own evidence requirements:
- Task 1 (visual): UI evidence fields only
- Task 2 (endpoint): API evidence fields only

---

## Default Metadata Fields

All test tasks share these fixed metadata values regardless of type:

| Field | Value |
|-------|-------|
| `initiative` | `{project}` (the project name passed to factory) |
| `priority` | `"P1"` |
| `assigned_to` | `"acceptance-test-executor"` |
| `impl_subject` | `{original impl_subject}` (unmodified, before prefix stripping) |

---

## Validation Logic

To validate test evidence for a completed task:

1. Identify `test_type` from task metadata
2. For each `evidence_required` field, check that at least one artifact in the
   task's artifact list has an accepted type
3. `evidence_optional` fields do not affect validity
4. Report: `{valid: bool, missing: list[str], present: list[str]}`

**For "both" (integration) test tasks**: The task was already split into two
separate tasks at creation time — validate each independently using its own
`test_type`.

---

## Cross-References

- Template text: [Test Task Templates](test-task-templates.md)
- Factory algorithm: [Test Task Factory SKILL.md](../SKILL.md)
- Task evidence field validation: [Evidence Schema](../../evidence-validation/refs/evidence-schema.md)
