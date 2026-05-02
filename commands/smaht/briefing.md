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

Before composing the briefing, name the **detected stack** back to the user
so it is obvious wicked-garden has read the project shape (#723 — stack
identity is a projection of the repo, never a hand-edited preset).

**Project scope (#742, finding 5):** if `--project` was supplied, scan that
project's source directory; otherwise fall back to `${PWD}`. Look up the
project's `source_dir` from its crew metadata when available — `--project foo`
must always read foo's tree, never whichever cwd the briefing happened to be
invoked from.

```bash
# Resolve the scope dir: use --project's recorded source_dir when supplied
# and known to crew; otherwise the user's current working directory.
SCOPE_DIR="${PWD}"
if [ -n "${project:-}" ]; then
  # Resolve the named project's recorded directory via the public API.
  # IMPORTANT: pass the project name through an environment variable, NOT
  # via shell-string interpolation — names may contain quotes or special
  # chars and direct interpolation would be a shell-injection risk.
  #
  # API surface (verified against scripts/crew/crew.py):
  #   list_projects(active_only=True) -> {"projects": [...]}
  #
  # Note: project_dir is the LOCAL crew workspace path
  # (~/.something-wicked/wicked-garden/projects/...), NOT the source repo
  # tree. Crew project records don't currently carry a `source_dir` field
  # — adding one is a separate change (#742 follow-up). Until then, named
  # briefings can resolve the project's metadata dir but stack signals
  # may still need to be probed from \${PWD}; we surface this gap rather
  # than silently using the wrong directory.
  PROJECT_DIR=$(WG_BRIEFING_PROJECT="${project}" \
    sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import os, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
try:
    from crew.crew import list_projects  # type: ignore
    name = os.environ.get('WG_BRIEFING_PROJECT', '')
    for entry in list_projects(active_only=True).get('projects', []):
        if entry.get('name') == name or entry.get('id') == name:
            print(entry.get('project_dir') or '')
            break
except Exception:
    pass
" 2>/dev/null)
  if [ -n "${PROJECT_DIR}" ] && [ -d "${PROJECT_DIR}" ]; then
    SCOPE_DIR="${PROJECT_DIR}"
  fi
fi

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/crew/_stack_signals.py" \
   "${SCOPE_DIR}" 2>/dev/null
```

**Archetype lookup (#742, finding 6):** the briefing template requires
`{archetype}`. Always run `archetype_detect.detect_archetype` against the
same `SCOPE_DIR` *before* rendering the line — never leave `{archetype}` as
a literal placeholder.

```bash
SCOPE_DIR="${SCOPE_DIR}" sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys, os
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from crew.archetype_detect import detect_archetype
# Pass project_dir via env var to avoid shell-string interpolation of
# paths that may contain single quotes or special characters.
# NOTE: detect_archetype uses rglob('*') under the hood when no explicit
# file list is provided. On large repos with node_modules/.venv/etc.
# this can be slow. Mitigation tracked in a #742 follow-up; for now
# the briefing accepts the cost in exchange for a real archetype value
# instead of a literal {archetype} placeholder.
result = detect_archetype({'project_dir': os.environ.get('SCOPE_DIR', '')})
print(result.get('archetype', 'unknown'))
" 2>/dev/null
```

If `language` is not `unknown`, include this single line at the top of the
briefing (omit entirely when language is `unknown`):

```
Detected stack: {language} ({package_manager}, frameworks: {frameworks}). Archetype: {archetype}.
```

In JSON-mode briefings, surface the same projection under a top-level
`detected_stack` field; do not invent a parallel state file.

```markdown
## Session Briefing ({days}d window)

Detected stack: python (uv, frameworks: click). Archetype: code-repo.

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
