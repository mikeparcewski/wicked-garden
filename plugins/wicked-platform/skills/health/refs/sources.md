# Observability Capability Discovery Patterns

Detailed patterns for discovering and integrating with observability capabilities.

## Discovery Process

### Step 1: List Available Servers

```bash
ListMcpResourcesTool
```

Returns list of available MCP servers with names and descriptions.

### Step 2: Match by Capability Indicators

Scan server descriptions and available resources to identify capabilities. Look for these indicators:

```markdown
## error-tracking capability
- Keywords: error, exception, crash, tracking, reporting, monitoring
- Resource patterns: errors, exceptions, issues, events
- Common features: stack traces, error grouping, user impact

## apm capability
- Keywords: apm, performance, monitoring, observability, application
- Resource patterns: metrics, services, transactions, traces
- Common features: latency metrics, throughput, service health

## logging capability
- Keywords: log, logging, search, aggregation, analytics
- Resource patterns: logs, events, queries, searches
- Common features: log search, filtering, aggregation

## tracing capability
- Keywords: trace, tracing, distributed, spans, requests
- Resource patterns: traces, spans, operations, services
- Common features: request flow, service dependencies, latency breakdown

## telemetry capability
- Keywords: metrics, telemetry, instrumentation, time-series, monitoring
- Resource patterns: metrics, counters, gauges, histograms
- Common features: custom metrics, instrumentation, alerts
```

### Step 3: Query Each Source

For each discovered capability, query for relevant health data based on what the capability provides.

## error-tracking Capability Integration

When you discover a server with error-tracking capability, query for these data points:

### Common Query Patterns

```markdown
1. Get error rate for recent time period
2. List top errors by frequency
3. Get errors for specific release/deployment
4. User/session impact metrics
5. Error trends over time
6. New vs recurring error classification
```

### Health Indicators to Extract

- **Error Rate**: Current vs baseline comparison
- **Error Distribution**: By severity, type, service
- **User Impact**: Sessions/users affected
- **Error Trends**: Increasing, decreasing, or stable
- **New Errors**: First-time occurrences vs recurring
- **Resolution Metrics**: Time to detect, time to resolve

### Capability Identification

A server has error-tracking capability if it provides:
- Error/exception data with timestamps
- Stack traces or error details
- Error grouping or classification
- Impact metrics (users, sessions, requests)
- Time-series error data

## apm Capability Integration

When you discover a server with apm capability, query for these data points:

### Common Query Patterns

```markdown
1. Service latency percentiles (p50, p95, p99)
2. Request throughput and error rates
3. Resource utilization (CPU, memory, connections)
4. Service health and availability
5. Active alerts and monitors
6. Transaction performance breakdown
7. External dependency health
```

### Health Indicators to Extract

- **Latency Metrics**: p50, p95, p99 compared to SLOs
- **Throughput**: Requests per second, trends
- **Error Rates**: By service, endpoint, or transaction
- **Resource Utilization**: CPU, memory, disk, network
- **Availability**: Uptime percentage, downtime events
- **Alert Status**: Active alerts, severity levels
- **Performance Scores**: Apdex, user experience metrics

### Capability Identification

A server has apm capability if it provides:
- Service-level performance metrics
- Request/transaction monitoring
- Latency and throughput data
- Service health indicators
- Resource utilization metrics
- Optional: AI-detected anomalies or problems

## logging Capability Integration

When you discover a server with logging capability, query for these data points:

### Common Query Patterns

```markdown
1. Search for error/warning patterns in time range
2. Count of log events by severity level
3. Log volume trends and anomalies
4. Correlation queries across services
5. Full-text search for specific patterns
6. Aggregation by service, host, or component
```

### Health Indicators to Extract

- **Error Log Frequency**: Count of ERROR level logs
- **Warning Trends**: Count and patterns of warnings
- **Log Volume**: Baseline vs current, detect anomalies
- **Pattern Detection**: Recurring error messages
- **Service Correlation**: Related logs across services
- **Alert Status**: If logging platform has alerting

### Capability Identification

