---
description: "Data pipeline design and review"
argument-hint: "<subcommand> [args...] — design --source <src> --target <tgt> [--frequency <freq>] | review <path>"
---

# /wicked-garden:data:pipeline

Design new data pipelines and review existing pipeline architecture for best practices, performance, and reliability.

## Instructions

### 1. Parse Arguments

Extract the subcommand and its arguments:
- `design --source <src> --target <tgt> [--frequency <freq>]` — Design a new pipeline
- `review <path>` — Review an existing pipeline directory

If no subcommand is given, show usage and exit.

### 2. Gather Context

For `review`: Read the pipeline files at the given path (scripts, configs, DAG definitions).
For `design`: Collect the source, target, and frequency parameters.

### 3. Dispatch to Data Engineer

```
Task(
  subagent_type="wicked-garden:data:data-engineer",
  prompt="""
  Perform pipeline {subcommand}.

  Subcommand: {subcommand}
  {Path: {path} with file contents (if review)}
  {Source: {src}, Target: {tgt}, Frequency: {freq} (if design)}

  For 'review':
  1. Analyze code quality, error handling, and security (credential management)
  2. Check for idempotency and incremental processing
  3. Assess logging, monitoring, and alerting
  4. Evaluate data validation between stages
  5. Check for silent data loss (e.g., dropna without logging)
  6. Prioritize findings as P1 (critical), P2 (high), P3 (medium)
  7. Provide specific remediation code examples

  For 'design':
  1. Recommend architecture pattern (batch ETL, streaming, incremental)
  2. Suggest orchestration tool (Airflow, Dagster, Prefect)
  3. Design data flow with stages (extract, transform, validate, load)
  4. Define quality gates between stages
  5. Plan monitoring (row counts, latency, error rates)
  6. Estimate costs
  7. Assess risks and mitigations

  Return structured markdown with architecture diagrams (ASCII), code examples, and checklists.
  """
)
```

### 4. Present Results

Display the agent's findings:

```markdown
## Pipeline {Subcommand}: {path or description}

{agent findings}
```
