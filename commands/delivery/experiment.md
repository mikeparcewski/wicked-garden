---
description: "Design statistically rigorous A/B test experiments"
argument-hint: "<description> — describe what you want to test"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:delivery:experiment

Design experiments with proper hypothesis formulation, metric selection, sample
size calculation, and instrumentation planning.

## Run it inline (no dispatch)

1. Parse the experiment `<description>` from arguments. If none provided, ask for one.
2. Read any referenced files (feature specs, analytics configs, baseline metrics) from the current directory.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/delivery/refs/experiment.md")` — hypothesis format, metrics hierarchy, sample-size rules, variant design, instrumentation plan, bus event, and output format.
4. Apply the rubric directly and emit the experiment design document.
