---
description: "Plan progressive feature rollouts with risk assessment"
argument-hint: "<description> — describe the feature to roll out"
---

# /wicked-garden:delivery:rollout

Plan safe, staged feature rollouts with risk assessment, canary deployment stages, monitoring, and rollback criteria.

## Instructions

### 1. Parse Arguments

Extract the rollout description from arguments. If no description provided, ask for one.

### 2. Gather Context

Read any referenced files (feature descriptions, baseline metrics, deployment configs) from the current directory.

### 3. Dispatch to Rollout Manager

```
Task(
  subagent_type="wicked-garden:delivery:rollout-manager",
  prompt="""
  {user description}

  Working directory: {cwd}
  {File contents if referenced}

  Provide a comprehensive rollout plan covering:
  1. Risk assessment: user impact, revenue impact, system criticality, reversibility
  2. Rollout strategy recommendation (canary, blue-green, ring-based)
  3. Staged rollout plan with traffic percentages, durations, and success criteria
  4. Success criteria with specific measurable thresholds
  5. Automatic rollback triggers (error rate, latency, revenue thresholds)
  6. Monitoring plan (dashboards, alerts with WARNING/CRITICAL levels)
  7. Communication plan (stakeholder matrix, templates)
  8. Rollback procedure (step-by-step)

  Return structured markdown suitable for team sign-off.
  """
)
```

### 4. Present Results

Display the agent's rollout plan document.
