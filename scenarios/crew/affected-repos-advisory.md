---
name: affected-repos-advisory
title: Affected Repos — Advisory Field Round-Trips Through Plan, Status, and Briefing
description: Issue #722 — the optional `affected_repos` list on process-plan.json validates, parses, and surfaces as a single advisory line in crew:status and smaht:briefing helpers; legacy plans without the field stay silent
type: testing
difficulty: intermediate
estimated_minutes: 5
---

# Affected Repos — Advisory Field End-to-End

This scenario asserts the four-beat round-trip of the `affected_repos`
advisory field added by the Issue #722 reframe (multi-repo as advisory
only, no DAG, no worktree provisioning, no cross-repo evidence
aggregation — those are deferred to the `wicked-garden-monorepo`
sibling plugin per `docs/v9/sibling-plugin-monorepo.md`).

The four beats:

1. The validator accepts a well-shaped `affected_repos` list and
   rejects malformed shapes.
2. The renderer prints the advisory line for the `crew:status` Step 4b
   surface.
3. The same renderer feeds the `smaht:briefing` "Affected repos:" line.
4. A legacy plan without the field stays silent — backward-compat is
   load-bearing for the millions of single-repo projects.

## Setup

```bash
export TEST_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import tempfile
print(tempfile.mkdtemp(prefix='wg-affected-repos-'))
")
echo "TEST_DIR=${TEST_DIR}"
```

## Step 1: Provision a process-plan.json with `affected_repos: [foo, bar]`

The plan mirrors the minimal valid shape `validate_plan.py` requires
(top-level keys, factors block, one specialist, one phase, one task)
plus the new optional `affected_repos` field.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, pathlib, sys
test_dir = pathlib.Path(os.environ['TEST_DIR'])

