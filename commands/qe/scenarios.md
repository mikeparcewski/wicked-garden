---
description: "[DEPRECATED v7.0] Use /wicked-testing:authoring instead"
argument-hint: "<forwarded to /wicked-testing:authoring>"
---

# /wicked-garden:qe:scenarios

## Instructions

### 0. Availability check

If `session_state.wicked_testing_missing == true`:
  Return: `wicked-testing required — run: npx wicked-testing install`
  Stop. Do not emit a deprecation notice.

### 1. Deprecation notice

Print exactly:
`[DEPRECATED] /wicked-garden:qe:scenarios is removed in v7.1 — use /wicked-testing:authoring instead.`

### 2. Delegate

Invoke skill `wicked-testing:authoring` with all args forwarded verbatim.

## See also

- `/wicked-garden:qe:acceptance` — run acceptance tests against scenarios (also deprecated; use `/wicked-testing:execution`)
