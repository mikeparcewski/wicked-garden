---
description: |
  Use when profiling a dataset's structure, validating it against a schema, or generating a data quality
  report (completeness, uniqueness, validity). NOT for interactive SQL queries (use data:analyze)
  or ML pipeline work (use data:ml).
argument-hint: "<subcommand> [args...] — profile <path> | validate --schema <schema> --data <path> | quality <path>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:data

Core data engineering ops: `profile`, `validate`, `quality`. NOT for interactive exploration
(use `data:analyze`) or ML pipeline review (use `data:ml`).

## Run it inline (no dispatch)

1. Parse `subcommand` (profile|validate|quality) and its args (`<path>`, `--schema` for validate).
2. Read the data file head/tail to capture columns / types / nulls / sample.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/data/refs/data.md")` — the profile, validate, and quality rubrics with output formats.
4. Apply the rubric for the requested subcommand and emit structured markdown with tables and prioritized findings.
