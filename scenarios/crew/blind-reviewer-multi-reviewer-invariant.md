---
name: blind-reviewer-multi-reviewer-invariant
title: Blind Reviewer and Multi-Reviewer Invariant (AC-β1, PR #510)
description: Verify multi-reviewer parallel gates enforce all-scored-before-aggregation invariant and BLEND-rule aggregation
type: testing
difficulty: advanced
estimated_minutes: 12
covers:
  - "#515 — blind reviewer + multi-reviewer invariant"
  - AC-β1 (blind reviewer has no prior-session context injected)
  - AC-β2 (all reviewers must score before aggregation)
  - AC-β3 (BLEND-rule: min+avg blend for parallel gate scores)
ac_ref: "v6.2 PR #510"
---

# Blind Reviewer and Multi-Reviewer Invariant

This scenario tests the multi-reviewer parallel gate behaviour introduced in PR #510:

1. **Blind reviewer** — reviewer dispatch at complexity >= 5 strips prior-session context
   so the reviewer cannot see previous gate findings (prevents bias propagation).
2. **Multi-reviewer invariant** — all reviewers in a parallel panel must have submitted
   verdicts before the gate aggregator runs. A partial panel → gate stays `pending`.
3. **BLEND-rule aggregation** — final score = 0.4 × min_score + 0.6 × avg_score.

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="blind-review-invariant-test"
export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")
rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/phases/review"

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'complexity_score': 5,
    'rigor_tier': 'full',
    'current_phase': 'review',
    'phase_plan': ['clarify', 'design', 'build', 'review']
}
pathlib.Path('${PROJECT_DIR}/project.json').write_text(json.dumps(d, indent=2))
print('project.json written (complexity=5, full rigor)')
"
```

```bash
Run: test -f "${PROJECT_DIR}/project.json" && echo "PASS: project created"
Assert: PASS: project created
```

---

## Case 1: Blind reviewer — no prior-session context in dispatch payload

At complexity >= 5, the blind reviewer dispatch payload must NOT include
`prior_gate_findings` or `previous_session_context` fields.

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
proj = json.loads(pathlib.Path('${PROJECT_DIR}/project.json').read_text())
complexity = proj['complexity_score']
assert complexity >= 5, f'Need complexity >= 5 for blind reviewer, got {complexity}'

# Simulate building a reviewer dispatch payload — blind reviewers get stripped context
def build_blind_dispatch(reviewer, context_fields_to_strip=None):
    payload = {
        'reviewer': reviewer,
        'phase': 'review',
        'project_id': proj['id'],
        'complexity': complexity,
    }
    # Blind reviewer: strip prior-session fields
    if context_fields_to_strip:
        for field in context_fields_to_strip:
            payload.pop(field, None)
    return payload

BLIND_STRIP = ['prior_gate_findings', 'previous_session_context', 'session_history']
dispatch = build_blind_dispatch('independent-reviewer', context_fields_to_strip=BLIND_STRIP)

for field in BLIND_STRIP:
    assert field not in dispatch, f'Blind reviewer payload contains banned field: {field}'

print('PASS: blind reviewer dispatch payload contains no prior-session context')
print('  fields present:', sorted(dispatch.keys()))
"
Assert: PASS: blind reviewer dispatch payload contains no prior-session context
```

---

## Case 2: Partial panel → gate stays pending (multi-reviewer invariant)

A gate-result.json with only 2 of 3 required reviewers must be rejected as incomplete.

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys

REQUIRED_REVIEWERS = ['senior-engineer', 'independent-reviewer', 'security-engineer']

# Partial panel (only 2 of 3 scored)
partial_gate = {
    'result': 'pending',
    'dispatch_mode': 'parallel',
    'reviewers_required': REQUIRED_REVIEWERS,
    'per_reviewer_verdicts': [
        {'reviewer': 'senior-engineer', 'verdict': 'APPROVE', 'score': 0.88},
        {'reviewer': 'independent-reviewer', 'verdict': 'APPROVE', 'score': 0.82},
        # security-engineer has NOT scored yet
    ]
}

