---
name: verification-protocol
title: 6-Point Verification Protocol
description: Verify verification_protocol.py CLI runs individual and full checks with correct verdicts
type: testing
difficulty: intermediate
estimated_minutes: 12
---

# 6-Point Verification Protocol

This scenario verifies that `verification_protocol.py` correctly executes the 6-point
verification protocol: debug artifact detection, acceptance criteria coverage, test suite
checks, individual check selection, full protocol run, and verdict logic.

## Setup

```bash
export VP_TMPDIR="${TMPDIR:-/tmp}/vp-test-$$"
mkdir -p "${VP_TMPDIR}/phases/clarify"
mkdir -p "${VP_TMPDIR}/phases/design"

# Create acceptance criteria file
cat > "${VP_TMPDIR}/phases/clarify/acceptance-criteria.md" <<'ACEOF'
## Acceptance Criteria

- AC-1: User can log in with valid credentials
- AC-2: Invalid credentials show error message
- AC-3: Session expires after 30 minutes
ACEOF

# Create a deliverable that references AC-1 and AC-2 but not AC-3
cat > "${VP_TMPDIR}/phases/design/design-doc.md" <<'DDEOF'
# Design Document

This design implements AC-1 (login flow) and AC-2 (error handling).
The login component validates credentials against the auth service.
DDEOF

# Create a Python file with debug artifacts
cat > "${VP_TMPDIR}/code.py" <<'PYEOF'
def login(user, pw):
    # TODO: add rate limiting
    print("debug: attempting login")
    return authenticate(user, pw)
PYEOF

# Verify verification_protocol.py is available
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" --help > /dev/null 2>&1 \
  && echo "verification_protocol.py available" || echo "NOT FOUND"
```

## Steps

### 1. Debug artifacts check (FAIL)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" run \
  --project test-vp --phases-dir "${VP_TMPDIR}/phases" \
  --check debug_artifacts --files "${VP_TMPDIR}/code.py" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
checks = d.get('checks', [d]) if not d.get('status') else [d]
for c in checks:
    if c.get('name', '') == 'debug_artifacts' or c.get('status'):
        print('STATUS:', c.get('status', 'N/A'))
        evidence = c.get('evidence', '')
        print('HAS_TODO:', 'TODO' in str(evidence).upper() or 'todo' in str(evidence))
        print('HAS_PRINT:', 'print' in str(evidence).lower())
        break
"
```

**Expected**: `STATUS: FAIL`, `HAS_TODO: True`, `HAS_PRINT: True`.

### 2. Debug artifacts check (PASS)

```bash
# Remove debug artifacts from the file
cat > "${VP_TMPDIR}/code_clean.py" <<'PYEOF'
def login(user, pw):
    return authenticate(user, pw)
PYEOF

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" run \
  --project test-vp --phases-dir "${VP_TMPDIR}/phases" \
  --check debug_artifacts --files "${VP_TMPDIR}/code_clean.py" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
checks = d.get('checks', [d]) if not d.get('status') else [d]
for c in checks:
    if c.get('name', '') == 'debug_artifacts' or c.get('status'):
        print('STATUS:', c.get('status', 'N/A'))
        break
"
```

**Expected**: `STATUS: PASS`.

### 3. Acceptance criteria check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" run \
  --project test-vp --phases-dir "${VP_TMPDIR}/phases" \
  --check acceptance_criteria \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
checks = d.get('checks', [d]) if not d.get('status') else [d]
for c in checks:
    if c.get('name', '') == 'acceptance_criteria' or c.get('status'):
        print('STATUS:', c.get('status', 'N/A'))
        evidence = str(c.get('evidence', ''))
        print('EVIDENCE_LENGTH:', len(evidence))
        break
"
```

**Expected**: Status reflects coverage gap (AC-3 not linked). Evidence mentions criteria coverage.

### 4. Test suite check (SKIP)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" run \
  --project test-vp --phases-dir "${VP_TMPDIR}/phases" \
  --check test_suite \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
checks = d.get('checks', [d]) if not d.get('status') else [d]
for c in checks:
    if c.get('name', '') == 'test_suite' or c.get('status'):
        print('STATUS:', c.get('status', 'N/A'))
        break
"
```

**Expected**: `STATUS: SKIP` (no test runner configured in temp directory).

### 5. Full protocol run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" run \
  --project test-vp --phases-dir "${VP_TMPDIR}/phases" \
  --files "${VP_TMPDIR}/code.py" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
checks = d.get('checks', [])
print('CHECK_COUNT:', len(checks))
names = [c.get('name', '') for c in checks]
print('HAS_ALL_6:', len(names) >= 6)
verdict = d.get('verdict', d.get('summary', {}).get('verdict', 'N/A'))
print('VERDICT:', verdict)
summary = d.get('summary', {})
print('SUMMARY_EXISTS:', bool(summary))
"
```

**Expected**: `CHECK_COUNT: 6`, `HAS_ALL_6: True`, `VERDICT:` present, `SUMMARY_EXISTS: True`.

### 6. Verdict logic

```bash
# With debug artifacts present (code.py has TODO + print), expect FAIL verdict
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" run \
  --project test-vp --phases-dir "${VP_TMPDIR}/phases" \
  --files "${VP_TMPDIR}/code.py" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
verdict = d.get('verdict', d.get('summary', {}).get('verdict', 'N/A'))
print('VERDICT_WITH_ISSUES:', verdict)
"

# With clean code, check for improved verdict
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/verification_protocol.py" run \
  --project test-vp --phases-dir "${VP_TMPDIR}/phases" \
  --files "${VP_TMPDIR}/code_clean.py" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
verdict = d.get('verdict', d.get('summary', {}).get('verdict', 'N/A'))
print('VERDICT_CLEAN:', verdict)
"
```

**Expected**: `VERDICT_WITH_ISSUES: FAIL`. `VERDICT_CLEAN:` should be PASS or improved.

## Success Criteria

- [ ] Debug artifacts check detects TODO and print() statements (FAIL)
- [ ] Debug artifacts check passes on clean code (PASS)
- [ ] Acceptance criteria check reports coverage information
- [ ] Test suite check returns SKIP when no test runner is configured
- [ ] Full protocol run returns all 6 checks with summary and verdict
- [ ] Verdict is FAIL when any check fails; improves when issues are removed

## Cleanup

```bash
rm -rf "${VP_TMPDIR}"
```
