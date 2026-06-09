---
description: |
  Use when creating or analyzing user flows, information architecture, and interaction patterns — in-chat,
  without a design tool. NOT for production visual design (use figma plugin) or accessibility audits (use product:a11y).
argument-hint: "<target-or-description> [--mode create|analyze]"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:ux

Design and analyze user flows, interaction patterns, and information architecture.
For a broad design audit (UI + a11y + research), use `product:ux-review` instead.

## Run it inline (no dispatch)

1. Parse `<target>` (path or description) and `--mode`. Auto-detect: description string -> `create`; file/dir path -> `analyze`.
2. Gather content: if a path, read the target files (components, pages, routing); if a description, use as the brief.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/ux.md")` — create/analyze steps, flow checklist, Nielsen heuristics, interaction patterns, diagram + output formats.
4. Apply the rubric directly and emit the flow/IA + findings. Pair with `product:mockup` for wireframes.
