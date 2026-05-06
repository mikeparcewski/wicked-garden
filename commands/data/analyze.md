---
description: Start interactive data analysis session for CSV/Excel files
argument-hint: "<file-path> [--focus <type>] [--context <file>] [--refresh] [--scenarios]"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:analyze

Interactive analysis on a CSV/Excel/data file. Routes by `--focus` to the right specialist (stats, quality, warehouse, ml). Use this for one-off data exploration on a file. NOT for profiling/validation/quality reports across a known schema (use `data:data`) or pipeline-level review (use `data:pipeline`).

## 1. Arg parse + profile

Extract `file-path`, `--focus` (stats|quality|warehouse|ml, default stats), `--context`, `--refresh`, `--scenarios`. Read first rows of the file to capture column names/types/nulls/sample.

## 2. Dispatch by focus (one of)

Common preamble: `File: {file-path}  Context: {context or none}  Profile: {columns/types/nulls/sample}  Scenarios: {--scenarios true/false}`. Each agent runs its standard rubric + emits wicked-scenarios api/perf blocks if `--scenarios`.

```
Task(subagent_type="wicked-garden:data:data-analyst",   prompt="<preamble>")  # --focus stats (default)
Task(subagent_type="wicked-garden:data:data-engineer",  prompt="<preamble>")  # --focus quality
Task(subagent_type="wicked-garden:data:data-architect", prompt="<preamble>")  # --focus warehouse
Task(subagent_type="wicked-garden:data:ml-engineer",    prompt="<preamble>")  # --focus ml
```
