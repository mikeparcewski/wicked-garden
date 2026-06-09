---
description: |
  Use when selecting or comparing agentic frameworks (LangChain, CrewAI, AutoGen, etc.) for a specific
  use case — gets latest ecosystem context via WebSearch. NOT for reviewing existing agentic code
  (use agentic:review) or architecture design (use agentic:design).
argument-hint: "[--compare fw1,fw2,...] [--language python|typescript|java|go] [--use-case TYPE]"
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:agentic:frameworks

Framework selection / comparison / wizard. Mode is derived from args: `--compare` →
side-by-side comparison; filters only (`--language`, `--use-case`) → filtered selection;
no args → interactive 5-question wizard.

## Run it inline (no dispatch)

1. Parse args to determine mode: comparison | selection | wizard.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/agentic/refs/frameworks.md")` — the
   mode detection table, wizard questions, decision tree, comparison table,
   scoring template, and output format.
3. Use WebSearch for latest 2026 ecosystem state (versions, features, community)
   before rendering the comparison or recommendation.
4. End output with a pointer to `/wicked-garden:agentic:design` as the next step.
