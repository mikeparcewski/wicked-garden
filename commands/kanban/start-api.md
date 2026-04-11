---
description: Check kanban data status and storage health
---

# /wicked-garden:kanban:start-api

Kanban data is stored locally via DomainStore. No external server required.

## Instructions

Check that kanban data is accessible:

```bash
python3 -c "
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _domain_store import DomainStore
ds = DomainStore('wicked-garden:kanban')
projects = ds.list('projects')
tasks = ds.list('tasks')
print(f'Projects: {len(projects) if projects else 0}')
print(f'Tasks: {len(tasks) if tasks else 0}')
print('Status: OK')
"
```

## Kanban CLI Access

```bash
cd "${CLAUDE_PLUGIN_ROOT}"

# List projects
uv run python scripts/_run.py scripts/kanban/kanban.py list-projects

# List tasks
uv run python scripts/_run.py scripts/kanban/kanban.py list-tasks PROJECT_ID

# Search
uv run python scripts/_run.py scripts/kanban/kanban.py search "query"
```

## Data Location

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:kanban
```

## Notes

- Data stored as local JSON files via DomainStore
- Integration-discovery can route to Linear/Jira MCP tools when configured
- Use `/wicked-garden:kanban:board-status` for a visual board view
