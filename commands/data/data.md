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

Core data engineering ops: `profile`, `validate`, `quality`. Use this for schema-level checks. NOT for interactive exploration (use `data:analyze`) or ML pipeline review (use `data:ml`).

## 1. Arg parse + read

Extract `subcommand` (profile|validate|quality) and its args (`<path>`, `--schema` for validate). Read the data file head/tail + capture columns/types/nulls.

## 2. Dispatch

```
Task(subagent_type="wicked-garden:data:data-engineer",
     prompt="""Run data {subcommand} on {path}. Schema: {schema-path or n/a}. Profile: {columns/types/nulls/sample}. Apply your standard rubric for the requested subcommand and return structured markdown with tables and prioritized findings.""")
```
