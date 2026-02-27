---
name: system-health-assessment
title: System Health Assessment and SLO Monitoring
description: Aggregate health metrics across services, detect trends, and provide proactive recommendations for reliability improvement
type: infrastructure
difficulty: intermediate
estimated_minutes: 10
---

# System Health Assessment and SLO Monitoring

This scenario demonstrates wicked-platform's observability capabilities, including health aggregation across services, SLO tracking, trend analysis, and capacity planning recommendations.

## Setup

Create a simulated microservices environment with health data:

```bash
# Create test environment
mkdir -p ~/test-wicked-platform/health-check
cd ~/test-wicked-platform/health-check

# Create service configuration
mkdir -p services/api-gateway services/user-service services/order-service services/inventory-service

# Create SLO definitions
cat > slo-config.yaml << 'EOF'
slos:
  api-gateway:
    availability: 99.9%
    latency_p95: 200ms
    latency_p99: 500ms
    error_rate: 0.1%

  user-service:
    availability: 99.5%
    latency_p95: 150ms
    latency_p99: 300ms
    error_rate: 0.5%

  order-service:
    availability: 99.9%
    latency_p95: 300ms
    latency_p99: 750ms
    error_rate: 0.1%

  inventory-service:
    availability: 99.0%
    latency_p95: 100ms
    latency_p99: 200ms
    error_rate: 1.0%
EOF

# Create simulated metrics (representing what would come from APM)
cat > metrics.json << 'EOF'
{
  "timestamp": "2024-01-15T15:00:00Z",
  "services": {
    "api-gateway": {
      "status": "healthy",
      "error_rate": 0.02,
      "latency_p50": 45,
      "latency_p95": 120,
      "latency_p99": 280,
      "throughput": 5000,
      "availability": 99.98
    },
    "user-service": {
      "status": "degraded",
      "error_rate": 1.5,
      "latency_p50": 200,
      "latency_p95": 450,
      "latency_p99": 800,
      "throughput": 2000,
      "availability": 99.2,
      "issues": ["database_connection_pool_exhaustion"]
    },
    "order-service": {
      "status": "healthy",
      "error_rate": 0.05,
      "latency_p50": 80,
      "latency_p95": 200,
      "latency_p99": 400,
      "throughput": 1500,
      "availability": 99.95
    },
    "inventory-service": {
      "status": "healthy",
      "error_rate": 0.3,
      "latency_p50": 30,
      "latency_p95": 75,
      "latency_p99": 150,
      "throughput": 3000,
      "availability": 99.7
    }
  },
  "trends_24h": {
    "error_rate_change": "+15%",
    "latency_change": "+8%",
    "traffic_change": "+12%"
  },
  "capacity": {
    "cpu_utilization": 68,
    "memory_utilization": 72,
    "connection_pool_utilization": 85
  }
}
EOF

# Create deployment history
cat > deployments.json << 'EOF'
[
  {
    "service": "user-service",
    "version": "v2.3.1",
    "timestamp": "2024-01-15T14:00:00Z",
    "changes": ["Updated database connection pool settings"]
  },
  {
    "service": "api-gateway",
    "version": "v1.8.0",
    "timestamp": "2024-01-14T10:00:00Z",
    "changes": ["Added rate limiting"]
  }
]
EOF

git init
git add -A
git commit -m "Setup health monitoring environment"
```

## Steps

### 1. Run System Health Check

```bash
/wicked-platform:health
```

**Expected**:
- Spawns SRE agent
- Discovers available observability sources (or uses local data)
- Aggregates health metrics across services
- Calculates overall health score
- Identifies issues and trends

### 2. Review Health Summary

The health report should show:

```markdown
## System Health Report

**Overall Status**: DEGRADED
**Assessment Time**: 2024-01-15 15:00:00 UTC
**Data Sources**: Local metrics (metrics.json)

### Health Summary

| Service | Status | Error Rate | Latency (p95) | SLO Status |
|---------|--------|------------|---------------|------------|
| api-gateway | HEALTHY | 0.02% | 120ms | Pass |
| user-service | DEGRADED | 1.5% | 450ms | FAIL |
| order-service | HEALTHY | 0.05% | 200ms | Pass |
| inventory-service | HEALTHY | 0.3% | 75ms | Pass |
```

### 3. Investigate Degraded Service

```bash
/wicked-platform:health user-service --detailed
```

**Expected**:
Detailed analysis of user-service issues:

```markdown
### user-service: Detailed Analysis

**Status**: DEGRADED
**Duration**: ~1 hour

#### SLO Violations

| Metric | SLO | Current | Violation |
|--------|-----|---------|-----------|
| Error Rate | 0.5% | 1.5% | 3x over |
| Latency p95 | 150ms | 450ms | 3x over |
| Latency p99 | 300ms | 800ms | 2.7x over |
| Availability | 99.5% | 99.2% | Below target |

#### Error Analysis

Top error pattern:
- `DatabaseConnectionError: Connection pool exhausted`
- Frequency: 30/min (baseline: 2/min)
- First seen: 14:15 UTC

#### Correlation

**Recent deployment**: user-service v2.3.1 (14:00 UTC)
- Change: "Updated database connection pool settings"
- Timeline: Deployment -> 15 min -> Errors begin

**Hypothesis**: Connection pool configuration change may have reduced pool size or timeout settings.
```

### 4. Review SLO Burn Rate

