---
name: obs-trace-capture
description: Verify that hook execution traces are captured and queryable via the traces command
category: infra
tags: [observability, traces, hooks]
tools:
  required: [slash-command]
difficulty: basic
timeout: 30
---

# Observability Trace Capture

Validates that the PostToolUse hook captures trace records during tool invocations and that
`/wicked-garden:observability:traces` can query them. Confirms that Layer 1 (runtime tracing)
is active and recording.

## Setup

No setup required. The PostToolUse hook automatically captures trace records for every tool
invocation. The `/wicked-garden:observability:traces` command queries the accumulated trace data.

## Steps

### Step 1: Query existing traces to establish a baseline

Invoke the traces command to see what has been recorded so far in this session:

```
/wicked-garden:observability:traces --tail 5
```

**Expect**: The command completes and either shows recent trace records or indicates no traces
exist yet for this session. Note the number of records visible.

### Step 2: Trigger tool activity and query traces again

Run any simple tool invocation (e.g., read a file or list a directory) to generate at least one
new PostToolUse event. Then query traces again:

```
/wicked-garden:observability:traces --tail 5
```

**Expect**:
- At least one new trace record appears compared to Step 1
- Each trace record includes a tool name, timestamp, and session identifier

### Step 3: Verify trace record structure with JSON output

Query traces in machine-readable mode:

```
/wicked-garden:observability:traces --tail 1 --json
```

**Expect**:
- The output is valid structured data (JSON)
- The most recent record contains at minimum: `ts` (timestamp), `tool` (tool name), and `session_id`
- The `tool` field reflects a real tool that was invoked during this session

## Expected Outcomes

1. The PostToolUse hook passively captures trace records without user intervention
2. The traces command retrieves recorded traces for the current session
3. Trace records contain the required fields (`ts`, `tool`, `session_id`) for debugging and audit
4. Traces are append-only and persist across tool invocations within a session

## Cleanup

Traces are append-only logs. No cleanup needed.
