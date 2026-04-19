---
name: in-flight-cutover
title: In-Flight Crew Project Cutover to Mode-3 (CR-2 / AC-α11)
description: |
  Acceptance scenario for CR-2 / AC-α11: legacy projects auto-tag as
  dispatch_mode="v6-legacy"; fresh projects default to "mode-3"; the
  /wicked-garden:crew:cutover command opts a legacy project into mode-3
  with an audit marker.
type: testing
difficulty: intermediate
estimated_minutes: 5
covers:
  - AC-α11 (in-flight cutover)
  - CR-2   (dispatch_mode field + _detect_dispatch_mode + /crew:cutover)
---

# In-Flight Crew Project Cutover

Projects created BEFORE the mode-3 merge retain `state.dispatch_mode: "v6-legacy"`
(auto-tagged on first approve call). Fresh projects default to `"mode-3"`. Users opt
legacy projects into mode-3 via `/wicked-garden:crew:cutover`.

---

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
export LEGACY_PROJECT="cutover-legacy-test"
export FRESH_PROJECT="cutover-fresh-test"

export LEGACY_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys; sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${LEGACY_PROJECT}')
")
export FRESH_DIR=$(sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys; sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects') / '${FRESH_PROJECT}')
")

rm -rf "${LEGACY_DIR}" "${FRESH_DIR}"
mkdir -p "${LEGACY_DIR}/phases" "${FRESH_DIR}/phases"

# Legacy project — NO dispatch_mode field
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {'id': '${LEGACY_PROJECT}', 'name': '${LEGACY_PROJECT}',
     'complexity_score': 3, 'current_phase': 'design',
     'phase_plan': ['clarify', 'design', 'build', 'review'],
     'phases': {}}
pathlib.Path('${LEGACY_DIR}/project.json').write_text(json.dumps(d, indent=2))
"

# Fresh project — dispatch_mode set to mode-3 from creation
sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, pathlib
d = {'id': '${FRESH_PROJECT}', 'name': '${FRESH_PROJECT}',
     'complexity_score': 3, 'current_phase': 'clarify',
     'phase_plan': ['clarify', 'design', 'build', 'review'],
     'dispatch_mode': 'mode-3',
     'phases': {}}
pathlib.Path('${FRESH_DIR}/project.json').write_text(json.dumps(d, indent=2))
"
```

---

## Case 1: legacy auto-tag

**Verifies**: AC-α11(i) — a project without `state.dispatch_mode` backfills to
`"v6-legacy"` on first `_detect_dispatch_mode()` read.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/phase_manager.py "${LEGACY_PROJECT}" detect-mode
```

### Assertions

- stdout contains `"dispatch_mode": "v6-legacy"`.
- The project record now has the field written back.

---

## Case 2: fresh project mode-3

**Verifies**: AC-α11(ii) — a fresh project defaults to `"mode-3"`.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/phase_manager.py "${FRESH_PROJECT}" detect-mode
```

### Assertions

- stdout contains `"dispatch_mode": "mode-3"`.

---

## Case 3: /crew:cutover opts legacy into mode-3

**Verifies**: AC-α11(iii) — `/wicked-garden:crew:cutover` flips the field and emits the
audit marker.

### Test

```bash
sh "${PLUGIN_ROOT}/scripts/_python.sh" "${PLUGIN_ROOT}/scripts/_run.py" \
  scripts/crew/phase_manager.py "${LEGACY_PROJECT}" cutover --to mode-3
```

### Assertions

- `state.dispatch_mode == "mode-3"` after cutover.
- `{LEGACY_DIR}/phases/.cutover-to-mode-3.json` exists and parses as JSON.
- The marker contains `prior_mode: "v6-legacy"` and `new_mode: "mode-3"`.

---

## Teardown

```bash
rm -rf "${LEGACY_DIR}" "${FRESH_DIR}"
```
