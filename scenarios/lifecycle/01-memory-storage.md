---
name: memory-storage
title: Aggressive Memory Storage Enforcement
description: Verify task_completed.py emits explicit mem:store directives with type hints and escalation
type: testing
difficulty: beginner
estimated_minutes: 8
---

# Aggressive Memory Storage Enforcement

This scenario verifies that completing a crew task triggers an explicit, typed memory storage
directive — not a vague suggestion. It also verifies the escalation prefix appears after 3+
un-actioned completions and that the hook is silent when no crew project is active.

## Setup

```bash
export TMPDIR=$(mktemp -d)

cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "memory_compliance_required": true,
  "memory_compliance_escalations": 0,
  "cp_project_id": "test-proj"
}
EOF
```

## Steps

### 1. Build task fires directive with type=procedural

```bash
echo '{"subject": "build: implement auth service", "task_id": "t1", "status": "completed", "project_id": "test-proj"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/task_completed.py" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); msg=d.get('systemMessage',''); print('MEMSTORE' if '/wicked-garden:mem:store' in msg else 'MISSING'); print('PROCEDURAL' if 'type=procedural' in msg else 'NO_TYPE'); print('NO_ESCALATION' if '[ESCALATION]' not in msg else 'ESCALATION_FOUND')"
```

**Expected**:
```
MEMSTORE
PROCEDURAL
NO_ESCALATION
```

### 2. Fix task fires directive with type=decision

```bash
echo '{"subject": "fix: resolve race condition in queue processor", "task_id": "t2", "status": "completed", "project_id": "test-proj"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/task_completed.py" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); msg=d.get('systemMessage',''); print('DECISION' if 'type=decision' in msg else 'WRONG_TYPE')"
```

**Expected**: `DECISION`

### 3. Phase/design task fires directive with type=episodic

```bash
echo '{"subject": "Phase: design - authentication architecture", "task_id": "t3", "status": "completed", "project_id": "test-proj"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/task_completed.py" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); msg=d.get('systemMessage',''); print('EPISODIC' if 'type=episodic' in msg else 'WRONG_TYPE')"
```

**Expected**: `EPISODIC`

### 4. Escalation prefix appears after escalations >= 3

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"memory_compliance_required": true, "memory_compliance_escalations": 3, "cp_project_id": "test-proj"}
EOF

echo '{"subject": "build: fourth task without storing memory", "task_id": "t4", "status": "completed", "project_id": "test-proj"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/task_completed.py" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); msg=d.get('systemMessage',''); print('ESCALATION' if msg.startswith('[ESCALATION]') else 'NO_ESCALATION')"
```

**Expected**: `ESCALATION`

### 5. Expanded deliverable keywords trigger directive

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"memory_compliance_required": true, "memory_compliance_escalations": 0, "cp_project_id": "test-proj"}
EOF

for subject in "test: write unit tests for queue" "review: security audit of auth" "document: API reference v2" "configure: set up CI pipeline" "analyze: performance bottlenecks"; do
  result=$(echo "{\"subject\": \"${subject}\", \"task_id\": \"tx\", \"status\": \"completed\", \"project_id\": \"test-proj\"}" \
    | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/task_completed.py" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if '/wicked-garden:mem:store' in d.get('systemMessage','') else 'MISSING')")
  echo "${subject}: ${result}"
done
```

**Expected**: Each subject line ends with `OK`

### 6. Hook is silent when memory_compliance_required=False

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"memory_compliance_required": false}
EOF

output=$(echo '{"subject": "build: standalone work", "task_id": "t9", "status": "completed"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/task_completed.py")

echo "${output}" | python3 -c "import sys,json; d=json.load(sys.stdin); msg=d.get('systemMessage'); print('SILENT' if not msg else 'NOT_SILENT')"
```

**Expected**: `SILENT`

## Expected Outcome

Each directive is specific, actionable, and includes the exact command name with a type hint.
Escalation pressure increases automatically after repeated non-compliance. The hook never fires
outside an active crew project.

## Success Criteria

- [ ] Build task directive contains "/wicked-garden:mem:store" and "type=procedural"
- [ ] Fix task directive contains "type=decision"
- [ ] Phase/design task directive contains "type=episodic"
- [ ] After memory_compliance_escalations >= 3, directive starts with "[ESCALATION]"
- [ ] Extended keywords (test, review, document, configure, analyze) trigger directive
- [ ] Hook is silent when memory_compliance_required=False
- [ ] Hook outputs valid JSON on every invocation

## Value Demonstrated

Vague memory directives ("consider storing this") are ignored because Claude can rationalize
away borderline cases. Explicit, typed directives with an escalating urgency signal create
consistent memory capture without requiring user intervention.

## Cleanup

```bash
rm -rf "${TMPDIR}"
```