```bash
/wicked-platform:health --slo-budget
```

**Expected**:
SLO burn rate analysis:

```markdown
### SLO Budget Status

#### user-service

**Error Budget (monthly)**:
- Budget: 0.5% (3.65 hours of downtime allowed)
- Burned: 2.1 hours
- Remaining: 1.55 hours (42%)
- Burn rate: 5x normal

**At current burn rate**:
- Monthly budget exhausted in: 3 days
- Action required: URGENT

#### api-gateway

**Error Budget (monthly)**:
- Budget: 0.1% (43 minutes allowed)
- Burned: 8 minutes
- Remaining: 35 minutes (81%)
- Burn rate: 0.8x normal (sustainable)
```

### 5. Get Capacity Recommendations

```bash
/wicked-platform:health --capacity
```

**Expected**:
Capacity planning insights:

```markdown
### Capacity Assessment

**Current Utilization**:
| Resource | Usage | Threshold | Status |
|----------|-------|-----------|--------|
| CPU | 68% | 70% | Normal |
| Memory | 72% | 70% | Elevated |
| Connection Pool | 85% | 80% | Critical |

**Traffic Trends**:
- Current: +12% week-over-week
- Projected: 15% monthly growth

**Capacity Forecast**:
| Threshold | Current | Days Until |
|-----------|---------|------------|
| 70% CPU | 68% | 4 days |
| 85% CPU | 68% | 18 days |
| 100% connections | 85% | 2 days |

### Recommendations

**Immediate** (within 24 hours):
1. Increase database connection pool size
2. Investigate user-service memory pressure
3. Add connection pool monitoring alerts

**This Week**:
1. Plan horizontal scaling for user-service
2. Review memory allocation across services
3. Implement connection pool auto-scaling

**This Month**:
1. Increase cluster capacity by 20%
2. Evaluate database read replica strategy
3. Review resource allocation policies
```

## Expected Outcome

Comprehensive health report:

```markdown
## System Health Report

**Overall Status**: DEGRADED
**Assessment Time**: 2024-01-15 15:00:00 UTC
**Reason**: user-service SLO violations

### Executive Summary

System operating with degraded performance in user-service. Other services healthy. Degradation correlates with recent deployment (user-service v2.3.1) and connection pool exhaustion.

### Service Health

| Service | Status | Error Rate | p95 Latency | SLO |
|---------|--------|------------|-------------|-----|
| api-gateway | HEALTHY | 0.02% | 120ms | Pass |
| user-service | DEGRADED | 1.5% | 450ms | FAIL |
| order-service | HEALTHY | 0.05% | 200ms | Pass |
| inventory | HEALTHY | 0.3% | 75ms | Pass |

### Issues Detected

#### user-service: SLO Violation
- **Severity**: HIGH
- **Started**: 14:15 UTC (45 min ago)
- **Error Rate**: 1.5% (3x SLO of 0.5%)
- **Latency p95**: 450ms (3x SLO of 150ms)
- **Root Cause**: Database connection pool exhaustion
- **Correlation**: Deployment v2.3.1 at 14:00 UTC
- **Blast Radius**: ~2000 req/min affected

### Trends (24h)

- **Error Rates**: Up 15% overall (user-service spike)
- **Latency**: Up 8% (correlated with user-service)
- **Traffic**: Up 12% (within capacity)

### Recommendations

**Immediate**:
1. Investigate user-service v2.3.1 connection pool changes
2. Consider rollback if fix not quickly available
3. Increase connection pool size as temporary mitigation

**Short-term**:
1. Add connection pool metrics to dashboards
2. Implement circuit breaker for database calls
3. Add integration tests for pool configuration

**Capacity**:
- Connection pool at 85% - scale before exhaustion
- Memory elevated (72%) - monitor for leaks
- Traffic growth sustainable at current capacity (+18 days headroom)
```

## Success Criteria

- [ ] Overall system health status accurately determined
- [ ] Individual service health correctly assessed
- [ ] SLO violations clearly identified
- [ ] Degraded service flagged and investigated
- [ ] Recent deployment correlation established
- [ ] Error patterns identified
- [ ] Capacity utilization tracked
- [ ] Actionable recommendations provided
- [ ] SLO burn rate calculated

## Value Demonstrated

**Problem solved**: Teams lack a unified view of system health. Information is scattered across monitoring tools, and correlating issues across services requires manual investigation. SLO tracking often happens in spreadsheets, not real-time.

**Why this matters**:

1. **Unified health view**: Instead of checking Datadog, then CloudWatch, then Prometheus, get a single aggregated health report across all services.

2. **Proactive alerting**: The burn rate analysis catches SLO violations before the monthly budget is exhausted. "You have 3 days" is more actionable than "SLO failed."

3. **Deployment correlation**: Automatically connects health degradation with recent deployments. No more asking "did someone deploy something?" in incident channels.

4. **Capacity forecasting**: Instead of reactive scaling during outages, get advance warning: "Connection pool hits limit in 2 days at current growth."

5. **Prioritized recommendations**: Immediate vs short-term vs strategic actions, so teams know what to do first.

This replaces the fragmented observability workflow where:
- Engineers check 5 different dashboards during incidents
- SLO tracking is manual or ignored
- Capacity planning happens after outages
- Deployment correlation is tribal knowledge

The `/health` command brings SRE best practices to any team's observability workflow.
