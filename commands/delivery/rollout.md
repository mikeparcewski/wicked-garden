---
description: "Plan progressive feature rollouts with risk assessment"
argument-hint: "<description> — describe the feature to roll out"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:delivery:rollout

Plan safe, staged feature rollouts with risk assessment, canary deployment
stages, monitoring, and rollback criteria.

## Run it inline (no dispatch)

1. Parse the rollout `<description>` from arguments. If none provided, ask for one.
2. Read any referenced files (feature descriptions, baseline metrics, deployment configs) from the current directory.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/delivery/refs/rollout.md")` — risk assessment matrix, strategy-by-risk table, stage definition template, alert thresholds, bus event, and output format.
4. Apply the rubric directly and emit the rollout plan document.
