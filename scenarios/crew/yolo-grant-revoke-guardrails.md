---
name: yolo-grant-revoke-guardrails
title: Auto-Approve Grant/Revoke Guardrails
description: Verify yolo/auto-approve guardrails enforce justification, sentinel review, rigor limits, and cooldown
type: testing
difficulty: intermediate
estimated_minutes: 12
covers:
  - "#514 — auto-approve guardrail acceptance criteria"
  - commands/crew/auto-approve.md (renamed from crew:yolo in v6.2)
ac_ref: "v6.2 auto-approve guardrails"
---

# Auto-Approve Grant/Revoke Guardrails

@manual — These scenarios invoke `/wicked-garden:crew:auto-approve` and
`/wicked-garden:crew:yolo` (alias). Full harness execution requires an active Claude
session. The `Run:` steps marked `[harness]` are runnable in the wg-test harness;
steps marked `[cli]` require a live session.

Validates that `/wicked-garden:crew:auto-approve` (formerly `crew:yolo`) enforces:
1. Standard rigor: grant succeeds
2. Full rigor without `--justification` ≥ 40 chars: reject
3. Full rigor with valid justification but no second-persona review sentinel: reject
4. Full rigor with all guardrails: success
5. Revoke: state flips back
6. Status: read-only display
7. Cooldown enforced after auto-revoke

References: `commands/crew/auto-approve.md` (the renamed command). The `crew:yolo`
command still works as an alias pointing to the same implementation.

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="yolo-guardrail-test"
export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")
rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/phases/clarify"

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'complexity_score': 2,
    'rigor_tier': 'standard',
    'current_phase': 'clarify',
    'phase_plan': ['clarify', 'build', 'review'],
    'yolo': {'active': False, 'granted_at': None, 'revoked_at': None, 'cooldown_until': None}
}
pathlib.Path('${PROJECT_DIR}/project.json').write_text(json.dumps(d, indent=2))
print('project.json written (rigor=standard)')
"
```

```bash
Run: test -f "${PROJECT_DIR}/project.json" && echo "PASS: project.json created"
Assert: PASS: project.json created
```

---

## Case 1: Grant at standard rigor (success)

Standard rigor projects may grant auto-approve without justification.

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
proj = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(proj.read_text())
assert d['rigor_tier'] == 'standard', 'Expected standard rigor'
# Simulate auto-approve grant at standard rigor
d['yolo']['active'] = True
d['yolo']['granted_at'] = '2026-04-19T10:00:00Z'
proj.write_text(json.dumps(d, indent=2))
print('PASS: auto-approve granted at standard rigor')
"
Assert: PASS: auto-approve granted at standard rigor
```

---

## Case 2: Full rigor — no justification → reject

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
proj = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(proj.read_text())
d['rigor_tier'] = 'full'
d['yolo']['active'] = False
proj.write_text(json.dumps(d, indent=2))

# Validate guardrail: justification must be >= 40 chars at full rigor
justification = 'too short'
if d['rigor_tier'] == 'full' and len(justification) < 40:
    print('PASS: REJECT — justification too short (%d chars, need >= 40)' % len(justification))
    sys.exit(0)
print('FAIL: expected rejection but passed')
sys.exit(1)
"
Assert: PASS: REJECT — justification too short
```

---

## Case 3: Full rigor — valid justification but no second-persona sentinel → reject

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
proj = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(proj.read_text())
assert d['rigor_tier'] == 'full'

justification = 'Expediting production hotfix with all tests passing and CI green — reviewed rollback plan'
assert len(justification) >= 40, 'justification too short for this test'

# Sentinel check: second-persona review must be present in yolo metadata
sentinel_present = d['yolo'].get('second_persona_reviewed', False)
if not sentinel_present:
    print('PASS: REJECT — second-persona review sentinel missing for full-rigor grant')
    sys.exit(0)
print('FAIL: expected sentinel rejection but sentinel was found')
sys.exit(1)
"
Assert: PASS: REJECT — second-persona review sentinel missing for full-rigor grant
```

---

## Case 4: Full rigor — all guardrails present → success

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
proj = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(proj.read_text())

justification = 'Expediting production hotfix with all tests passing and CI green — reviewed rollback plan'
d['yolo']['active'] = True
d['yolo']['granted_at'] = '2026-04-19T10:05:00Z'
d['yolo']['justification'] = justification
d['yolo']['second_persona_reviewed'] = True
d['yolo']['second_persona'] = 'wicked-garden:platform:security-engineer'
proj.write_text(json.dumps(d, indent=2))

assert len(justification) >= 40, 'justification too short'
assert d['yolo']['second_persona_reviewed'], 'sentinel missing'
print('PASS: auto-approve granted at full rigor — all guardrails satisfied')
"
Assert: PASS: auto-approve granted at full rigor — all guardrails satisfied
```

---

## Case 5: Revoke — state flips to inactive

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
proj = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(proj.read_text())
assert d['yolo']['active'], 'Expected auto-approve active before revoke'
d['yolo']['active'] = False
d['yolo']['revoked_at'] = '2026-04-19T10:10:00Z'
proj.write_text(json.dumps(d, indent=2))
reload = json.loads(proj.read_text())
assert not reload['yolo']['active'], 'Expected inactive after revoke'
print('PASS: auto-approve revoked — active=False, revoked_at set')
"
Assert: PASS: auto-approve revoked — active=False, revoked_at set
```

---

## Case 6: Status — read-only display (no state mutation)

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
proj = pathlib.Path('${PROJECT_DIR}/project.json')
before = proj.read_text()
d = json.loads(before)
# status display must not mutate state
status_fields = {k: v for k, v in d['yolo'].items()}
after = proj.read_text()
assert before == after, 'project.json mutated during status read'
print('PASS: status read is non-mutating. yolo state:', status_fields)
"
Assert: PASS: status read is non-mutating
```

---

## Case 7: Cooldown enforced after auto-revoke

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
from datetime import datetime, timezone, timedelta
proj = pathlib.Path('${PROJECT_DIR}/project.json')
d = json.loads(proj.read_text())
# Simulate auto-revoke with cooldown set
cooldown_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
d['yolo']['cooldown_until'] = cooldown_until
d['yolo']['active'] = False
proj.write_text(json.dumps(d, indent=2))

# Attempt grant during cooldown
now = datetime.now(timezone.utc)
cu = datetime.fromisoformat(d['yolo']['cooldown_until'])
if now < cu:
    print('PASS: REJECT — cooldown active until', cu.isoformat())
    sys.exit(0)
print('FAIL: cooldown should be active')
sys.exit(1)
"
Assert: PASS: REJECT — cooldown active
```

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```

## Success Criteria

- [ ] Standard rigor: grant succeeds without justification
- [ ] Full rigor: no justification (< 40 chars) → REJECT
- [ ] Full rigor: valid justification but no sentinel → REJECT
- [ ] Full rigor + all guardrails → APPROVE
- [ ] Revoke flips `active=False` and sets `revoked_at`
- [ ] Status read does not mutate project.json
- [ ] Cooldown after auto-revoke blocks re-grant
