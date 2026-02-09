# Cost Metrics Reference

Comprehensive guide to FinOps cost metrics and KPIs.

## Core Cost Metrics

### Absolute Metrics

**Total Spend**
```
Sum of all costs for a given period
Use: Overall budget tracking
```

**Cost by Service**
```
Breakdown: Compute, Storage, Network, Database, Other
Use: Identify major cost drivers
```

**Cost by Team/Project**
```
Tag-based allocation
Use: Chargeback, showback, accountability
```

**Cost by Environment**
```
Production, Staging, Development
Use: Rightsize non-production spending
```

### Relative Metrics

**Cost Change**
```
Change = (Current - Prior) / Prior × 100%
Use: Trend analysis
```

**Cost per Unit**
```
Examples:
- Cost per user
- Cost per transaction
- Cost per GB stored
- Cost per API call

Use: Efficiency metrics, scaling analysis
```

**Budget Variance**
```
Variance = (Actual - Budget) / Budget × 100%
Use: Budget tracking
```

## Efficiency Metrics

### Utilization Metrics

**Compute Utilization**
```
CPU Utilization = Avg CPU% over period
Memory Utilization = Avg Memory% over period

Targets:
- Production: 60-70% (headroom for spikes)
- Non-production: 40-50%
- Batch: 80-90%
```

**Storage Utilization**
```
Active Data Ratio = Frequently accessed / Total storage
Target: Maximize hot tier usage, move cold to cheaper tiers
```

**Reserved Instance Utilization**
```
RI Utilization = Hours used / Hours purchased × 100%
Target: >90% utilization
```

### Waste Metrics

**Idle Resources**
```
Resources with <5% utilization over 7+ days
Cost impact: Full cost, zero value
```

**Unattached Storage**
```
EBS volumes, disk snapshots with no attached instance
Cost impact: Ongoing storage costs for unused data
```

**Orphaned Resources**
```
Load balancers with no targets, IPs with no instances
Cost impact: Service charges for unused infrastructure
```

## FinOps KPIs

### Cost Avoidance

```
Cost Avoidance = What we would have spent - What we did spend

Examples:
- Rightsizing: $10k/mo → $6k/mo = $4k avoidance
- Spot instances: $5k/mo → $1k/mo = $4k avoidance
- RI purchases: $8k/mo → $5k/mo = $3k avoidance
```

### Cost Optimization Rate

```
Optimization Rate = Savings realized / Total spend × 100%

Benchmarks:
- 5-10%: Good
- 10-15%: Excellent
- >15%: Outstanding (or massively over-provisioned initially)
```

### Unit Economics

```
Cost per Customer = Total infrastructure cost / Active customers
Cost per Transaction = Total infrastructure cost / Transactions

Use: Track efficiency over time as you scale
Goal: Decreasing unit costs (economies of scale)
```

### Coverage Metrics

**Tagging Coverage**
```
Tagged Resources = Resources with required tags / Total resources × 100%
Target: >90% coverage for accurate allocation
```

**RI/Savings Plan Coverage**
```
Commitment Coverage = Hours covered / Total hours × 100%
Target: 60-80% (balance commitment with flexibility)
```

## Benchmarking Metrics

### Cloud Spend as % of Revenue

```
Cloud Efficiency Ratio = Annual cloud spend / Annual revenue × 100%

Industry benchmarks (SaaS):
- Early stage: 20-30%
- Growth stage: 10-20%
- Mature: 5-10%
```

### Infrastructure Cost per Employee

```
Cost per Employee = Monthly infrastructure cost / Number of employees

Varies widely by industry and stage
Use: Track changes over time, not absolute benchmarks
```

## Trend Metrics

### Month-over-Month Growth

```
MoM Growth = (Current month - Prior month) / Prior month × 100%

Compare to:
- Revenue growth
- User growth
- Transaction growth

Goal: Infrastructure growth < business growth (improving efficiency)
```

### Run Rate

```
Annual Run Rate = Current monthly spend × 12

Use: Project annual costs from current spending
Warning: Assumes no growth or changes
```

### Forecast Accuracy

```
Forecast Error = |Forecasted - Actual| / Actual × 100%

Targets:
- 1-month forecast: <5% error
- 3-month forecast: <10% error
- 12-month forecast: <20% error
```

## Anomaly Detection Metrics

### Standard Deviation Method

```
Upper Bound = Mean + (2 × Standard Deviation)
Lower Bound = Mean - (2 × Standard Deviation)

Anomaly: Any value outside bounds
```

### Percentage Change Threshold

```
Anomaly if: |Current - Prior| / Prior > Threshold

Common thresholds:
- 20%: Standard sensitivity
- 30%: Lower sensitivity (fewer alerts)
- 10%: High sensitivity (more alerts)
```

### Z-Score Method

```
Z-Score = (Value - Mean) / Standard Deviation

Anomaly if: |Z-Score| > 2
```

## Business Alignment Metrics

### Cost per Feature

```
Feature Cost = Infrastructure cost attributed to feature / Time period

Use: Prioritize feature investments by cost/value
```

### Environment Ratio

```
Prod:Non-Prod Ratio = Production cost / Non-production cost

Typical ratios:
- Early stage: 1:1 (heavy experimentation)
- Growth: 2:1 to 3:1
- Mature: 4:1 to 5:1
```

### Innovation Budget

```
Innovation % = R&D infrastructure / Total infrastructure × 100%

Typical: 10-20% for healthy innovation
```

## Reporting Frequency

**Daily**:
- Total spend (quick check)
- Anomaly alerts

**Weekly**:
- Service breakdown
- Top spenders
- Budget tracking

**Monthly**:
- Full cost analysis
- Team allocation
- Optimization review
- Forecast update

**Quarterly**:
- Strategic cost review
- RI/savings plan analysis
- Efficiency trends
- Benchmark comparison

## Metric Selection Guide

**For executives**:
- Total spend
- Budget variance
- MoM growth
- Cost as % of revenue

**For engineering teams**:
- Cost by service
- Cost by team
- Utilization metrics
- Waste metrics

**For FinOps team**:
- All of the above
- Tagging coverage
- RI utilization
- Forecast accuracy
- Optimization opportunities
