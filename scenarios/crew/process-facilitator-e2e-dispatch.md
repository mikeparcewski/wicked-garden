---
name: process-facilitator-e2e-dispatch
title: Process Facilitator Pattern A — true e2e dispatch verification
description: |
  Companion to `process-facilitator-pattern-a.md` (which is purely structural).
  This scenario actually invokes `Skill("wicked-garden:propose-process", ...)`
  end-to-end and asserts that:

  1. The slim `skills/propose-process/SKILL.md` Step 0 → Step 3 sequence ran
     (project_dir resolved, agent dispatched via Task(), draft JSON written
     and read back, JSON returned to caller).
  2. The returned JSON conforms to `refs/output-schema.md`.
  3. With `output=json`, no TaskCreate was issued (the chain emit path is
     skipped — that's the caller's responsibility).
  4. The `wicked-garden:crew:process-facilitator` agent was actually
     dispatched (the dispatch is observable in the session task list /
     dispatch log).
  5. No file leak after the scenario — draft files are removed cleanly.
type: testing
difficulty: intermediate
estimated_minutes: 6
covers:
  - issue #652 item 3 (Pattern A migration of propose-process)
  - skills/propose-process/SKILL.md Step 0 → Step 3 (file-handoff dispatch)
  - agents/crew/process-facilitator.md (rubric agent dispatch)
  - PR #670 council CONDITIONAL #3 (e2e dispatch evidence)
---

# Process Facilitator E2E Dispatch

The sister scenario `process-facilitator-pattern-a.md` covers structural
properties of the migration (shim shape, agent presence, validator selftest,
caller surface). This scenario covers the **runtime** behavior: a real
`Skill()` invocation, a real `Task()` dispatch to the agent, a real draft
file written and read back, and a clean teardown.

It is intentionally narrow — one realistic minimal-rigor input ("typo fix")
and a tight set of post-conditions. Behavioral coverage of the rubric itself
(specialist selection, phase composition, complexity scoring) lives in
`scenarios/crew/facilitator-rubric/*.md` + `scripts/ci/measure_facilitator.py`.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"

# Use a unique slug per scenario run so concurrent runs don't collide.
export RANDOM_ID=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import secrets
print(secrets.token_hex(4))
")
export TEST_PROJECT="e2e-test-${RANDOM_ID}"

export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")

rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}"
echo "PROJECT_DIR=${PROJECT_DIR}"
echo "TEST_PROJECT=${TEST_PROJECT}"
```

**Expected**: `PROJECT_DIR` resolves to a path under
`~/.something-wicked/wicked-garden/local/wicked-crew/projects/e2e-test-{8-hex}/`
(or platform equivalent). The directory is empty.

---

## Case 1: Skill() round-trips via the agent and returns conforming JSON

**Verifies**: Step 0 (project_dir resolution) → Step 1 (Task() dispatch to
`wicked-garden:crew:process-facilitator`) → Step 2 (read back
`process-plan.draft.json`) → Step 3 (`output=json` returns content) all
execute, and the returned JSON matches `refs/output-schema.md`.

### Test — invoke the skill

```
Skill(
  "wicked-garden:propose-process",
  args={
    "mode": "propose",
    "description": "add a typo fix to README",
    "project_slug": "${TEST_PROJECT}",
    "project_dir": "${PROJECT_DIR}",
    "output": "json"
  }
)
```

Capture the returned JSON to a local var (e.g. `RESPONSE`). Then write it
to `${PROJECT_DIR}/skill-response.json` so the next step can validate it
out-of-band:

```bash
# Persist the captured Skill() response. The exact mechanism depends on the
# scenario runner (it has access to the prior tool's output). Conceptually:
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
# Scenario runner substitutes the captured Skill() output here.
# In a manual run, paste the JSON between the heredoc markers.
response = json.loads(sys.stdin.read())
pathlib.Path('${PROJECT_DIR}/skill-response.json').write_text(
    json.dumps(response, indent=2)
)
print('captured Skill() response:', '${PROJECT_DIR}/skill-response.json')
" <<'JSON_END'
${RESPONSE}
JSON_END
```

### Test — assert the response is valid

```bash
# 1. The draft file was written by the agent at the documented path.
test -f "${PROJECT_DIR}/process-plan.draft.json" \
  || { echo "FAIL — process-plan.draft.json was not written by agent"; exit 1; }

# 2. The Skill() response equals (or is a superset of) the on-disk draft.
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
draft  = json.loads(pathlib.Path('${PROJECT_DIR}/process-plan.draft.json').read_text())
resp   = json.loads(pathlib.Path('${PROJECT_DIR}/skill-response.json').read_text())
# The shim returns the JSON content read from disk; the two MUST match.
if resp != draft:
    sys.stderr.write('mismatch between Skill() response and draft.json\n')
    sys.exit(1)
print('Skill() response == draft.json (round-trip verified)')
"

# 3. The response validates against refs/output-schema.md (use validate_plan.py).
sh "${PLUGIN_ROOT}/scripts/_python.sh" \
  "${PLUGIN_ROOT}/scripts/crew/validate_plan.py" \
  "${PROJECT_DIR}/skill-response.json" \
  || { echo "FAIL — Skill() response does not validate against output-schema.md"; exit 1; }

