# wicked-delivery

Feature delivery tactics: A/B test design, progressive rollouts, and delivery risk monitoring. Focused on how features ship safely.

Design statistically rigorous experiments, plan progressive rollouts with feature flags, and track delivery risks across the project lifecycle.

## Quick Start

```bash
# Install
claude plugin install wicked-delivery@wicked-garden

# Generate a sprint health report
/wicked-delivery:report sprint-health

# Design an A/B test
/wicked-delivery:design hypothesis="Larger CTA increases conversions"

# Plan a progressive rollout
/wicked-delivery:rollout feature=new-checkout strategy=canary
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-delivery:report` | Generate delivery reports | `/wicked-delivery:report sprint-health` |

## Skills

| Skill | What It Does | Example |
|-------|-------------|---------|
| `/wicked-delivery:design` | Design A/B tests with statistical rigor | `/wicked-delivery:design "Blue CTA increases clicks by 10%"` |
| `/wicked-delivery:rollout` | Plan progressive feature rollouts | `/wicked-delivery:rollout feature-new-dashboard` |
| `/wicked-delivery:reporting` | Multi-perspective delivery reporting | `/wicked-delivery:reporting project-export.json` |

## Workflows

### Experiment Design

```bash
/wicked-delivery:design "Larger CTA increases conversions by 10%"
# Outputs: hypothesis validation, sample size, duration, success criteria, monitoring plan
```

### Progressive Rollout

```bash
/wicked-delivery:rollout feature-new-checkout
# Outputs: risk assessment, rollout stages, monitoring, rollback plan
```

### Delivery Reporting

```bash
/wicked-delivery:reporting project-export.json
# Outputs: multi-perspective analysis from engineering, product, QE, operations, leadership
```

## Agents

| Agent | Focus |
|-------|-------|
| `experiment-designer` | A/B test design, hypothesis validation, statistical rigor |
| `rollout-manager` | Progressive rollouts, canary deployments, feature flags |
| `risk-monitor` | Delivery risk tracking, escalation management, dependency chains |

## Data API

This plugin exposes computed delivery metrics via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| metrics | stats | Computed delivery metrics (throughput, cycle time, backlog health, completion rate) from kanban task data |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-delivery/metrics/stats
```

Or directly via CLI:
```bash
python3 scripts/api.py stats metrics [--project PROJECT_ID]
```

Returns throughput (tasks/day over 14-day rolling window), cycle time (avg/median/p50/p75/p95 in hours), backlog health (aging count, oldest, average age), and completion rate. Requires wicked-kanban for task data; gracefully returns `{"available": false}` when kanban is not installed.

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Auto-engaged during delivery phases | Use commands directly |
| wicked-qe | Technical risk assessment and test validation | Manual risk analysis |
| wicked-kanban | Persistent tracking for experiments and rollouts | Session-only context |
| wicked-mem | Cross-session learning from past rollouts | Session-only context |
| wicked-product | Feature context for experiment design | Manual context gathering |

## License

MIT
