---
description: Show current kanban board state with projects and tasks, grouped by board type
argument-hint: "[--board-type crew|jam|collaboration|issues]"
---

# /wicked-garden:kanban:board-status

Display current kanban board state. Supports scoped views by board type.

## Instructions

### 1. Resolve Active Project

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/_run.py scripts/kanban/kanban.py list-projects
```

Use the active project (first non-archived, or repo-matched). Note the PROJECT_ID.

### 2. Fetch Initiatives

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/_run.py scripts/kanban/kanban.py list-initiatives PROJECT_ID
```

If `--board-type` was provided, filter the list to initiatives where `board_type` matches (or infer: missing `board_type` on legacy records defaults to `"crew"`, name `"Issues"` defaults to `"issues"`).

**If `--board-type` filter returns no initiatives**, output:

```
No {board_type} board found for this project.
Create one with: /wicked-garden:kanban:initiative create "{Name}" --board-type {board_type}
```

Then stop.

### 3. Fetch Tasks Per Board Type

For each initiative (or each board-type group), determine its column schema. Use the following column IDs and display names:

| Board Type | Swimlane IDs | Display Names |
|------------|--------------|---------------|
| crew | todo, in_progress, review, done | Backlog, In Progress, Review, Done |
| jam | jam:brainstorming, jam:perspectives_gathered, jam:synthesized, jam:decision_made | Brainstorming, Perspectives Gathered, Synthesized, Decision Made |
| collaboration | collab:setup, collab:in_progress, collab:review, collab:complete | Setup, In Progress, Review, Complete |
| issues | todo, in_progress, done | Triage, In Progress, Done |

Fetch task counts per swimlane:

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/_run.py scripts/kanban/kanban.py list-tasks PROJECT_ID --swimlane SWIMLANE_ID --initiative INITIATIVE_ID
```

### 4. Check Recent Activity

```bash
cd ${CLAUDE_PLUGIN_ROOT} && uv run python scripts/_run.py scripts/kanban/kanban.py activity PROJECT_ID --limit 10
```

### 5. Render Output

#### Without `--board-type` (all boards):

```
## Kanban Board Status

### Crew Board — {Initiative Name}
Backlog: 2  |  In Progress: 1  |  Review: 0  |  Done: 5

### Jam Board — {Initiative Name}
Brainstorming: 3  |  Perspectives Gathered: 1  |  Synthesized: 0  |  Decision Made: 2

### Collaboration Board — {Initiative Name}
Setup: 1  |  In Progress: 2  |  Review: 1  |  Complete: 4

**Recent Activity**:
- Task created: "Add logout endpoint"
- Status change: "JWT service" → in_progress
```

#### With `--board-type jam` (scoped view):

```
## Jam Board — {Initiative Name}

Brainstorming: 3  |  Perspectives Gathered: 1  |  Synthesized: 0  |  Decision Made: 2

Tasks in Brainstorming:
- "Explore async pattern options" (P1)
- "Research event sourcing" (P2)
```

When scoped, list the tasks in each column by name and priority.
