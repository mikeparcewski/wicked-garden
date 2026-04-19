---
name: convergence-lifecycle
title: Convergence Lifecycle — State Progression + Stall Detection
description: |
  Acceptance scenario for issue #460. Drives scripts/crew/convergence.py through
  the full Designed -> Built -> Wired -> Tested -> Integrated -> Verified chain,
  rejects illegal transitions, surfaces a stall at the 3-session threshold, and
  confirms the review-phase gate verdict flips REJECT -> APPROVE as the artifact
  converges.
type: testing
difficulty: intermediate
estimated_minutes: 10
covers:
  - issue #460 (convergence lifecycle scenario)
  - scripts/crew/convergence.py CLI surface (record / status / stall / verify-gate)
---

# Convergence Lifecycle — State Progression + Stall Detection

Verifies that `convergence.py` correctly drives a code artifact from `Designed`
through `Verified`, rejects forward-skips and out-of-order transitions, detects
an artifact stalled across 3 sessions, and flips the `convergence-verify` gate
from REJECT to APPROVE once the artifact reaches `Verified`.

All assertions are structural (JSON shape + string equality). No LLM in the loop.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="convergence-lifecycle-test"

# Resolve the project dir via the same _paths helper phase_manager uses
export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")

rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/phases/build" "${PROJECT_DIR}/phases/test" "${PROJECT_DIR}/phases/review"

# Minimal project.json so convergence.py can resolve the project_dir via phase_manager
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'complexity_score': 3,
    'current_phase': 'build',
    'phase_plan': ['clarify', 'design', 'build', 'test', 'review'],
    'rigor_tier': 'standard',
    'dispatch_mode': 'mode-3',
    'phases': {k: {'status': 'pending'} for k in ['clarify', 'design', 'build', 'test', 'review']}
}
pathlib.Path('${PROJECT_DIR}/project.json').write_text(json.dumps(d, indent=2))
print('project.json written')
"
```

**Expected stdout**: `project.json written`

---

## Case 1: Full state progression Designed -> Verified

**Verifies**: every forward transition is accepted, evidence envelopes persist,
and `current_state` tracks the latest landing.

### Test

```bash
ART="src/widget.py"

# Designed (initial landing — must target Designed)
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART}" --to Designed \
  --verifier architect --phase build --ref "${ART}" \
  --desc "Design note describes widget contract and interfaces." \
  --session-id s1 > /dev/null

# Built
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART}" --to Built \
  --verifier implementer --phase build --ref "${ART}" \
  --desc "Module compiles and unit-boots cleanly under python -c import." \
  --session-id s1 > /dev/null

# Wired
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART}" --to Wired \
  --verifier implementer --phase build --ref "${ART}" \
  --desc "Caller in app.py now invokes widget.run() on request path." \
  --session-id s1 > /dev/null

# Tested
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART}" --to Tested \
  --verifier qe --phase test --ref "${ART}" \
  --desc "tests/test_widget.py covers happy path and edge case." \
  --session-id s1 > /dev/null

# Integrated
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART}" --to Integrated \
  --verifier qe --phase test --ref "${ART}" \
  --desc "End-to-end flow exercises widget via the public API boundary." \
  --session-id s1 > /dev/null

# Verified
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART}" --to Verified \
  --verifier reviewer --phase review --ref "${ART}" \
  --desc "Review sign-off: ready to ship. Traceability intact." \
  --session-id s1 > /dev/null

# Confirm final state via status
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" status \
  --project "${TEST_PROJECT}" --artifact "${ART}" \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
print('CURRENT_STATE:', d.get('current_state'))
print('HISTORY_LEN:', len(d.get('history', [])))
"
```

**Expected**:

```
CURRENT_STATE: Verified
HISTORY_LEN: 6
```

---

## Case 2: Illegal first landing rejected

**Verifies**: `_validate_transition` rejects a first landing that isn't `Designed`.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "src/new-artifact.py" --to Built \
  --verifier implementer --phase build --ref "src/new-artifact.py" \
  --desc "Trying to skip straight to Built on first landing." \
  --session-id s1 \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
err = d.get('error', '')
print('REJECTED:', bool(err))
print('MENTIONS_DESIGNED:', 'Designed' in err)
"
```

**Expected**:

```
REJECTED: True
MENTIONS_DESIGNED: True
```

---

## Case 3: Illegal forward skip rejected

**Verifies**: an artifact in `Built` cannot skip straight to `Tested`.

### Test

