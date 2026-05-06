---
description: Generate actionable recommendations from customer feedback insights
argument-hint: "[--priority high|medium|low|critical] [--feature X] [--format brief|detailed]"
next-step: null
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:synthesize

Translate customer feedback analysis into prioritized, evidence-backed action items. Step 3 of 3 in the voice pipeline (`listen` → `analyze` → `synthesize`). Use after `/wicked-garden:product:analyze` has produced themes/sentiment/trends. Pass `--priority` to filter, `--feature` to scope, `--format` for output depth.

## 1. Locate analysis input

```bash
PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
ls "${PRODUCT_ROOT}/voice/analysis/"
```

If empty, tell user to run `/wicked-garden:product:analyze` first and stop.

## 2. Dispatch

```
Task(subagent_type="wicked-garden:product:user-voice",
     prompt="""Synthesize customer feedback into prioritized recommendations.
Analysis source: {PRODUCT_ROOT}/voice/analysis/  Priority filter: {--priority or 'all'}
Feature focus: {--feature or 'all'}  Format: {--format or 'detailed'}
Apply impact × frequency × trend × effort × risk-of-inaction prioritization. Levels: critical/high/medium/low.
For each: action, evidence (quotes + numbers + segment), expected outcome, risk of inaction, effort (S/M/L/XL), dependencies.
Also identify quick wins, strategic initiatives, and metrics to track. Return inline.""")
```
