---
name: orchestrator-no-inline-work
title: Phase Executor Delegation Enforcement
description: Verify phase-executor.md delegates specialist work via Task() and pre_tool.py fails open on file writes
type: workflow
difficulty: intermediate
estimated_minutes: 8
fixes: "#522"
---

# Phase Executor Delegation Enforcement

This scenario validates that the phase executor agent (`agents/crew/phase-executor.md`):
1. Delegates specialist work (risk assessment, code review) to subagents via Task()
2. Uses wicked-* ecosystem tools before falling back to manual analysis
3. Does not inline qualitative analysis that should be done by a specialist
4. Pre-tool hook fails open on direct file writes (never denies)

Note: The v5 orchestrator agent was removed in v6. Orchestration is now performed by
phase-executor.md dispatched by phase_manager.execute().

## Setup

No special setup needed.

```bash
Run: test -f "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "phase-executor.md found"
Assert: phase-executor.md found
```

## Steps

### 1. phase-executor.md exists at the expected path

```bash
Run: test -f "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: file found"
Assert: PASS: file found
```

### 2. phase-executor.md contains Task() dispatch

```bash
Run: grep -q "Task(" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: Task() dispatch found"
Assert: PASS: Task() dispatch found
```

### 3. phase-executor.md references wicked-garden ecosystem tools

```bash
Run: grep -q "wicked-garden" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: wicked-garden ecosystem reference found"
Assert: PASS: wicked-garden ecosystem reference found
```

### 4. phase-executor.md instructs recording executor-status.json

```bash
Run: grep -q "executor-status.json" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: executor-status.json instruction found"
Assert: PASS: executor-status.json instruction found
```

### 5. phase-executor.md defines parallelization_check output

```bash
Run: grep -q "parallelization_check" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: parallelization_check defined"
Assert: PASS: parallelization_check defined
```

### 6. phase-executor.md references delegating sub-tasks in parallel (SC-6)

```bash
Run: grep -qi "parallel" "${CLAUDE_PLUGIN_ROOT}/agents/crew/phase-executor.md" && echo "PASS: parallel dispatch referenced"
Assert: PASS: parallel dispatch referenced
```

### 7. Pre-tool hook fails open (allows) on file writes

```bash
Run: echo '{"tool_name": "Write", "tool_input": {"file_path": "/tmp/test_output.py", "content": "print(hello)"}}' | \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pre_tool.py" | \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
data = json.load(sys.stdin)
# Hook should allow (fail open) — never deny writes
decision = data.get('hookSpecificOutput', {}).get('permissionDecision', '')
print('decision:', decision)
assert decision == 'allow', f'Expected allow (fail open), got: {decision}'
print('PASS: pre_tool allows writes (fail open)')
"
Assert: PASS: pre_tool allows writes (fail open)
```

### 8. Pre-tool hook allows writes to .something-wicked/ paths

```bash
Run: echo '{"tool_name": "Write", "tool_input": {"file_path": "/home/user/.something-wicked/wicked-garden/projects/test-slug/wicked-crew/projects/test/status.md", "content": "status: ok"}}' | \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pre_tool.py" | \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
data = json.load(sys.stdin)
decision = data.get('hookSpecificOutput', {}).get('permissionDecision', '')
print('decision:', decision)
assert decision == 'allow', f'Expected allow for allowlisted path, got: {decision}'
print('PASS: allowlisted path allowed')
"
Assert: PASS: allowlisted path allowed
```

## Expected Outcome

### phase-executor.md structure
- File exists at `agents/crew/phase-executor.md`
- Uses `Task()` dispatch to delegate specialist work
- References wicked-garden ecosystem tools before manual analysis
- Defines `parallelization_check` output block (SC-6 compliance)
- Instructions require recording `executor-status.json`

### pre_tool.py behavior
- Always fails open (permissionDecision: "allow") — never denies on any write
- .something-wicked/ paths are always allowed

## Success Criteria

### phase-executor.md
- [ ] File exists at `agents/crew/phase-executor.md`
- [ ] `Task()` dispatch present
- [ ] wicked-garden ecosystem tools referenced
- [ ] executor-status.json instruction present
- [ ] parallelization_check output defined (SC-6)

### pre_tool.py
- [ ] Non-allowlisted writes return permissionDecision: "allow" (fail open)
- [ ] .something-wicked/ paths are always allowed

## Value Demonstrated

The phase executor enforces quality gates by delegating specialist verification to domain
subagents via Task() rather than performing all analysis inline. This keeps the gate
result objective, reproducible, and free from context contamination across runs.
Pre-tool failing open ensures gate enforcement never blocks legitimate writes by the
agents it oversees.
