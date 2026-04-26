---
name: process-facilitator-pattern-a
title: Process Facilitator Pattern A — Skill→Agent file-handoff contract
description: |
  Acceptance scenario for issue #652 item 3. Verifies the slim
  `skills/propose-process/SKILL.md` correctly dispatches to the new
  `agents/crew/process-facilitator.md` agent via Task(), reads back the
  draft plan from disk, and preserves the existing JSON output contract
  so the 6 callers (`crew:start`, `crew:execute` ×2, `crew:just-finish`,
  `crew/phase-executor` ×2) continue working unchanged.
type: testing
difficulty: intermediate
estimated_minutes: 8
covers:
  - issue #652 item 3 (Pattern A migration of propose-process)
  - skills/propose-process/SKILL.md (delegation shim)
  - agents/crew/process-facilitator.md (extracted rubric)
  - file-handoff contract via ${project_dir}/process-plan.draft.json
---

# Process Facilitator Pattern A

Verifies that the Pattern A migration of `wicked-garden:propose-process` works
end-to-end: the slim SKILL.md is a thin dispatch shim, the agent file holds the
full rubric and writes a draft JSON file, and downstream validation
(`scripts/crew/validate_plan.py`) accepts the result.

All structural assertions can be checked with Bash + Python; the LLM
behavioral side (rubric quality) is exercised by the existing
`scenarios/crew/facilitator-rubric/*.md` suite.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="smoke-test-pattern-a"

# Resolve the project dir using the same path helper crew:start uses
export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")

rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}"
echo "PROJECT_DIR=${PROJECT_DIR}"
```

**Expected**: `PROJECT_DIR` resolves to a path under `~/.something-wicked/wicked-garden/local/wicked-crew/projects/smoke-test-pattern-a` (or platform equivalent).

---

## Case 1: Slim SKILL.md is a delegation shim

**Verifies**: `skills/propose-process/SKILL.md` is the thin shim shape
(≤90 lines, contains the `Task(subagent_type="wicked-garden:crew:process-facilitator")`
dispatch, no rubric content remains inline).

### Test

```bash
# Line count: shim should be ≤90 (target ≤80, ceiling 90 for headroom)
LINES=$(wc -l < "${PLUGIN_ROOT}/skills/propose-process/SKILL.md")
test "${LINES}" -le 90 || { echo "SKILL.md too long: ${LINES} > 90"; exit 1; }

# Dispatch line is present
grep -q 'Task(' "${PLUGIN_ROOT}/skills/propose-process/SKILL.md" \
  || { echo "missing Task() dispatch"; exit 1; }
grep -q 'wicked-garden:crew:process-facilitator' "${PLUGIN_ROOT}/skills/propose-process/SKILL.md" \
  || { echo "missing process-facilitator subagent_type"; exit 1; }

# Rubric content is gone (no full factor list inline)
if grep -q 'reversibility.*blast_radius.*compliance_scope' "${PLUGIN_ROOT}/skills/propose-process/SKILL.md"; then
  echo "rubric still inline in SKILL.md (factor list found)"
  exit 1
fi

echo "Case 1 PASS — slim shim shape verified (${LINES} lines)"
```

**Expected stdout**: `Case 1 PASS — slim shim shape verified (...)`.

---

## Case 2: Agent file exists and carries the rubric

**Verifies**: the new `agents/crew/process-facilitator.md` exists, has the
right frontmatter, and contains the rubric content moved out of SKILL.md.

### Test

```bash
test -f "${PLUGIN_ROOT}/agents/crew/process-facilitator.md" \
  || { echo "process-facilitator.md missing"; exit 1; }

# Frontmatter sanity
grep -q '^name: process-facilitator' "${PLUGIN_ROOT}/agents/crew/process-facilitator.md" \
  || { echo "missing name: process-facilitator"; exit 1; }
grep -q '^subagent_type: wicked-garden:crew:process-facilitator' "${PLUGIN_ROOT}/agents/crew/process-facilitator.md" \
  || { echo "missing subagent_type"; exit 1; }

# Rubric content moved here (factor list IS inline)
grep -q 'reversibility' "${PLUGIN_ROOT}/agents/crew/process-facilitator.md" \
  && grep -q 'compliance_scope' "${PLUGIN_ROOT}/agents/crew/process-facilitator.md" \
  || { echo "rubric content missing from agent"; exit 1; }

# File-handoff contract is documented
grep -q 'process-plan.draft.json' "${PLUGIN_ROOT}/agents/crew/process-facilitator.md" \
  || { echo "missing file-handoff contract"; exit 1; }

echo "Case 2 PASS — agent file contains rubric + file-handoff contract"
```

**Expected stdout**: `Case 2 PASS — agent file contains rubric + file-handoff contract`.

---

## Case 3: validate_plan.py self-test still green

**Verifies**: the canonical schema validator is intact and accepts a known-good
plan. This is the gate that downstream callers (`crew:start` Step 5.5) use to
assert the agent's draft.json output is well-formed.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/validate_plan.py" --selftest
```