```bash
ART2="src/skipper.py"

sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART2}" --to Designed \
  --verifier architect --phase build --ref "${ART2}" \
  --desc "Design note for skipper artifact." \
  --session-id s1 > /dev/null

sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART2}" --to Built \
  --verifier implementer --phase build --ref "${ART2}" \
  --desc "Skipper compiles cleanly." \
  --session-id s1 > /dev/null

# Attempt Built -> Tested (must be Built -> Wired)
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${ART2}" --to Tested \
  --verifier qe --phase test --ref "${ART2}" \
  --desc "Trying to skip Wired, straight to Tested." \
  --session-id s1 \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
err = d.get('error', '')
print('REJECTED:', bool(err))
print('MENTIONS_WIRED:', 'Wired' in err)
"
```

**Expected**:

```
REJECTED: True
MENTIONS_WIRED: True
```

---

## Case 4: Thin evidence rejected

**Verifies**: evidence envelope validation — description >= 10 chars.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "src/thin.py" --to Designed \
  --verifier architect --phase build --ref "src/thin.py" \
  --desc "short" \
  --session-id s1 \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
err = d.get('error', '')
print('REJECTED:', bool(err))
print('MENTIONS_DESCRIPTION:', 'description' in err.lower())
"
```

**Expected**:

```
REJECTED: True
MENTIONS_DESCRIPTION: True
```

---

## Case 5: Stall detection at session 3

**Verifies**: an artifact held in a pre-Integrated state across 3 distinct
sessions surfaces as a stall finding at `--threshold 3`.

Strategy: create a fresh artifact that lands in `Built` on session `s-stall-1`,
then record unrelated project activity on `s-stall-2` and `s-stall-3` (any
transition on *any* artifact bumps the session set that `sessions_in_state`
counts). The stalled artifact never advances.

### Test

```bash
STALL_ART="src/stalled.py"
PROBE_ART="src/probe.py"

# Land stalled artifact in Built on session 1
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${STALL_ART}" --to Designed \
  --verifier architect --phase build --ref "${STALL_ART}" \
  --desc "Design note for stalled artifact." \
  --session-id s-stall-1 > /dev/null

sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${STALL_ART}" --to Built \
  --verifier implementer --phase build --ref "${STALL_ART}" \
  --desc "Stalled artifact built but never wired up." \
  --session-id s-stall-1 > /dev/null

# Session 2: advance a probe artifact (establishes s-stall-2 as an active session)
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${PROBE_ART}" --to Designed \
  --verifier architect --phase build --ref "${PROBE_ART}" \
  --desc "Probe artifact design note — session 2." \
  --session-id s-stall-2 > /dev/null

# Session 3: probe advances again (s-stall-3 present in log)
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "${TEST_PROJECT}" --artifact "${PROBE_ART}" --to Built \
  --verifier implementer --phase build --ref "${PROBE_ART}" \
  --desc "Probe built cleanly — session 3." \
  --session-id s-stall-3 > /dev/null

# Stall report with default threshold (3 sessions)
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" stall \
  --project "${TEST_PROJECT}" --threshold 3 \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
stalls = d.get('stalls', [])
by_id = {s.get('artifact_id'): s for s in stalls}
print('THRESHOLD:', d.get('threshold'))
print('STALL_COUNT_GE_1:', d.get('count', 0) >= 1)
print('STALLED_ART_PRESENT:', 'src/stalled.py' in by_id)
print('STALLED_STATE:', by_id.get('src/stalled.py', {}).get('state'))
print('STALLED_SESSIONS_GE_3:', by_id.get('src/stalled.py', {}).get('sessions_in_state', 0) >= 3)
"
```

**Expected**: stalled artifact surfaces at threshold 3.

```
THRESHOLD: 3
STALL_COUNT_GE_1: True
STALLED_ART_PRESENT: True
STALLED_STATE: Built
STALLED_SESSIONS_GE_3: True
```

(Skipper from Case 3 is also surfaced as stalled since session s1 predates
s-stall-1/2/3 — any pre-Integrated artifact that hasn't moved for the probe's
three subsequent sessions qualifies. The assertions here focus on
`src/stalled.py` as the load-bearing case.)

---

## Case 6: verify-gate REJECT while pre-Integrated artifacts exist

**Verifies**: any artifact in a pre-Integrated state (Designed/Built/Wired/Tested)
triggers REJECT with a `pre-integrated` finding per artifact.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" verify-gate \
  --project "${TEST_PROJECT}" --threshold 3 \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
findings = d.get('findings', [])
kinds = sorted({f.get('kind') for f in findings})
print('GATE:', d.get('gate'))
print('RESULT:', d.get('result'))
print('FINDING_KINDS:', ','.join(kinds))
print('HAS_PRE_INTEGRATED:', any(f.get('kind') == 'pre-integrated' for f in findings))
"
```

