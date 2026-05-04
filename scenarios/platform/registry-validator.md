---
name: registry-validator
description: Verify the startup-time allowlist validator surfaces drift between in-code allowlists (phases, reviewers, bus handlers, skill refs) and the assets they reference, fails open at SessionStart, and exits non-zero in CI on missing references
category: infra
tags: [bootstrap, validation, allowlist, registry, fail-open]
tools:
  required: [bash]
difficulty: intermediate
timeout: 60
execution: manual
---

# Registry Allowlist Validator

The plugin hardcodes a number of allowlists — phase fallback agents, gate-policy
reviewer subagent_types, projector handlers in `daemon/projector.py::_HANDLERS`,
and skill references inside agent frontmatter. When one of those references
goes stale (renamed agent, deleted skill, deferred handler), bootstrap and unit
probes still pass — the failure only surfaces when traffic hits the missing
asset. Theme 8 closes that invisible gap with a startup-time validator.

This scenario covers two surfaces:

- **CLI**: `scripts/_validate_registry.py` walks every allowlist and exits
  non-zero when any `missing` / `malformed` / `invalid_id` finding is present.
- **Bootstrap**: `hooks/scripts/bootstrap.py` calls the same validator inside
  the SessionStart flow and surfaces blocking findings as a `[Registry]`
  briefing line. The validator is FAIL-OPEN — any exception or unavailable
  source-of-truth must NOT block session start.

## Setup

No setup required. The validator is stdlib-only and reads the source-of-truth
files already in the repository:
`.claude-plugin/phases.json`, `.claude-plugin/gate-policy.json`,
`scripts/_bus.py::BUS_EVENT_MAP`, `daemon/projector.py::_HANDLERS`, and the
agent frontmatter under `agents/`.

## Steps

### Step 1: Run the CLI validator on the clean working tree

From the plugin root, run:

```
python scripts/_validate_registry.py
```

**Expect**:

- The command completes in well under a second (no subprocess, no network).
- The summary line lists each check that ran:
  `phases, gate_policy, bus_handlers, skill_refs`.
- The output ends with `OK` and the exit status is `0`.
- Any `external` findings (drop-in plugin reviewers like
  `wicked-testing:risk-assessor`) are listed but do NOT cause failure.

### Step 2: Confirm machine-readable output

Run:

```
python scripts/_validate_registry.py --json
```

**Expect**:

- Output is valid JSON parseable by `python -c "import json,sys; json.load(sys.stdin)"`.
- The top-level object has keys `ok`, `checks_run`, `findings`, `summary`.
- `ok` is `true` on a clean tree; `false` when blocking findings exist.

### Step 3: Inject a broken phase fallback and verify the validator fails

Pick a phase in `.claude-plugin/phases.json` with a real `fallback_agent`
(for example, `clarify` → `facilitator`) and temporarily edit the JSON so
that the fallback names a non-existent agent (e.g. `nonexistent-agent`).

Re-run:

```
python scripts/_validate_registry.py
```

**Expect**:

- The summary shows `missing >= 1`.
- A line of the form
  `[missing] phases.fallback_agent: clarify → nonexistent-agent — ...`
  appears in the output.
- The exit status is `1` (non-zero).

Revert the phases.json edit before continuing.

### Step 4: Inject a broken gate-policy reviewer and verify the validator fails

In `.claude-plugin/gate-policy.json`, change one tier's `reviewers` list to
include `phantom-reviewer`. Re-run the CLI.

**Expect**:

- A line of the form
  `[missing] gate-policy.reviewer: <gate>.<tier> → phantom-reviewer — ...`
  appears.
- Exit status `1`.

Revert the gate-policy.json edit.

### Step 5: Verify bootstrap surfaces blocking findings as a session warning

With a synthetic broken-state tree (or a temporarily edited gate-policy), run
the bootstrap helper directly:

```
python -c "
import os, sys
os.environ.setdefault('CLAUDE_PLUGIN_ROOT', os.getcwd())
sys.path.insert(0, 'scripts')
sys.path.insert(0, 'hooks/scripts')
import bootstrap
print(bootstrap._run_registry_validation())
"
```

**Expect**:

- On a clean tree: prints `None` (no [Registry] line in the briefing).
- On a tree with blocking findings: prints a multi-line `[Registry] ...`
  briefing block listing each blocking finding by category, check, and
  target.

### Step 6: Verify fail-open behaviour by simulating a validator error

Temporarily rename `scripts/_validate_registry.py` to
`scripts/_validate_registry.py.disabled`, then re-run the bootstrap helper
from Step 5.

**Expect**:

- A stderr line beginning with `[wicked-garden] registry validation skipped:`
  is printed.
- The helper still returns `None` (does not raise).
- A real bootstrap session would continue normally — no blocking on the
  validator's absence.

Restore the filename before continuing.

## Expected Outcomes

1. The CLI validator runs cleanly on the current tree and exits `0`.
2. Synthetic missing references (broken `fallback_agent`, broken reviewer)
   produce blocking findings categorised as `missing` with exit code `1`.
3. The bootstrap surface is silent on a clean tree and warns on broken
   trees — never blocks SessionStart.
4. The validator is fail-open: removing the validator script entirely
   surfaces a stderr note but does not break bootstrap.

## Cleanup

Revert any temporary edits to `.claude-plugin/phases.json` and
`.claude-plugin/gate-policy.json`. Restore the validator filename if
renamed for Step 6.
