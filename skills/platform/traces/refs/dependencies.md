# Service Dependency Analysis

Patterns for analyzing service dependencies from distributed traces.

## Critical Path Detection

The critical path is the sequence of synchronous operations that must complete for a request to finish. Optimizing the critical path has the highest impact.

### Identifying the Critical Path

```
Request (500ms total)
  ├─> Service A (100ms) [CRITICAL]
  │   └─> Database (80ms) [CRITICAL]
  ├─> Service B (200ms) [CRITICAL]
  │   ├─> Cache (5ms) [CRITICAL]
  │   └─> External API (180ms) [CRITICAL - BOTTLENECK]
  └─> Service C (50ms) [parallel, not critical]
```

**Critical Path**: Request → A → Database → B → External API
**Total Critical Time**: 100 + 80 + 200 = 380ms (excluding parallel Service C)

### Analysis Steps

1. **Trace from entry point to completion**
   - Identify root span
   - Follow synchronous child spans
   - Note parallel operations

2. **Mark all required (synchronous) services**
   - Services that must complete
   - Operations that block progress
   - Ignore async/background tasks

3. **Identify longest path**
   - Calculate cumulative time
   - Find bottleneck operations
   - Consider dependencies

4. **Focus optimization on critical path**
   - 10% improvement on critical path = 10% overall improvement
   - 50% improvement on non-critical = minimal overall impact

### Optimization Priority

```markdown
High Priority (on critical path):
- External API call: 180ms (47% of critical path)
- Service B total: 200ms (53% of critical path)

Medium Priority (on critical path but smaller):
- Database query: 80ms (21% of critical path)

Low Priority (parallel, not blocking):
- Service C: 50ms (not on critical path)
```

## Fan-Out Pattern Detection

A fan-out occurs when a single request triggers many downstream calls. This amplifies load and increases failure probability.

### Pattern: Scatter-Gather

```
Request (300ms total)
  └─> Aggregator Service
      ├─> Microservice 1 (100ms) [parallel]
      ├─> Microservice 2 (200ms) [parallel]
      ├─> Microservice 3 (150ms) [parallel]
      ├─> Microservice 4 (80ms) [parallel]
      └─> Microservice 5 (250ms) [parallel - slowest!]
```

**Total time = slowest service (250ms)**

### Risks

1. **Load Amplification**
   - 1 request → 5 downstream requests
   - 1000 req/s → 5000 req/s on downstream services
   - Can overwhelm downstream systems

2. **Increased Failure Probability**
   - If each service has 99% uptime
   - Combined probability = 0.99^5 = 95%
   - More services = more likely something fails

3. **Latency = Slowest Service**
   - p95 latency determined by slowest service
   - One slow service affects all requests
   - Variance increases with fan-out size

### Mitigation Strategies

**1. Set Timeouts**
```javascript
const results = await Promise.all([
  Promise.race([service1(), timeout(200)]),
  Promise.race([service2(), timeout(200)]),
  Promise.race([service3(), timeout(200)]),
  // ...
]);
```

**2. Implement Circuit Breakers**
```javascript
const results = await Promise.all([
  circuitBreaker.call(service1),
  circuitBreaker.call(service2),
  circuitBreaker.call(service3),
  // ...
]);
```

**3. Graceful Degradation**
```javascript
const results = await Promise.allSettled([
  service1(),
  service2(),
  service3(),
]);

// Use partial results if some services fail
const successfulResults = results
  .filter(r => r.status === 'fulfilled')
  .map(r => r.value);
```

**4. Reduce Fan-Out**
```javascript
// BAD: Query each service individually
const [posts, comments, likes, shares, views] = await Promise.all([
  getPostsByUser(userId),
  getCommentsByUser(userId),
  getLikesByUser(userId),
  getSharesByUser(userId),
  getViewsByUser(userId),
]);

// BETTER: Single aggregated service
const userActivity = await getUserActivity(userId); // Returns all in one call
```

## Circular Dependency Detection

Circular dependencies occur when Service A calls B, which calls A (or longer cycles A → B → C → A).

### Pattern: Direct Cycle

```
Request
  ├─> Service A
  │   └─> Service B
  │       └─> Service A (CIRCULAR!)
```

### Pattern: Indirect Cycle

```
Request
  ├─> Service A
  │   └─> Service B
  │       └─> Service C
  │           └─> Service A (CIRCULAR!)
```

### Detection in Traces

Look for:
- Same service appearing multiple times in call chain
- Increasing depth of nested calls
- Request IDs appearing multiple times

```
Trace ID: abc123
  ├─> user-service (depth=1, id=span-1)
  │   └─> auth-service (depth=2, id=span-2)
  │       └─> user-service (depth=3, id=span-3) ⚠️ CIRCULAR!
```

### Risks

1. **Infinite Loops**
   - Without depth limits, can loop forever
   - Resource exhaustion
   - Service crashes