A server has logging capability if it provides:
- Log search and filtering
- Severity/level-based queries
- Time-range queries
- Log aggregation and counting
- Full-text search across logs
- Optional: Log correlation, alerting

## tracing Capability Integration

When you discover a server with tracing capability, query for these data points:

### Common Query Patterns

```markdown
1. Traces with errors in time range
2. Service operation latencies
3. Service dependency graph/map
4. Slow traces exceeding threshold
5. Service-to-service call patterns
6. Trace success/failure rates
7. Span duration analysis
```

### Health Indicators to Extract

- **Trace Error Rate**: Percentage of failed traces
- **Latency Distribution**: p50, p95, p99 from trace data
- **Service Dependencies**: Call graph, dependency health
- **Slow Operations**: Operations exceeding SLO
- **Success Rate**: Successful vs failed requests
- **Bottlenecks**: Slowest services or operations

### Capability Identification

A server has tracing capability if it provides:
- Distributed trace data with spans
- Service dependency information
- Request timing and latency data
- Trace filtering (by service, time, status)
- Span-level detail and attributes
- Optional: TraceQL or similar query language

## telemetry Capability Integration

When you discover a server with telemetry capability, query for these data points:

### Common Query Patterns

```markdown
1. Time-series metrics queries (rates, histograms)
2. Custom metric values and trends
3. Alert rule status (firing, pending, resolved)
4. Service health indicators (up/down status)
5. Resource metrics (CPU, memory, network)
6. Application-specific instrumentation
7. Histogram percentile calculations
```

### Health Indicators to Extract

- **Custom Metrics**: Application-defined metrics vs thresholds
- **Service Status**: Up/down indicators
- **Alert Status**: Active alerts from metrics
- **Resource Metrics**: Infrastructure health indicators
- **Rate Metrics**: Request rates, error rates, etc.
- **Histogram Data**: Latency percentiles from histograms

### Capability Identification

A server has telemetry capability if it provides:
- Time-series metric data
- Custom instrumentation support
- Metric queries (PromQL or similar)
- Metric aggregation and calculations
- Alert rules based on metrics
- Optional: Unified observability (traces + metrics + logs)

## Graceful Fallback

When no integrations available, fall back to local analysis:

### Code-Based Health Assessment

```bash
# Search for error patterns in code
wicked-search: error, exception, throw patterns

# Check for TODO/FIXME comments
wicked-search: TODO, FIXME, HACK

# Review recent commits
git log --since="24 hours ago"

# Check for common anti-patterns
wicked-search: catch without handling, silent failures
```

**Provide Guidance**:
```markdown
No observability integrations detected.

Health assessment limited to static code analysis.

**Recommendations**:
1. Install error-tracking capability (e.g., via MCP)
2. Install apm capability (e.g., via MCP)
3. Install logging capability (e.g., via MCP)

Benefits:
- Real-time error tracking
- Performance monitoring
- Production incident response
- Deployment correlation
```

## Multi-Capability Correlation

When multiple capabilities are available, correlate for richer insights:

```markdown
### Correlation Example

**From error-tracking capability**: 45 errors/min "Database connection timeout"
**From apm capability**: user-service latency p95: 2.3s (was 200ms)
**From logging capability**: Log pattern "ConnectionPool exhausted" started 14:25 UTC
**From deployment tracking**: Deployment user-service-v2.3.1 at 14:23 UTC

**Correlated Health View**:
- Issue: Database connection pool exhaustion
- Started: 2 minutes after deployment
- Root Cause: Connection pool size reduced in v2.3.1
- Impact: 45 errors/min, 2500 users affected
- Recommendation: Rollback to v2.3.0
```

## Health Scoring Algorithm

Aggregate health from multiple sources:

```markdown
Health Score = weighted average of:
- Error Rate Score (40%): (baseline / current) * 100
- Latency Score (30%): (SLO / actual) * 100
- SLO Compliance (20%): percentage of SLOs met
- Alert Status (10%): 100 if no alerts, 50 if warnings, 0 if critical

Overall Status:
- HEALTHY: Score >= 90
- DEGRADED: Score 70-89
- CRITICAL: Score < 70
```

Adjust weights based on system priorities (e.g., error rate more critical than latency for some systems).
