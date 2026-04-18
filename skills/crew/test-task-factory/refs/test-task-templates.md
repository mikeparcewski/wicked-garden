# Test Task Templates

Full description templates per test type. These are filled by substituting
`{impl_description}` and `{safe_name}` from the factory algorithm.

---

## UI Template (test_category: visual)

```
Visual test task for implementation: '{impl_description}'.

Required evidence before completion:
- screenshot: At least one screenshot of the rendered UI change
  (file path in phases/test/evidence/ or inline base64)
- visual_diff: Optional but recommended — diff image showing before/after

Collect evidence using:
- Browser screenshot via Read tool or browser automation
- Store screenshot at: phases/test/evidence/{safe_name}-screenshot.png

Run validate_test_evidence([artifacts], 'ui') before marking this task complete.
Task cannot be marked complete without at least one screenshot artifact.
```

**Substitution values**:
- `{impl_description}` — cleaned implementation description (phase prefix stripped)
- `{safe_name}` — lowercase alphanumeric slug of impl_description, max 50 chars

**Evidence fields for this template**:

| Field | Required | Accepted artifact types |
|-------|----------|------------------------|
| screenshot | Yes | `image`, `screenshot` |
| visual_diff | No (optional) | `image`, `visual_diff` |

---

## API Template (test_category: endpoint)

```
Endpoint test task for implementation: '{impl_description}'.

Required evidence before completion:
- request_payload: HTTP request body + headers (method, URL, headers, body)
- response_payload: HTTP response body + status code
- response_timing: Optional — response time in milliseconds

Collect evidence using:
- curl or httpie to call the endpoint
- Append to the native task description via TaskUpdate, referencing any on-disk artifact paths
- Request artifact type: api_request
- Response artifact type: api_response

Run validate_test_evidence([artifacts], 'api') before marking this task complete.
Task cannot be marked complete without both request_payload and response_payload.
```

**Substitution values**:
- `{impl_description}` — cleaned implementation description (phase prefix stripped)

**Evidence fields for this template**:

| Field | Required | Accepted artifact types |
|-------|----------|------------------------|
| request_payload | Yes | `api_request`, `request` |
| response_payload | Yes | `api_response`, `response` |
| response_timing | No (optional) | any timing artifact |

---

## Template Filling Rules

1. Replace `{impl_description}` literally — preserve original casing
2. Replace `{safe_name}` with the computed slug (lowercase, dashes, max 50 chars)
3. Do not add extra whitespace or modify surrounding text
4. The resulting text is the task `description` field verbatim

## Subject Construction Pattern

```
Test: {project} - {impl_description} ({test_category})
```

Examples:
- `"Test: checkout - Integrate payment flow (visual)"`
- `"Test: checkout - Integrate payment flow (endpoint)"`
- `"Test: auth-service - Add auth endpoint (endpoint)"`

The project name is never stripped or modified. The impl_description is the
cleaned description (phase prefix already removed).
