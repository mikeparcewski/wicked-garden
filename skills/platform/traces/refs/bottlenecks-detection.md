# Performance Bottleneck Patterns: Detection

Detailed analysis patterns for identifying common performance bottlenecks in distributed traces.

## N+1 Query Pattern

Sequential database queries in a loop - the most common database performance issue.

### Trace Signature

```
Request (500ms total)
  |-> getUser() (10ms)
  |-> getUserPosts() (200ms)
  |   |-> SELECT posts WHERE user_id=1 (20ms)
  |   |-> SELECT posts WHERE user_id=2 (20ms)
  |   |-> SELECT posts WHERE user_id=3 (20ms)
  |   |-> SELECT posts WHERE user_id=4 (20ms)
  |   +-> ... (10 more queries)
```

**Characteristics**:
- Many sequential DB spans (typically 10+)
- Each query has similar duration
- Total time = query_time x count
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
  |-> callStripeAPI() (300ms)
  |-> callTwilioAPI() (250ms)
  +-> callSendGridAPI() (200ms)
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

**Expected Improvement**: ~450ms reduction (800ms -> 300ms, only waiting for slowest)

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
  +-> SELECT user WHERE id=123 (80ms)

Request 2 (100ms)
  +-> SELECT user WHERE id=123 (80ms) // Same query!

Request 3 (100ms)
  +-> SELECT user WHERE id=123 (80ms) // Same query again!
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

**Expected Improvement**: ~80ms reduction on cache hits (100ms -> 20ms)

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

**Expected Improvement**: ~60ms reduction on cache hits (100ms -> 40ms, Redis lookup ~20ms)
