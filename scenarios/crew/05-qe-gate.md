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

## v6 approval-check ordering (important)

`approve_phase` runs checks in this order and raises on the **first** failure:

1. **re-eval addendum freshness** (AC-8) — `phases/{phase}/reeval-log.jsonl` must exist
   and post-date `phase.started_at`. Bypass with `--skip-reeval --reason '<why>'`.
2. **required deliverables** — files listed in `phases.json` for the phase (e.g.
   `architecture.md` for design) must exist and meet `min_bytes`. Bypass with
   `--override-deliverables --reason '<why>'`.
3. **specialist engagement** recorded from the session dispatch log (post-gate
   bookkeeping; not an error source for this scenario).
4. **gate result** — `phases/{phase}/gate-result.json` must exist and not REJECT.
   Bypass with `--override-gate --reason '<why>'`.

To assert "gate is the first error", the scenario must pre-satisfy (1) and (2) so
check (4) is the only remaining failure mode. Each step below does that in setup.

## Setup

```bash
export TEST_PROJECT="gate-enforcement-test"
export PROJECT_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")

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

# v6 prerequisites — must be satisfied BEFORE the gate check runs.
# Writes reeval-log.jsonl (AC-8) and architecture.md (design deliverable)
# so the only failure mode left is the gate itself.
seed_preconditions() {
  local phase="${1:-design}"
  local phase_dir="${PROJECT_DIR}/phases/${phase}"
  mkdir -p "${phase_dir}"

  # 1. Re-eval addendum — must post-date phase.started_at. We write "now"
  #    in ISO-8601 which is always >= the phase start recorded on entry.
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, datetime
p = pathlib.Path('${phase_dir}/reeval-log.jsonl')
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
p.write_text(json.dumps({
    'triggered_at': now,
    'mode': 're-evaluate',
    'phase': '${phase}',
    'outcome': 'no-change',
}) + '\n')
"

  # 2. Required deliverables for design phase (architecture.md, min_bytes=200).
  #    For other phases this is a no-op; extend as needed.
  if [ "${phase}" = "design" ]; then
    sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import pathlib
p = pathlib.Path('${phase_dir}/architecture.md')
# 300+ bytes of plausible architecture content to clear the 200-byte floor
p.write_text('# Architecture\n\n' + ('Design notes for gate-enforcement-test. ' * 10))
"
  fi
}

reset_phase() {
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
p = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(p.read_text())
d['current_phase'] = 'design'
d['phases']['design'] = 'in_progress'
p.write_text(json.dumps(d, indent=2))
"
  # Re-seed preconditions so earlier steps don't leave the phase in a state
  # where the re-eval or deliverable check fires before the gate check.
  seed_preconditions design
}
```

## Steps

### 1. Approval blocked when gate not run (preconditions satisfied)

```bash
seed_preconditions design
mock_gate design NONE
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 1
- stderr contains "Gate not run for phase 'design'" or equivalent (gate is the
  first error only because re-eval + deliverables preconditions were seeded)
- stderr contains "--override-gate"
- project.json current_phase still "design" (not advanced)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
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

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 1
- stderr contains "REJECT" or "Resolve findings"
- project.json current_phase still "design"

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
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

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 0
- project current_phase advances to "build"

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
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

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design \
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

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design \
  --override-gate --reason "fast-pass waived for hotfix" \
  2>&1
echo "Exit: $?"

grep "Gate Override" "${PROJECT_DIR}/phases/design/status.md" 2>/dev/null && echo "AUDIT_PRESENT" || echo "NO_AUDIT"
```

**Expected**: exit code 0, `AUDIT_PRESENT`

### 6. Phase with gate_required=false approves without gate check

