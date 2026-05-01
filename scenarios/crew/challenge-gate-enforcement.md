---
name: challenge-gate-enforcement
title: Challenge Gate Enforcement — Write Blocked Without Valid Contrarian Artifact
description: Verify the Issue #442 challenge-artifacts gate blocks build-phase Write/Edit when the contrarian artifact is missing, invalid, or convergence-collapsed — and clears once a well-formed steelmanned artifact is in place
type: testing
difficulty: advanced
estimated_minutes: 20
---

# Challenge Gate Enforcement — Write Blocked Without Valid Contrarian Artifact

This scenario exercises the `_check_challenge_gate` hook path in
`hooks/scripts/pre_tool.py` end-to-end. Unit tests in
`tests/crew/test_challenge_manifest.py` cover the parser and gate
evaluator in isolation, but no scenario drove the full hook flow:
Write intent → active crew project discovery → complexity check →
artifact validation → deny reason.

The four cases are:

1. **Artifact present and well-formed** → Write on a normal source file
   is allowed (gate clears).
2. **Artifact missing** at build phase, complexity 7 → Write denied
   with a deny-reason that names the missing file and the contrarian
   specialist.
3. **Artifact present but invalid** (convergence collapse — all three
   resolved challenges share one theme) → Write denied with a reason
   that references "collapse" and the converged theme.
4. **`WG_CHALLENGE_GATE=off` scoped bypass** → Same invalid artifact
   that blocked in case 3 now returns allow, proving the documented
   escape hatch works.

The hook functions are tested directly via Python import. This avoids
requiring a running Claude session, keeps the scenario deterministic,
and exercises the exact code path the real hook executes.

(v6.0 removed the global `CREW_GATE_ENFORCEMENT=legacy` switch;
`WG_CHALLENGE_GATE=off` is the only remaining scoped bypass, kept as
a temporary rollback when the contrarian specialist is unavailable.)

## Setup

```bash
export TEST_PROJECT="test-challenge-gate"
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"

# Scope the hook's project discovery to this scenario's workspace.
# _find_active_crew_project filters by CLAUDE_PROJECT_NAME or cwd basename.
export CLAUDE_PROJECT_NAME="wg-scenario-challenge-gate"

# Resolve both the DomainStore record path and the project phases
# directory. Crew stores projects as a sibling pair:
#   wicked-crew/projects/{id}.json   — DomainStore record (list() reads this)
#   wicked-crew/projects/{id}/       — phase artifacts (challenge-artifacts.md)
export PROJECTS_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
print(get_local_path('wicked-crew', 'projects'))
")
export PROJECT_JSON="${PROJECTS_ROOT}/${TEST_PROJECT}.json"
export PROJECT_DIR="${PROJECTS_ROOT}/${TEST_PROJECT}"
echo "PROJECT_JSON=${PROJECT_JSON}"
echo "PROJECT_DIR=${PROJECT_DIR}"

# Clean start — remove any prior run's state
rm -f "${PROJECT_JSON}"
rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}"

# DomainStore record + phase directory. The record sits at
# projects/{id}.json so `DomainStore('wicked-crew').list('projects')`
# picks it up; phase content goes under projects/{id}/phases/...
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from _paths import get_local_path
projects_root = get_local_path('wicked-crew', 'projects')
d = {
    'id': '${TEST_PROJECT}',
    'name': '${TEST_PROJECT}',
    'workspace': '${CLAUDE_PROJECT_NAME}',
    'complexity_score': 7,
    'current_phase': 'build',
    'phase_plan': ['clarify', 'design', 'test-strategy', 'build', 'test', 'review'],
    'phases': {
        'clarify': {'status': 'completed'},
        'design': {'status': 'completed'},
        'test-strategy': {'status': 'completed'},
        'build': {'status': 'in_progress'},
        'test': {'status': 'pending'},
        'review': {'status': 'pending'}
    }
}
(projects_root / '${TEST_PROJECT}.json').write_text(json.dumps(d, indent=2))
# Also drop a mirror project.json inside the phase dir for tools that
# read it directly (challenge_manifest uses project_dir / 'project.json').
(projects_root / '${TEST_PROJECT}' / 'project.json').write_text(json.dumps(d, indent=2))
print('project record written to', projects_root / '${TEST_PROJECT}.json')
"
```

**Expected**: `project.json written to <path>`

## Helper: run Write guard

All steps build a PreToolUse tool_input for a Write on a normal source
file and invoke `_handle_write_guard` directly. The helper returns the
hook's JSON output so each step can assert on `permissionDecision` and
`permissionDecisionReason`.

