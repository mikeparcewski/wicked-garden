---
description: "Session briefing — what happened since last time"
argument-hint: "[--days N] [--project name]"
---

# /wicked-garden:smaht:briefing

Generate a "what happened since last session" briefing. Primary source: unified event log. Fallback: individual domain queries.

## Instructions

### 1. Determine Time Window

Default: last 24 hours. Override with `--days N`. If `--project` specified, filter to that project.

### 2. Query the Event Log (primary)

Single query replaces 4 separate domain calls:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/_event_store.py query \
  --since "${days:-1}d" \
  ${project:+--project "$project"} \
  --limit 100 \
  --json
```

This returns events from ALL domains in one timeline — mem decisions, crew phase transitions, kanban task changes, jam outcomes.

### 2b. Fallback (if event log is empty or unavailable)

If the event log returns no results (new install, events.db not yet populated), fall back to individual queries:

**Memory:** `/wicked-garden:mem:recall "recent decisions and learnings" --limit 10`

**Kanban:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/kanban/kanban.py list-projects --json
```

**Crew:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

### 2c. Git Activity (always supplement)

Git history is not in the event log — always query directly:

```bash
git log --oneline --since="${days:-1} days ago" --no-merges 2>/dev/null | head -15
```

### 3. Categorize Events

Group events from the timeline by type:

| Event action pattern | Briefing section |
|---------------------|-----------------|
| `memories.created`, `memories.updated` | Recent Decisions |
| `projects.created`, `phases.*` | Active Work (crew) |
| `tasks.created`, `tasks.updated` | Active Work (kanban) |
| `sessions.created`, `*.migrated` | Brainstorm Outcomes |
| Everything else | Other Activity |

### 4. Synthesize Briefing

```markdown
## Session Briefing ({days}d window)

### Recent Decisions
{events from mem domain — decisions stored, patterns learned}
- "Chose JWT over sessions" (2 days ago)
- "Rate limiting goes after gateway" (yesterday)

### Active Work
**Crew**: {project name} — phase: {current}, next: {next step}
**Kanban**: {N tasks in progress}, {M tasks completed since last session}

### Brainstorm Outcomes
{jam session decisions made in the window}

### Code Changes
{git commits grouped by area}

### Suggested Next Steps
{based on the event timeline:}
- Continue: {most recent active crew phase}
- Review: {files changed since last session}
- Decide: {any open questions from jam sessions}
```

### 5. Contextual Discovery

Suggest ONE related command based on the briefing content:

- If active crew project → suggest `crew:execute` or `crew:status`
- If recent mem decisions but no crew project → suggest `crew:start`
- If code changes but no review → suggest `engineering:review`
- If brainstorm outcomes with no follow-up → suggest `jam:revisit`

Keep it to ONE suggestion. Frame as: "You might find X useful because..."
