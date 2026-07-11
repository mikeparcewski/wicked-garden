---
name: wicked-garden-smaht
context: fork
description: |
  Context assembly / briefing builder (the name is a phonetic play on "smart").
  Gathers a relevant on-demand context briefing over wicked-brain + wicked-garden:search
  + domain state. Pull-model: subagents call it when they need background rather than
  having context pushed onto every prompt (v6 replaced the v5 push orchestrator, #428).
  Routes three sub-actions backed by refs/: briefing (what happened since the last
  session — NOT live state), state (live SessionState/adapter/directive inspection —
  NOT since-last-session), events-import (DomainStore records → unified event log).

  Use when: gathering a context briefing before a task, "assemble context",
  "give me a briefing", "what happened since my last session", resuming work after
  a session break, building background on an unfamiliar area, "show session state",
  "inspect live session state", "import domain records into the event log", or any
  former /wicked-garden:smaht:{briefing|state|events-import} invocation.
  Aliases: context-assembly, briefing, smart-context.
user-invocable: true
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# Context Assembly (v6 pull-model)

Gather relevant context from wicked-brain + wicked-garden:search + domain state when
a subagent or command asks for it. There is no per-prompt push — the user prompt
submit hook no longer runs an orchestrator.

## Sub-action router

| Sub-action | Use for | Args | Ref |
|------------|---------|------|-----|
| `briefing` | What happened **since the last session** — recent events, active crew projects, memory updates, post-compaction WIP recovery. NOT live session-state inspection (use `state`). | `[--days N] [--project name]` | `refs/briefing.md` |
| `state` | **Live** SessionState, adapter outputs, smaht directive settings, recent bus events. NOT what-happened-since-last-session (use `briefing`). | `[--state] [--events N] [--project <name>] [--json]` | `refs/state.md` |
| `events-import` | Import existing DomainStore JSON records into the unified event log as historical `{source}.migrated` events (idempotent). | `[--domain D] [--dry-run]` | `refs/events-import.md` |

Run a sub-action inline (no dispatch):

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/smaht/refs/<sub-action>.md")` — the full rubric.
2. Apply the rubric directly using the parsed args.

No sub-action named? The caller wants general context assembly — use the quick
reference below (and `briefing` when resuming after a session break).

## Quick Reference

```bash
# Brain search — primary knowledge source
wicked-brain:search "your query"

# Brain query — conceptual / "how does X work"
wicked-brain:query "how does the facilitator rubric work"

# Codebase symbol / docs search (FTS5 over indexed code, docs, wiki)
wicked-brain:search "symbol or pattern"

# Pull v11 archetype-mode project state (the v6 crew.py find-active
# auto-resolver was deleted with the universal pipeline — look up by name)
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} status --json
```

## Context Sources

| Source | Plugin | Content |
|--------|--------|---------|
| brain | wicked-brain (required) | Code, docs, wiki, memories — FTS5 search |
| search | wicked-garden | Indexed code symbols + docs |
| mem | wicked-garden | Memories, decisions, learnings |
| crew | wicked-garden | Project phase, outcomes, constraints |
| jam | wicked-garden | Brainstorm sessions, perspectives |

## Pull-Model Rules

1. **Ask only for what you need.** Each adapter costs latency and tokens.
2. **Brain first.** `wicked-brain:search` replaces Grep/Glob/Agent(Explore) for any
   open-ended search. Fall back to raw tools only when the brain returns empty.
3. **Active chain matters.** When a crew project is active, prefer queries scoped
   to that project's `chain_id` — see `scripts/_session.py::SessionState.active_chain_id`.
4. **Recent events win.** For debugging, prefer the last 20 chain-matching events
   over broad semantic search.

## Sub-Skills

- [discovery/SKILL.md](discovery/SKILL.md) — Contextual discovery: suggest ONE
  related follow-up based on what was just used (feeds the `briefing` sub-action's
  step 5)
- [intent/SKILL.md](intent/SKILL.md) — Show or set the sticky session intent
  variable (simple-edit / feature / research / rigor)
- [propose-skills/SKILL.md](propose-skills/SKILL.md) — Mine session transcripts
  for repetitive patterns worth turning into skills (read-only report)

## v5 → v6 Notes

The v5 HOT/FAST/SLOW/SYNTHESIZE tiered orchestrator
(`scripts/smaht/v2/orchestrator.py`) was deleted in #428. Adapters (`brain_adapter`,
`domain_adapter`, `events_adapter`, etc.) still live under `scripts/smaht/adapters/`
and can be called directly by subagents as needed. There is no longer a central
router that decides HOT vs FAST vs SLOW — the caller decides by picking which
adapters (or skill calls) to invoke.
