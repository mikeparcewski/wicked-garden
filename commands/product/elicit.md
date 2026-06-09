---
description: |
  Use when turning a vague idea or stakeholder ask into structured user stories with acceptance criteria.
  NOT for requirements traceability graphs (use the requirements-graph skill) or UX flows (use product:ux).
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:elicit

Elicit requirements and write user stories with acceptance criteria.

## Run it inline (no dispatch)

1. Read context: the target document(s) (`outcome.md`, brief, `docs/requirements/`), or accept `--interactive`. Honor `--personas` and `--scope`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/elicit.md")` — the process, INVEST quality criteria, completeness check, traceability, and output format.
3. Apply the rubric directly and emit user stories (priority + complexity + dependencies + AC) and open questions.

For complexity >= 3 or compliance projects, produce a requirements **graph** instead — load the `requirements-analysis` / `requirements-graph` skills. Persist on the active clarify task via `TaskUpdate`.
