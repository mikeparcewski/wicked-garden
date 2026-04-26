---
description: |
  Use when starting a new session and you want to know what happened since the last one — recent events,
  active crew projects, and memory updates. NOT for live session state inspection (use smaht:state).
argument-hint: "[--days N] [--project name]"
---

# /wicked-garden:smaht:briefing

Generate a "what happened since last session" briefing. Primary source: unified event log. Fallback: individual domain queries.

## Instructions

### 0. Post-Compaction Recovery

If this briefing is requested after a context compaction event, check for WIP state first and present it prominently at the top of the briefing:

1. Check for WIP snapshot file at the session's history condenser directory (`wip_snapshot.json`)
2. If no snapshot, query `HistoryCondenser(session_id).get_session_state()` for live working state
3. Read native tasks for in-progress items: list task JSON under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/` and filter by `status == "in_progress"`.
4. Present recovered WIP state at the top of the briefing output:
   - **Current task**: what the user was working on
   - **Recent decisions**: choices already made (do NOT re-ask)
   - **Active files**: files in scope for the current work
   - **Open questions**: unresolved items that still need answers
   - **In-progress tasks**: native tasks currently being worked (filter `metadata.event_type=="task"` for human-visible items)
5. Add: "Context was compacted. Review this state before proceeding. Do NOT repeat completed work."

If no compaction occurred (normal briefing request), skip this step entirely.

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

This returns events from ALL domains in one timeline — mem decisions, crew phase transitions, native task changes, jam outcomes.

### 2b. Fallback (if event log is empty or unavailable)

If the event log returns no results (new install, events.db not yet populated), fall back to individual queries:

**Memory:** `wicked-brain:memory "recent decisions and learnings" --limit 10`

**Native tasks:** read task JSON under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/` and summarize counts by `status` and `metadata.event_type`.

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
| `tasks.created`, `tasks.updated` | Active Work (tasks) |
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
**Tasks**: {N in progress}, {M completed since last session}

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

### When context is thin

If the briefing doesn't give you enough to orient — no active project, sparse events, or missing decisions — invoke `wicked-garden:ground` to pull richer brain + bus context before proceeding.
