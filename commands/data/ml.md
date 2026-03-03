---
description: "ML model review and training pipeline design"
argument-hint: "<subcommand> [args...] — review <path> | pipeline --type <classification|regression|ranking>"
---

# /wicked-garden:data:ml

Review machine learning models and design training pipelines.

## Instructions

### 1. Parse Arguments

Extract the subcommand and its arguments:
- `review <path>` — Review ML model code for issues and production readiness
- `pipeline --type <type>` — Design a training pipeline for the given task type

If no subcommand is given, show usage and exit.

### 2. Gather Context

For `review`: Read the model files at the given path (model code, prediction scripts, configs).
For `pipeline`: Collect the task type and any additional context from the user.

### 3. Dispatch to ML Engineer

```
Task(
  subagent_type="wicked-garden:data:ml-engineer",
  prompt="""
  Perform ML {subcommand}.

  Subcommand: {subcommand}
  {Path: {path} with file contents (if review)}
  {Task type: {type} (if pipeline)}

  For 'review':
  1. Check for data leakage (time-based features using now(), future info)
  2. Assess evaluation methodology (metrics, cross-validation, baselines)
  3. Review feature engineering (consistency between train/inference, documentation)
  4. Check class imbalance handling
  5. Evaluate production readiness:
     - Model versioning
     - Input validation
     - Monitoring hooks
     - Error handling
     - Latency considerations
  6. Prioritize findings as P1 (critical), P2 (high), P3 (medium)
  7. Generate a model card for documentation
  8. Provide specific code fixes for critical issues

  For 'pipeline':
  1. Define problem setup (task type, success metrics, baseline)
  2. Design data loading and feature engineering stages
  3. Recommend model architecture based on data size and type
  4. Design evaluation framework (metrics, splits, cross-validation)
  5. Plan hyperparameter tuning strategy
  6. Design deployment pattern (batch/API/streaming)
  7. Add monitoring (drift detection, performance tracking)

  Return structured markdown with code examples and checklists.
  """
)
```

### 4. Present Results

Display the agent's findings:

```markdown
## ML {Subcommand}: {path or type}

{agent findings}
```
