---
description: |
  Use when you need a quick ASCII wireframe or HTML mockup in-chat without Figma overhead.
  NOT for production design work — use the figma plugin for that.
argument-hint: "<description-or-target> [--format ascii|html|spec] [--fidelity low|medium|high]"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:mockup

Generate wireframes, mockups, and component specs at the right fidelity — ASCII for
ideation, HTML/CSS for stakeholder review, annotated spec for developer handoff.

## Run it inline (no dispatch)

1. Parse `<description-or-target>`, `--format` (ascii/html/spec), `--fidelity` (low/medium/high). Auto-select format: bare description / low -> ascii; high / stakeholder context -> html; file path -> spec.
2. Gather context: if a description, use as the brief; if a file path, read it to understand the current structure; recall design tokens via `wicked-brain:memory`.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/mockup.md")` — fidelity selection, ASCII/HTML/spec formats, generation process, and output format.
4. Apply the rubric directly and emit the mockup with state/responsive/a11y annotations and open questions. Pair with `product:ux` (flows) and `product:screenshot` (compare to built UI).
