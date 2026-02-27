---
description: Name the current session for better sprint/initiative organization
argument-hint: <session-name>
---

# /wicked-garden:kanban-name-session

Give the current Claude Code session a descriptive name. This creates an initiative that groups related tasks together.

## Instructions

1. Get the current project for this repo:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban.py list-projects
   ```

2. Create a named initiative for the session:
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/kanban.py create-initiative PROJECT_ID "SESSION_NAME"
   ```

3. Confirm to the user with the initiative details

## Example Usage

```
/wicked-garden:kanban-name-session "Implementing Auth"
```

## How It Works

- Sessions map to **initiatives** in the kanban
- New tasks created during the session are automatically tagged with the active initiative
- Tasks can be filtered by initiative to see work done in a session
- If no session is named, tasks use a default `daily-{date}` initiative

## Output

Confirm with:
- Initiative ID
- Session name
- Project it belongs to
