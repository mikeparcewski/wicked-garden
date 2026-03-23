---
name: obs-contract-assert
description: Verify that the assert command discovers and validates plugin schemas, reporting pass/fail counts
category: infra
tags: [observability, contracts, schemas]
tools:
  required: [slash-command]
difficulty: intermediate
timeout: 60
---

# Observability Contract Assertions

Validates that `/wicked-garden:observability:assert` discovers registered schemas, validates them
against their targets, and reports a clean pass with 0 failures. Also confirms that assertion
results are logged for audit purposes. Covers Layer 3 (contract assertions) of the observability
stack.

## Setup

No setup required. The `/wicked-garden:observability:assert` command handles schema discovery
and validation internally. Schemas must exist in `schemas/{plugin}/{script}.json` before assertions
can run.

## Steps

### Step 1: Run contract assertions against the observability domain

Invoke the assert command targeting the observability domain:

```
/wicked-garden:observability:assert --plugin wicked-garden
```

**Expect**: The command completes without error and prints a summary of schemas validated.

### Step 2: Verify all schemas pass with zero failures

Examine the output from Step 1.

**Expect**:
- The summary shows at least 3 schemas passed
- The summary shows 0 schemas failed
- No violation details appear in the output (violations only print on failure)

### Step 3: Run assertions in machine-readable mode and verify log persistence

Invoke the assert command again with JSON output:

```
/wicked-garden:observability:assert --plugin wicked-garden --json
```

**Expect**:
- The output is valid structured data (JSON) with per-script pass/fail results
- Each result record includes a `schema` identifier and a `result` field
- The command references or writes to a persistent assertion log for audit purposes

## Expected Outcomes

1. The assert command discovers all registered schemas for the target plugin and validates each one
2. All schemas pass validation with 0 failures, confirming that plugin scripts return data matching their declared contracts
3. Machine-readable output provides per-script results suitable for CI integration
4. Assertion results are persisted as audit records so that regressions can be detected over time

## Cleanup

Assertion logs are persistent audit records. No cleanup needed.
