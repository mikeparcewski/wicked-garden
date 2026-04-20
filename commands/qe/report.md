---
description: "[DEPRECATED v7.0] Use /wicked-testing:insight instead"
argument-hint: "<forwarded to /wicked-testing:insight>"
---

# /wicked-garden:qe:report

## Instructions

### 0. Availability check

If `session_state.wicked_testing_missing == true`:
  Return: `wicked-testing required — run: npx wicked-testing install`
  Stop. Do not emit a deprecation notice.

### 1. Deprecation notice

Print exactly:
`[DEPRECATED] /wicked-garden:qe:report is removed in v7.1 — use /wicked-testing:insight instead.`

### 2. Delegate

Invoke skill `wicked-testing:insight` with all args forwarded verbatim.
