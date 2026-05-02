---
name: contrarian-missing-section
title: Contrarian v2 — Missing Required Section Triggers Specific Validator Error
description: An artifact with three of four v2 sections (no "unasked question") fails validation with a reason naming the missing section
type: testing
difficulty: intermediate
estimated_minutes: 5
---

# Contrarian v2 — Missing Required Section

Issue #721 v2 schema requires four sections. This scenario verifies that
omitting any one of them produces a validator error that names the
missing section, so authors know exactly what to add.

The validator is `scripts/crew/challenge_manifest.py validate` — also
the same module the hook gate calls into via `artifact_satisfies_gate`.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile, sys
print(tempfile.mkdtemp(prefix='wg-contrarian-missing-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

**Expected**: a temp dir path is printed.

## Step 1: Write artifact with 3 of 4 sections (missing "unasked question")

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, pathlib, textwrap
test_dir = pathlib.Path(os.environ['TEST_DIR'])
(test_dir / "challenge-artifacts.md").write_text(textwrap.dedent("""\
    # Challenge Artifacts

    ## Incongruent Representation

    The dominant story claims the new pipeline ships value this quarter.
    The actual shape of the work is a refactor disguised as a feature.
    No customer in recent interviews asked for it.

    ## Steelman of Alternative Path

    I argue we should not ship the pipeline this quarter. The current
    system serves traffic with a known operational profile. Replacing it
    now diverts engineers from a backlog of customer-facing fixes. A
    staged rewrite carries less risk and preserves rollback. Most
    importantly, no customer has asked for the work.

    ## Dissent Vectors Covered

    - [x] security
    - [x] cost
    - [x] operability
    - [ ] ethics
    - [ ] ux
    - [ ] maintenance
    """), encoding="utf-8")
print("artifact written (no 'unasked question' section)")
PYEOF
```

**Expected**: `artifact written (no 'unasked question' section)`

## Step 2: Validate — expect missing-section error naming "unasked question"

```bash
result=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/challenge_manifest.py" \
  validate "${TEST_DIR}/challenge-artifacts.md" 2>&1)
echo "${result}"

echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
out = sys.stdin.read()
assert out.startswith('INVALID:'), f'Expected INVALID prefix, got: {out!r}'
assert 'unasked question' in out.lower(), f'Expected missing section name, got: {out!r}'
print('PASS: missing-section validator names the omitted section')
"
```

**Expected**:
```
INVALID: challenge artifact is missing required section(s): unasked question.
PASS: missing-section validator names the omitted section
```

## Success Criteria

- [ ] Validator returns non-zero exit
- [ ] Error message starts with `INVALID:`
- [ ] Error message contains the literal string `unasked question`

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR
```
