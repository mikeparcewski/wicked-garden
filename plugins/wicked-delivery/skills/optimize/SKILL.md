---
name: optimize
description: |
  Cloud cost optimization recommendations. Right-sizing analysis, reserved capacity planning,
  spot instance opportunities, waste detection, and architecture cost reviews.

  Use when: "optimize costs", "reduce cloud spending", "right-size resources",
  "find savings", "unused resources", "cost recommendations"
---

# Optimize Skill

Identify and prioritize cloud cost optimization opportunities.

## Purpose

Drive cost efficiency through:
- Right-sizing recommendations
- Reserved capacity analysis
- Spot instance opportunities
- Waste elimination
- Architecture cost reviews

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-delivery:optimize` | Full optimization analysis |
| `/wicked-delivery:optimize --quick-wins` | Immediate savings |
| `/wicked-delivery:optimize --rightsizing` | Instance sizing |
| `/wicked-delivery:optimize --reservations` | RI/savings plans |
| `/wicked-delivery:optimize --waste` | Find unused resources |

## Process

### 1. Discover Usage Data

Check for capabilities:
- **resource-monitoring**: CPU, memory, disk, network metrics
- **cost-optimization**: Built-in recommendation engines
- **infrastructure-cost**: Resource specifications

**Fallback**: Work with resource specs and estimates

### 2. Right-Sizing Analysis

Collect 7-14 day metrics: CPU, memory, network, disk

**Criteria**:
- <20% CPU/memory → Downsize
- >80% sustained → Upsize
- Spiky → Auto-scaling

See [Right-Sizing](refs/rightsizing.md) for methodology.

### 3. Reserved Capacity

Find 24/7 workloads (>70% uptime), compare on-demand vs reserved costs, recommend term.

Commitment types vary by provider but all offer similar savings for predictable workloads.

See [Reservations](refs/reservations.md).

### 4. Spot Opportunities

**Good**: Batch jobs, CI/CD, data processing, stateless services, dev/test
**Bad**: Databases, single points of failure, real-time services

### 5. Waste Detection

Scan for: Idle instances, unattached volumes, old snapshots, orphaned IPs, unused load balancers

See [Waste Checklist](refs/waste.md).

### 6. Architecture Review

Cost-sensitive patterns: Data transfer, database architecture, storage tiering, caching

### 7. Prioritize

**Quick Wins**: Delete unused, right-size obvious
**High Value**: RI purchases, spot migration
**Strategic**: Architecture refactoring

## Integration

**wicked-mem**: Store optimization results
**wicked-search**: Find resource configurations

## Output Format

```markdown
## Cost Optimization Analysis

### Executive Summary
**Total Savings**: ${total}/month (${annual}/year)
**Quick Wins**: ${quick}/month

### Priority 1: Quick Wins
1. Delete 15 unattached EBS volumes - $200/mo
2. Right-size i-xyz789 - $35/mo

### Priority 2: Reserved Capacity
Production DB fleet - $1,680/mo savings

### Priority 3: Spot Migration
CI/CD fleet - $584/mo savings

### Priority 4: Architecture
Add caching - $200/mo savings

### Implementation Roadmap
**Week 1**: Quick wins ($350/mo)
**Week 2-3**: Reserved capacity ($1,680/mo)
**Month 2**: Spot migration ($584/mo)

**Total 90-day savings**: $2,814/month

### ROI
**Annual savings**: $33,768
**Implementation cost**: $8,000
**Payback**: 8 days
```

## Events

Published:
- `[finops:optimization:identified:success]`
- `[finops:optimization:completed:success]`
- `[finops:savings:validated:success]`

Subscribed:
- `[arch:design:completed:success]`

## Configuration

```yaml
optimization:
  min_savings_threshold: 100
  rightsizing:
    cpu_downsize_threshold: 20
    memory_downsize_threshold: 30
    evaluation_period_days: 14
  reservations:
    min_utilization: 70
    default_term: 1
```

## Tips

1. **Start with waste**: Easiest wins
2. **Measure first**: Use actual metrics
3. **Pilot changes**: Test before rollout
4. **Track savings**: Validate predictions
5. **Continuous review**: Ongoing process
6. **Balance risk**: Don't sacrifice reliability

## Reference Materials

- [Right-Sizing Methodology](refs/rightsizing.md)
- [Reserved Capacity Guide](refs/reservations.md)
- [Waste Detection Patterns](refs/waste.md)
