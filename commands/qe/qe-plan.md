---
description: "[DEPRECATED v7.0] Use /wicked-testing:plan instead"
argument-hint: "<forwarded to /wicked-testing:plan>"
---

# /wicked-garden:qe:qe-plan

## Instructions

### 0. Availability check

If `session_state.wicked_testing_missing == true`:
  Return: `wicked-testing required — run: npx wicked-testing install`
  Stop. Do not emit a deprecation notice.

### 1. Deprecation notice

Print exactly:
`[DEPRECATED] /wicked-garden:qe:qe-plan is removed in v7.1 — use /wicked-testing:plan instead.`

### 2. Delegate

Invoke skill `wicked-testing:plan` with all args forwarded verbatim.