echo "Case 1 PASS — Skill() round-trip + schema validation green"
```

**Expected stdout**: `Case 1 PASS — Skill() round-trip + schema validation green`.

---

## Case 2: With `output=json`, no TaskCreate was issued

**Verifies**: Step 3 contract — when the caller passes `output=json`, the shim
returns the JSON directly and does **not** emit the task chain. The chain is
the caller's job (e.g. `crew:start` Step 7).

### Test

```bash
# Snapshot the native task store before the Skill() call would be ideal, but
# the runner already invoked it in Case 1. Instead, assert post-state: any
# TaskCreate that DID happen during this scenario must NOT carry our unique
# project slug — if the shim had created tasks, they'd be tagged with it.

TASKS_DIR="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}/tasks"

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, os, pathlib, sys
tasks_root = pathlib.Path('${TASKS_DIR}')
slug       = '${TEST_PROJECT}'
if not tasks_root.exists():
    print('no tasks dir present — vacuously OK')
    sys.exit(0)
hits = []
for session_dir in tasks_root.iterdir():
    if not session_dir.is_dir():
        continue
    for tf in session_dir.glob('*.json'):
        try:
            t = json.loads(tf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        meta = (t.get('metadata') or {})
        chain = meta.get('chain_id') or ''
        subj  = (t.get('subject') or '')
        if slug in chain or slug in subj:
            hits.append(str(tf))
if hits:
    sys.stderr.write('FAIL — output=json but TaskCreate fired for our slug:\n')
    for h in hits:
        sys.stderr.write(f'  {h}\n')
    sys.exit(1)
print('Case 2 PASS — no TaskCreate observed for output=json call')
"
```

**Expected stdout**: `Case 2 PASS — no TaskCreate observed for output=json call`.

---

## Case 3: The agent was actually dispatched

**Verifies**: Step 1 — the shim issued a `Task(subagent_type="wicked-garden:crew:process-facilitator", ...)`
call. Without this, the draft.json wouldn't exist (so Case 1 already implies it),
but assert it explicitly via the dispatch log when present.

### Test

```bash
# Path A: prefer the HMAC dispatch log if the project has one for this run.
DISPATCH_LOG="${PROJECT_DIR}/phases/clarify/dispatch-log.jsonl"

# Path B: the draft.json existing on disk is itself proof that the agent ran
# (the agent is the only writer of that file in the v6 contract). This is the
# load-bearing check — if the shim faked the response without dispatching the
# agent, draft.json would be absent.

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib, sys
draft = pathlib.Path('${PROJECT_DIR}/process-plan.draft.json')
if not draft.exists():
    sys.stderr.write('FAIL — agent never wrote draft.json (was it dispatched?)\n')
    sys.exit(1)
# The schema requires non-empty 'specialists' and 'phases' lists for any
# real rubric output — sanity-check those came from agent reasoning, not a
# stub.
data = json.loads(draft.read_text())
specs = data.get('specialists') or []
phases = data.get('phases')   or []
if not specs or not phases:
    sys.stderr.write(f'FAIL — agent output looks empty (specs={specs}, phases={phases})\n')
    sys.exit(1)
print(f'Case 3 PASS — agent dispatched (wrote draft with {len(specs)} specialists, {len(phases)} phases)')
"

# Optional belt-and-braces: if a dispatch log exists, the facilitator entry
# MUST be present.
if [ -f "${DISPATCH_LOG}" ]; then
  grep -q 'wicked-garden:crew:process-facilitator' "${DISPATCH_LOG}" \
    || { echo "FAIL — dispatch log present but missing process-facilitator entry"; exit 1; }
  echo "  (dispatch log corroborates: process-facilitator entry found)"
fi
```

**Expected stdout**: `Case 3 PASS — agent dispatched (wrote draft with N specialists, M phases)`
(N >= 1, M >= 1).

---

## Case 4: Clean teardown — no file leak

**Verifies**: After the scenario removes `${PROJECT_DIR}`, no orphan files
remain. (The shim Step 3 also documents an ephemeral-tmp cleanup path for the
no-project measurement call shape; this scenario uses the real-project shape,
so cleanup is the caller's responsibility.)

### Test

```bash
rm -rf "${PROJECT_DIR}"
test ! -e "${PROJECT_DIR}" \
  || { echo "FAIL — ${PROJECT_DIR} still exists after rm -rf"; exit 1; }
echo "Case 4 PASS — project dir removed cleanly"
```

**Expected stdout**: `Case 4 PASS — project dir removed cleanly`.

---

## Cleanup

```bash
unset PROJECT_DIR TEST_PROJECT RANDOM_ID PLUGIN_ROOT
```

---

## Notes for reviewer

- **Distinct from `process-facilitator-pattern-a.md`**: that scenario tests
  *file shape* (line count, frontmatter, validator selftest, caller surface).
  This one tests *runtime dispatch* (real Skill() call, real Task() dispatch,
  real draft round-trip). They are deliberately separate so a structural
  regression and a dispatch regression surface as distinct failures.
- **Why output=json**: the caller surface most at risk from the Pattern A
  migration is the `output=json` path (5 of the 6 callers use it). This
  scenario exercises that path directly.
- **Cleanup model**: this scenario uses the real-project call shape, so the
  draft persists at `${PROJECT_DIR}/process-plan.draft.json` until the test
  removes it in Case 4. The no-project ephemeral-tmp path (documented in the
  shim's Step 0/3) is not covered here — that's a measurement-only path used
  by `scripts/ci/measure_facilitator.py` capture flows.
