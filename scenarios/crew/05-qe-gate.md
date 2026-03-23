---
name: qe-gate
title: QE Gate Enforcement at Phase Approval
description: Verify phase approval is blocked when gate not run or returns REJECT, and bypass requires audit trail
type: testing
difficulty: intermediate
estimated_minutes: 12
---

# QE Gate Enforcement at Phase Approval

This scenario verifies that `phase_manager.py approve` enforces gate requirements by blocking
when the gate was not run, blocking on REJECT results, and allowing bypass only with
`--override-gate` while writing an audit record. It uses the gate-result.json mock mechanism
to test REJECT and PASS outcomes without running the full QE orchestrator.

## Setup

```bash
export TEST_PROJECT="gate-enforcement-test"
export PROJECT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-crew/projects/${TEST_PROJECT}"

mkdir -p "${PROJECT_DIR}/phases/design"
mkdir -p "${PROJECT_DIR}/phases/clarify"

cat > "${PROJECT_DIR}/project.json" <<'EOF'
{
  "name": "gate-enforcement-test",
  "current_phase": "design",
  "phase_plan": ["clarify", "design", "build"],
  "phases": {
    "clarify": "approved",
    "design": "in_progress",
    "build": "pending"
  },
  "complexity": 4,
  "signals": ["quality", "integration"]
}
EOF

# Helper function for mocking gate results
mock_gate() {
  local phase="$1"
  local result="$2"   # PASS | REJECT | NONE
  local findings="${3:-}"
  local gate_file="${PROJECT_DIR}/phases/${phase}/gate-result.json"

  if [ "${result}" = "NONE" ]; then
    rm -f "${gate_file}"
  elif [ "${result}" = "REJECT" ]; then
    echo "{\"result\": \"REJECT\", \"findings\": [\"${findings}\"], \"type\": \"mock\"}" > "${gate_file}"
  else
    echo '{"result": "PASS", "findings": [], "type": "mock"}' > "${gate_file}"
  fi
}

reset_phase() {
  python3 -c "
import json, pathlib
p = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(p.read_text())
d['current_phase'] = 'design'
d['phases']['design'] = 'in_progress'
p.write_text(json.dumps(d, indent=2))
"
}
```

## Steps

### 1. Approval blocked when gate not run

```bash
mock_gate design NONE
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" approve "${TEST_PROJECT}" design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 1
- stderr contains "Gate not run for phase 'design'" or equivalent
- stderr contains "--override-gate"
- project.json current_phase still "design" (not advanced)

```bash
python3 -c "
import json, pathlib
d = json.loads(pathlib.Path('${PROJECT_DIR}/project.json').read_text())
print('PHASE_HELD' if d['current_phase'] == 'design' else 'PHASE_ADVANCED_UNEXPECTEDLY')
"
```

**Expected**: `PHASE_HELD`

### 2. Approval blocked on REJECT gate result

```bash
reset_phase
mock_gate design REJECT "test coverage below threshold"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" approve "${TEST_PROJECT}" design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 1
- stderr contains "REJECT" or "Resolve findings"
- project.json current_phase still "design"

```bash
python3 -c "
import json, pathlib
d = json.loads(pathlib.Path('${PROJECT_DIR}/project.json').read_text())
print('PHASE_HELD' if d['current_phase'] == 'design' else 'PHASE_ADVANCED_UNEXPECTEDLY')
"
```

**Expected**: `PHASE_HELD`

### 3. PASS gate result allows approval to proceed

```bash
reset_phase
mock_gate design PASS

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" approve "${TEST_PROJECT}" design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 0
- project current_phase advances to "build"

```bash
python3 -c "
import json, pathlib
d = json.loads(pathlib.Path('${PROJECT_DIR}/project.json').read_text())
print('ADVANCED' if d['current_phase'] == 'build' else 'NOT_ADVANCED')
"
```

**Expected**: `ADVANCED`

### 4. --override-gate bypasses REJECT with audit trail written

```bash
reset_phase
mock_gate design REJECT "known issue tracked in JIRA-456"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" approve "${TEST_PROJECT}" design \
  --override-gate --reason "known issue tracked in JIRA-456, not blocking release" \
  2>&1
echo "Exit: $?"
```

**Expected**: exit code 0

```bash
echo "--- Checking audit trail ---"
grep -A5 "Gate Override" "${PROJECT_DIR}/phases/design/status.md" 2>/dev/null || echo "NO_OVERRIDE_RECORD"
```

**Expected**: `## Gate Override` section present, containing the reason text

### 5. --override-gate bypasses gate-not-run with audit trail

```bash
reset_phase
mock_gate design NONE

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" approve "${TEST_PROJECT}" design \
  --override-gate --reason "fast-pass waived for hotfix" \
  2>&1
echo "Exit: $?"

grep "Gate Override" "${PROJECT_DIR}/phases/design/status.md" 2>/dev/null && echo "AUDIT_PRESENT" || echo "NO_AUDIT"
```

**Expected**: exit code 0, `AUDIT_PRESENT`

### 6. Phase with gate_required=false approves without gate check

```bash
# Advance project back to ideate phase (gate_required=false)
python3 -c "
import json, pathlib
p = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(p.read_text())
d['current_phase'] = 'ideate'
d['phases']['ideate'] = 'in_progress'
p.write_text(json.dumps(d, indent=2))
"

mkdir -p "${PROJECT_DIR}/phases/ideate"

# No gate-result.json present for ideate
rm -f "${PROJECT_DIR}/phases/ideate/gate-result.json"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" approve "${TEST_PROJECT}" ideate 2>&1
echo "Exit: $?"
```

**Expected**: exit code 0, no gate error

### 7. Malformed gate-result.json treated as gate-not-run

```bash
reset_phase
echo 'not valid json{' > "${PROJECT_DIR}/phases/design/gate-result.json"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" approve "${TEST_PROJECT}" design 2>&1
echo "Exit: $?"
```

**Expected**: exit code 1 (malformed = gate not run = blocking)

## Expected Outcome

Gate enforcement is deterministic and non-bypassable without an explicit override flag. Every
bypass is recorded in the phase's status.md with a timestamp, approver, and reason. The mock
mechanism (writing gate-result.json) makes these tests fast and infrastructure-free.

## Success Criteria

- [ ] Approval blocked (exit 1) when no gate-result.json present for gate_required phase
- [ ] Approval blocked (exit 1) when gate-result.json contains REJECT
- [ ] Approval succeeds (exit 0) when gate-result.json contains PASS and phase advances
- [ ] --override-gate with --reason bypasses REJECT and phase advances
- [ ] Gate override written to status.md with reason and timestamp
- [ ] --override-gate bypasses gate-not-run state with audit trail
- [ ] gate_required=false phases (e.g. ideate) approve without any gate check
- [ ] Malformed gate-result.json treated as gate-not-run (blocking)

## Value Demonstrated

Before this change, gate enforcement was advisory prose. Claude followed it inconsistently.
Converting it to a ValueError + sys.exit(1) makes enforcement deterministic and independent
of LLM compliance. The --override-gate escape hatch preserves human override authority while
creating an audit trail that makes bypasses visible.

## Cleanup

```bash
rm -rf "${PROJECT_DIR}"
```
