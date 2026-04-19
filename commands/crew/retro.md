---
description: Generate a retrospective from operate phase data
argument-hint: "[--project project-name]"
---

# /wicked-garden:crew:retro

Aggregate incidents, feedback, and operational metrics into a structured retrospective. Stores the summary in wicked-garden:mem for future crew projects.

## Arguments

- `--project` (optional): Project name. Default: active project

## Instructions

### 1. Find Active Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

If `--project` is provided, use that instead. If neither is available, inform user.

### 2. Read Project State

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} status --json
```

### 3. Gather Operate Data

Collect all operate-phase artifacts:

**Incidents**:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_PLUGIN_ROOT}/scripts')))
from _domain_store import DomainStore
ds = DomainStore('wicked-crew')
incidents = [i for i in ds.list('incidents') if i.get('project_id') == '{project_name}']
print(json.dumps(incidents, indent=2))
"
```

**Feedback**:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_PLUGIN_ROOT}/scripts')))
from _domain_store import DomainStore
ds = DomainStore('wicked-crew')
feedback = [f for f in ds.list('feedback') if f.get('project_id') == '{project_name}']
print(json.dumps(feedback, indent=2))
"
```

**Traceability coverage**:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/traceability.py coverage --project "{project_name}"
```

### 4. Delegate Retro Generation

Delegate to the delivery manager agent for structured retrospective generation:

```
Task(
  subagent_type="wicked-garden:delivery:delivery-manager",
  prompt="Generate a structured retrospective for crew project '{project-name}'.

## Operate Phase Data

### Incidents ({incident_count} total)
{incidents_summary}

### Feedback ({feedback_count} total, {positive_count} positive, {negative_count} negative)
{feedback_summary}

### Traceability Coverage
{coverage_report}

### Project Context
- Description: {description}
- Complexity: {complexity_score}/7
- Signals: {signals}
- Phase plan: {phase_plan}

## Generate

Produce a structured retrospective with these sections:

1. **What Broke** — incidents, root causes, patterns
2. **What Users Said** — feedback themes, sentiment trends
3. **Monitoring Gaps** — what we missed, what to add
4. **Follow-up Items** — concrete action items for future iterations
5. **Crew Process Observations** — did the phase plan match reality? Were specialists effective?

Be specific and actionable. Reference incident IDs and feedback IDs."
)
```

If the delivery manager agent is not available, generate the retrospective inline using the gathered data.

### 5. Store Retro in Memory

Store the retrospective summary in wicked-garden:mem for future crew projects:

```
/wicked-garden:mem:store "{retro_summary}" --type learning --tags "crew,retro,{project-name},operate" --importance 7
```

This ensures future projects in the same area benefit from operational learnings.

### 6. Store Retro as Deliverable

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"retro_summary": {retro_json}, "retro_generated_at": "{iso_timestamp}"}' \
  --json
```

### 6b. Auto-Populate Action Items (additive side-effect, issue #461)

After the retro markdown artifact is written, scan it and seed each
action item into `delivery.process_memory` so they receive stable `AI-NNN`
identifiers and surface at future session starts via the facilitator
context. This is a side-effect only — the retro markdown itself is not
modified. Fails open if `process_memory` is unavailable.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/retro_action_items.py" \
  --project "{project-name}" \
  --retro-md "{retro_md_path}" \
  --session-id "${CLAUDE_SESSION_ID:-}" \
  --json
```

### 7. Display Retrospective

```markdown
## Retrospective: {project-name}

### What Broke
{incidents analysis — patterns, root causes, severity distribution}

### What Users Said
{feedback themes — positive highlights, negative pain points, requests}

### Monitoring Gaps
{what was not monitored, what alerts were missing, observability holes}

### Follow-up Items
| Priority | Item | Owner | Source |
|----------|------|-------|--------|
{action items table}

### Crew Process Observations
{phase plan effectiveness, specialist routing accuracy, gate quality}

---

### Data Summary
- **Incidents**: {count} ({critical} critical, {high} high, {medium} medium, {low} low)
- **Feedback**: {count} ({positive} positive, {neutral} neutral, {negative} negative)
- **Coverage**: {coverage_pct}% requirements traced to endpoints

**Retro stored in wicked-garden:mem** for future project context.

To complete the operate phase: `/wicked-garden:crew:approve operate`
```

## Examples

```bash
# Generate retro for active project
/wicked-garden:crew:retro

# Generate retro for specific project
/wicked-garden:crew:retro --project my-feature-project
```