**Expected exit code**: `0`.

---

## Case 4: validate_plan.py accepts a synthetic agent-shaped draft

**Verifies**: a JSON object matching the file-handoff contract (the shape the
agent writes to `process-plan.draft.json`) is accepted by the schema validator.
Acts as a contract test between the agent's documented output and downstream
consumers.

### Test

```bash
DRAFT="${PROJECT_DIR}/process-plan.draft.json"
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
plan = {
    'project_slug': 'smoke_test_pattern_a',
    'mode': 'propose',
    'summary': 'Trivial typo fix on a button label; minimal rigor smoke test.',
    'factors': {
        'reversibility':      {'reading': 'HIGH',   'why': 'pure copy revert'},
        'blast_radius':       {'reading': 'LOW',    'why': 'one component'},
        'compliance_scope':   {'reading': 'LOW',    'why': 'no PII / regulated data'},
        'user_facing_impact': {'reading': 'HIGH',   'why': 'visible label change'},
        'novelty':            {'reading': 'LOW',    'why': 'done many times'},
        'scope_effort':       {'reading': 'LOW',    'why': 'one file, one line'},
        'state_complexity':   {'reading': 'LOW',    'why': 'no state'},
        'operational_risk':   {'reading': 'LOW',    'why': 'no runtime change'},
        'coordination_cost':  {'reading': 'LOW',    'why': 'single owner'}
    },
    'specialists': [
        {'name': 'frontend-engineer', 'why': 'owns the button component'}
    ],
    'phases': [
        {'name': 'build', 'why': 'one-line copy edit', 'primary': ['frontend-engineer']}
    ],
    'rigor_tier': 'minimal',
    'complexity': 0,
    'tasks': [
        {
            'id': 't1',
            'title': 'Update button label copy',
            'phase': 'build',
            'specialist': 'frontend-engineer',
            'blockedBy': [],
            'metadata': {
                'chain_id': 'smoke_test_pattern_a.root',
                'event_type': 'task',
                'source_agent': 'facilitator',
                'phase': 'build',
                'rigor_tier': 'minimal',
                'test_required': False,
                'test_types': [],
                'evidence_required': []
            }
        }
    ]
}
pathlib.Path('${DRAFT}').write_text(json.dumps(plan, indent=2))
print('draft written:', '${DRAFT}')
"

sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/crew/validate_plan.py" "${DRAFT}"
```

**Expected**: validator exits `0` (silent on success). The draft JSON has the
same shape as the existing rubric output per
`skills/propose-process/refs/output-schema.md`.

---

## Case 5: Caller surface is unchanged

**Verifies**: none of the 6 caller sites changed in the migration — the slim
shim plus the agent preserve the existing Skill() invocation API.

### Test

```bash
# All 6 documented caller invocations still call Skill(skill="wicked-garden:propose-process")
COUNT=$(grep -c 'wicked-garden:propose-process' \
  "${PLUGIN_ROOT}/commands/crew/start.md" \
  "${PLUGIN_ROOT}/commands/crew/execute.md" \
  "${PLUGIN_ROOT}/commands/crew/just-finish.md" \
  "${PLUGIN_ROOT}/agents/crew/phase-executor.md" 2>/dev/null \
  | awk -F: '{sum += $2} END {print sum}')
test "${COUNT}" -ge 6 \
  || { echo "expected ≥6 propose-process references in callers, got ${COUNT}"; exit 1; }

# No caller switched to invoking the agent directly via Task() instead of Skill()
if grep -rE 'Task\([^)]*wicked-garden:crew:process-facilitator' \
  "${PLUGIN_ROOT}/commands" "${PLUGIN_ROOT}/agents" 2>/dev/null | grep -v 'agents/crew/process-facilitator.md' | grep -v 'skills/propose-process/SKILL.md'; then
  echo "FAIL — a caller bypassed the skill and dispatched the agent directly"
  exit 1
fi

echo "Case 5 PASS — caller surface unchanged (${COUNT} Skill() refs preserved)"
```

**Expected stdout**: `Case 5 PASS — caller surface unchanged (...)`.

---

## Cleanup

```bash
rm -rf "${PROJECT_DIR}"
unset PROJECT_DIR TEST_PROJECT PLUGIN_ROOT
```

---

## Notes for reviewer

- **Behavioral coverage** of the rubric itself (factor scoring, specialist
  selection, phase composition) is owned by `scenarios/crew/facilitator-rubric/`
  scenarios 01–10 and `scripts/ci/measure_facilitator.py`. This scenario covers
  only the structural Pattern A migration.
- **Hot-path safety**: `crew:start` calls the skill on every project creation.
  Case 5 is the load-bearing assertion — if any caller broke, projects would
  start with empty task chains.
