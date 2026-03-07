# Kanban Scoped Boards

Deep reference for the scoped-board system: column schemas, swimlane provisioning, backward compatibility, wicked-mem triggers, and CLI examples.

---

## Board Type Overview

Each initiative has a `board_type` field that determines its column set. Four types are supported:

| board_type | Purpose |
|------------|---------|
| `crew` | Software development phases (default) |
| `jam` | Ideation, brainstorming, and design decisions |
| `collaboration` | Cross-team or multi-stakeholder workflows |
| `issues` | Bug tracking and general issue management |

---

## Column Schemas

### crew (default)

Used for software development and crew-phase tracking.

| Swimlane ID | Display Name | Terminal? |
|-------------|--------------|-----------|
| `todo` | Backlog | No |
| `in_progress` | In Progress | No |
| `review` | Review | No |
| `done` | Done | Yes |

These IDs share the project default swimlanes (`todo`, `in_progress`, `done`). Creating a crew initiative is effectively a no-op for swimlane provisioning when those lanes already exist.

### jam

Used for brainstorming and decision-making workflows.

| Swimlane ID | Display Name | Terminal? |
|-------------|--------------|-----------|
| `jam:brainstorming` | Brainstorming | No |
| `jam:perspectives_gathered` | Perspectives Gathered | No |
| `jam:synthesized` | Synthesized | No |
| `jam:decision_made` | Decision Made | Yes |

Namespaced `jam:*` IDs prevent collision with crew swimlanes when both board types coexist in the same project.

### collaboration

Used for coordinated work across teams or stakeholders.

| Swimlane ID | Display Name | Terminal? |
|-------------|--------------|-----------|
| `collab:setup` | Setup | No |
| `collab:in_progress` | In Progress | No |
| `collab:review` | Review | No |
| `collab:complete` | Complete | Yes |

### issues

Used for bug reports and non-project task tracking. Shares plain IDs with crew for backward compatibility.

| Swimlane ID | Display Name | Terminal? |
|-------------|--------------|-----------|
| `todo` | Triage | No |
| `in_progress` | In Progress | No |
| `done` | Done | Yes |

---

## Swimlane Provisioning

When `create-initiative` is called, `_provision_swimlanes()` runs automatically:

1. Fetches existing swimlane IDs for the project
2. Loops over the board type's schema
3. Appends only lanes whose ID is not already present (additive, idempotent)
4. Existing swimlanes are never modified or removed

This means:
- Creating a second `crew` initiative on a project with existing default lanes is a no-op
- Creating a `jam` initiative appends `jam:*` lanes alongside the existing crew lanes
- Both board types then coexist in the same project without collision

**Schema registry location:** `BOARD_SCHEMAS` dict at the top of `scripts/kanban/kanban.py`.

---

## Backward Compatibility

Initiatives created before this feature was added will not have a `board_type` field.

The `_resolve_board_type(initiative)` helper provides lazy inference:

```python
def _resolve_board_type(initiative: dict) -> str:
    if bt := initiative.get("board_type"):
        return bt
    if initiative.get("name") == "Issues":
        return "issues"
    return "crew"
```

Rules:
- If `board_type` is present on the record, use it as-is
- If the initiative name is `"Issues"`, infer `"issues"`
- All other legacy records default to `"crew"`

No data migration is required. The inference runs on every read.

---

## wicked-mem Integration

When a task is moved to a terminal column on certain board types, a memory record is written via `_trigger_mem_write()` inside `update_task()`.

### Trigger Map

| Terminal Swimlane | mem type | source |
|-------------------|----------|--------|
| `jam:decision_made` | `decision` | `kanban:jam` |
| `collab:complete` | `finding` | `kanban:collaboration` |

`crew` and `issues` terminal columns (`done`) are intentionally excluded. Crew domain handles its own memory via crew hooks.

### Payload

```json
{
  "type": "decision",
  "content": "{task name}\n{task description}\n{artifact content}",
  "source": "kanban:jam",
  "task_id": "abc12345",
  "initiative_id": "proj:init"
}
```

Content is assembled from: task name + description + any inline artifact `content` fields.

### Failure Handling

The mem write runs in a subprocess with a 5-second timeout. Any exception is silently swallowed — mem writes are additive context and must never block task updates.

---

## CLI Examples

### Create a Jam Board Initiative

```bash
# Via kanban.py
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-initiative PROJECT_ID "API Design Session" --board-type jam

# Via kanban_initiative.py (used by crew hooks)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban_initiative.py create "API Design Session" --board-type jam
```

### Create a Collaboration Board Initiative

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-initiative PROJECT_ID "Partner Integration Review" --board-type collaboration
```

### Move a Task Through Jam Columns

```bash
# Start brainstorming
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane jam:brainstorming

# Gather perspectives
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane jam:perspectives_gathered

# Synthesize
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane jam:synthesized

# Reach decision — triggers wicked-mem write
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane jam:decision_made
```

### Move a Task Through Collaboration Columns

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane collab:setup
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane collab:in_progress
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane collab:review
# Triggers wicked-mem write
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID TASK_ID --swimlane collab:complete
```

### Filter Initiatives by Board Type

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-initiatives PROJECT_ID --board-type jam
```

### Board Status Scoped to Jam

```
/wicked-garden:kanban:board-status --board-type jam
```

---

## Design Notes

- Swimlane ID namespacing (`jam:*`, `collab:*`) prevents index collisions when multiple board types coexist in one project
- `crew` and `issues` share plain IDs (`todo`, `in_progress`, `done`) for full backward compatibility with existing tasks and hooks
- `board_type` is stored directly on the initiative record — no separate DomainStore source is required
- `update_initiative` allows `board_type` as an updatable field for post-creation correction
