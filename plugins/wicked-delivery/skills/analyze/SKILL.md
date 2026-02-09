---
name: analyze
description: |
  Cloud cost analysis and breakdown. Aggregate cost data from discovered cloud sources,
  analyze spending by service/team/project, detect anomalies, and provide cost visibility.

  Use when: "analyze cloud costs", "cost breakdown", "what are we spending",
  "cost by service", "cost anomalies", "budget tracking"
---

# Analyze Skill

Comprehensive cloud cost analysis with capability-based discovery.

## Purpose

Provide cost visibility through:
- Capability-based cloud cost discovery
- Multi-dimensional cost breakdown
- Anomaly detection
- Trend analysis
- Budget tracking

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-delivery:analyze` | Full cost analysis |
| `/wicked-delivery:analyze --anomalies` | Focus on cost spikes |
| `/wicked-delivery:analyze --team [name]` | Team-specific analysis |
| `/wicked-delivery:analyze --service [name]` | Service-specific |

## Process

### 1. Discover Cost Data Sources

Check for capabilities:
- **cloud-cost**: Cloud provider billing data
- **kubernetes-cost**: Container cost allocation
- **multi-cloud-cost**: Unified cost aggregation
- **infrastructure-cost**: IaC-based cost estimation
- **cost-optimization**: Recommendations engine

**Fallback hierarchy**: Cloud billing APIs → Multi-cloud platforms → IaC modeling → Manual entry

See [Capability Discovery](refs/discovery.md).

### 2. Aggregate Cost Data

**By Service**: Compute, Storage, Database, Network, Other
**By Dimension**: Team, Project, Environment, Region, Time

### 3. Calculate Metrics

Total spend, daily spend, cost per unit, change vs prior, top drivers

See [Cost Metrics](refs/metrics.md) for comprehensive KPIs.

### 4. Detect Anomalies

**Indicators**: >20% variance, new services, spikes, budget breaches

**Methods**: Threshold, statistical (Z-score), trend-based, service-specific

See [Anomaly Detection](refs/anomalies.md).

### 5. Generate Breakdown

Multi-dimensional analysis across service × team × environment × time.

### 6. Track vs Budget

Current vs budget, projected EOM spend, alert thresholds (50%, 80%, 100%)

## Integration

**wicked-mem**: Store/retrieve cost data
**wicked-search**: Find resource configurations
**wicked-kanban**: Track cost reviews

## Output Format

```markdown
## Cloud Cost Analysis: {Period}

### Executive Summary
**Total Spend**: ${total}
**Change**: {+/-}% vs {prior}
**Budget Status**: {ON TRACK | OVER | UNDER}
**Top Drivers**: {top 3}

### Cost Breakdown

#### By Service
| Service | Current | Prior | Change | % Total |
{rows}

#### By Team
| Team | Cost | Budget | Variance |
{rows}

### Anomalies
- {service}: ${amount} ({%}) - {reason}

### Budget Tracking
**Cap**: ${budget}
**Current**: ${current} ({%}%)
**Projected**: ${projected}

### Recommendations
1. {action}
```

## Data Requirements

**Minimum**: Cost by service, total spend
**Recommended**: 6+ months history, tags, usage metrics, budgets
**Optimal**: Real-time APIs, resource-level granularity, business metrics

## Capability Discovery

Query for available cost capabilities at runtime:

### cloud-cost Capability

Provides cloud provider billing and usage data. Tools exposing this capability offer service-level breakdowns, cost allocation tags, and time-series data.

### kubernetes-cost Capability

Provides container-level cost allocation, namespace/pod costs, and efficiency metrics for Kubernetes workloads.

### multi-cloud-cost Capability

Provides unified cost aggregation across multiple cloud providers with normalized reporting and cross-provider analytics.

### infrastructure-cost Capability

Provides cost estimation based on infrastructure-as-code definitions. Useful for planning and "what-if" scenarios.

See [Discovery Patterns](refs/discovery.md) for detailed capability detection logic.

## Events

Published:
- `[finops:analysis:started:success]`
- `[finops:analysis:completed:success]`
- `[finops:anomaly:detected:warning]`

## Configuration

```yaml
analysis:
  default_period: monthly
  anomaly_threshold: 20
  currency: USD

tagging:
  required_tags: [Team, Project, Environment]
```

## Tips

1. **Tag Everything**: Enables cost allocation
2. **Review Regularly**: Weekly checks, monthly deep dives
3. **Compare Periods**: Trends matter
4. **Investigate Spikes**: Every anomaly needs explanation
5. **Share Widely**: Transparency drives accountability

## Reference Materials

- [Capability Discovery](refs/discovery.md) - Find cloud cost tools
- [Anomaly Detection Methods](refs/anomalies.md) - Detect spikes
- [Cost Metrics Reference](refs/metrics.md) - FinOps KPIs
