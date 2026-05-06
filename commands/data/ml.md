---
description: "ML model review and training pipeline design"
argument-hint: "<subcommand> [args...] — review <path> | pipeline --type <classification|regression|ranking>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:ml

ML model `review` and training-`pipeline` design. Use this for model-side work. NOT for ETL pipeline design (use `data:pipeline`) or data profiling (use `data:data`).

## 1. Arg parse + gather

Extract `subcommand` (review|pipeline) and args (`<path>` for review, `--type <classification|regression|ranking>` for pipeline). For review, read model files at `<path>`.

## 2. Dispatch

```
Task(subagent_type="wicked-garden:data:ml-engineer",
     prompt="""Run ML {subcommand}. Path: {path or n/a}. Task type: {type or n/a}. For review: cover leakage, evaluation, features, imbalance, production readiness, P1/P2/P3, model card. For pipeline: cover problem setup, data/feature stages, model arch, evaluation, tuning, deployment, monitoring. Return structured markdown.""")
```
