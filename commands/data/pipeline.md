---
description: "Data pipeline design and review"
argument-hint: "<subcommand> [args...] — design --source <src> --target <tgt> [--frequency <freq>] | review <path>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:pipeline

Data pipeline `design` and `review`. Use this for ETL/streaming pipeline architecture. NOT for ML training pipelines (use `data:ml`) or one-off file analysis (use `data:analyze`).

## 1. Arg parse + gather

Extract `subcommand` (design|review) and args. For review, read pipeline files at `<path>`. For design, capture `--source`, `--target`, `--frequency`.

## 2. Dispatch

```
Task(subagent_type="wicked-garden:data:data-engineer",
     prompt="""Run pipeline {subcommand}. Path: {path or n/a}. Source/Target/Frequency: {src or n/a} / {tgt or n/a} / {freq or n/a}. For review: code quality, idempotency, monitoring, validation, silent-loss, P1/P2/P3 with code fixes. For design: architecture pattern, orchestrator, stage flow, quality gates, monitoring, costs, risks. Return structured markdown.""")
```
