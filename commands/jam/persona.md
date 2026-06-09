---
description: |
  Use when you want to quote or trace a specific persona's position across all rounds of a brainstorm —
  e.g., "what did the Security Reviewer say across each round?" NOT for full session transcript (use jam:transcript).
argument-hint: "<persona-name> [--session-id ID] [--json]"
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# /wicked-garden:jam:persona

Retrieve all contributions from a specific persona across every round of a
brainstorm session. Useful for quoting a particular expert's position or
understanding how their view evolved.

## Run it inline (no dispatch)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/jam/refs/persona.md")` — the rubric:
   script invocation, round-count note, and no-match fallback (list session personas).
2. Run the script and present the output per the rubric.
