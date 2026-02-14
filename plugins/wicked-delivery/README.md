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
