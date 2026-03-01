---
description: Show current project status, phase, and next steps
---

# /wicked-garden:crew:status

Display the current project state and available integrations.

## Instructions

### 1. Find Active Project

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/crew.py" find-active --json
```

If no active project found (`"project": null`), inform user and suggest `/wicked-garden:crew:start`.

### 2. Read Project State

Use the project name from the find-active result:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} status --json
```

This returns: name, current_phase, phase_plan, phase statuses, signals, complexity, and kanban fields.

### 3. Detect Available Plugins

Check which plugins are installed:

```bash
# Check for each plugin
for plugin in wicked-jam wicked-search wicked-product wicked-mem wicked-kanban; do
  if claude mcp list 2>/dev/null | grep -q "$plugin"; then
    echo "$plugin: available"
  else
    echo "$plugin: not installed"
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
| wicked-jam | {available/not installed} | clarify |
| wicked-search | {available/not installed} | design |
| wicked-product | {available/not installed} | qe, review |
| wicked-mem | {available/not installed} | all phases |
| wicked-kanban | {available/not installed} | build |

### Next Steps

{Based on current phase and status}
```

### 6. Suggest Actions

Based on current state:
- If phase awaiting approval: suggest `/wicked-garden:crew:approve {phase}`
- If phase in progress: suggest `/wicked-garden:crew:execute`
- If project complete: show completion summary
