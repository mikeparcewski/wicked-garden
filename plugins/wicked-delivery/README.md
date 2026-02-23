# wicked-delivery

Turn vague "let's ship it" pressure into statistically rigorous experiment designs, risk-gated progressive rollouts, and multi-perspective delivery reports that engineering, product, and leadership all read differently.

## Quick Start

```bash
# Install
claude plugin install wicked-delivery@wicked-garden

# Design an A/B test from a hypothesis
/wicked-delivery:design "Larger CTA increases conversions by 10%"

# Plan a progressive rollout
/wicked-delivery:rollout feature-new-checkout
```

## Workflows

### Experiment Design: From Hypothesis to Launch Plan

Someone says "let's A/B test the checkout button." Without statistical rigor, that experiment will run too short, use the wrong metric, and produce inconclusive results. The design skill fixes that:

```bash
/wicked-delivery:design "Larger CTA increases conversions by 10%"
```

Output:
```
Hypothesis: Larger primary CTA increases checkout conversion rate by ≥10%
Primary metric: checkout_conversion_rate (binomial)
Guardrail metrics: page_load_time, bounce_rate, add_to_cart_rate

Sample size: 4,200 users per variant (MDE 10%, power 80%, alpha 0.05)
Duration: 14 days minimum (accounting for weekly seasonality)
Rollout: 10% → 50% → 100% with monitoring gates at each stage

Success criteria: p < 0.05 on primary metric, no regression on guardrails
Stopping rules: Harm threshold at -5% conversion OR p < 0.001 for early win
```

### Progressive Rollout with Rollback Plan

Feature flags without a plan are just risk deferred. The rollout skill builds the whole plan:

```bash
/wicked-delivery:rollout feature-new-checkout
```

Output:
```
Rollout: feature-new-checkout
Strategy: canary → staged → full

Stage 1 (5%): Internal users + beta opt-ins. Gate: error rate < 0.1%
Stage 2 (20%): Non-US traffic. Gate: p95 latency < 500ms, no payment errors
Stage 3 (50%): US East. Gate: conversion parity with control ± 2%
Stage 4 (100%): Full traffic. Monitor for 72h before flag cleanup

Rollback trigger: error rate > 0.5% OR any payment failure spike
Rollback time: < 2 min via flag flip. Owner: @platform-oncall
Monitoring: Datadog dashboard link + PagerDuty alert IDs
```

### Multi-Perspective Delivery Report

One project, five different stakeholders, five different questions. The reporting skill handles all of them from a single export:

```bash
/wicked-delivery:reporting project-export.json
```

Produces separate views for: engineering (velocity, cycle time, blockers), product (feature delivery, scope changes), QE (defect density, test coverage gaps), operations (reliability impact, deployment frequency), and leadership (timeline vs. plan, budget, risk).

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-delivery:report` | Generate multi-perspective delivery reports | `/wicked-delivery:report sprint-health` |
| `/wicked-delivery:setup` | Configure cost model, commentary sensitivity, sprint cadence | `/wicked-delivery:setup` |

## Skills

| Skill | What It Does | Example |
|-------|-------------|---------|
| `design` | Design A/B tests with statistical rigor | `/wicked-delivery:design "Blue CTA increases clicks by 10%"` |
| `rollout` | Plan progressive feature rollouts | `/wicked-delivery:rollout feature-new-dashboard` |
| `reporting` | Multi-perspective delivery reporting from project data | `/wicked-delivery:reporting project-export.json` |

## Agents

### Experimentation and Rollout

| Agent | Focus |
|-------|-------|
| `experiment-designer` | A/B test design, hypothesis validation, statistical rigor |
| `rollout-manager` | Progressive rollouts, canary deployments, feature flags |
| `risk-monitor` | Delivery risk tracking, escalation management, dependency chains |

### PMO

| Agent | Focus |
|-------|-------|
| `delivery-manager` | Sprint management, velocity tracking, scope management |
| `progress-tracker` | Milestone tracking, completion forecasting, slippage detection |
| `stakeholder-reporter` | Multi-perspective stakeholder reports, executive summaries |

### Onboarding

| Agent | Focus |
|-------|-------|
| `onboarding-guide` | New developer onboarding, contribution pathways |
| `codebase-narrator` | Codebase structure analysis, architecture walkthroughs |

### FinOps

| Agent | Focus |
|-------|-------|
| `finops-analyst` | Cloud cost analysis, billing interpretation, budget variance |
| `cost-optimizer` | Cost reduction, right-sizing, idle resource cleanup |
| `forecast-specialist` | Cost forecasting, capacity planning, timeline prediction |

## Data API

This plugin exposes computed delivery metrics via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| metrics | stats | Throughput, cycle time (avg/p50/p75/p95), backlog health, completion rate, effort allocation. Optional cost/ROI when cost model is configured. |
| commentary | list | Rule-based delivery insights from metric deltas, auto-refreshed on task changes |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-delivery/metrics/stats
GET /api/v1/data/wicked-delivery/commentary/list
```

Or directly via CLI:
```bash
python3 scripts/api.py stats metrics [--project PROJECT_ID]
python3 scripts/api.py list commentary
```

**Metrics**: Returns throughput (tasks/day over 14-day rolling window), cycle time (avg/median/p50/p75/p95 in hours), backlog health (aging count, oldest, average age), completion rate, and effort allocation. Requires wicked-kanban for task data; gracefully returns `{"available": false}` when kanban is not installed.

**Effort Allocation**: Breaks down task distribution by crew phase (clarify, design, build, test, review) and by signal dimension (security, architecture, data, etc.). Available when both wicked-kanban and wicked-crew are installed.

**Cost estimation** (opt-in): Run `/wicked-delivery:setup` or manually create `~/.something-wicked/wicked-delivery/cost_model.json`:

```json
{
  "currency": "USD",
  "priority_costs": { "P0": 2.50, "P1": 1.50, "P2": 0.75, "P3": 0.40 },
  "complexity_costs": { "0": 0.50, "1": 0.75, "2": 1.00, "3": 1.50, "4": 2.00, "5": 3.00, "6": 4.50, "7": 6.00 }
}
```

**Commentary**: Auto-refreshed by a PostToolUse hook on task changes. Default thresholds: completion rate >10%, cycle time p95 >25%, throughput >20%, backlog aging crossing 10/20. Tune via `/wicked-delivery:setup` or `~/.something-wicked/wicked-delivery/settings.json`.

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-crew | Auto-engaged during delivery phases | Use commands directly |
| wicked-qe | Technical risk assessment and test validation in rollout plans | Manual risk analysis |
| wicked-kanban | Persistent task data for metrics, commentary, and effort allocation | Metrics unavailable |
| wicked-mem | Cross-session learning from past rollout outcomes | Patterns lost between sessions |
| wicked-product | Feature context injected into experiment design | Manual context gathering |

## License

MIT
