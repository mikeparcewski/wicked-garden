---
description: Show current project status, phase, and next steps
---

# /wicked-garden:crew:status

Display the current project state and available integrations.

## Instructions

### 1. Find Active Project

Look for the most recently modified project:

```bash
ls -t ~/.something-wicked/wicked-garden/local/wicked-crew/projects/ 2>/dev/null | head -1
```

If no projects exist, inform user and suggest `/wicked-garden:crew:start`.

### 2. Read Project State

Read `project.md` to get:
- Project name and description
- Current phase
- Status
- Phase history

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
