---
name: orchestrator-no-inline-work
title: Execution Orchestrator Delegation Enforcement
description: Verify execution-orchestrator.md delegates specialist work via Task() and pre_tool.py fails open on file writes
type: workflow
difficulty: intermediate
estimated_minutes: 8
---

# Execution Orchestrator Delegation Enforcement

This scenario validates that the execution orchestrator agent:
1. Delegates specialist work (risk assessment, code review) to subagents via Task()
2. Uses wicked-* ecosystem tools before falling back to manual analysis
3. Does not inline qualitative analysis that should be done by a specialist
4. Pre-tool hook fails open on direct file writes (never denies)

## Setup

No special setup needed.

```bash
test -f "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && echo "execution-orchestrator.md found"
```

## Steps

### 1. execution-orchestrator.md exists at the expected path

```bash
test -f "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && echo "PASS: file found"
```

Expected: `PASS: file found`

### 2. execution-orchestrator.md contains Task() dispatch for risk assessment

```bash
grep -q "Task(" "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && echo "PASS: Task() dispatch found"
```

Expected: `PASS: Task() dispatch found`

### 3. execution-orchestrator.md references wicked-garden ecosystem tools first

```bash
grep -q "wicked-garden" "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && echo "PASS: wicked-garden ecosystem reference found"
```

Expected: `PASS: wicked-garden ecosystem reference found`

### 4. execution-orchestrator.md instructs running actual test suites (not grep-only)

```bash
grep -q "exit code" "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && echo "PASS: exit code instruction found"
```

Expected: `PASS: exit code instruction found`

### 5. execution-orchestrator.md defines APPROVE/CONDITIONAL/REJECT gate decisions

```bash
grep -q "APPROVE" "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && \
grep -q "CONDITIONAL" "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && \
grep -q "REJECT" "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && \
echo "PASS: All three gate decisions defined"
```

Expected: `PASS: All three gate decisions defined`

### 6. execution-orchestrator.md delegates risk validation to a subagent

```bash
grep -q "wicked-garden:qe:risk-assessor" "${CLAUDE_PLUGIN_ROOT}/agents/crew/execution-orchestrator.md" && echo "PASS: risk-assessor subagent delegation found"
```

Expected: `PASS: risk-assessor subagent delegation found`

### 7. Pre-tool hook fails open (allows) on file writes

```bash
# Simulate a Write hook call to a non-allowlisted path during build phase
echo '{"tool_name": "Write", "tool_input": {"file_path": "/tmp/test_output.py", "content": "print(hello)"}}' | \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pre_tool.py" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
# Hook should allow (fail open) — never deny writes
decision = data.get('hookSpecificOutput', {}).get('permissionDecision', '')
print('decision:', decision)
assert decision == 'allow', f'Expected allow (fail open), got: {decision}'
print('PASS: pre_tool allows writes (fail open)')
"
```

Expected: `PASS: pre_tool allows writes (fail open)`

### 8. Pre-tool hook allows writes to .something-wicked/ paths

```bash
echo '{"tool_name": "Write", "tool_input": {"file_path": "/home/user/.something-wicked/wicked-garden/local/wicked-crew/projects/test/status.md", "content": "status: ok"}}' | \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pre_tool.py" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
decision = data.get('hookSpecificOutput', {}).get('permissionDecision', '')
print('decision:', decision)
assert decision == 'allow', f'Expected allow for allowlisted path, got: {decision}'
print('PASS: allowlisted path allowed')
"
```

Expected: `PASS: allowlisted path allowed`

## Expected Outcome

### execution-orchestrator.md structure
- File exists at `agents/crew/execution-orchestrator.md`
- Uses `Task()` dispatch to delegate specialist work (risk-assessor subagent)
- References wicked-garden ecosystem tools before manual analysis
- Instructions require running actual test suites and capturing exit codes
- Gate decisions are APPROVE, CONDITIONAL, and REJECT — explicitly defined

### pre_tool.py behavior
- Always fails open (permissionDecision: "allow") — never denies on any write
- .something-wicked/ paths are always allowed

## Success Criteria

### execution-orchestrator.md
- [ ] File exists at expected path
- [ ] `Task()` dispatch present (delegates risk validation to wicked-garden:qe:risk-assessor)
- [ ] wicked-garden ecosystem tools referenced (use ecosystem before manual analysis)
- [ ] Exit code instruction present (test suites must be run, not just file-grepped)
- [ ] APPROVE, CONDITIONAL, and REJECT gate decisions all defined

### pre_tool.py
- [ ] Non-allowlisted writes return permissionDecision: "allow" (fail open)
- [ ] .something-wicked/ paths are always allowed

## Value Demonstrated

The execution orchestrator enforces quality gates by delegating specialist verification
(risk assessment, code review) to domain subagents via Task() rather than performing all
analysis inline. This keeps the gate result objective, reproducible, and free from
context contamination across runs. Pre-tool failing open ensures gate enforcement never
blocks legitimate writes by the agents it oversees.