**Expected**:

```
GATE: convergence-verify
RESULT: REJECT
FINDING_KINDS: pre-integrated,stall
HAS_PRE_INTEGRATED: True
```

(Stall finding is also present because Case 5 left `src/stalled.py` stuck in Built.)

---

## Case 7: verify-gate APPROVE on a clean project

**Verifies**: a project where every artifact has reached Verified passes the gate.

### Test

```bash
CLEAN_PROJECT="convergence-clean-test"
export CLEAN_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${CLEAN_PROJECT}')
")

rm -rf "${CLEAN_DIR}"
mkdir -p "${CLEAN_DIR}/phases/build" "${CLEAN_DIR}/phases/test" "${CLEAN_DIR}/phases/review"

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {'id': '${CLEAN_PROJECT}', 'name': '${CLEAN_PROJECT}', 'complexity_score': 2,
     'current_phase': 'review', 'phase_plan': ['build','test','review'],
     'rigor_tier': 'minimal', 'dispatch_mode': 'mode-3',
     'phases': {k: {'status':'pending'} for k in ['build','test','review']}}
pathlib.Path('${CLEAN_DIR}/project.json').write_text(json.dumps(d, indent=2))
"

CLEAN_ART="src/clean.py"
for STATE_PHASE in "Designed:build" "Built:build" "Wired:build" "Tested:test" "Integrated:test" "Verified:review"; do
  STATE="${STATE_PHASE%:*}"
  PHASE="${STATE_PHASE#*:}"
  sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" record \
    --project "${CLEAN_PROJECT}" --artifact "${CLEAN_ART}" --to "${STATE}" \
    --verifier auto --phase "${PHASE}" --ref "${CLEAN_ART}" \
    --desc "Clean-path transition to ${STATE}." \
    --session-id clean-s1 > /dev/null
done

sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/convergence.py" verify-gate \
  --project "${CLEAN_PROJECT}" \
  | sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
d = json.load(sys.stdin)
print('RESULT:', d.get('result'))
print('FINDINGS:', len(d.get('findings', [])))
"
```

**Expected**:

```
RESULT: APPROVE
FINDINGS: 0
```

---

## Case 8: JSONL log is append-only and phase-partitioned

**Verifies**: records land under `phases/{phase}/convergence-log.jsonl`, one
JSONL object per line, with every required envelope field present.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
base = pathlib.Path('${PROJECT_DIR}/phases')
phases_found = sorted([p.name for p in base.iterdir() if (p / 'convergence-log.jsonl').is_file()])
print('PHASES_WITH_LOG:', ','.join(phases_found))
all_rows = []
for p in phases_found:
    for line in (base / p / 'convergence-log.jsonl').read_text().splitlines():
        if line.strip():
            all_rows.append(json.loads(line))
required = {'artifact_id','from_state','to_state','timestamp','session_id','phase','evidence'}
ok = all(required.issubset(r.keys()) for r in all_rows)
print('ROW_COUNT:', len(all_rows))
print('ALL_ROWS_VALID:', ok)
ev_required = {'verifier','phase','artifact_ref','description'}
ev_ok = all(ev_required.issubset(r['evidence'].keys()) for r in all_rows)
print('ALL_EVIDENCE_VALID:', ev_ok)
"
```

**Expected**:

```
PHASES_WITH_LOG: build,review,test
ROW_COUNT: 12
ALL_ROWS_VALID: True
ALL_EVIDENCE_VALID: True
```

(12 = Case 1's 6 transitions + Case 3's 2 valid landings (Designed, Built) +
Case 5's 4 valid landings (stalled x2, probe x2). Rejected records in Cases 2,
3 (Tested skip), and 4 never reach the log.)

---

## Success Criteria

- [ ] Case 1 — Full Designed -> Verified chain lands, history length 6
- [ ] Case 2 — First-landing non-Designed is rejected with mention of Designed
- [ ] Case 3 — Built -> Tested skip is rejected with mention of Wired
- [ ] Case 4 — Sub-10-char description rejected with mention of description
- [ ] Case 5 — Artifact held across 3 sessions surfaces at threshold 3
- [ ] Case 6 — verify-gate returns REJECT when pre-Integrated artifacts exist
- [ ] Case 7 — verify-gate returns APPROVE when every artifact is Verified
- [ ] Case 8 — Log is phase-partitioned JSONL with full evidence envelope

## Cleanup

```bash
rm -rf "${PROJECT_DIR}" "${CLEAN_DIR}"
```
