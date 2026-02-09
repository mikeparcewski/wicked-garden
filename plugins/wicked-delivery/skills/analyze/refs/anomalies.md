# Cost Anomaly Detection Methods

Techniques for identifying unusual cost patterns and spikes.

## Anomaly Definition

A cost anomaly is a significant deviation from expected spending patterns that warrants investigation.

**Not all increases are anomalies**:
- Planned growth: Expected
- Known events: Product launch, marketing campaign
- Seasonal patterns: Holiday traffic, quarter-end

**True anomalies**:
- Unexpected spikes
- Gradual drift from baseline
- New services appearing
- Configuration mistakes

## Detection Methods

### 1. Threshold-Based Detection

**Simple percentage change**:

```
Threshold: 20% (configurable)

If: |Current - Prior| / Prior > 0.20
Then: ANOMALY
```

**Example**:
```
Prior month: $10,000
Current: $13,000
Change: +30% → ANOMALY (exceeds 20% threshold)

Prior month: $10,000
Current: $11,500
Change: +15% → NORMAL (below threshold)
```

**Pros**:
- Simple to understand
- Easy to configure
- Fast to compute

**Cons**:
- Fixed threshold misses context
- Doesn't account for growth trends
- High false positive rate

**Best for**: Quick checks, obvious spikes

### 2. Statistical Methods

#### Standard Deviation

**Method**:
```
1. Calculate mean and std dev of historical costs
2. Define bounds: Mean ± (2 × Std Dev)
3. Flag values outside bounds
```

**Example**:
```
Historical costs: [$9k, $10k, $11k, $9.5k, $10.5k, $12k]
Mean: $10.33k
Std Dev: $1.03k

Upper bound: $10.33k + (2 × $1.03k) = $12.39k
Lower bound: $10.33k - (2 × $1.03k) = $8.27k

Current: $15k → ANOMALY (exceeds upper bound)
```

**Pros**:
- Accounts for historical variance
- Mathematically sound
- Adjusts to data patterns

**Cons**:
- Requires sufficient history (20+ data points)
- Assumes normal distribution
- Sensitive to outliers

**Best for**: Stable, predictable workloads

#### Z-Score

**Method**:
```
Z-Score = (Value - Mean) / Std Dev

If |Z-Score| > 2: ANOMALY
```

**Example**:
```
Mean: $10k, Std Dev: $1k
Current: $13k

Z-Score = ($13k - $10k) / $1k = 3
|3| > 2 → ANOMALY
```

**Interpretation**:
- Z-Score 1-2: Moderate deviation
- Z-Score 2-3: Significant anomaly
- Z-Score >3: Major anomaly

**Best for**: Datasets with known variance

### 3. Trend-Based Detection

#### Moving Average

**Method**:
```
1. Calculate moving average (e.g., 3-month)
2. Define acceptable deviation (e.g., ±25%)
3. Flag if current exceeds deviation
```

**Example**:
```
Costs: [Jan: $9k, Feb: $10k, Mar: $11k, Apr: $15k]

3-month moving avg (for Apr): ($9k + $10k + $11k) / 3 = $10k
Apr actual: $15k
Deviation: ($15k - $10k) / $10k = +50% → ANOMALY (exceeds 25%)
```

**Pros**:
- Smooths out noise
- Adapts to trends
- Good for growing workloads

**Cons**:
- Lags current state
- Needs sufficient history

**Best for**: Growth scenarios, seasonal patterns

#### Exponential Smoothing

**Method**:
```
Forecast = α × Actual + (1-α) × Prior_Forecast
α = 0.3 (typical)

Anomaly if: |Actual - Forecast| / Forecast > threshold
```

**Pros**:
- Emphasizes recent data
- Responsive to changes
- Requires minimal history

**Best for**: Fast-changing environments

### 4. Service-Specific Detection

#### New Service Detection

**Method**:
```
1. Track services with costs > $0 this period
2. Compare to prior period services
3. Flag new services not in baseline
```

**Example**:
```
Prior services: [EC2, RDS, S3]
Current services: [EC2, RDS, S3, Lambda, SageMaker]

New services detected: Lambda, SageMaker
→ Investigate: Why were these services started?
```

**Best for**: Catching unplanned deployments

#### Service Growth Outliers

**Method**:
```
1. Calculate growth rate per service
2. Flag services with outlier growth
```

**Example**:
```
Overall growth: +10%

Service growth:
- EC2: +12% (normal)
- RDS: +8% (normal)
- S3: +150% (ANOMALY - investigate)
```

### 5. Resource-Level Detection

#### Instance Type Changes

**Method**:
```
Track instance type distribution over time
Flag significant shifts
```

**Example**:
```
Prior: 80% t3.medium, 20% m5.large
Current: 50% t3.medium, 50% m5.2xlarge

→ ANOMALY: Shift to much larger instances
→ Investigate: Why the upsizing?
```

#### Region Distribution

**Method**:
```
Track cost by region
Flag unusual regional activity
```

**Example**:
```
Typical: 90% us-east-1, 10% us-west-2
Current: 60% us-east-1, 30% eu-west-1, 10% us-west-2

→ ANOMALY: New EU spend
→ Investigate: Test deployment? Customer expansion?
```

## Root Cause Analysis

Once anomaly detected, investigate:

### 1. Time Correlation

**When did it start?**
```
Spike started: Jan 15, 2:00 PM UTC

Correlate with:
- Deployments (check CI/CD logs)
- Configuration changes (check IaC commits)
- Traffic patterns (check analytics)
- Scheduled jobs (check cron logs)
```

