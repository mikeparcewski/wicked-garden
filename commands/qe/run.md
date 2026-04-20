---
description: "[DEPRECATED v7.0] Use /wicked-testing:execution instead"
argument-hint: "<forwarded to /wicked-testing:execution>"
---

# /wicked-garden:qe:run

## Instructions

### 0. Availability check

If `session_state.wicked_testing_missing == true`:
  Return: `wicked-testing required — run: npx wicked-testing install`
  Stop. Do not emit a deprecation notice.

### 1. Deprecation notice

Print exactly:
`[DEPRECATED] /wicked-garden:qe:run is removed in v7.1 — use /wicked-testing:execution instead.`

### 2. Delegate

Invoke skill `wicked-testing:execution` with all args forwarded verbatim.
