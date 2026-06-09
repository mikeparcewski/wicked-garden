---
description: |
  Use when you want the raw pre-synthesis perspectives from a brainstorm — minority views, strong dissents,
  and nuances that synthesis may have compressed. NOT for the full session (use jam:transcript).
argument-hint: "[--session-id ID] [--json]"
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# /wicked-garden:jam:thinking

Display all pre-synthesis perspectives from a brainstorm session — the raw,
unfiltered thinking from every persona before synthesis. Exposes minority views,
strong dissents, and nuances that synthesis may have de-emphasized.

## Run it inline (no dispatch)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/jam/refs/thinking.md")` — the rubric:
   script invocation, framing note about compression ratio, and missing-data handling.
2. Run the script and present the output per the rubric.
