---
description: |
  Use when starting a new session and you want to know what happened since the last one — recent events,
  active crew projects, and memory updates. NOT for live session state inspection (use smaht:state).
argument-hint: "[--days N] [--project name]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
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

**Crew:** in v11, look up archetype-mode projects explicitly via
`phase_manager <name> status --json`. The v6-era find-active auto-resolver
was deleted with the universal pipeline.

### 2c. Git Activity (always supplement)

Git history is not in the event log — always query directly:

```bash
git log --oneline --since="${days:-1} days ago" --no-merges 2>/dev/null | head -15
```

### 2d. Repo method — wicked-understanding (advisory, fail-open)

Surface whether this repo's **how-to-work-here playbooks** exist (the opt-in
wicked-understanding layer — the *how*, complementing brain's *what*). Prints
nothing if absent or unavailable:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - <<'PY' 2>/dev/null || true
import os
from pathlib import Path
roots = [Path.home()/".claude"/"skills"]
cfg = os.environ.get("CLAUDE_CONFIG_DIR")
if cfg: roots.append(Path(cfg)/"skills")
names = set()
for r in roots:
    try:
        if r.exists():
            names |= {e.name for e in r.iterdir()
                      if e.is_dir() and e.name.startswith(("repo-", "fix-bug", "add-feature"))}
    except OSError:
        pass
if names:
    print("Repo playbooks available (wicked-understanding): " + ", ".join(sorted(names)[:8]))
PY
```

If present, add a **Repo method:** line to the briefing and tell the agent to load
the matching playbook for build / fix / migrate work instead of rediscovering the
method. If absent, you may note that `npx skills add mikeparcewski/wicked-understanding --all`
would generate them.

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

**Project scope:** if `--project` was supplied, scan `${PWD}` (the project
source-dir lookup was a v6 helper tied to `crew.py::list_projects`,
deleted in v11). The fallback when `--project` is absent is also
`${PWD}`. Briefings now always read from cwd.

_Stack signal extraction was removed in v11; the v6 helpers were
target-kind classifiers tied to the old gate-policy. v11 work-shape
archetypes are emitted by the prompt-submit hook, not derived from
filesystem traversal. Skip this section in v11 briefings._

If `language` is not `unknown`, include this single line at the top of the
briefing (omit entirely when language is `unknown`):

```
Detected stack: {language} ({package_manager}, frameworks: {frameworks}). Archetype: {archetype}.
```

In JSON-mode briefings, surface the same projection under a top-level
`detected_stack` field; do not invent a parallel state file.

**Affected repos (#722, advisory):** when the active project (or the one
named via `--project`) carries an optional `affected_repos` list in its
`process-plan.json`, surface it as a single advisory line directly under
the `Detected stack:` line. The helper script below is fail-open: it
prints NOTHING when the field is missing, empty, or malformed, so this
block stays silent on every legacy project. The full DAG / worktrees /
cross-repo evidence workflow lives in the `wicked-garden-monorepo`
sibling plugin (see `docs/v9/sibling-plugin-monorepo.md`).

_The `affected_repos` helper was removed in v11. Multi-repo coordination
was tied to the v6 universal pipeline's process-plan.json schema, which
the v11 archetype catalog superseded. Future cross-repo orchestration
work belongs in the `wicked-garden-monorepo` sibling plugin._

Format (when non-empty):

```
Affected repos: foo, bar (advisory — see docs/v9/sibling-plugin-monorepo.md)
```

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
