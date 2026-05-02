---
name: contrarian-well-formed
title: Contrarian v2 — Well-Formed Artifact Validates and Clears the Gate
description: A v2-conformant artifact (all 4 sections meeting per-section minima, >=3 dissent vectors covered) passes validate_artifact and artifact_satisfies_gate
type: testing
difficulty: intermediate
estimated_minutes: 5
---

# Contrarian v2 — Well-Formed Artifact

This scenario asserts the happy path: an artifact that satisfies every
v2 rule (4 sections × per-section minima + >=3 canonical dissent
vectors) returns `OK` from the validator CLI and clears
`artifact_satisfies_gate` end-to-end.

This is the inverse of the missing-section and convergence-collapse
scenarios — it proves the gate accepts what it should accept, not just
that it rejects what it should reject.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-contrarian-wellformed-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Write a fully-conformant v2 artifact

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, pathlib, textwrap
test_dir = pathlib.Path(os.environ['TEST_DIR'])
(test_dir / "phases" / "design").mkdir(parents=True, exist_ok=True)
(test_dir / "phases" / "design" / "challenge-artifacts.md").write_text(textwrap.dedent("""\
    # Challenge Artifacts

    ## Incongruent Representation

    The dominant story claims the new pipeline ships value this quarter.
    The actual shape of the work is a refactor disguised as a feature.
    Recent customer interviews surfaced needs that this work pushes back,
    and none of the interviewees asked for the pipeline itself.

    ## Unasked Question

    What measurable user outcome would tell us this migration was worth
    the engineering quarter it consumes? And what is the rollback plan
    if customer-facing latency regresses by 50ms?

    ## Steelman of Alternative Path

    I argue we should not ship the pipeline this quarter. The current
    system serves traffic with a known operational profile and a runbook
    on-call already trusts. Replacing it now diverts engineers from a
    backlog of customer-facing fixes that have measurable revenue impact.
    A staged rewrite over two quarters carries less rollback risk and
    preserves optionality. Most importantly, no customer has asked for
    the work, and the team's product council has not prioritised it
    against other inflight commitments. We can revisit next quarter once
    the customer signal is clearer.

    ## Dissent Vectors Covered

    - [x] security
    - [x] cost
    - [x] operability
    - [x] ethics
    - [ ] ux
    - [ ] maintenance
    """), encoding="utf-8")
print("v2 well-formed artifact written (4 vectors covered)")
PYEOF
```

**Expected**: `v2 well-formed artifact written (4 vectors covered)`

## Step 2: CLI validate returns OK

```bash
result=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/challenge_manifest.py" \
  validate "${TEST_DIR}/phases/design/challenge-artifacts.md" 2>&1)
echo "${result}"

echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
out = sys.stdin.read().strip()
assert out == 'OK', f'Expected exactly OK, got: {out!r}'
print('PASS: well-formed artifact validates as OK')
"
```

**Expected**:
```
OK
PASS: well-formed artifact validates as OK
```

## Step 3: artifact_satisfies_gate returns (True, "")

The gate-level check that the hook actually calls in production.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, pathlib, os
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
import challenge_manifest as cm
ok, reason = cm.artifact_satisfies_gate(pathlib.Path('${TEST_DIR}'), phase='design')
assert ok, f'Expected gate to clear, got reason: {reason!r}'
assert reason == '', f'Expected empty reason on pass, got: {reason!r}'
print('PASS: artifact_satisfies_gate returns (True, \"\")')
"
```

**Expected**: `PASS: artifact_satisfies_gate returns (True, "")`

## Step 4: Sidecar override path also passes

If a `challenge-artifacts.meta.json` is present, the gate prefers it for
vector counting. Verify a sidecar with a vector list also passes.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, pathlib
test_dir = pathlib.Path(os.environ['TEST_DIR'])
(test_dir / "phases" / "design" / "challenge-artifacts.meta.json").write_text(
    json.dumps({"vectors": ["security", "cost", "operability"], "questions_count": 2}),
    encoding="utf-8",
)
print("sidecar written")
PYEOF

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, pathlib
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
import challenge_manifest as cm
ok, reason = cm.artifact_satisfies_gate(pathlib.Path('${TEST_DIR}'), phase='design')
assert ok, f'Expected gate to clear with sidecar, got: {reason!r}'
print('PASS: gate clears via sidecar-derived vector list')
"
```

**Expected**: `PASS: gate clears via sidecar-derived vector list`

## Success Criteria

- [ ] CLI validate prints exactly `OK` and exits 0
- [ ] `artifact_satisfies_gate` returns `(True, "")`
- [ ] With a well-formed sidecar, gate still clears

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR
```
