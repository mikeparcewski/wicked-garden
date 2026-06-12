---
description: Full agentic codebase review with framework detection, agent topology analysis, and remediation roadmap
argument-hint: "[path] [--quick] [--framework NAME] [--output FILE]"
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:agentic:review

Full agentic-codebase review: framework detection → topology → architecture +
safety + performance assessments → pattern scoring → unified remediation roadmap.

Use `agentic:audit` for compliance-grade safety evidence; `agentic:design` for
greenfield design. This reviews an **AI agent system**; for ordinary source code use
`engineering:review`, and for a binding go/no-go verdict use `archetype:review`
(see `docs/domains.md` → "review appears in three domains").

## Run it inline (no dispatch)

1. Parse `[path]`, `--quick`, `--framework`, `--output`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/agentic/refs/review.md")` — the full
   5-step review rubric: framework+topology detection, architecture assessment,
   safety 8-layer, performance assessment, pattern scoring + issue taxonomy,
   and output format.
3. Run the detection scripts from the ref (Step 1). If `--quick`, stop and return
   the structural summary. Otherwise apply all rubric steps directly.
4. Write to `--output` file when set; otherwise return inline.
