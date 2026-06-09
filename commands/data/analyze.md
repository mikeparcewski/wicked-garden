---
description: Start interactive data analysis session for CSV/Excel files
argument-hint: "<file-path> [--focus <type>] [--context <file>] [--refresh] [--scenarios]"
phase_relevance: ["clarify", "design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:analyze

Interactive analysis on a CSV/Excel/data file. Use for one-off data exploration.
NOT for schema-level checks (use `data:data`) or pipeline review (use `data:pipeline`).

## Run it inline (no dispatch)

1. Parse `<file-path>`, `--focus` (stats|quality|warehouse|ml, default `stats`), `--context`, `--refresh`, `--scenarios`.
2. Read first rows of the file to capture column names / types / nulls / sample.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/data/refs/analyze.md")` — the EDA rubric, quality/warehouse/ml modes, insight pattern, and output format.
4. Apply the rubric directly for the chosen `--focus` mode and emit the analysis.
