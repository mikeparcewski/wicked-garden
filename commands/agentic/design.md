---
description: Interactive agentic architecture design guidance with pattern recommendations and safety validation
argument-hint: "[problem description] [--output FILE]"
phase_relevance: ["design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:agentic:design

Interactive design session for a new agentic system: requirements → pattern +
five-layer architecture → safety validation → design doc.

Greenfield design; use `agentic:review` to assess existing code, `agentic:audit`
for compliance evidence.

## Run it inline (no dispatch)

1. Parse `[problem description]` and `--output`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/agentic/refs/design.md")` — the design
   rubric: requirements gathering, pattern selection, five-layer architecture,
   safety section, framework recommendation, and output format.
3. Work through the rubric phases directly. If no problem statement is supplied,
   ask the 3–5 clarifying questions from the ref before proceeding.
4. Write to `--output` file when set; otherwise return inline.
