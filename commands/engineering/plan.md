---
description: |
  Use when you have a change request or issue and need a detailed implementation plan with specific file
  changes, risk assessment, and test recommendations — before writing any code.
  NOT for free-form planning (use native Task planning) or architecture decisions (use engineering:arch).
argument-hint: "<change request or issue description>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:engineering:plan

Analyze a change request against the current codebase and produce a detailed implementation plan
with specific file changes, risk assessment, and test recommendations.

## Run it inline (no dispatch)

1. Parse the change request: identify goal, scope, and constraints. Ask a clarifying question if
   the request is too vague to scope (e.g. no target file or system identified).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/plan.md")` — exploration checklist,
   risk assessment checklist, plan output format, and security/performance heuristics.
3. Explore the affected code: entry points, key files, callers, existing patterns, test coverage.
   Use `wicked-garden:search:blast-radius {symbol}` for impact analysis.
4. Apply the risk assessment checklist (breaking changes, performance, security, data integrity,
   test gaps, deployment coordination).
5. Emit the Implementation Plan output format: Summary, Scope (in/out), Changes Required per
   file, Risk Assessment table, Test Plan, Rollout Considerations, Open Questions.
6. Present the plan and ask: "Ready to proceed with implementation, or would you like to adjust
   the approach?" Do not write any code until approved.
