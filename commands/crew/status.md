---
description: Show current project status, phase, and next steps
---

# /wicked-garden:crew:status

Display the current project state and available integrations.

> **Scope**: `crew:status` is a **read-only state view** — no phase changes, no writes.
> To **enter the post-delivery operate phase**, use `/wicked-garden:crew:operate`.
> If the output is hard to parse, pipe it through `/wicked-garden:crew:explain`.

## Instructions

### 1. Find Active Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

If no active project found (`"project": null`), inform user and suggest `/wicked-garden:crew:start`.

### 2. Read Project State

Use the project name from the find-active result:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} status --json
```

This returns: name, current_phase, phase_plan, phase statuses, signals, complexity, and review_tier.

### 3. Detect Available Plugins

Check which plugins are installed:

```bash
# Check for wicked-brain (required companion plugin)
if curl -s --connect-timeout 1 -X POST http://localhost:4242/api -H "Content-Type: application/json" -d '{"action":"health"}' 2>/dev/null | grep -q '"ok"'; then
    echo "wicked-brain: available"
  else
    echo "wicked-brain: not running"
  fi
done
```

### 4. Determine Integration Level

Based on available plugins:
- **Level 4**: All specialized plugins available
- **Level 3**: Some specialized plugins (jam/scout/lens)
- **Level 2**: Only wicked-brain (no specialized plugins)
- **Level 1**: Standalone (no optional plugins)

### 5. Display Status

```markdown
## wicked-garden:crew Project Status

**Project**: {name}
**Phase**: {current_phase}
**Status**: {status}
**Complexity**: {complexity}/7 (review tier: {review_tier})
```

Only render `### Phase Progress` when the project has real phase progress to show. Suppress this section (skip the header and table entirely) when **all** of the following are true:
- `phase_plan` from the JSON output is null or empty (no committed plan yet), AND
- every value in the `phases` dict is `"pending"` (no phase has been started)

This fires for projects where the topology fallback populated the dict with all-pending entries — showing 9 rows of "pending" is noise, not signal.

When the section is shown, render one row per phase from the actual `phases` dict (do not hardcode clarify/design/qe/build/review):

```markdown
### Phase Progress

| Phase | Status |
|-------|--------|
| {phase} | {status} |
```

Only render `### Available Integrations` when the integration check in Step 3 returns at least one integration result. Always render it when plugin detection produced results (even if all are "not running") — the integration level itself is the signal. Skip the header only if the plugin detection step produced no output at all (e.g., command unavailable).

```markdown
### Available Integrations (Level {n})

| Plugin | Status | Used In |
|--------|--------|---------|
| jam | built-in | clarify |
| search | built-in | design |
| product | built-in | test-strategy, review |
| mem | built-in | all phases |
| wicked-brain | {running/not running} | context assembly |
```

Always render `### Next Steps` — this section IS the empty-state signal when no phases or actions are active:

```markdown
### Next Steps

{Based on current phase and status}
```

### 6. Show Operate Phase Data (if applicable)

If the current phase is "operate" or if operate data exists in the project state, show a summary:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_PLUGIN_ROOT}/scripts')))
from _domain_store import DomainStore
ds = DomainStore('wicked-crew')
incidents = [i for i in ds.list('incidents') if i.get('project_id') == '{project_name}']
feedback = [f for f in ds.list('feedback') if f.get('project_id') == '{project_name}']
print(json.dumps({'incidents': len(incidents), 'feedback': len(feedback)}, indent=2))
"
```

If incidents or feedback exist, display:

```markdown
### Operate Phase Data

| Metric | Count |
|--------|-------|
| Incidents | {incident_count} |
| Feedback | {feedback_count} |
| Checklist items | {completed}/{total} |

Use `/wicked-garden:crew:operate --status` for full operational details.
```

### 6b. Show Cross-Session Quality Telemetry Trend (Issue #443)

Run drift classification against the project's timeline. If the project has
fewer than 5 sessions, skip this block quietly.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/drift.py" classify {project_name}
```

When the output's `classification.zone` is `"insufficient"`, skip the block
entirely (not enough history yet).

Otherwise display:

```markdown
### Quality Trend (cross-session)

- **Metric**: gate_pass_rate
- **Latest**: {classification.latest}
- **Baseline mean** (last 4 sessions): {classification.baseline.mean} ± {classification.baseline.stddev}
- **Drop vs baseline**: {classification.drop_pct * 100:.1f}%
- **EWMA slope**: {classification.ewma_slope}
- **Classification**: {classification.zone} — {"SIGNAL (special-cause)" if zone == "special-cause" else "watch" if zone == "warn" else "noise (common-cause)"}
- **Sessions observed**: {classification.session_count}

{If classification.drift is true: show "Drift detected — see `wicked.quality.drift_detected` event on wicked-bus" and list `classification.reasons`}
{If actionable: recommend crew retro or gate-review; otherwise explicitly label as common-cause noise and state "no new gate will be added for common-cause variation"}
```

Rationale: per Issue #443 acceptance, common-cause variation must not trigger
new process gates. Special-cause classification (outside 3σ) or a >=15% drop
are the only signals worth escalating.

### 6c. Show Convergence Lifecycle (Issue #445)

Additive section — surfaces per-artifact convergence state. The script is
fail-open: it returns an empty status dict when no convergence log exists,
so this section stays silent for projects that have not started tracking.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/convergence.py" status \
  --project "$PROJECT" 2>/dev/null || true

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/convergence.py" stall \
  --project "$PROJECT" 2>/dev/null || true
```

If the status response has `total > 0`, render an additive section AFTER the
existing Phase Progress table (do not restructure the existing output):

```markdown
### Convergence Lifecycle

| Artifact | State | Sessions in state | Over budget? | Last phase |
|----------|-------|-------------------|--------------|------------|
| {id} | {state} | {n} | {yes/no} | {phase} |

**Stalls** ({count}):
- {artifact}: stuck in {state} for {n} sessions

See `/wicked-garden:crew:convergence` for the raw lifecycle view and
`convergence verify-gate` for the review-phase gate verdict.
```

If the convergence log does not exist (empty output or `total == 0`), skip
this section entirely — no noise on projects that do not use convergence
tracking yet.

### 7. Suggest Actions

Based on current state:
- If phase awaiting approval: suggest `/wicked-garden:crew:approve {phase}`
- If phase in progress: suggest `/wicked-garden:crew:execute`
- If operate phase active: suggest `/wicked-garden:crew:incident`, `/wicked-garden:crew:feedback`, or `/wicked-garden:crew:retro`
- If convergence stalls surfaced: suggest `/wicked-garden:crew:convergence stall` for the full view
- If project complete: show completion summary

### When context is thin

If the status output doesn't give you enough to decide the next step — no active project, ambiguous phase state, or missing signals — invoke `wicked-garden:ground` to pull richer brain + bus context for the current work.
