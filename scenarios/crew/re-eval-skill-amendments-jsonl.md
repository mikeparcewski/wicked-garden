---
name: re-eval-skill-amendments-jsonl
title: Re-Eval Skill Invocation and Amendments JSONL Append-Only Log (AC-α4, PR #511)
description: Verify re-eval skill invocation at phase boundary, addendum.jsonl append-only behavior, and amendments.jsonl as separate append-only log
type: testing
difficulty: intermediate
estimated_minutes: 10
covers:
  - "#518 — re-eval skill + amendments.jsonl acceptance criteria"
  - AC-α4 (every phase-end re-eval appends to process-plan.addendum.jsonl)
  - "#478 (amendments.jsonl replaces design-addendum-N.md per-file pattern)"
  - "#511 (re-eval skill phase boundary wiring)"
ac_ref: "v6.2 PR #511 | scripts/crew/reeval_addendum.py + amendments.py"
---

# Re-Eval Skill Invocation and Amendments JSONL Append-Only Log

This scenario tests two distinct append-only JSONL logs:

- **`process-plan.addendum.jsonl`** — one record per phase-end re-eval (AC-α4).
  Written by `scripts/crew/reeval_addendum.py`. Never rewritten; only appended.
- **`amendments.jsonl`** — per-phase log for design/AC mutations. Written by
  `scripts/crew/amendments.py`. Replaces `design-addendum-N.md` files (#478).

Both logs must be **append-only** — a rewrite (overwrite) is always a violation.

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export TEST_PROJECT="reeval-amendments-test"
export PROJECT_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${TEST_PROJECT}')
")
rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/phases/design"

sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'complexity_score': 3,
    'rigor_tier': 'standard',
    'current_phase': 'design',
    'phase_plan': ['clarify', 'design', 'build', 'review'],
    'phases': {'clarify': {'status': 'approved'}, 'design': {'status': 'in_progress'}}
}
pathlib.Path('${PROJECT_DIR}/project.json').write_text(json.dumps(d, indent=2))
print('project.json written')
"
```

```bash
Run: test -f "${PROJECT_DIR}/project.json" && echo "PASS: project created"
Assert: PASS: project created
```

---

## Case 1: addendum.jsonl — first append creates file and writes record

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

from reeval_addendum import append, read

project_dir = pathlib.Path('${PROJECT_DIR}')
record = {
    'phase': 'design',
    'trigger': 'phase-end',
    'chain_id': '${TEST_PROJECT}.design',
    'summary': 'Initial design re-eval — no mutations required',
    'plan_mutations': [],
    'scope_changes': []
}
append(project_dir, phase='design', record=record)

addendum_path = project_dir / 'process-plan.addendum.jsonl'
assert addendum_path.exists(), f'addendum.jsonl not created at {addendum_path}'

records = read(project_dir, phase_filter='design')
assert len(records) >= 1, f'Expected >= 1 record, got {len(records)}'
assert records[0]['phase'] == 'design', f'phase mismatch: {records[0]}'
print(f'PASS: addendum.jsonl created with {len(records)} record(s)')
"
Assert: PASS: addendum.jsonl created with 1 record(s)
```

---

## Case 2: addendum.jsonl — second append adds to file (never overwrites)

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

from reeval_addendum import append, read

project_dir = pathlib.Path('${PROJECT_DIR}')
addendum_path = project_dir / 'process-plan.addendum.jsonl'

before_size = addendum_path.stat().st_size
before_lines = len([l for l in addendum_path.read_text().splitlines() if l.strip()])

# Append a second record
record2 = {
    'phase': 'design',
    'trigger': 'task-completion',
    'chain_id': '${TEST_PROJECT}.design',
    'summary': 'AC clarification: FR-3 scope narrowed to API layer only',
    'plan_mutations': [{'type': 'scope-narrowing', 'detail': 'FR-3 limited to API layer'}],
    'scope_changes': ['FR-3']
}
append(project_dir, phase='design', record=record2)

after_size = addendum_path.stat().st_size
after_lines = len([l for l in addendum_path.read_text().splitlines() if l.strip()])

assert after_size > before_size, 'File did not grow — possible overwrite'
assert after_lines == before_lines + 1, f'Expected {before_lines + 1} lines, got {after_lines}'
print(f'PASS: addendum.jsonl grew from {before_lines} to {after_lines} lines (append-only)')
"
Assert: PASS: addendum.jsonl grew from 1 to 2 lines (append-only)
```

---

## Case 3: amendments.jsonl — append records design/AC mutations

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')

from amendments import append as amend_append, list_amendments

project_dir = pathlib.Path('${PROJECT_DIR}')

# First amendment
amd_id_1 = amend_append(
    project_dir=project_dir,
    phase='design',
    trigger='gate-conditional',
    summary='Narrowed FR-3 to API layer per gate CONDITIONAL',
    patches=[{'target': 'phases/design/design.md', 'operation': 'replace',
              'rationale': 'Gate required scope clarification'}],
    resolution_refs=['COND-001']
)

# Second amendment
amd_id_2 = amend_append(
    project_dir=project_dir,
    phase='design',
    trigger='re-eval',
    summary='Added error-handling section to design.md',
    patches=[{'target': 'phases/design/design.md', 'operation': 'add',
              'rationale': 'Reviewer noted missing error path'}],
    resolution_refs=[]
)

amendments_path = project_dir / 'phases' / 'design' / 'amendments.jsonl'
assert amendments_path.exists(), f'amendments.jsonl not found at {amendments_path}'

amendments = list_amendments(project_dir, phase='design')
assert len(amendments) >= 2, f'Expected >= 2 amendments, got {len(amendments)}'

# Verify amendment IDs are distinct and monotonic scope_version
scope_versions = [a['scope_version'] for a in amendments if a.get('source') != 'legacy-md']
assert scope_versions == sorted(scope_versions), 'scope_version not monotonically increasing'

print(f'PASS: amendments.jsonl has {len(amendments)} record(s), IDs: {amd_id_1}, {amd_id_2}')
"
Assert: PASS: amendments.jsonl has 2 record(s)
```

---

## Case 4: validate_reeval_addendum — all appended records are valid

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/validate_reeval_addendum.py "${PROJECT_DIR}/process-plan.addendum.jsonl"
Assert: exit code 0 (all records valid per addendum schema)
```

---

## Case 5: chain_id starts with project ID

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json, pathlib
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
from reeval_addendum import read

project_dir = pathlib.Path('${PROJECT_DIR}')
records = read(project_dir)
for r in records:
    chain_id = r.get('chain_id', '')
    assert chain_id.startswith('${TEST_PROJECT}.'), (
        f'chain_id does not start with project ID: {chain_id!r}'
    )
print(f'PASS: all {len(records)} addendum records have valid chain_id prefix')
"
Assert: PASS: all 2 addendum records have valid chain_id prefix
```

---

## Teardown

```bash
rm -rf "${PROJECT_DIR}"
```

## Success Criteria

- [ ] `reeval_addendum.append` creates `process-plan.addendum.jsonl` on first call
- [ ] Second `append` call adds a line (file grows, not overwritten)
- [ ] `amendments.append` creates `phases/{phase}/amendments.jsonl`
- [ ] Both amendments have distinct `amendment_id` and monotonically increasing `scope_version`
- [ ] `validate_reeval_addendum.py` accepts all appended records (exit 0)
- [ ] Every addendum record's `chain_id` starts with `{project-id}.`