2. **Cascading Failures**
   - Failure in one service affects all in cycle
   - Amplified load
   - Difficult to isolate issues

3. **Complex Debugging**
   - Hard to trace request flow
   - Unclear ownership
   - Tangled dependencies

### Mitigation Strategies

**1. Add Request ID Tracking**
```javascript
async function callService(serviceName, requestId, depth = 0) {
  // Prevent infinite loops
  if (depth > 10) {
    throw new Error('Max call depth exceeded - possible circular dependency');
  }

  return await service.call(serviceName, { requestId, depth: depth + 1 });
}
```

**2. Detect Cycles**
```javascript
const callChain = new Set();

async function callService(serviceName, requestId) {
  const key = `${serviceName}:${requestId}`;

  if (callChain.has(key)) {
    throw new Error(`Circular dependency detected: ${serviceName} called twice in same request`);
  }

  callChain.add(key);
  try {
    return await service.call(serviceName, { requestId });
  } finally {
    callChain.delete(key);
  }
}
```

**3. Refactor to Remove Cycle**

```javascript
// BAD: Circular dependency
// user-service → auth-service → user-service

// Service A (user-service)
async function getUser(id) {
  const authStatus = await authService.checkAuth(id); // Calls auth-service
  return { ...user, authStatus };
}

// Service B (auth-service)
async function checkAuth(userId) {
  const user = await userService.getUser(userId); // Calls user-service CIRCULAR!
  return user.isActive;
}

// GOOD: Break the cycle
// Extract shared logic to new service or use events

// Service A (user-service)
async function getUser(id) {
  return user; // Just return user, no auth check
}

// Service B (auth-service)
async function checkAuth(userId) {
  const isActive = await db.query('SELECT is_active FROM users WHERE id = ?', [userId]);
  return isActive; // Query database directly, no service call
}

// Service C (api-gateway)
async function getUserWithAuth(id) {
  const [user, authStatus] = await Promise.all([
    userService.getUser(id),
    authService.checkAuth(id)
  ]);
  return { ...user, authStatus };
}
```

## Dependency Health Monitoring

Track health of service dependencies over time.

### Metrics to Track

```markdown
For each dependency:
- **Availability**: % of successful calls
- **Latency**: p50, p95, p99 response times
- **Error Rate**: % of failed calls
- **Timeout Rate**: % of calls timing out
- **Circuit Breaker State**: open/closed/half-open
```

### Dependency Score

```javascript
function calculateDependencyHealth(service) {
  const availability = service.successRate; // 0-100
  const latencySLO = service.p95 < service.sloTarget; // boolean
  const errorRate = service.errorRate; // 0-100

  // Weight: availability 50%, latency 30%, errors 20%
  const score =
    (availability * 0.5) +
    (latencySLO ? 30 : 0) +
    ((100 - errorRate) * 0.2);

  return score; // 0-100
}
```

### Health Status

- **HEALTHY**: Score >= 90, all metrics within SLO
- **DEGRADED**: Score 70-89, some metrics elevated
- **CRITICAL**: Score < 70, SLO violations or unavailable

### Dependency Dashboard

```markdown
## Service Dependencies Health

| Dependency | Availability | p95 Latency | Error Rate | Status |
|------------|--------------|-------------|------------|--------|
| Database | 99.9% | 50ms | 0.01% | HEALTHY |
| Redis Cache | 99.5% | 5ms | 0.5% | HEALTHY |
| Payment API | 98% | 800ms | 2% | DEGRADED ⚠️ |
| Email Service | 95% | 200ms | 5% | CRITICAL ⚠️ |

**Action Required**:
- Payment API: p95 latency exceeds SLO (500ms), investigate slow transactions
- Email Service: High error rate, check service status and implement circuit breaker
```

## Service Dependency Map

Visualize service dependencies from traces.

### Graph Representation

```
┌─────────────┐
│ API Gateway │ (entry point)
└──────┬──────┘
       │
   ┌───┴────┬─────────┐
   │        │         │
   ▼        ▼         ▼
┌──────┐ ┌────┐  ┌─────────┐
│ User │ │Auth│  │ Product │
│ Svc  │ │Svc │  │ Service │
└───┬──┘ └─┬──┘  └────┬────┘
    │      │          │
    ▼      ▼          ▼
┌─────────────────────┐
│     Database        │ (leaf node)
└─────────────────────┘
```

### Analysis

- **Entry Points**: Services with no upstream callers
- **Leaf Nodes**: Services with no downstream calls (typically databases, caches)
- **Hub Services**: Services with many connections (potential single point of failure)
- **Isolated Services**: Services called infrequently or by single caller

### Impact Analysis

```markdown
If Database fails:
- Direct impact: User Service, Auth Service, Product Service
- Indirect impact: API Gateway (all requests fail)
- Blast radius: 100% of traffic

If Product Service fails:
- Direct impact: API Gateway (product endpoints only)
- Indirect impact: None (isolated service)
- Blast radius: ~30% of traffic
```
