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
| `/wicked-delivery:setup` | Configure cost model, commentary, and metrics | `/wicked-delivery:setup` |

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
| metrics | stats | Computed delivery metrics (throughput, cycle time, backlog health, completion rate, effort allocation, optional cost/ROI) from kanban task data |
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

**Effort Allocation**: Breaks down task distribution by crew phase (clarify, design, test-strategy, build, test, review) and by signal dimension (security, architecture, data, etc.) from crew project signals. Detects phases from task subject prefixes and maps signals via crew's `project.json`. Available when both wicked-kanban and wicked-crew are installed.

**Cost estimation** (opt-in): Run `/wicked-delivery:setup` or manually create `~/.something-wicked/wicked-delivery/cost_model.json`:

```json
{
  "currency": "USD",
  "priority_costs": { "P0": 2.50, "P1": 1.50, "P2": 0.75, "P3": 0.40 },
  "complexity_costs": { "0": 0.50, "1": 0.75, "2": 1.00, "3": 1.50, "4": 2.00, "5": 3.00, "6": 4.50, "7": 6.00 }
}
```

When configured, `stats metrics` includes cost/ROI fields. Without this file, no cost data is returned.

**Commentary**: Auto-refreshed by a PostToolUse hook on task changes. Regenerates when metrics cross configurable thresholds with a cooldown period. Default thresholds: completion rate >10%, cycle time p95 >25%, throughput >20%, backlog aging crossing 10/20. Tune via `/wicked-delivery:setup` or `~/.something-wicked/wicked-delivery/settings.json`.

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
