---
name: context-assembly
description: |
  On-demand context assembly over wicked-brain + wicked-garden:search. v6 replaced
  the v5 push-model orchestrator (deleted in #428) with a pull-model skill —
  subagents call this skill directly when they need a context briefing rather
  than having one pushed onto every prompt.

  Use when: gathering a context briefing before a task, resuming work after
  a session break, or assembling background on an unfamiliar area.
user-invocable: true
---

# Context Assembly (v6 pull-model)

Gather relevant context from wicked-brain + wicked-garden:search + domain state when
a subagent or command asks for it. There is no per-prompt push — the user prompt
submit hook no longer runs an orchestrator.

## Quick Reference

```bash
# Brain search — primary knowledge source
wicked-brain:search "your query"

# Brain query — conceptual / "how does X work"
wicked-brain:query "how does the facilitator rubric work"

# Codebase symbol search
/wicked-garden:search:code "symbol or pattern"
/wicked-garden:search:docs "doc or markdown text"

# Pull active crew project state
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
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

- [discovery/SKILL.md](discovery/SKILL.md) — Integration discovery and adapter configuration

## v5 → v6 Notes

The v5 HOT/FAST/SLOW/SYNTHESIZE tiered orchestrator
(`scripts/smaht/v2/orchestrator.py`) was deleted in #428. Adapters (`brain_adapter`,
`domain_adapter`, `events_adapter`, etc.) still live under `scripts/smaht/adapters/`
and can be called directly by subagents as needed. There is no longer a central
router that decides HOT vs FAST vs SLOW — the caller decides by picking which
adapters (or skill calls) to invoke.
