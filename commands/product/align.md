---
description: |
  Use when you have divergent stakeholder positions on scope, priority, or direction and need to surface
  concerns, map them to trade-offs, and build consensus. NOT for requirements elicitation (use product:elicit)
  or UX design (use product:ux).
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:align

Facilitate stakeholder alignment, surface concerns, and build consensus.

## Run it inline (no dispatch)

1. Read context: the target document if provided, plus `--stakeholders`, `--focus` (concerns/tradeoffs/conflicts), `--conflict`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/align.md")` — the process, facilitation checklist, questions to ask, and output format.
3. Apply the rubric directly: identify stakeholders, surface concerns, classify ALIGNED / CONFLICTED / UNCLEAR, propose compromises, and emit decisions-required + next steps (owner + deadline).

Persist status via `TaskCreate`/`TaskUpdate` (`metadata.event_type="task"`); store stakeholder patterns via `wicked-brain:memory`.
