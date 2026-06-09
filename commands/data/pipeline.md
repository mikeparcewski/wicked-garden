---
description: "Data pipeline design and review"
argument-hint: "<subcommand> [args...] — design --source <src> --target <tgt> [--frequency <freq>] | review <path>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:pipeline

Data pipeline `design` and `review`. NOT for ML training pipelines (use `data:ml`)
or one-off file analysis (use `data:analyze`).

## Run it inline (no dispatch)

1. Parse `subcommand` (design|review) and args. For `review`, read pipeline files at `<path>`. For `design`, capture `--source`, `--target`, `--frequency`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/data/refs/pipeline.md")` — the design checklist, review rubric with P1/P2/P3 findings, and engineering standards.
3. Apply the rubric for the requested subcommand and emit structured markdown.
