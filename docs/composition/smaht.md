# smaht composition map

Context assembly and session intelligence — briefings, live state inspection, event log, and contextual discovery.

## Surface inventory

| Type | Name | One-line purpose |
|---|---|---|
| command | /wicked-garden:smaht:briefing | Cross-domain catch-up since last session (recent events, active projects, memory updates) |
| command | /wicked-garden:smaht:events-import | Import existing DomainStore JSON records into the unified event log |
| command | /wicked-garden:smaht:state | Inspect live SessionState, adapter outputs, and smaht directive settings |
| skill | wicked-garden:smaht:context-assembly | Pull-model context gathering from wicked-brain + search + domain state |
| skill | wicked-garden:smaht:discovery | Contextual command discovery — suggests one related command after each run (Stop hook, not user-invocable) |

> Note: `smaht:events-query` was relocated to `crew:activity` in PR #636 — see the crew composition map for cross-domain activity search.

Note: smaht has no agents on disk. Context intelligence is delivered via skills and hooks (`hooks/scripts/prompt_submit.py`).

## Workflow patterns

### 1. Session start catch-up
User opens a new session and wants to orient quickly.

```
/smaht:briefing [--days N] [--project name]
```

Queries wicked-brain + events log + active crew projects. Returns recent activity summary, memory updates, and one discovery suggestion. Default window is 7 days.

### 2. Diagnosing context assembly problems
Context injected into a prompt seems wrong, stale, or missing.

```
/smaht:state --state          # dump live SessionState
/smaht:state --events 20      # show last N events fed to adapters
/smaht:state --json           # machine-readable output for scripting
```

Use `state`, not `briefing`, when the problem is live session state vs. historical catch-up.

### 3. Migrating legacy DomainStore records
Historical JSON records predate the unified event log and need to be imported.

```
/smaht:events-import --domain jam --dry-run    # preview
/smaht:events-import --domain jam              # commit
```

One-time operation per domain after migrating to the unified log. Run `--dry-run` first.

### 4. On-demand context assembly (subagent use)
A subagent or command needs a context briefing before acting.

```
# In agent/command markdown:
Skill: wicked-garden:smaht:context-assembly
```

v6 pull-model: nothing is pushed onto every prompt. Subagents call this skill when they need background. The `prompt_submit.py` hook injects a short pull directive; complex/risky prompts get an expanded directive routing through `wicked-brain:query`.

## When to add a new surface

- **New command** — when there is a distinct user-facing inspection or data-management action not covered by `briefing`, `state`, or `events-import`. smaht commands are operational tools, not workflow drivers; keep the surface small. (Cross-domain activity search lives in `crew:activity` post-#636.)
- **New skill** — when a reusable context-gathering pattern is needed by 2+ agents/commands. `context-assembly` is the primary skill; add a new one only if the assembly logic for a new use case is fundamentally different (different sources, different output contract). `discovery` is hook-driven and not user-invocable — that pattern can extend via refs, not new skills.
- **No agents needed** — smaht intelligence lives in skills and hooks. Do not add agents to this domain; if a dispatched subagent is needed, it belongs in the domain whose work it is doing.

## Cross-domain dependencies

```
smaht
  calls →  wicked-brain:query       (complex/risky prompt enrichment)
  calls →  wicked-brain:search      (context-assembly skill)
  calls →  search domain            (context-assembly skill)
  reads ←  all domains              (state inspector + crew:activity read the unified log)

hooks/scripts/prompt_submit.py
  injects  → pull directives on every UserPromptSubmit
  reads    ← SessionState.active_chain_id (crew chain-aware scoring)
  invokes  → smaht:discovery skill (contextual suggestion via _suggest_discovery())

hooks/scripts/stop.py
  emits    → wicked.fact.extracted events (brain auto-memorize ingestion path)
            (Note: stop.py does NOT invoke the discovery skill; that's prompt_submit.py.)
```

## Anti-patterns

- **Using `smaht:briefing` for live session inspection.** `briefing` queries historical data (events log, brain memory). Use `smaht:debug --state` to inspect what is happening right now in the current session.
- **Adding push-model context injection.** v5's per-prompt orchestrator was deleted in #428. Do not reintroduce it. Context assembly is pull-only — subagents call `context-assembly` when they need it.
- **Querying brain files directly from a command.** Route through `wicked-brain:query` or `wicked-brain:search`. The `context-assembly` skill handles source fan-out and budget enforcement; do not replicate that logic in individual commands.
- **Making `discovery` user-invocable.** The discovery skill is Stop-hook-driven by design. It produces one suggestion per Stop, not an on-demand catalog. Keep `user-invocable: false`.