# Build the fixture using the same REQUIRED_FACTOR_KEYS the validator
# enforces, so the scenario stays in lockstep with the schema.
sys.path.insert(0, str(pathlib.Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')) / 'scripts' / 'crew'))
import validate_plan as vp

plan = {
    "project_slug": "affected-repos-scenario",
    "summary": "Issue #722 advisory round-trip fixture.",
    "rigor_tier": "standard",
    "complexity": 3,
    "factors": {
        key: {"reading": "LOW", "risk_level": "high_risk", "why": "fixture"}
        for key in vp.REQUIRED_FACTOR_KEYS
    },
    "specialists": [{"name": "backend-engineer", "why": "writes the code"}],
    "phases": [
        {"name": "build", "why": "do the work", "primary": ["backend-engineer"]}
    ],
    "tasks": [
        {
            "id": "t1",
            "title": "Implement",
            "phase": "build",
            "blockedBy": [],
            "metadata": {
                "chain_id": "affected-repos-scenario.root",
                "event_type": "coding-task",
                "source_agent": "facilitator",
                "phase": "build",
                "rigor_tier": "standard",
            },
        }
    ],
    "affected_repos": ["foo", "bar"],
}

(test_dir / "process-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

# Confirm the validator round-trips the field (no violations).
violations = vp.validate(plan)
assert violations == [], f"Expected zero violations, got: {violations}"
print("PASS: process-plan.json written and validates clean")
PYEOF
```

**Expected**: `PASS: process-plan.json written and validates clean`

## Step 2: crew:status helper renders the advisory line

The `crew:status` command (Step 4b) calls
`scripts/crew/affected_repos.py render --project-dir ...`. Exercise the
exact CLI shape the command uses.

```bash
result=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/affected_repos.py" \
  render --project-dir "${TEST_DIR}")
echo "${result}"

echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
out = sys.stdin.read().strip()
assert out.startswith('Affected repos: foo, bar'), f'unexpected prefix: {out!r}'
assert 'advisory' in out, f'missing advisory tag: {out!r}'
assert 'docs/v9/sibling-plugin-monorepo.md' in out, f'missing doc pointer: {out!r}'
print('PASS: crew:status helper renders the advisory line correctly')
"
```

**Expected**:
```
Affected repos: foo, bar (advisory — see docs/v9/sibling-plugin-monorepo.md)
PASS: crew:status helper renders the advisory line correctly
```

## Step 3: smaht:briefing helper renders the same advisory line

The briefing surface uses the identical CLI invocation (`render
--project-dir ...`) — verify the contract holds when the same plan is
read by what the briefing calls.

```bash
result=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/affected_repos.py" \
  render --project-dir "${TEST_DIR}")

echo "${result}" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
out = sys.stdin.read().strip()
assert out == 'Affected repos: foo, bar (advisory — see docs/v9/sibling-plugin-monorepo.md)', \
    f'briefing surface drifted from status surface: {out!r}'
print('PASS: smaht:briefing helper renders the same line as crew:status')
"
```

**Expected**: `PASS: smaht:briefing helper renders the same line as crew:status`

## Step 4: Backward compatibility — legacy plan without `affected_repos` stays silent

This is the load-bearing assertion: every existing wicked-garden
project must continue to render as it did before #722. The renderer
must print **nothing** when the field is absent.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, pathlib, sys
test_dir = pathlib.Path(os.environ['TEST_DIR'])
sys.path.insert(0, str(pathlib.Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')) / 'scripts' / 'crew'))
import validate_plan as vp

# Same plan as Step 1 minus affected_repos — represents every legacy
# project on disk.
plan = {
    "project_slug": "legacy-single-repo",
    "summary": "Legacy plan without affected_repos.",
    "rigor_tier": "standard",
    "complexity": 3,
    "factors": {
        key: {"reading": "LOW", "risk_level": "high_risk", "why": "fixture"}
        for key in vp.REQUIRED_FACTOR_KEYS
    },
    "specialists": [{"name": "backend-engineer", "why": "writes the code"}],
    "phases": [
        {"name": "build", "why": "do the work", "primary": ["backend-engineer"]}
    ],
    "tasks": [
        {
            "id": "t1",
            "title": "Implement",
            "phase": "build",
            "blockedBy": [],
            "metadata": {
                "chain_id": "legacy-single-repo.root",
                "event_type": "coding-task",
                "source_agent": "facilitator",
                "phase": "build",
                "rigor_tier": "standard",
            },
        }
    ],
}

assert "affected_repos" not in plan, "fixture invariant: legacy plan must not declare the field"
assert vp.validate(plan) == [], "legacy plan must validate cleanly"

(test_dir / "process-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
print("legacy plan written")
PYEOF

# Renderer MUST stay silent — empty stdout means crew:status / briefing
# skip the section entirely (preserves the pre-#722 output verbatim).
result=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/affected_repos.py" \
  render --project-dir "${TEST_DIR}")

if [ -z "${result}" ]; then
  echo "PASS: renderer stayed silent on legacy plan (backward-compat preserved)"
else
  echo "FAIL: renderer emitted output for legacy plan: ${result}"
  exit 1
fi
```

**Expected**:
```
legacy plan written
PASS: renderer stayed silent on legacy plan (backward-compat preserved)
```

## Step 5: Renderer rejects malformed shape silently (fail-open)

The renderer is fail-open by design — `crew:status` and `smaht:briefing`
must NEVER break because the plan got mangled. The validator is the
component that surfaces shape errors.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" <<'PYEOF'
import json, os, pathlib
test_dir = pathlib.Path(os.environ['TEST_DIR'])
# Smuggle an invalid shape (string instead of list). The validator
# would reject this; the renderer must silently render nothing.
(test_dir / "process-plan.json").write_text(
    json.dumps({"affected_repos": "this-is-not-a-list"}),
    encoding="utf-8",
)
print("malformed plan written")
PYEOF

result=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/affected_repos.py" \
  render --project-dir "${TEST_DIR}")

if [ -z "${result}" ]; then
  echo "PASS: renderer fail-open on malformed shape"
else
  echo "FAIL: renderer emitted output for malformed plan: ${result}"
  exit 1
fi
```

**Expected**:
```
malformed plan written
PASS: renderer fail-open on malformed shape
```

## Success Criteria

- [ ] Step 1: process-plan.json with `affected_repos: [foo, bar]` validates clean
- [ ] Step 2: `crew:status` helper renders the exact advisory line with the doc pointer
- [ ] Step 3: `smaht:briefing` helper renders the same line as `crew:status` (single contract)
- [ ] Step 4: legacy plan without `affected_repos` produces empty output (backward compat)
- [ ] Step 5: renderer fails open on malformed shape (no exception, no broken briefing)

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, shutil
shutil.rmtree(os.environ['TEST_DIR'], ignore_errors=True)
"
unset TEST_DIR
```
