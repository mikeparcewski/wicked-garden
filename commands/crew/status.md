---
description: Show current project status, phase, and next steps
---

# /wicked-garden:crew:status

Display the current project state and available integrations.

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

This returns: name, current_phase, phase_plan, phase statuses, signals, complexity, review_tier, and kanban fields.

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
- **Level 2**: Only wicked-mem
- **Level 1**: Standalone (no optional plugins)

### 5. Display Status

```markdown
## wicked-garden:crew Project Status

**Project**: {name}
**Phase**: {current_phase}
**Status**: {status}
**Complexity**: {complexity}/7 (review tier: {review_tier})

### Phase Progress

| Phase | Status | Notes |
|-------|--------|-------|
| clarify | {status} | {notes} |
| design | {status} | {notes} |
| qe | {status} | {notes} |
| build | {status} | {notes} |
| review | {status} | {notes} |

### Available Integrations (Level {n})

| Plugin | Status | Used In |
|--------|--------|---------|
| jam | built-in | clarify |
| search | built-in | design |
| product | built-in | qe, review |
| mem | built-in | all phases |
| kanban | built-in | build |
| wicked-brain | {running/not running} | context assembly |

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

### 7. Suggest Actions

Based on current state:
- If phase awaiting approval: suggest `/wicked-garden:crew:approve {phase}`
- If phase in progress: suggest `/wicked-garden:crew:execute`
- If operate phase active: suggest `/wicked-garden:crew:incident`, `/wicked-garden:crew:feedback`, or `/wicked-garden:crew:retro`
- If project complete: show completion summary
