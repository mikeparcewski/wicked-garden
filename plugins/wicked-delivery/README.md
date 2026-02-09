# wicked-delivery

Delivery management that goes beyond task tracking. Sprint health reports in seconds, personalized developer onboarding with learning paths, A/B test design with statistical rigor, and FinOps cost optimization.

The PM stuff Claude Code doesn't do by default -- 11 AI agents covering sprint health, developer onboarding, experiment design, progressive rollouts, and cost savings, all in one plugin.

## Quick Start

```bash
# Install
claude plugin install wicked-delivery@wicked-garden

# Generate a sprint health report
/wicked-delivery:report sprint-health

# Onboard a new developer
/wicked-delivery:guide auth-system

# Design an A/B test
/wicked-delivery:design hypothesis="Larger CTA increases conversions"

# Find cost savings
/wicked-delivery:optimize target=20% focus=compute
```

## Commands & Skills

### Reporting

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-delivery:report` | Generate delivery reports | `/wicked-delivery:report sprint-health` |

### Developer Onboarding

| Skill | What It Does | Example |
|-------|-------------|---------|
| `/wicked-delivery:guide` | Create personalized learning paths | `/wicked-delivery:guide auth-system` |
| `/wicked-delivery:orient` | Codebase orientation walkthrough | `/wicked-delivery:orient component=payments` |
| `/wicked-delivery:explain` | Deep code explanations | `/wicked-delivery:explain file=src/core.ts` |

### Experiments & Rollouts

| Skill | What It Does | Example |
|-------|-------------|---------|
| `/wicked-delivery:design` | Design A/B tests with statistical rigor | `/wicked-delivery:design hypothesis="..."` |
| `/wicked-delivery:rollout` | Plan progressive feature rollouts | `/wicked-delivery:rollout feature=new-checkout strategy=canary` |
| `/wicked-delivery:analyze` | Analyze experiment results | `/wicked-delivery:analyze experiment-id=test-1` |

### Cost Optimization

| Skill | What It Does | Example |
|-------|-------------|---------|
| `/wicked-delivery:forecast` | Project future infrastructure costs | `/wicked-delivery:forecast period=Q2` |
| `/wicked-delivery:optimize` | Find savings opportunities | `/wicked-delivery:optimize target=20% focus=compute` |

## Workflows

### Sprint Health Check

```bash
/wicked-delivery:report sprint-health    # Generate report
# Then use agents for deeper analysis:
# delivery-manager for velocity tracking
# risk-monitor for blockers
# stakeholder-reporter for exec summary
```

### Developer Onboarding

```bash
/wicked-delivery:guide new-developer focus=backend   # Learning path
/wicked-delivery:orient component=authentication     # System walkthrough
/wicked-delivery:explain file=src/auth/jwt.ts        # Deep dive on code
```

### Cost Optimization

```bash
/wicked-delivery:optimize target=20% focus=compute   # Find savings
/wicked-delivery:forecast period=Q2                  # Project impact
```

## Agents

| Agent | Focus |
|-------|-------|
| `delivery-manager` | Sprint management, velocity tracking |
| `progress-tracker` | Task completion, delivery forecasting |
| `risk-monitor` | Risk identification, escalation |
| `stakeholder-reporter` | Multi-stakeholder communication |
| `onboarding-guide` | Personalized learning paths |
| `codebase-narrator` | Interactive code walkthroughs |
| `experiment-designer` | A/B test design, hypothesis validation |
| `rollout-manager` | Progressive rollouts, feature flags |
| `finops-analyst` | Cost allocation, budget tracking |
| `cost-optimizer` | Right-sizing, savings identification |
| `forecast-specialist` | Cost projections, trend analysis |

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Integrated into delivery phases | Use commands directly |
| wicked-kanban | Persistent task tracking for reports | Session-only context |
| wicked-mem | Cross-session learning | Session-only context |
| wicked-workbench | Sprint boards, burndown charts | Text output only |

## License

MIT