```bash
write_guard() {
  local file_path="$1"
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json, os
sys.path.insert(0, '${PLUGIN_ROOT}/hooks/scripts')
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
# Ensure the hook resolves the same plugin root the scenario does.
os.environ['CLAUDE_PLUGIN_ROOT'] = '${PLUGIN_ROOT}'
from pre_tool import _handle_write_guard
result = _handle_write_guard({'file_path': '$file_path', 'content': 'print(1)\n'})
print(result)
"
}
```

A normal build-phase Write target is `src/payments/processor.py` under
the workspace root — not on the orchestrator allowlist, not the
challenge-artifacts file itself. That is the target used throughout.

## Steps

### Step 1: Well-formed challenge artifact → Write ALLOWED

Install a well-formed artifact with three distinct themes, all resolved
challenges carrying a ≥40-char steelman. The gate must clear and Write
must be permitted.

```bash
mkdir -p "${PROJECT_DIR}/phases/design"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, textwrap, pathlib
project_dir = pathlib.Path(os.environ['PROJECT_DIR'])
body = textwrap.dedent("""\
    # Challenge Artifacts

    ## Strongest Opposing View

    The proposed payment processor trades operational simplicity for a
    novel coordination primitive. The best version of the opposite
    position is that the existing queue-based integration has delivered
    three years of reliable throughput and its failure modes are fully
    understood by on-call.

    ## Challenges

    ### Challenge CH-01: novel-coordination-primitive
    - theme: correctness
    - raised_by: contrarian
    - status: resolved
    - steelman: Current queue semantics are well-understood and have
      stood up to production load for three years. Replacing them
      introduces unknown-unknowns that a rewrite does not.

    ### Challenge CH-02: observability-regression
    - theme: operability
    - raised_by: contrarian
    - status: resolved
    - steelman: Today on-call can grep a single log stream. The new
      design fragments traces across four services and that
      fragmentation is a measurable, persistent cost.

    ### Challenge CH-03: rollout-blast-radius
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: The migration window forces all tenants onto the new
      schema simultaneously. A bug there has a global blast radius
      versus the current per-tenant isolation.

    ## Convergence Check

    3 challenges across 3 themes (correctness, operability, security).
    No collapse.

    ## Resolution

    CH-01: chose the new primitive with a documented rollback runbook.
    CH-02: accepted with a tracing-evidence requirement. CH-03: accepted
    with a canary stage and explicit rollback criteria.
    """)
(project_dir / "phases" / "design" / "challenge-artifacts.md").write_text(body, encoding="utf-8")
print("well-formed challenge artifact written")
PYEOF

result=$(write_guard "src/payments/processor.py")
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
decision = d.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')
assert decision != 'deny', f'Expected allow but got deny: {d}'
print('PASS: well-formed artifact cleared the gate — Write allowed')
"
```

**Expected**: `PASS: well-formed artifact cleared the gate — Write allowed`

The hook must NOT return `permissionDecision: deny`. (It may return the
default allow, or an allow with an orchestrator-allowlist warning —
both are acceptable; only `deny` would be a failure.)

### Step 2: Missing challenge artifact → Write BLOCKED

Remove the artifact entirely. Build phase at complexity 7 must deny the
Write with a reason that names the missing file and the contrarian
specialist.

```bash
rm -f "${PROJECT_DIR}/phases/design/challenge-artifacts.md"

result=$(write_guard "src/payments/processor.py")
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision') == 'deny', f'Expected deny but got: {d}'
reason = out.get('permissionDecisionReason', '')
assert 'challenge' in reason.lower(), f'Expected challenge mentioned, got: {reason}'
assert 'challenge-artifacts.md' in reason, f'Expected artifact filename, got: {reason}'
assert 'contrarian' in reason.lower(), f'Expected contrarian mentioned, got: {reason}'
assert 'WG_CHALLENGE_GATE' in reason, f'Expected bypass hint in reason, got: {reason}'
print('PASS: missing artifact blocked with specific reason')
print('reason:', reason)
"
```

**Expected**: `PASS: missing artifact blocked with specific reason`

The reason must contain all of: `challenge-artifacts.md`, `contrarian`,
and `WG_CHALLENGE_GATE`. A generic "gate failed" is not acceptable.

### Step 3: Invalid artifact (convergence collapse) → Write BLOCKED