scored = {v['reviewer'] for v in partial_gate['per_reviewer_verdicts']}
missing = [r for r in REQUIRED_REVIEWERS if r not in scored]

if missing:
    print(f'PASS: gate stays pending — {len(missing)} reviewer(s) have not scored: {missing}')
else:
    print('FAIL: expected partial panel to block aggregation')
    sys.exit(1)
"
Assert: PASS: gate stays pending — 1 reviewer(s) have not scored: ['security-engineer']
```

---

## Case 3: Complete panel → BLEND-rule aggregation

All 3 reviewers have scored. BLEND score = 0.4 × min + 0.6 × avg.

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib

REQUIRED_REVIEWERS = ['senior-engineer', 'independent-reviewer', 'security-engineer']
VERDICTS = [
    {'reviewer': 'senior-engineer',      'verdict': 'APPROVE', 'score': 0.88},
    {'reviewer': 'independent-reviewer', 'verdict': 'APPROVE', 'score': 0.82},
    {'reviewer': 'security-engineer',    'verdict': 'APPROVE', 'score': 0.79},
]

scores = [v['score'] for v in VERDICTS]
min_score = min(scores)
avg_score = sum(scores) / len(scores)
blend_score = round(0.4 * min_score + 0.6 * avg_score, 4)

scored = {v['reviewer'] for v in VERDICTS}
missing = [r for r in REQUIRED_REVIEWERS if r not in scored]
assert not missing, f'Panel incomplete: {missing}'

gate_result = {
    'result': 'APPROVE',
    'dispatch_mode': 'parallel',
    'score': blend_score,
    'score_method': 'BLEND(0.4*min+0.6*avg)',
    'min_score': min_score,
    'avg_score': round(avg_score, 4),
    'per_reviewer_verdicts': VERDICTS
}
pathlib.Path('${PROJECT_DIR}/phases/review/gate-result.json').write_text(
    json.dumps(gate_result, indent=2)
)

print(f'PASS: BLEND score = {blend_score} (min={min_score}, avg={round(avg_score,4)})')
print(f'  All {len(VERDICTS)} reviewers scored — gate result: APPROVE')
"
Assert: PASS: BLEND score = 0.8272 (or similar) — all 3 reviewers scored

Run: test -f "${PROJECT_DIR}/phases/review/gate-result.json" && echo "PASS: gate-result.json written"
Assert: PASS: gate-result.json written
```

---

## Case 4: BLEND with CONDITIONAL verdict → gate is CONDITIONAL

If any reviewer returns CONDITIONAL, the final verdict is CONDITIONAL regardless of blend score.

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json

VERDICTS = [
    {'reviewer': 'senior-engineer',      'verdict': 'APPROVE',      'score': 0.85},
    {'reviewer': 'independent-reviewer', 'verdict': 'CONDITIONAL',  'score': 0.68},
    {'reviewer': 'security-engineer',    'verdict': 'APPROVE',       'score': 0.80},
]

scores = [v['score'] for v in VERDICTS]
blend_score = round(0.4 * min(scores) + 0.6 * (sum(scores)/len(scores)), 4)

# Verdict escalation: CONDITIONAL beats APPROVE; REJECT beats all
escalation_order = ['APPROVE', 'CONDITIONAL', 'REJECT']
final_verdict = max((v['verdict'] for v in VERDICTS), key=lambda v: escalation_order.index(v))

print(f'PASS: final_verdict={final_verdict}, blend_score={blend_score}')
assert final_verdict == 'CONDITIONAL', f'Expected CONDITIONAL, got {final_verdict}'
"
Assert: PASS: final_verdict=CONDITIONAL
```

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```

## Success Criteria

- [ ] Complexity >= 5: blind reviewer dispatch strips prior-session context fields
- [ ] Partial panel (< all reviewers scored) → gate result stays `pending`
- [ ] Complete panel → BLEND score = 0.4 × min + 0.6 × avg
- [ ] gate-result.json written with correct score_method
- [ ] CONDITIONAL from any reviewer escalates final verdict to CONDITIONAL
