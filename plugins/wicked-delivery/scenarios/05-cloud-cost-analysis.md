---
name: cloud-cost-analysis
title: Cloud Cost Analysis and Optimization
description: Analyze cloud spending, detect anomalies, and identify optimization opportunities
type: workflow
difficulty: intermediate
estimated_minutes: 10
---

# Cloud Cost Analysis and Optimization

This scenario validates that wicked-delivery can help engineering and finance teams understand cloud spending, detect cost anomalies, and identify optimization opportunities.

## Setup

Create a context simulating a company's cloud cost data:

```bash
# Create test project directory
mkdir -p ~/test-wicked-delivery/finops-analysis
cd ~/test-wicked-delivery/finops-analysis

# Create monthly cost data (simulating cloud billing export)
cat > monthly-costs.csv <<'EOF'
month,service,team,environment,cost
2024-09,EC2,platform,production,18450.00
2024-09,EC2,platform,staging,2340.00
2024-09,EC2,product,production,12890.00
2024-09,RDS,platform,production,8920.00
2024-09,RDS,product,production,4560.00
2024-09,S3,platform,production,3200.00
2024-09,S3,product,production,1890.00
2024-09,Lambda,platform,production,890.00
2024-09,CloudFront,marketing,production,2100.00
2024-09,Untagged,unknown,unknown,4500.00
2024-10,EC2,platform,production,19200.00
2024-10,EC2,platform,staging,2890.00
2024-10,EC2,product,production,13400.00
2024-10,RDS,platform,production,9100.00
2024-10,RDS,product,production,4780.00
2024-10,S3,platform,production,3450.00
2024-10,S3,product,production,2100.00
2024-10,Lambda,platform,production,1200.00
2024-10,CloudFront,marketing,production,2300.00
2024-10,Untagged,unknown,unknown,5200.00
2024-11,EC2,platform,production,19800.00
2024-11,EC2,platform,staging,8900.00
2024-11,EC2,product,production,14100.00
2024-11,RDS,platform,production,9300.00
2024-11,RDS,product,production,5100.00
2024-11,S3,platform,production,3700.00
2024-11,S3,product,production,2400.00
2024-11,Lambda,platform,production,2800.00
2024-11,CloudFront,marketing,production,2500.00
2024-11,Untagged,unknown,unknown,6100.00
EOF

# Create budget configuration
cat > budgets.json <<'EOF'
{
  "monthly_budget": 65000,
  "team_budgets": {
    "platform": 35000,
    "product": 25000,
    "marketing": 5000
  },
  "alerts": {
    "warning_threshold": 0.80,
    "critical_threshold": 0.95
  }
}
EOF

# Create resource inventory (for right-sizing analysis)
cat > resource-inventory.md <<'EOF'
# Cloud Resource Inventory

## EC2 Instances

### Platform Team - Production
| Instance ID | Type | vCPU | Memory | Avg CPU (14d) | Avg Mem (14d) |
|-------------|------|------|--------|---------------|---------------|
| i-prod-web-01 | m5.xlarge | 4 | 16GB | 12% | 45% |
| i-prod-web-02 | m5.xlarge | 4 | 16GB | 15% | 48% |
| i-prod-api-01 | m5.2xlarge | 8 | 32GB | 8% | 22% |
| i-prod-api-02 | m5.2xlarge | 8 | 32GB | 9% | 25% |
| i-prod-batch | c5.4xlarge | 16 | 32GB | 65% | 78% |

### Platform Team - Staging
| Instance ID | Type | vCPU | Memory | Avg CPU (14d) | Avg Mem (14d) |
|-------------|------|------|--------|---------------|---------------|
| i-stag-web-01 | m5.xlarge | 4 | 16GB | 3% | 18% |
| i-stag-api-01 | m5.xlarge | 4 | 16GB | 2% | 15% |
| i-stag-batch | m5.xlarge | 4 | 16GB | 45% | 60% |

## RDS Instances
| Instance ID | Type | Engine | Avg CPU | Storage |
|-------------|------|--------|---------|---------|
| db-prod-primary | db.r5.2xlarge | PostgreSQL | 35% | 500GB |
| db-prod-replica | db.r5.2xlarge | PostgreSQL | 12% | 500GB |

## EBS Volumes
- 15 unattached volumes totaling 450GB ($45/month)
- 8 old snapshots > 90 days ($120/month)
EOF

echo "Setup complete. FinOps context created."
```

