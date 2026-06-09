---
description: |
  Use when reviewing an existing system's architecture — evaluating component boundaries, coupling, layer
  violations, or recommending design patterns. Outputs ADR-style analysis with trade-offs.
  NOT for greenfield design (use the architecture skill) or code-level review (use engineering:review).
argument-hint: "[component or system] [--scope module|service|system]"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:engineering:arch

Architecture analysis of a component, service, or system. Use `engineering:arch` for
component/system-level review; use `engineering:review` for code-level review.

## Run it inline (no dispatch)

1. Parse `[target]` and `--scope` (module | service | system; infer if absent from directory depth
   and file count).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/arch.md")` — rubric, checklists, output
   formats, and architecture principles for both module/service and system scope.
3. Map the directory layout, entry points, key dependencies, and data flow of the target.
4. Apply the scope-appropriate checklist from the rubric directly. Flag unauthorized architectural
   changes or scope creep when reviewing a diff.
5. Emit the scope-appropriate output format (strengths, concerns table, recommendations,
   trade-off table, ADR candidates for system scope).
