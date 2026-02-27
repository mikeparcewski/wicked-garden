# Debugging Code Patterns

## Binary Search Debugging

```bash
git bisect start
git bisect bad HEAD
git bisect good v1.2.0
# Git will checkout commits to test
# After each test:
git bisect good  # or git bisect bad
# Continue until found
git bisect reset
```

## Log-Based Debugging

```javascript
console.log('1. Input:', input);
console.log('2. Validated:', validated);
console.log('3. Result:', result);
```

## Performance Profiling

```javascript
console.time('operation');
await expensiveOperation();
console.timeEnd('operation');

// Or with Performance API
const start = performance.now();
await expensiveOperation();
const duration = performance.now() - start;
console.log(`Operation took ${duration}ms`);
```

## Common Error Patterns

### Null/Undefined Issues

```javascript
// Problem: user.profile.name (profile is null)
// Fix: Optional chaining
const name = user?.profile?.name ?? 'Unknown';

// Problem: Cannot read property of undefined
// Fix: Guard clauses
if (!user || !user.profile) {
  return 'Unknown';
}
return user.profile.name;
```

### Async Timing Issues

```javascript
// Problem: Race condition
let result;
fetchData().then(data => result = data);
console.log(result); // undefined - promise not resolved yet

// Fix: Use await
const result = await fetchData();
console.log(result); // correct value

// Problem: Parallel promises with errors
await Promise.all([promise1, promise2]); // Fails fast

// Fix: Handle all settled
const results = await Promise.allSettled([promise1, promise2]);
results.forEach((result, i) => {
  if (result.status === 'rejected') {
    console.error(`Promise ${i} failed:`, result.reason);
  }
});
```

### Scope/Closure Issues

```javascript
// Problem: var in loop
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100); // Logs: 3,3,3
}

// Fix: Use let (block scope)
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100); // Logs: 0,1,2
}

// Problem: Stale closure
function createCounter() {
  let count = 0;
  return {
    increment: () => count++,
    getCount: () => count
  };
}

// Fix: Use current state, not captured
function useCounter() {
  const [count, setCount] = useState(0);
  const increment = useCallback(() => {
    setCount(c => c + 1); // Use function updater
  }, []);
}
```

### Race Conditions

```javascript
// Problem: Lost updates
let count = 0;
async function increment() {
  const current = count;
  await delay(10);
  count = current + 1; // Multiple calls overwrite each other
}

// Fix: Atomic operations
async function increment() {
  count++; // Or use locks/transactions for complex cases
}

// Problem: Multiple async setState
const [data, setData] = useState([]);
setData(data.concat(newItem)); // Bad: uses stale data

// Fix: Functional update
setData(prev => prev.concat(newItem));
```

## Debugging Techniques

### Stack Trace Analysis

```
Error: Cannot read property 'id' of undefined
    at processUser (app.js:42:15)       <- Where it failed
    at handleRequest (app.js:28:10)     <- What called it
    at Server.<anonymous> (app.js:10:5) <- Origin
```

Work backwards:
1. Line 42: `user.id` - user is undefined
2. Line 28: Called processUser without validating user
3. Line 10: Request handler didn't check if user exists

### Breakpoint Debugging

```javascript
// Add debugger statement
function complexFunction(data) {
  debugger; // Execution pauses here in DevTools
  const processed = processData(data);
  return processed;
}
```

### Conditional Logging

```javascript
const DEBUG = process.env.NODE_ENV === 'development';

function log(...args) {
  if (DEBUG) {
    console.log('[DEBUG]', ...args);
  }
}

log('User state:', user); // Only in development
```

### Network Debugging

```javascript
// Add request/response logging
fetch(url)
  .then(response => {
    console.log('Response status:', response.status);
    console.log('Response headers:', response.headers);
    return response.json();
  })
  .then(data => {
    console.log('Response data:', data);
    return data;
  })
  .catch(error => {
    console.error('Fetch failed:', error);
    console.error('URL:', url);
  });
```

## Database Debugging

### Query Analysis

```sql
-- Check query execution plan
EXPLAIN ANALYZE
SELECT * FROM orders
WHERE user_id = 123
AND created_at > '2024-01-01';

-- Look for:
-- - Sequential scans (add index)
-- - High cost estimates
-- - Missing indexes
```

### N+1 Query Detection

```javascript
// Problem: N+1 queries
const users = await User.findAll();
for (const user of users) {
  const orders = await Order.findAll({ where: { userId: user.id } });
  user.orders = orders;
}

// Fix: Eager loading
const users = await User.findAll({
  include: [{ model: Order }]
});
```

## Memory Leak Debugging

```javascript
// Problem: Event listener not removed
component.addEventListener('click', handler);
// Component destroyed but listener remains

// Fix: Cleanup
useEffect(() => {
  const handler = () => { /* ... */ };
  component.addEventListener('click', handler);

  return () => {
    component.removeEventListener('click', handler);
  };
}, []);
```