Install an artifact that satisfies every syntactic check (all four
required sections, three challenges, steelmans ≥40 chars, >300 bytes)
but has all three challenges resolved under a single theme. The
convergence-collapse detector must fire and the gate must deny.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, textwrap, pathlib
project_dir = pathlib.Path(os.environ['PROJECT_DIR'])
body = textwrap.dedent("""\
    # Challenge Artifacts

    ## Strongest Opposing View

    A meaningful narrative summarising the opposing case in full,
    long enough to pass the minimum byte size and give reviewers a
    concrete thing to push back on during the build phase.

    ## Challenges

    ### Challenge CH-01: trust-boundary
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: Opposition argues the trust boundary must remain where
      it is today, full stop, for auditor clarity and signed chain.

    ### Challenge CH-02: secret-rotation-cost
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: Opposition argues the secret rotation cost is materially
      under-estimated by the current design and should block build.

    ### Challenge CH-03: key-material-colocation
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: Opposition argues that co-locating the key material
      with the service violates the compliance boundary we agreed to.

    ## Convergence Check

    All three in one theme — self-reported. Needs broadening.

    ## Resolution

    All three closed pending broader dissent dimensions.
    """)
(project_dir / "phases" / "design" / "challenge-artifacts.md").write_text(body, encoding="utf-8")
print("collapsed-theme challenge artifact written")
PYEOF

result=$(write_guard "src/payments/processor.py")
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
out = d.get('hookSpecificOutput', {})
assert out.get('permissionDecision') == 'deny', f'Expected deny but got: {d}'
reason = out.get('permissionDecisionReason', '')
assert 'collapse' in reason.lower(), f'Expected collapse mentioned, got: {reason}'
assert 'security' in reason.lower(), f'Expected collapsed theme name, got: {reason}'
print('PASS: convergence-collapse blocked with theme name referenced')
print('reason:', reason)
"
```

**Expected**: `PASS: convergence-collapse blocked with theme name referenced`

### Step 4: Re-validate after cleanup → Write ALLOWED again

Replace the collapsed artifact with the well-formed one from Step 1
(three distinct themes). The same Write that was just denied must now
be allowed — no hook-server restart, no cache bust, no state outside
the filesystem.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, textwrap, pathlib
project_dir = pathlib.Path(os.environ['PROJECT_DIR'])
body = textwrap.dedent("""\
    # Challenge Artifacts

    ## Strongest Opposing View

    The proposed payment processor trades operational simplicity for a
    novel coordination primitive. The best version of the opposite
    position is that the existing queue-based integration has delivered
    three years of reliable throughput and its failure modes are fully
    understood by on-call.

    ## Challenges

    ### Challenge CH-01: novel-coordination-primitive
    - theme: correctness
    - raised_by: contrarian
    - status: resolved
    - steelman: Current queue semantics are well-understood and have
      stood up to production load for three years. Replacing them
      introduces unknown-unknowns that a rewrite does not.

    ### Challenge CH-02: observability-regression
    - theme: operability
    - raised_by: contrarian
    - status: resolved
    - steelman: Today on-call can grep a single log stream. The new
      design fragments traces across four services and that
      fragmentation is a measurable, persistent cost.

    ### Challenge CH-03: rollout-blast-radius
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: The migration window forces all tenants onto the new
      schema simultaneously. A bug there has a global blast radius
      versus the current per-tenant isolation.

    ## Convergence Check

    3 challenges across 3 themes. No collapse.

    ## Resolution

    CH-01, CH-02, CH-03 all closed with documented steelmans.
    """)
(project_dir / "phases" / "design" / "challenge-artifacts.md").write_text(body, encoding="utf-8")
print("artifact re-validated with 3 distinct themes")
PYEOF

result=$(write_guard "src/payments/processor.py")
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
decision = d.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')
assert decision != 'deny', f'Expected allow after re-validation but got deny: {d}'
print('PASS: gate re-cleared once artifact fixed — Write allowed')
"
```

**Expected**: `PASS: gate re-cleared once artifact fixed — Write allowed`

This proves the gate re-reads the artifact on every Write — there is
no sticky bad-state. Fix the file, the gate clears.

### Step 5: Scoped bypass via WG_CHALLENGE_GATE=off → Write ALLOWED

Restore the broken artifact from Step 3 and confirm the gate would
block again without the bypass. Then set `WG_CHALLENGE_GATE=off` and
verify the same Write is allowed — proving the documented rollback
escape hatch works exactly as advertised.

