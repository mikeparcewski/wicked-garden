---
name: contrarian-convergence-collapse
title: Contrarian v2 — Single-Vector Coverage Triggers Convergence Collapse
description: An artifact with all four sections present but only 1 dissent vector covered must fail validation and (when run via the gate) emit "convergence collapse" with the covered-count and required minimum
type: testing
difficulty: intermediate
estimated_minutes: 5
---

# Contrarian v2 — Convergence Collapse

Convergence collapse in v2 (Issue #721) is defined entirely by the
**Dissent Vectors Covered** checklist: fewer than 3 canonical `[x]`
checkmarks fires the collapse signal. Per the issue, the gate emits
**CONDITIONAL** with reason "convergence collapse: only N dissent
vector(s) covered, >= 3 required".

This scenario verifies both the validator path (per-section minimum)
and the convergence detector emit the expected reason text.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-contrarian-collapse-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Write artifact with all 4 sections but only 1 vector covered

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, pathlib, textwrap
test_dir = pathlib.Path(os.environ['TEST_DIR'])
(test_dir / "challenge-artifacts.md").write_text(textwrap.dedent("""\
    # Challenge Artifacts

    ## Incongruent Representation

    The story is that the new auth flow improves security. The actual
    work narrows attack surface in one place while expanding it in two
    others. The team has not modelled the net change.

    ## Unasked Question

    What is the net change in attack surface across all three planes?

    ## Steelman of Alternative Path

    I argue we should keep the existing flow. It has stood up to three
    years of audit without finding. The proposed flow introduces a
    custom token format that no auditor has reviewed. The migration
    forces every tenant onto the new flow simultaneously. Rollback would
    require coordinated downtime across all tenants.

    ## Dissent Vectors Covered

    - [x] security
    - [ ] cost
    - [ ] operability
    - [ ] ethics
    - [ ] ux
    - [ ] maintenance
    """), encoding="utf-8")
print("single-vector artifact written")
PYEOF
```

**Expected**: `single-vector artifact written`

## Step 2: Validate via CLI — expect specific error naming the count

The `validate` CLI calls `validate_artifact` first; the per-section
minimum on "dissent vectors covered" will fire on this fixture. The
message must include the actual count (`1`) and the required minimum
(`3`) so authors can act on it without re-reading the source.

```bash
result=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/challenge_manifest.py" \
  validate "${TEST_DIR}/challenge-artifacts.md" 2>&1)
echo "${result}"

echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
out = sys.stdin.read().lower()
assert 'invalid:' in out or 'convergence-collapse' in out, f'Expected fail prefix, got: {out!r}'
assert 'dissent vectors covered' in out or 'convergence collapse' in out, \
    f'Expected vector failure, got: {out!r}'
assert '1' in out and '3' in out, f'Expected counts in message, got: {out!r}'
print('PASS: single-vector coverage rejected with counted reason')
"
```

**Expected**: `PASS: single-vector coverage rejected with counted reason`

## Step 3: Direct convergence-collapse detector check

Confirms the dedicated detector also fires on the same fixture and
yields the canonical reason wording from the issue spec.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
import challenge_manifest as cm
text = open('${TEST_DIR}/challenge-artifacts.md').read()
collapsed, why = cm.detect_convergence_collapse(cm.parse_artifact(text))
assert collapsed, 'expected collapse=True'
assert 'convergence collapse' in why.lower()
assert 'only 1 dissent vector' in why.lower()
assert '>= 3 required' in why.lower()
print('PASS: detect_convergence_collapse returns spec-shaped reason')
"
```

**Expected**: `PASS: detect_convergence_collapse returns spec-shaped reason`

## Success Criteria

- [ ] CLI validate exits non-zero on the single-vector fixture
- [ ] Error message names "dissent vectors covered" or "convergence collapse"
- [ ] Error message includes both the actual count (1) and the required minimum (3)
- [ ] `detect_convergence_collapse` returns `(True, "convergence collapse: only 1 dissent vector(s) covered, >= 3 required...")`

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR
```
