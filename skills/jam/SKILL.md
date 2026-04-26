---
name: jam
description: |
  Orchestrates AI-powered brainstorming sessions with dynamic focus groups.
  quick sessions are ephemeral (no storage). brainstorm and council sessions
  are tracked as native tasks (process) and stored in wicked-brain:memory (outcome).
  Use when: "brainstorm this", "explore ideas", "get different perspectives",
  "focus group", "what do you think about", "pros and cons", "quick check".
context: fork
---

# Brainstorming Skill

Generate diverse perspectives through structured focus group sessions.

## Session Types

- **quick** (`/wicked-garden:jam:quick`) — 4 personas, 1 forced round, brief synthesis. Ephemeral. Best for gut-checks and rapid exploration.
- **brainstorm** (`/wicked-garden:jam:brainstorm`) — 4-6 personas, 2-3 rounds, evidence gathering, decision record storage. Best for important decisions and complex problems.
- **council** (`/wicked-garden:jam:council`) — Structured verdict with external LLMs. Best for high-stakes calls requiring external challenge.

## Quick-Start

```
# Fast gut-check (ephemeral, ~60s)
/wicked-garden:jam:quick "Should we use feature flags or config files here?"

# Full session with evidence and decision storage
/wicked-garden:jam:brainstorm "Architecture approach for the new event bus"

# High-stakes council with external LLM challenge
/wicked-garden:jam:council "Go/no-go on the v9 storage migration"
```

## Agents

- `agents/jam/quick-facilitator.md` — single-pass, 4 personas, no storage, no bus events
- `agents/jam/brainstorm-facilitator.md` — multi-round, evidence gathering, transcript storage, decision record

## References

- `refs/facilitation-patterns.md` — persona archetype pool, session length guidance, anti-patterns
- `refs/synthesis-patterns.md` — synthesis structure, quality checklist, decision record format
