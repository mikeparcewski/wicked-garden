---
description: "Design statistically rigorous A/B test experiments"
argument-hint: "<description> — describe what you want to test"
---

# /wicked-garden:delivery:experiment

Design experiments with proper hypothesis formulation, metric selection, sample size calculation, and instrumentation planning.

## Instructions

### 1. Parse Arguments

Extract the experiment description from arguments. If no description provided, ask for one.

### 2. Gather Context

Read any referenced files (feature specs, analytics configs, baseline metrics) from the current directory.

### 3. Dispatch to Experiment Designer

```
Task(
  subagent_type="wicked-garden:delivery:experiment-designer",
  prompt="""
  {user description}

  Working directory: {cwd}
  {File contents if referenced}

  Provide a comprehensive experiment design covering:
  1. Hypothesis formulation: "[Action] will [effect] [metric] by [amount] because [reason]"
  2. Metrics hierarchy: primary (ONE), secondary, guardrail
  3. Sample size calculation with stated assumptions (significance, power)
  4. Duration estimate based on traffic
  5. Control and treatment variant definitions
  6. Instrumentation plan (events, properties, tracking code)
  7. Success criteria and decision framework
  8. Risks and mitigations

  Return structured markdown suitable for stakeholder review.
  """
)
```

### 4. Present Results

Display the agent's experiment design document.
