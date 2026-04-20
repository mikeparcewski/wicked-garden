---
name: gate-result-schema-validator-env-bypasses
title: Gate-Result Schema Validator and Env-Var Bypasses (AC-9, PR #501)
description: Verify schema validator rejects missing required fields, banned reviewers, oversized fields; env-var bypasses scoped per-check
type: testing
difficulty: advanced
estimated_minutes: 12
covers:
  - "#517 — gate-result schema validator acceptance criteria"
  - AC-9 §5.4 (schema validator floor + content sanitizer)
  - "#479 (gate-result schema validation)"
ac_ref: "v6.1 PR #501 | scripts/crew/gate_result_schema.py + gate_result_constants.py"
---

# Gate-Result Schema Validator and Env-Var Bypasses

This scenario tests `scripts/crew/gate_result_schema.py::validate_gate_result()`:

1. Missing required fields raise `GateResultSchemaError`.
2. Banned reviewer names (e.g. `just-finish-auto`, `fast-pass`) raise `GateResultSchemaError`.
3. Oversized fields (reason > 8192 bytes, conditions > 2048 bytes) raise `GateResultSchemaError`.
4. `WG_GATE_RESULT_SCHEMA_VALIDATION=off` bypasses schema validation.

All tests use direct Python import — no running Claude session required.

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
```

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
from gate_result_schema import validate_gate_result, GateResultSchemaError
print('PASS: gate_result_schema importable')
"
Assert: PASS: gate_result_schema importable
```

---

## Case 1: Missing required fields → GateResultSchemaError

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
os.environ.pop('WG_GATE_RESULT_SCHEMA_VALIDATION', None)
from gate_result_schema import validate_gate_result, GateResultSchemaError

# Missing 'result' and 'reviewer'
incomplete = {'score': 0.75}
try:
    validate_gate_result(incomplete)
    print('FAIL: expected GateResultSchemaError, got none')
    sys.exit(1)
except GateResultSchemaError as e:
    print(f'PASS: GateResultSchemaError raised for missing required fields: {e}')
"
Assert: PASS: GateResultSchemaError raised for missing required fields
```

---

## Case 2: Banned reviewer name → GateResultSchemaError

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
os.environ.pop('WG_GATE_RESULT_SCHEMA_VALIDATION', None)
from gate_result_schema import validate_gate_result, GateResultSchemaError

BANNED_REVIEWERS = ['just-finish-auto', 'fast-pass', 'auto-approve-all']
for banned in BANNED_REVIEWERS:
    payload = {
        'result': 'APPROVE', 'score': 0.85, 'reviewer': banned,
        'phase': 'review', 'gate': 'final-audit'
    }
    try:
        validate_gate_result(payload)
        print(f'FAIL: banned reviewer \"{banned}\" was not rejected')
        sys.exit(1)
    except GateResultSchemaError as e:
        print(f'PASS: banned reviewer \"{banned}\" rejected: {e}')
"
Assert: PASS: banned reviewer "just-finish-auto" rejected
Assert: PASS: banned reviewer "fast-pass" rejected
Assert: PASS: banned reviewer "auto-approve-all" rejected
```

---

## Case 3: Oversized reason field → GateResultSchemaError

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
os.environ.pop('WG_GATE_RESULT_SCHEMA_VALIDATION', None)
from gate_result_schema import validate_gate_result, GateResultSchemaError
from gate_result_constants import MAX_REASON_BYTES

oversized_reason = 'x' * (MAX_REASON_BYTES + 1)
payload = {
    'result': 'APPROVE', 'score': 0.85, 'reviewer': 'senior-engineer',
    'phase': 'review', 'gate': 'final-audit', 'reason': oversized_reason
}
try:
    validate_gate_result(payload)
    print('FAIL: expected GateResultSchemaError for oversized reason, got none')
    sys.exit(1)
except GateResultSchemaError as e:
    print(f'PASS: oversized reason ({len(oversized_reason.encode())} bytes > {MAX_REASON_BYTES}) rejected: {e}')
"
Assert: PASS: oversized reason rejected
```

---

## Case 4: Oversized conditions entry → GateResultSchemaError

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
os.environ.pop('WG_GATE_RESULT_SCHEMA_VALIDATION', None)
from gate_result_schema import validate_gate_result, GateResultSchemaError
from gate_result_constants import MAX_CONDITION_BYTES

oversized_condition = 'c' * (MAX_CONDITION_BYTES + 1)
payload = {
    'result': 'CONDITIONAL', 'score': 0.65, 'reviewer': 'senior-engineer',
    'phase': 'design', 'gate': 'design-quality',
    'conditions': [oversized_condition]
}
try:
    validate_gate_result(payload)
    print('FAIL: expected GateResultSchemaError for oversized condition, got none')
    sys.exit(1)
except GateResultSchemaError as e:
    print(f'PASS: oversized condition ({MAX_CONDITION_BYTES + 1} bytes) rejected: {e}')
"
Assert: PASS: oversized condition rejected
```

---

## Case 5: Valid gate-result → no exception

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
os.environ.pop('WG_GATE_RESULT_SCHEMA_VALIDATION', None)
from gate_result_schema import validate_gate_result, GateResultSchemaError

valid = {
    'result': 'APPROVE', 'score': 0.85, 'reviewer': 'senior-engineer',
    'phase': 'design', 'gate': 'design-quality',
    'reason': 'Architecture review complete. No blocking issues.'
}
try:
    validate_gate_result(valid)
    print('PASS: valid gate-result passed validation with no exception')
except GateResultSchemaError as e:
    print(f'FAIL: unexpected GateResultSchemaError on valid payload: {e}')
    sys.exit(1)
"
Assert: PASS: valid gate-result passed validation with no exception
```

---

## Case 6: WG_GATE_RESULT_SCHEMA_VALIDATION=off bypasses validation

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts/crew')
os.environ['WG_GATE_RESULT_SCHEMA_VALIDATION'] = 'off'
# Re-import to pick up env change
import importlib
import gate_result_schema
importlib.reload(gate_result_schema)
from gate_result_schema import validate_gate_result, GateResultSchemaError

# This would normally fail (missing required fields + banned reviewer)
bad_payload = {'reviewer': 'just-finish-auto'}
try:
    validate_gate_result(bad_payload)
    print('PASS: WG_GATE_RESULT_SCHEMA_VALIDATION=off bypassed schema validation')
except GateResultSchemaError as e:
    print(f'FAIL: validation ran despite bypass env var: {e}')
    sys.exit(1)
finally:
    del os.environ['WG_GATE_RESULT_SCHEMA_VALIDATION']
"
Assert: PASS: WG_GATE_RESULT_SCHEMA_VALIDATION=off bypassed schema validation
```

---

## Success Criteria

- [ ] `validate_gate_result` raises `GateResultSchemaError` for missing required fields
- [ ] Banned reviewer names (`just-finish-auto`, `fast-pass`, `auto-approve-*`) are rejected
- [ ] `reason` field > `MAX_REASON_BYTES` (8192) raises `GateResultSchemaError`
- [ ] `conditions[]` entry > `MAX_CONDITION_BYTES` (2048) raises `GateResultSchemaError`
- [ ] Valid gate-result passes without exception
- [ ] `WG_GATE_RESULT_SCHEMA_VALIDATION=off` suppresses all validation