```bash
# Restore the collapsed-theme artifact that failed in Step 3
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import os, textwrap, pathlib
project_dir = pathlib.Path(os.environ['PROJECT_DIR'])
body = textwrap.dedent("""\
    # Challenge Artifacts

    ## Strongest Opposing View

    A meaningful narrative summarising the opposing case in full,
    long enough to pass the minimum byte size and give reviewers a
    concrete thing to push back on during the build phase.

    ## Challenges

    ### Challenge CH-01: trust-boundary
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: Opposition argues the trust boundary must remain where
      it is today, full stop, for auditor clarity and signed chain.

    ### Challenge CH-02: secret-rotation-cost
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: Opposition argues the secret rotation cost is materially
      under-estimated by the current design and should block build.

    ### Challenge CH-03: key-material-colocation
    - theme: security
    - raised_by: contrarian
    - status: resolved
    - steelman: Opposition argues that co-locating the key material
      with the service violates the compliance boundary we agreed to.

    ## Convergence Check

    All three in one theme — self-reported.

    ## Resolution

    All three closed pending broader dissent dimensions.
    """)
(project_dir / "phases" / "design" / "challenge-artifacts.md").write_text(body, encoding="utf-8")
print("collapsed artifact restored for bypass test")
PYEOF

# Confirm it blocks without the bypass (baseline — the bypass MUST actually change behavior)
unset WG_CHALLENGE_GATE
result=$(write_guard "src/payments/processor.py")
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
decision = d.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')
assert decision == 'deny', f'Baseline failed — expected deny without bypass, got: {d}'
print('baseline: deny (as expected — bypass not set)')
"

# Set the scoped bypass and re-run — must now allow
export WG_CHALLENGE_GATE=off
result=$(write_guard "src/payments/processor.py")
echo "${result}"
echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
d = json.loads(sys.stdin.read())
decision = d.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')
assert decision != 'deny', f'Expected allow with bypass but got deny: {d}'
print('PASS: WG_CHALLENGE_GATE=off bypasses the gate — Write allowed')
"

# Leave the environment clean for subsequent steps / re-runs
unset WG_CHALLENGE_GATE
```

**Expected**:
```
baseline: deny (as expected — bypass not set)
PASS: WG_CHALLENGE_GATE=off bypasses the gate — Write allowed
```

Confirming both sides of the bypass proves it genuinely changes
behavior rather than masking an already-passing gate. `WG_CHALLENGE_GATE`
only accepts the literal string `off` (case-insensitive, whitespace
tolerant) — any other value, including `true`/`1`, leaves the gate
enforced. That's intentional: it is a rollback switch, not a config
knob.

## Expected Outcome

Every failure path produces a specific, actionable deny-reason — the
filename, the contrarian agent name, and the bypass hint. Every happy
path allows the Write. The bypass environment variable works exactly
as documented and only in the scoped form.

## Success Criteria

- [ ] Step 1: well-formed 3-theme artifact → Write allowed
- [ ] Step 2: missing artifact → deny with `challenge-artifacts.md`,
      `contrarian`, and `WG_CHALLENGE_GATE` all cited in the reason
- [ ] Step 3: convergence-collapsed artifact → deny with `collapse`
      and the collapsed theme name cited in the reason
- [ ] Step 4: replacing the collapsed artifact with a well-formed one
      allows the same Write with no other state change
- [ ] Step 5: baseline denies; `WG_CHALLENGE_GATE=off` allows the same
      Write; `unset WG_CHALLENGE_GATE` returns to deny-by-default

## Value Demonstrated

The challenge gate is a design-integrity check: build cannot start
until the opposing case has been articulated in writing. Unit tests
cover parser and validator behavior in isolation, but the real hook
path involves four moving parts — active-project discovery, phase
read, complexity threshold, and artifact lookup — any one of which
could silently fail open.

This scenario exercises all four together against a fixture project
and confirms:

* The hook finds the right project via workspace scoping.
* The complexity gate fires only when the artifact is actually
  required (build phase, complexity ≥ 4).
* Invalid artifacts produce a deny-reason a human can act on without
  reading the hook source.
* Fixing the artifact clears the gate without restart or cache bust.
* The escape hatch is real and narrow — only `WG_CHALLENGE_GATE=off`
  disables enforcement.

Without this end-to-end coverage, a refactor of `_find_active_crew_project`
or `_check_challenge_gate` could silently skip the entire gate and
every unit test would still pass.

## Cleanup

```bash
rm -f "${PROJECT_JSON}"
rm -rf "${PROJECT_DIR}"
unset CLAUDE_PROJECT_NAME
unset WG_CHALLENGE_GATE
unset TEST_PROJECT
unset PROJECT_DIR
unset PROJECT_JSON
unset PROJECTS_ROOT
unset PLUGIN_ROOT
```
