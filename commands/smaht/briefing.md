---
description: "Session briefing — what happened since last time"
argument-hint: "[--days N] [--project name]"
---

# /wicked-garden:smaht:briefing

Generate a "what happened since last session" briefing by pulling from memory, kanban, crew, and git.

## Instructions

### 1. Determine Time Window

Default: last 24 hours. Override with `--days N`.

### 2. Gather Context (parallel)

Run these in parallel to minimize latency:

**Memory changes:**
```
/wicked-garden:mem:recall "recent decisions and learnings" --limit 10
```

**Kanban activity:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/kanban/kanban.py list-projects --json
```

**Crew project status:**
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

**Git activity:**
```bash
git log --oneline --since="{N} days ago" --no-merges 2>/dev/null | head -15
```

### 3. Synthesize Briefing

Present as a concise briefing:

```markdown
## Session Briefing

### Recent Decisions
{memories stored since last session — decisions, patterns, learnings}

### Active Work
{crew projects in progress — current phase, next step}
{kanban tasks in progress — grouped by project}

### Code Changes
{git commits since last session — grouped by area}

### Suggested Next Steps
{based on active work and recent context:}
- Continue: {active crew project phase}
- Review: {recently changed files that haven't been reviewed}
- Decide: {open questions from recent jam sessions}
```

### 4. Suggest Discovery

At the end of the briefing, suggest one command the user hasn't used recently that relates to their current work context. Example:

> Based on your active auth migration, you might find `search:blast-radius handleAuth` useful to see what depends on the auth module.

Keep it to ONE suggestion. The goal is gentle discovery, not a feature dump.
