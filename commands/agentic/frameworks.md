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

Framework selection / comparison / wizard. Mode is derived from args: `--compare` → side-by-side comparison; filters only (`--language`, `--use-case`) → filtered selection; no args → interactive 5-question wizard. End-of-output should suggest `/wicked-garden:agentic:design` as the next step.

## 1. Dispatch framework researcher

```
Task(subagent_type="wicked-garden:agentic:framework-researcher",
     prompt="""Mode: {comparison|selection|wizard}
Compare: {fw_list or 'n/a'}  Language: {lang or 'any'}  Use case: {use_case or 'any'}

Load skill wicked-garden:agentic:frameworks. Use WebSearch for latest 2026 ecosystem state
(versions, features, community). Render the comparison table / decision guide / wizard
flow per mode, with code samples, recommendation + rationale, and a final pointer to
`/wicked-garden:agentic:design` for the next step.""")
```