```bash
# Advance project back to ideate phase (gate_required=false)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
p = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(p.read_text())
d['current_phase'] = 'ideate'
d['phases']['ideate'] = 'in_progress'
p.write_text(json.dumps(d, indent=2))
"

mkdir -p "${PROJECT_DIR}/phases/ideate"

# ideate is gate_required=false, but the re-eval addendum check (AC-8) still
# runs for every phase. Seed the addendum + the brainstorm-summary.md
# deliverable so the only thing we're exercising is the "no gate" path.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, datetime
phase_dir = pathlib.Path('${PROJECT_DIR}/phases/ideate')
phase_dir.mkdir(parents=True, exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
(phase_dir / 'reeval-log.jsonl').write_text(
    json.dumps({'triggered_at': now, 'mode': 're-evaluate', 'phase': 'ideate', 'outcome': 'no-change'}) + '\n'
)
(phase_dir / 'brainstorm-summary.md').write_text(
    '# Brainstorm summary\n\n' + ('Exploration notes for gate-enforcement-test. ' * 5)
)
"

# No gate-result.json present for ideate
rm -f "${PROJECT_DIR}/phases/ideate/gate-result.json"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase ideate 2>&1
echo "Exit: $?"
```

**Expected**: exit code 0, no gate error

### 7. Malformed gate-result.json treated as gate-not-run

```bash
reset_phase
echo 'not valid json{' > "${PROJECT_DIR}/phases/design/gate-result.json"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design 2>&1
echo "Exit: $?"
```

**Expected**: exit code 1 (malformed = gate not run = blocking)

### 8. v6 ordering: re-eval error surfaces BEFORE gate error

This step documents the v6 ordering explicitly — when multiple checks would
fail, the re-eval addendum error is surfaced first, not the gate error.

```bash
reset_phase
# Delete the addendum that seed_preconditions wrote, but leave the
# architecture.md deliverable + NONE gate in place.
rm -f "${PROJECT_DIR}/phases/design/reeval-log.jsonl"
mock_gate design NONE

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 1
- stderr contains "re-evaluation addendum" (or "reeval-log.jsonl") — NOT
  "Gate not run". The addendum check is check 0 and fires first.

### 9. v6 ordering: deliverable error surfaces BEFORE gate error

```bash
reset_phase
# Addendum is present (from reset_phase → seed_preconditions), but delete
# the architecture.md deliverable and leave gate NONE.
rm -f "${PROJECT_DIR}/phases/design/architecture.md"
mock_gate design NONE

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" "${TEST_PROJECT}" approve --phase design 2>&1
echo "Exit: $?"
```

**Expected**:
- exit code 1
- stderr contains "Missing required deliverables" and "architecture.md" — NOT
  "Gate not run". The deliverable check is check 1 and fires before the
  gate check.

## Expected Outcome

Gate enforcement is deterministic and non-bypassable without an explicit override flag. Every
bypass is recorded in the phase's status.md with a timestamp, approver, and reason. The mock
mechanism (writing gate-result.json) makes these tests fast and infrastructure-free.

The v6 check ordering (re-eval → deliverables → gate) is explicit and
deterministic: tests that want to isolate gate behavior must seed the earlier
preconditions, and tests 8/9 prove the ordering by removing one precondition at
a time and observing which error surfaces first.

## Success Criteria

- [ ] Approval blocked (exit 1) when no gate-result.json present for gate_required phase
      (with re-eval + deliverable preconditions satisfied, so gate is the first error)
- [ ] Approval blocked (exit 1) when gate-result.json contains REJECT
- [ ] Approval succeeds (exit 0) when gate-result.json contains PASS and phase advances
- [ ] --override-gate with --reason bypasses REJECT and phase advances
- [ ] Gate override written to status.md with reason and timestamp
- [ ] --override-gate bypasses gate-not-run state with audit trail
- [ ] gate_required=false phases (e.g. ideate) approve without any gate check
- [ ] Malformed gate-result.json treated as gate-not-run (blocking)
- [ ] Missing re-eval addendum surfaces BEFORE gate error (v6 ordering, check 0)
- [ ] Missing deliverable surfaces BEFORE gate error (v6 ordering, check 1)

## Value Demonstrated

Before this change, gate enforcement was advisory prose. Claude followed it inconsistently.
Converting it to a ValueError + sys.exit(1) makes enforcement deterministic and independent
of LLM compliance. The --override-gate escape hatch preserves human override authority while
creating an audit trail that makes bypasses visible.

## Cleanup

```bash
rm -rf "${PROJECT_DIR}"
```
