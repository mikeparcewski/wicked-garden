# Performance Bottleneck Patterns

Detailed analysis patterns for common performance bottlenecks in distributed traces.

## N+1 Query Pattern

Sequential database queries in a loop - the most common database performance issue.

### Trace Signature

```
Request (500ms total)
  ├─> getUser() (10ms)
  ├─> getUserPosts() (200ms)
  │   ├─> SELECT posts WHERE user_id=1 (20ms)
  │   ├─> SELECT posts WHERE user_id=2 (20ms)
  │   ├─> SELECT posts WHERE user_id=3 (20ms)
  │   ├─> SELECT posts WHERE user_id=4 (20ms)
  │   └─> ... (10 more queries)
```

**Characteristics**:
- Many sequential DB spans (typically 10+)
- Each query has similar duration
- Total time = query_time × count
- Linear scaling with data size

### Code Pattern

```javascript
// BAD: N+1 pattern
const users = await db.query('SELECT * FROM users');
for (const user of users) {
  user.posts = await db.query('SELECT * FROM posts WHERE user_id = ?', [user.id]); // N queries
}
```

### Fix: Batch Query

```javascript
// GOOD: Single batch query
const users = await db.query('SELECT * FROM users');
const userIds = users.map(u => u.id);
const posts = await db.query('SELECT * FROM posts WHERE user_id IN (?)', [userIds]);

// Group posts by user_id
const postsByUser = {};
posts.forEach(post => {
  if (!postsByUser[post.user_id]) postsByUser[post.user_id] = [];
  postsByUser[post.user_id].push(post);
});

users.forEach(user => {
  user.posts = postsByUser[user.id] || [];
});
```

### Fix: SQL JOIN

```javascript
// BETTER: Single JOIN query
const usersWithPosts = await db.query(`
  SELECT u.*, p.id as post_id, p.title, p.content
  FROM users u
  LEFT JOIN posts p ON p.user_id = u.id
`);

// Transform flat results to nested structure
const users = transformToNested(usersWithPosts);
```

**Expected Improvement**: 100-500ms reduction depending on query count and latency.

## Synchronous External Calls

Waiting for external API responses sequentially instead of in parallel.

### Trace Signature

```
Request (800ms total)
  ├─> callStripeAPI() (300ms)
  ├─> callTwilioAPI() (250ms)
  └─> callSendGridAPI() (200ms)
```

**Characteristics**:
- Sequential external HTTP spans
- Each blocking the next
- Total time = sum of all external calls
- Could be parallelized

### Code Pattern

```javascript
// BAD: Sequential external calls
const payment = await stripeAPI.charge(amount);
const sms = await twilioAPI.send(phone, message);
const email = await sendgridAPI.send(to, subject, body);
```

### Fix: Parallel Execution

```javascript
// GOOD: Parallel external calls
const [payment, sms, email] = await Promise.all([
  stripeAPI.charge(amount),
  twilioAPI.send(phone, message),
  sendgridAPI.send(to, subject, body)
]);
```

**Expected Improvement**: ~450ms reduction (800ms → 300ms, only waiting for slowest)

### Fix: Async Processing

For non-critical operations:

```javascript
// BETTER: Async background processing
const payment = await stripeAPI.charge(amount); // Critical, wait for it

// Non-critical, process asynchronously
queue.add('send-sms', { phone, message });
queue.add('send-email', { to, subject, body });

// Return immediately without waiting
```

**Expected Improvement**: ~550ms reduction, user doesn't wait for non-critical operations.

## Missing Caching

Repeated identical queries without caching.

### Trace Signature

```
Request 1 (100ms)
  └─> SELECT user WHERE id=123 (80ms)

Request 2 (100ms)
  └─> SELECT user WHERE id=123 (80ms) // Same query!

Request 3 (100ms)
  └─> SELECT user WHERE id=123 (80ms) // Same query again!
```

**Characteristics**:
- Same query executed multiple times
- Results likely unchanged between calls
- High latency for data that rarely changes
- Cache lookup spans missing

### Code Pattern

```javascript
// BAD: No caching
async function getUser(id) {
  return await db.query('SELECT * FROM users WHERE id = ?', [id]);
}

// Called multiple times per request
const user1 = await getUser(123);
const user2 = await getUser(123); // Same user, queries again!
```

### Fix: In-Memory Cache

```javascript
// GOOD: In-memory cache
const cache = new Map();

async function getUser(id) {
  const cacheKey = `user:${id}`;

  if (cache.has(cacheKey)) {
    return cache.get(cacheKey);
  }

  const user = await db.query('SELECT * FROM users WHERE id = ?', [id]);
  cache.set(cacheKey, user);

  return user;
}
```

**Expected Improvement**: ~80ms reduction on cache hits (100ms → 20ms)

### Fix: Redis Cache

```javascript
// BETTER: Redis cache (shared across instances)
async function getUser(id) {
  const cacheKey = `user:${id}`;

  // Check Redis cache
  const cached = await redis.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  // Query database
  const user = await db.query('SELECT * FROM users WHERE id = ?', [id]);

  // Store in cache (1 hour TTL)
  await redis.set(cacheKey, JSON.stringify(user), 'EX', 3600);

  return user;
}
```

**Expected Improvement**: ~60ms reduction on cache hits (100ms → 40ms, Redis lookup ~20ms)

## Database Query Inefficiency

Slow database operations due to missing indexes or inefficient queries.

### Trace Signature

```
Request (2000ms total)
  └─> SELECT * FROM orders WHERE status='pending' (1800ms) // SLOW!
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

**Expected Improvement**: 1700ms reduction (2000ms → 300ms)

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
  ├─> Acquire DB connection (300ms) // Waiting for connection!
  ├─> SELECT ... (50ms)
  ├─> UPDATE ... (100ms)
  ├─> Wait for lock (800ms) // Blocked by another transaction!
  └─> COMMIT (50ms)
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

**Expected Improvement**: Eliminates wait time for connections (300ms → 0ms)

## External API Bottlenecks

Third-party APIs with high latency or rate limits.

### Trace Signature

```
Request (3000ms total)
  ├─> Internal processing (100ms)
  └─> Call external API (2800ms) // Majority of time!
      └─> Wait for response (2800ms)
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

**Expected Improvement**: 2700ms reduction on cache hits (3000ms → 300ms)

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