### 2. Resource Drill-Down

**Which resources?**
```
Service-level: S3 costs up 150%
Bucket-level: prod-data-lake bucket +$5k
Operation-level: GET requests up 10x

→ Root cause: New analytics job querying S3 excessively
```

### 3. Tag Analysis

**Which team/project?**
```
Tag: Team=DataEngineering, Project=Analytics
→ Direct inquiry to Data Engineering team
```

### 4. Usage Metrics

**Is it usage or price?**
```
EC2 costs: +50%
EC2 hours: +48%
Unit price: ~stable

→ Conclusion: Legitimate usage increase, not a pricing issue
→ Investigate: Why the capacity increase?
```

## Anomaly Severity Classification

### P0 - Critical (Immediate action)
- Cost spike >100% month-over-month
- Unrecognized services with material cost
- Security-related anomalies (crypto mining)
- Budget breach >120%

**Response**: Immediate investigation, potential resource shutdown

### P1 - High (Same day)
- Cost spike 50-100%
- New high-cost services
- Budget breach 100-120%
- Major regional cost shift

**Response**: Investigate within hours, stakeholder notification

### P2 - Medium (This week)
- Cost spike 20-50%
- Gradual cost drift
- Service growth outliers
- Budget at 90-100%

**Response**: Scheduled investigation, trend monitoring

### P3 - Low (Track)
- Cost spike 10-20%
- Known growth patterns
- Minor variance
- Budget <90%

**Response**: Document, monitor, review in regular cycle

## Alerting Best Practices

### Alert Configuration

```yaml
anomaly_detection:
  thresholds:
    p0: 100  # % change
    p1: 50
    p2: 20
    p3: 10

  evaluation_period: 7  # days

  alert_channels:
    p0: [slack, pagerduty, email]
    p1: [slack, email]
    p2: [email]
    p3: [dashboard]
```

### Alert Content

**Good alert**:
```
🚨 COST ANOMALY DETECTED (P1)

Service: S3
Current: $15,234 (vs $8,450 prior month)
Change: +80% ($6,784 increase)

Top contributors:
- prod-data-lake bucket: +$5,200
- analytics-temp bucket: +$1,400

Detected: 2025-01-25 14:00 UTC
Investigating: Data Engineering team notified
```

**Bad alert**:
```
Costs are high
```

## False Positive Reduction

### Known Events

Suppress alerts for planned events:

```yaml
known_events:
  - name: "Black Friday traffic"
    start: 2025-11-24
    end: 2025-11-27
    expected_increase: 200%
    services: [EC2, CloudFront, RDS]

  - name: "Data migration project"
    start: 2025-01-15
    end: 2025-01-30
    expected_increase: 50%
    services: [EC2, S3, Data Transfer]
```

### Growth Expectations

Account for business growth:

```
User growth: +20% month-over-month
Expected infrastructure growth: +15%

Alert threshold: Growth > 30% (15% expected + 15% buffer)
```

### Day-of-Week Patterns

```
Weekend costs typically -40% vs weekday
Don't alert on Sunday cost drop
```

## Continuous Improvement

### Track Accuracy

```markdown
## Anomaly Detection Accuracy Report

Period: Q1 2025

**Alerts Generated**: 24
**True Positives**: 18 (75%)
**False Positives**: 6 (25%)

**False Positive Root Causes**:
- Known marketing campaign (3)
- Planned migration (2)
- Seasonal pattern (1)

**Adjustments Made**:
- Added campaign to known events
- Increased threshold for migration period
- Implemented day-of-week pattern detection

**Q2 Target**: <15% false positive rate
```

### Feedback Loop

```
1. Anomaly detected
2. Alert sent
3. Investigation completed
4. Outcome recorded:
   - True positive: What was the cause?
   - False positive: Why was it flagged incorrectly?
5. Adjust thresholds/rules
6. Improve detection
```

## Example Anomaly Scenarios

### Scenario 1: Configuration Error

```
Anomaly: EC2 costs +300% overnight
Investigation:
- Auto-scaling policy misconfigured
- Min instances set to 100 instead of 10
- Scaled up at midnight
Action: Fix policy, terminate excess instances
Prevention: Policy validation in IaC review
```

### Scenario 2: Security Incident

```
Anomaly: Unknown service (Amazon SageMaker) with $2k cost
Investigation:
- No approved SageMaker usage
- Launched from compromised credentials
- Training crypto mining models
Action: Shut down resources, rotate credentials, security review
Prevention: Service Control Policies (SCPs) to restrict services
```

### Scenario 3: Legitimate Growth

```
Anomaly: Overall costs +40%
Investigation:
- New product launch last week
- User signups +50%
- Infrastructure scaling appropriately
Action: None (expected growth)
Update: Adjust forecasts for new baseline
```

## Tools and Automation

### Automated Detection Scripts

```python
def detect_anomalies(current, historical):
    mean = statistics.mean(historical)
    stdev = statistics.stdev(historical)

    z_score = (current - mean) / stdev

    if abs(z_score) > 2:
        severity = "P1" if abs(z_score) > 3 else "P2"
        return {
            'anomaly': True,
            'severity': severity,
            'z_score': z_score,
            'current': current,
            'expected': mean
        }

    return {'anomaly': False}
```

### Integration with Monitoring

- Cloud provider native alerting
- Budget alert systems
- Custom dashboards (Grafana, Datadog)
- Slack/email/PagerDuty notifications
