---
name: orchestrator-no-inline-work
title: Orchestrator No Inline Work
description: Verify orchestrator.md enforces delegation-only and pre_tool.py warns on direct file writes during build/review phases
type: workflow
difficulty: intermediate
estimated_minutes: 8
---

# Orchestrator No Inline Work

This scenario validates that the orchestrator agent:
1. Does NOT perform inline analysis, implementation, or review work
2. Always delegates to subagents via Task() for non-trivial work
3. Has a clear "Allowed Inline Operations" list
4. Pre-tool hook warns when orchestrator attempts direct file writes outside the allowlist during build/review phases

## Setup

No special setup needed.

```bash
grep -q "Allowed Inline Operations" "${CLAUDE_PLUGIN_ROOT}/agents/crew/orchestrator.md" && echo "Orchestrator-only pattern enforced"
```

## Steps

### 1. Orchestrator.md no longer contains inline fallback work section

```bash
grep -c "inline fallback work" "${CLAUDE_PLUGIN_ROOT}/agents/crew/orchestrator.md"
```

Expected: `0` (the inline fallback work section has been removed)

### 2. Orchestrator.md contains delegation-only instruction

```bash
grep -q "NEVER perform" "${CLAUDE_PLUGIN_ROOT}/agents/crew/orchestrator.md" && echo "PASS: NEVER perform found"
```

Expected: `PASS: NEVER perform found`

### 3. Orchestrator.md has Allowed Inline Operations section

```bash
grep -q "Allowed Inline Operations" "${CLAUDE_PLUGIN_ROOT}/agents/crew/orchestrator.md" && echo "PASS: Allowed Inline Operations section found"
```

Expected: `PASS: Allowed Inline Operations section found`

### 4. Allowed operations include task lifecycle tools

```bash
grep -A 10 "Allowed Inline Operations" "${CLAUDE_PLUGIN_ROOT}/agents/crew/orchestrator.md" | grep -q "TaskCreate\|TaskUpdate\|TaskList" && echo "PASS: Task lifecycle tools listed"
```

Expected: `PASS: Task lifecycle tools listed`

### 5. Allowed operations include phase_manager.py and status.md

```bash
grep -A 15 "Allowed Inline Operations" "${CLAUDE_PLUGIN_ROOT}/agents/crew/orchestrator.md" | grep -q "phase_manager\|status.md" && echo "PASS: Phase state access listed"
```

Expected: `PASS: Phase state access listed`

### 6. Pre-tool hook warns on file writes during build phase

```bash
# Simulate a Write hook call to a non-allowlisted path during build phase
echo '{"tool_name": "Write", "tool_input": {"file_path": "/tmp/test_output.py", "content": "print(hello)"}}' | \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pre_tool.py" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
# Hook should allow (fail open) but may include a systemMessage warning
decision = data.get('hookSpecificOutput', {}).get('permissionDecision', '')
print('decision:', decision)
assert decision == 'allow', f'Expected allow (fail open), got: {decision}'
print('PASS: pre_tool allows writes (fail open)')
"
```

Expected: `PASS: pre_tool allows writes (fail open)`

### 7. Pre-tool hook allows writes to .something-wicked/ paths

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

### 8. Fallback delegation instruction uses Task() not inline prose

```bash
grep -A 5 "NEVER perform" "${CLAUDE_PLUGIN_ROOT}/agents/crew/orchestrator.md" | grep -q "Task()" && echo "PASS: Task() dispatch referenced in fallback instruction"
```

Expected: `PASS: Task() dispatch referenced in fallback instruction`

## Expected Outcome

### orchestrator.md changes
- "inline fallback work" section removed (lines 79-83 content replaced)
- New instruction: dispatch to fallback agents (facilitator, researcher, implementer, reviewer) via Task() when no specialist available
- "NEVER perform analysis, implementation, or review work directly" stated explicitly
- "Allowed Inline Operations" section added listing: read project state, call phase_manager.py, call specialist_discovery.py, use TaskCreate/TaskUpdate/TaskList, write status.md

### pre_tool.py changes
- Write/Edit handler checks for active crew project in build or review phase
- If orchestrator context detected AND file path is NOT allowlisted, emits systemMessage warning
- Allowlist: paths containing `.something-wicked/` OR paths ending in `status.md`
- Always fail open (permissionDecision: "allow") — never deny

## Success Criteria

### orchestrator.md
- [ ] No mention of "inline fallback work" (section removed)
- [ ] "NEVER perform analysis, implementation, or review work directly" present
- [ ] "Allowed Inline Operations" section present with task lifecycle tools
- [ ] Fallback instruction references Task() dispatch to facilitator/researcher/implementer/reviewer

### pre_tool.py
- [ ] Write/Edit handler calls orchestrator context detection
- [ ] Non-allowlisted writes in build/review phase emit systemMessage warning
- [ ] .something-wicked/ paths are always allowed
- [ ] Always fails open (never denies on orchestrator check)

## Value Demonstrated

The orchestrator accumulating inline work defeats the purpose of fresh-dispatch architecture: context bloats, retries are dirty, and the orchestrator becomes entangled with implementation state. Enforcing delegation-only keeps the orchestrator lean and stateless, enabling clean phase retries and true parallel build dispatch.
