---
description: Quick exploration with fewer personas and one round
argument-hint: "<idea or question>"
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# /wicked-garden:jam:quick

Quick 60-second exploration with 4 personas and 1 round.

> **Progression**: `quick` (60s gut-check, ephemeral) → `brainstorm` (full session
> with evidence + decision storage) → `council` (structured verdict with external LLMs).
> See also: `/wicked-garden:jam:brainstorm`, `/wicked-garden:jam:council`

## Run it inline (no dispatch)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/jam/refs/quick.md")` — the single-pass
   rubric: 4 personas, 1 forced round, synthesis format (Key Insights / Action
   Items / Open Questions), hard constraints (no storage, no multi-AI, ≤200 words).
2. Apply the rubric directly to the topic. Do NOT run additional rounds. Do NOT store.
