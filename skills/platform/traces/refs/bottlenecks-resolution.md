# Performance Bottleneck Patterns: Resolution

Resolution strategies for database, resource contention, and external API bottlenecks.

## Database Query Inefficiency

Slow database operations due to missing indexes or inefficient queries.

### Trace Signature

```
Request (2000ms total)
  +-> SELECT * FROM orders WHERE status='pending' (1800ms) // SLOW!
```

**Characteristics**:
- Single DB span taking majority of time
- Query time varies with data size
- Often involves table scans
- EXPLAIN shows no index usage

### Analysis Steps

```sql
-- Check query execution plan
EXPLAIN SELECT * FROM orders WHERE status='pending';

-- Look for:
-- - "Seq Scan" or "Table Scan" (bad)
-- - "Index Scan" (good)
-- - High "cost" values
-- - Large "rows" estimates
```

### Fix: Add Index

```sql
-- Add index on filtered column
CREATE INDEX idx_orders_status ON orders(status);

-- Verify improvement
EXPLAIN SELECT * FROM orders WHERE status='pending';
-- Should now show "Index Scan"
```

**Expected Improvement**: 1700ms reduction (2000ms -> 300ms)

### Fix: Optimize Query

```javascript
// BAD: Fetching all columns
const orders = await db.query(`
  SELECT * FROM orders WHERE status='pending'
`);

// GOOD: Fetch only needed columns
const orders = await db.query(`
  SELECT id, user_id, total, created_at
  FROM orders
  WHERE status='pending'
`);

// BETTER: Add pagination
const orders = await db.query(`
  SELECT id, user_id, total, created_at
  FROM orders
  WHERE status='pending'
  LIMIT 100 OFFSET 0
`);
```

**Expected Improvement**: Varies, but typically 30-50% reduction

## Resource Contention

Lock waits, queue delays, or connection pool exhaustion.

### Trace Signature

```
Request (1500ms total)
  |-> Acquire DB connection (300ms) // Waiting for connection!
  |-> SELECT ... (50ms)
  |-> UPDATE ... (100ms)
  |-> Wait for lock (800ms) // Blocked by another transaction!
  +-> COMMIT (50ms)
```

**Characteristics**:
- Time gaps between spans
- Wait time not attributed to specific service
- Timing varies significantly between requests
- Correlation with concurrent load

### Database Lock Contention

```javascript
// BAD: Long-running transaction holding locks
await db.transaction(async (trx) => {
  const user = await trx('users').where({ id }).forUpdate(); // Locks row

  // Expensive external call while holding lock!
  const result = await externalAPI.process(user);

  await trx('users').where({ id }).update({ status: result.status });
});
```

### Fix: Reduce Lock Duration

```javascript
// GOOD: Minimize lock duration
// Do expensive work outside transaction
const result = await externalAPI.process(user);

// Quick transaction just for update
await db.transaction(async (trx) => {
  await trx('users').where({ id }).update({ status: result.status });
});
```

**Expected Improvement**: 750ms reduction (no waiting for locks)

### Connection Pool Exhaustion

```javascript
// BAD: Not returning connections
async function query() {
  const conn = await pool.getConnection();
  const result = await conn.query('SELECT ...');
  // Forgot to release connection!
  return result;
}
```

### Fix: Always Release Connections

```javascript
// GOOD: Properly release connections
async function query() {
  const conn = await pool.getConnection();
  try {
    const result = await conn.query('SELECT ...');
    return result;
  } finally {
    conn.release(); // Always release
  }
}

// BETTER: Use connection pool query method
async function query() {
  return await pool.query('SELECT ...'); // Auto-releases
}
```

**Expected Improvement**: Eliminates wait time for connections (300ms -> 0ms)

## External API Bottlenecks

Third-party APIs with high latency or rate limits.

### Trace Signature

```
Request (3000ms total)
  |-> Internal processing (100ms)
  +-> Call external API (2800ms) // Majority of time!
      +-> Wait for response (2800ms)
```

**Characteristics**:
- External HTTP call dominates request time
- High p95/p99 variance
- Occasional timeouts
- No control over external service

### Fix: Add Caching

```javascript
// Cache external API responses
async function getExternalData(key) {
  const cached = await cache.get(`external:${key}`);
  if (cached) return cached;

  const data = await externalAPI.fetch(key);
  await cache.set(`external:${key}`, data, 'EX', 300); // 5min cache

  return data;
}
```

**Expected Improvement**: 2700ms reduction on cache hits (3000ms -> 300ms)

### Fix: Async Processing

```javascript
// Don't block user request
async function processOrder(order) {
  // Save order immediately
  await db.save(order);

  // Queue external processing
  await queue.add('enrich-order', { orderId: order.id });

  // Return to user immediately
  return { status: 'processing', orderId: order.id };
}

// Background worker processes enrichment
async function enrichOrder(orderId) {
  const data = await externalAPI.fetch(orderId);
  await db.update('orders', { id: orderId, enrichedData: data });
}
```

**Expected Improvement**: User experiences 100ms instead of 3000ms

### Fix: Set Timeouts

```javascript
// Prevent hanging on slow external APIs
const response = await Promise.race([
  externalAPI.fetch(key),
  timeout(5000) // Fail after 5 seconds
]);

if (!response) {
  // Use fallback or cached data
  return await getFallbackData(key);
}
```

**Expected Improvement**: Caps max latency at timeout value (5000ms)
