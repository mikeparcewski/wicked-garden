---
description: "ML model review and training pipeline design"
argument-hint: "<subcommand> [args...] — review <path> | pipeline --type <classification|regression|ranking>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:ml

ML model `review` and training-`pipeline` design. NOT for ETL pipeline design
(use `data:pipeline`) or data profiling (use `data:data`).

## Run it inline (no dispatch)

1. Parse `subcommand` (review|pipeline) and args (`<path>` for review, `--type` for pipeline).
2. For `review`, read model files at `<path>`.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/data/refs/ml.md")` — the model review checklist, pipeline design template, deployment readiness checklist, and MLOps standards.
4. Apply the rubric for the requested subcommand and emit structured markdown.