## Steps

### 1. Analyze Current Spending

Ask the FinOps analyst for a cost breakdown:

```
Task tool: subagent_type="wicked-delivery:finops-analyst"
prompt="Analyze our cloud costs for November. Data is in monthly-costs.csv. Give me a breakdown by service and team."
```

**Expected Output**:
- **Total Spend**: $74,700 (November)
- **By Service**:
  | Service | Cost | % of Total | vs Last Month |
  |---------|------|------------|---------------|
  | EC2 | $42,800 | 57% | +9% |
  | RDS | $14,400 | 19% | +3% |
  | S3 | $6,100 | 8% | +8% |
  | Lambda | $2,800 | 4% | +133% |
  | CloudFront | $2,500 | 3% | +9% |
  | Untagged | $6,100 | 8% | +17% |
- **By Team**:
  | Team | Cost | Budget | Status |
  |------|------|--------|--------|
  | Platform | $44,500 | $35,000 | OVER |
  | Product | $21,600 | $25,000 | OK |
  | Marketing | $2,500 | $5,000 | OK |
  | Unknown | $6,100 | - | UNALLOCATED |

### 2. Detect Anomalies

Identify unusual spending patterns:

```
Task tool: subagent_type="wicked-delivery:finops-analyst"
prompt="What cost anomalies do you see? What's causing the spending increases?"
```

**Expected Output**:
- **Anomaly 1: Staging EC2 Spike**
  - November: $8,900 (vs $2,890 in October)
  - Change: +208%
  - Likely cause: New instances or forgot to terminate resources
  - **Action**: Investigate staging environment for orphaned instances

- **Anomaly 2: Lambda Growth**
  - November: $2,800 (vs $1,200 in October)
  - Change: +133%
  - Likely cause: New function deployment or increased invocations
  - **Action**: Review Lambda metrics for invocation counts

- **Anomaly 3: Untagged Costs Growing**
  - November: $6,100 (up from $4,500 in September)
  - Trend: +35% over 3 months
  - **Action**: Enforce tagging policy, identify untagged resources

### 3. Get Optimization Recommendations

Find savings opportunities:

```
Task tool: subagent_type="wicked-delivery:cost-optimizer"
prompt="Based on our resource inventory in resource-inventory.md, what cost optimization opportunities exist? What's the potential savings?"
```

**Expected Output**:
- **Priority 1: Right-Sizing (Quick Wins)**
  | Resource | Current | Recommended | Savings/mo |
  |----------|---------|-------------|------------|
  | i-prod-api-01 | m5.2xlarge | m5.xlarge | $95 |
  | i-prod-api-02 | m5.2xlarge | m5.xlarge | $95 |
  | i-stag-web-01 | m5.xlarge | t3.medium | $85 |
  | i-stag-api-01 | m5.xlarge | t3.medium | $85 |
  | db-prod-replica | db.r5.2xlarge | db.r5.xlarge | $340 |
  - **Total Right-Sizing Savings**: $700/month

- **Priority 2: Waste Elimination**
  - Delete 15 unattached EBS volumes: $45/month
  - Clean up old snapshots: $120/month
  - Shut down staging overnight: ~$150/month
  - **Total Waste Savings**: $315/month

- **Priority 3: Reserved Capacity** (for stable workloads)
  - Production EC2 fleet: 1-year RI saves ~30%
  - RDS instances: Reserved pricing saves ~35%
  - **Estimated Annual Savings**: $12,000-15,000

- **Total Potential Savings**: $1,015/month + $12-15K annual

### 4. Forecast Future Costs

Project spending forward:

```
Task tool: subagent_type="wicked-delivery:forecast-specialist"
prompt="Based on the trend in monthly-costs.csv, forecast our costs for the next quarter. Include best, likely, and worst case scenarios."
```

**Expected Output**:
- **Trend Analysis**:
  - Monthly growth rate: ~8% average
  - Key drivers: EC2 expansion, Lambda growth, untagged creep

