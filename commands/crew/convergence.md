---
description: Show artifact convergence lifecycle — states, stalls, and gate verdict
argument-hint: "[status|record|stall|verify-gate] [--project P] [--artifact A]"
---

# /wicked-garden:crew:convergence

Expose the raw convergence lifecycle view for artifacts in a crew project.

Convergence tracks whether code artifacts have actually made it into the
production path: `Designed -> Built -> Wired -> Tested -> Integrated -> Verified`.
A task marked `completed` is not the same as an artifact being wired in.

## Arguments

- `status` (default) — show state + sessions-in-state + aging budget per artifact
- `record` — append a transition (used by agents, not usually by humans)
- `stall` — list artifacts stuck in a pre-Integrated state
- `verify-gate` — evaluate the `convergence-verify` review gate and print verdict
- `--project <name>` — project id (defaults to active project)
- `--artifact <id>` — restrict to a single artifact
- `--threshold <n>` — stall threshold in sessions (default: 3)
- `--session-id <id>` — override `CLAUDE_SESSION_ID`

## Instructions

### 1. Determine Active Project

If `--project` is not supplied, use the active project:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

Fail gracefully if there is no active project and instruct the user to pass
`--project` or start one with `/wicked-garden:crew:start`.

### 2. Dispatch to Convergence CLI

Invoke the backing script with the parsed subcommand:

```bash
# Status (default)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/convergence.py" status \
  --project "$PROJECT" ${ARTIFACT:+--artifact "$ARTIFACT"}

# Record a transition
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/convergence.py" record \
  --project "$PROJECT" --artifact "$ARTIFACT" --to "$TO_STATE" \
  --verifier "$VERIFIER" --phase "$PHASE" \
  --ref "$REF" --desc "$DESC"

# Stall report
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/convergence.py" stall \
  --project "$PROJECT" --threshold "${THRESHOLD:-3}"

# Review-phase gate
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/convergence.py" verify-gate \
  --project "$PROJECT"
```

All output is JSON.

### 3. Render Human-Readable Summary

Parse the JSON and present it to the user as a table:

```markdown
## Convergence Status — {project}

| Artifact | State | Sessions in state | Budget | Over budget? | Last phase |
|----------|-------|-------------------|--------|--------------|------------|
| ... | ... | ... | ... | ... | ... |

### Stalls (>= {threshold} sessions)
- {artifact}: stuck in {state} for {n} sessions

### Gate: convergence-verify
- Verdict: {APPROVE|CONDITIONAL|REJECT}
- Findings: {count}
- Legacy bypass active: {true|false}
```

If the convergence log is empty, tell the user convergence tracking has not
been started for this project and how to record the first transition.

## Examples

```bash
# Default: status view for active project
/wicked-garden:crew:convergence

# Stall report with custom threshold
/wicked-garden:crew:convergence stall --threshold 5

# Gate verdict (what the review phase will see)
/wicked-garden:crew:convergence verify-gate --project my-project

# One specific artifact's full history
/wicked-garden:crew:convergence status --artifact src/foo.py
```

## Notes

- The convergence log lives at
  `<project>/phases/<phase>/convergence-log.jsonl` — one JSONL record per
  transition, append-only.
- Gate verdict is informational here; enforcement happens inside
  `phase_manager.approve_phase` during review approval.
- Fails open when the log is missing (graceful degradation).
- `CREW_GATE_ENFORCEMENT=legacy` forces APPROVE verdict.
