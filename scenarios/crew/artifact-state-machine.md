---
name: artifact-state-machine
title: Artifact Lifecycle State Machine
description: Verify artifact_state.py CLI manages lifecycle transitions, rejects invalid moves, and supports bulk checks
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Artifact Lifecycle State Machine

This scenario verifies that `artifact_state.py` correctly manages artifact lifecycle states:
registering artifacts in DRAFT, walking through valid transitions, rejecting invalid
transitions, handling gate rejects, bulk-checking phase readiness, filtering by state,
and enforcing CLOSED as a terminal state.

## Setup

```bash
# Verify artifact_state.py is available
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --help > /dev/null 2>&1 \
  && echo "artifact_state.py available" || echo "NOT FOUND"
```

## Steps

### 1. Register artifact

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json register \
  --name arch.md --type design --project test-asm --phase design \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('STATE:', d.get('state', 'N/A'))
print('HAS_ID:', bool(d.get('id')))
aid = d.get('id', '')
print('ARTIFACT_ID:', aid)
"
```

**Expected**: `STATE: DRAFT`, `HAS_ID: True`. Record the ARTIFACT_ID for subsequent steps.

### 2. Valid transitions through full lifecycle

```bash
# Capture artifact ID from registration
ART_ID=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json register \
  --name lifecycle.md --type design --project test-asm --phase design \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Artifact: ${ART_ID}"

# DRAFT -> IN_REVIEW
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${ART_ID}" --to IN_REVIEW --by reviewer \
  | python3 -c "import sys,json; print('STATE:', json.load(sys.stdin).get('state'))"

# IN_REVIEW -> APPROVED
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${ART_ID}" --to APPROVED --by gate-pass \
  | python3 -c "import sys,json; print('STATE:', json.load(sys.stdin).get('state'))"

# APPROVED -> IMPLEMENTED
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${ART_ID}" --to IMPLEMENTED --by build-phase \
  | python3 -c "import sys,json; print('STATE:', json.load(sys.stdin).get('state'))"

# IMPLEMENTED -> VERIFIED
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${ART_ID}" --to VERIFIED --by test-phase \
  | python3 -c "import sys,json; print('STATE:', json.load(sys.stdin).get('state'))"

# VERIFIED -> CLOSED
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${ART_ID}" --to CLOSED --by delivery \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('STATE:', d.get('state')); print('HISTORY_LEN:', len(d.get('state_history', [])))"
```

**Expected**: States progress DRAFT -> IN_REVIEW -> APPROVED -> IMPLEMENTED -> VERIFIED -> CLOSED. `HISTORY_LEN:` >= 5.

### 3. Invalid transition rejected

```bash
# Register a fresh artifact in DRAFT, try to skip to APPROVED
SKIP_ID=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json register \
  --name skip-test.md --type design --project test-asm --phase design \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${SKIP_ID}" --to APPROVED --by shortcut 2>&1
echo "Exit: $?"
```

**Expected**: Error mentioning valid transitions from DRAFT (only IN_REVIEW). Non-zero exit or error in output.

### 4. Gate reject handler

```bash
# Register artifact, move to IN_REVIEW, then revert to DRAFT (simulating gate reject)
GATE_ID=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json register \
  --name gate-test.md --type design --project test-asm --phase design \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${GATE_ID}" --to IN_REVIEW --by reviewer > /dev/null

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${GATE_ID}" --to DRAFT --by gate-reject \
  | python3 -c "import sys,json; print('STATE:', json.load(sys.stdin).get('state'))"
```

**Expected**: `STATE: DRAFT` -- IN_REVIEW can revert to DRAFT.

### 5. Bulk check

```bash
# Register 3 artifacts in design phase, approve 2
BULK1=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json register \
  --name bulk-1.md --type design --project test-asm --phase design \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

BULK2=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json register \
  --name bulk-2.md --type design --project test-asm --phase design \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

BULK3=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json register \
  --name bulk-3.md --type design --project test-asm --phase design \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Approve bulk-1 and bulk-2 (DRAFT -> IN_REVIEW -> APPROVED)
for AID in "${BULK1}" "${BULK2}"; do
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
    --id "${AID}" --to IN_REVIEW --by reviewer > /dev/null
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
    --id "${AID}" --to APPROVED --by gate > /dev/null
done

# bulk-3 stays in DRAFT
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json bulk-check \
  --project test-asm --phase design --required-state APPROVED \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
# CLI returns {pass: bool, total: int, passing: int, failing: [ids]}
print('PASS:', d.get('pass', False))
failing = d.get('failing', [])
print('FAILING:', len(failing))
print('TOTAL:', d.get('total', 0))
print('PASSING:', d.get('passing', 0))
"
```

**Expected**: `PASS: False`, `FAILING:` >= 1 (bulk-3 not approved), `TOTAL:` >= 3, `PASSING:` >= 2.

### 6. List with filters

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json list \
  --project test-asm --state APPROVED \
  | python3 -c "
import sys, json
# CLI returns a JSON array of artifact records directly
items = json.load(sys.stdin)
if not isinstance(items, list):
    items = items.get('artifacts', [])
all_approved = all(a.get('state') == 'APPROVED' for a in items)
print('ALL_APPROVED:', all_approved)
print('COUNT:', len(items))
"
```

**Expected**: `ALL_APPROVED: True`, `COUNT:` >= 2 (bulk-1 and bulk-2).

### 7. CLOSED is terminal

```bash
# Use the lifecycle artifact from step 2 (already CLOSED)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/artifact_state.py" --json transition \
  --id "${ART_ID}" --to DRAFT --by reopen 2>&1
echo "Exit: $?"
```

**Expected**: Error — CLOSED has no valid transitions. Non-zero exit or error message.

## Success Criteria

- [ ] Register creates artifact in DRAFT state with a unique ID
- [ ] Full lifecycle DRAFT -> IN_REVIEW -> APPROVED -> IMPLEMENTED -> VERIFIED -> CLOSED succeeds
- [ ] State history grows with each transition
- [ ] DRAFT -> APPROVED (skipping IN_REVIEW) is rejected
- [ ] IN_REVIEW -> DRAFT revert works (gate reject path)
- [ ] Bulk check returns `pass: false` with a non-empty `failing` list when not all artifacts meet required state
- [ ] List filter by state returns only matching artifacts
- [ ] CLOSED is terminal — transitions from CLOSED are rejected

## Cleanup

No filesystem cleanup needed. Artifacts are stored in DomainStore under test-asm project.