- **Q1 Forecast**:
  | Month | Best Case | Likely | Worst Case |
  |-------|-----------|--------|------------|
  | Dec | $72,000 | $78,000 | $85,000 |
  | Jan | $75,000 | $84,000 | $95,000 |
  | Feb | $78,000 | $90,000 | $105,000 |

- **Budget Implications**:
  - Current quarterly budget: $195,000
  - Likely Q1 spend: $252,000
  - Gap: $57,000 over budget (29%)

- **Recommendations**:
  - Implement right-sizing immediately ($700/mo savings)
  - Address staging anomaly (~$6,000/mo savings)
  - Start reserved capacity planning for Q2

### 5. Generate Cost Report

Create a stakeholder-ready report:

```
Task tool: subagent_type="wicked-delivery:finops-analyst"
prompt="Generate a monthly FinOps report I can share with engineering leadership."
```

**Expected Output**:
```markdown
## Cloud Cost Report: November 2024

### Executive Summary
**Total Spend**: $74,700
**Budget**: $65,000
**Status**: OVER BUDGET (+15%)
**Trend**: Growing 8%/month

### Key Findings
1. Platform team 27% over budget ($44.5K vs $35K target)
2. Staging costs spiked 208% - investigation needed
3. $6,100 in untagged resources (no cost allocation)
4. Lambda costs up 133% - review deployment changes

### Cost by Service
[table]

### Cost by Team
[table]

### Optimization Opportunities
| Category | Monthly Savings | Effort |
|----------|----------------|--------|
| Right-sizing | $700 | Low |
| Waste cleanup | $315 | Low |
| Reserved capacity | $1,000 | Medium |
| **Total** | **$2,015** | |

### Recommendations
1. URGENT: Investigate staging EC2 spike
2. THIS WEEK: Delete unattached volumes and old snapshots
3. THIS MONTH: Right-size underutilized instances
4. Q1: Evaluate reserved capacity for stable workloads

### Forecast
Q1 likely spend: $252K (29% over budget without action)
With optimizations: $240K (23% over - still needs budget adjustment)
```

## Expected Outcome

- Clear cost breakdown by service, team, and environment
- Anomalies detected with magnitude and likely causes
- Optimization opportunities prioritized by savings and effort
- Forecast includes multiple scenarios
- Stakeholder report is actionable with specific recommendations
- If wicked-mem available: historical trends inform analysis

## Success Criteria

- [ ] Total cost calculated correctly from data
- [ ] Cost breakdown includes by-service and by-team views
- [ ] Budget comparison shows over/under status
- [ ] At least 2 cost anomalies identified with % change
- [ ] Anomalies include likely cause hypothesis
- [ ] Right-sizing recommendations based on CPU/memory utilization
- [ ] Waste recommendations (unattached volumes, old snapshots)
- [ ] Savings estimates provided in dollars
- [ ] Forecast includes best/likely/worst scenarios
- [ ] Report format suitable for leadership (executive summary first)
- [ ] Recommendations prioritized by urgency and effort

## Value Demonstrated

**Real-world value**: Cloud costs are one of the largest line items for technology companies, yet most teams have limited visibility into spending. Engineers spin up resources and forget them. Teams exceed budgets without knowing. Finance gets surprised at month-end.

wicked-delivery's FinOps capabilities provide:

1. **Cost visibility**: Clear breakdown eliminates "where did that $10K go?"
2. **Anomaly detection**: Catch spending spikes before they become budget crises
3. **Right-sizing guidance**: Match resource size to actual usage
4. **Waste elimination**: Find forgotten resources draining budget
5. **Forecasting**: Plan budgets with data, not guesses
6. **Accountability**: Team-level allocation enables cost ownership

For organizations spending $50K+/month on cloud, even 10% optimization represents significant savings. The finops-analyst and cost-optimizer agents apply the same analysis patterns used by dedicated FinOps teams, making cost discipline accessible to any engineering team.

The integration with wicked-mem means cost trends persist across sessions - you can track whether your optimization efforts are working over time.

## Integration Notes

**With wicked-mem**: Stores cost snapshots for trend analysis over months
**With wicked-search**: Finds resource configurations in IaC files
**With wicked-kanban**: Creates optimization tasks for tracking
**Standalone**: Works with provided cost data files

## Cleanup

```bash
rm -rf ~/test-wicked-delivery/finops-analysis
```
