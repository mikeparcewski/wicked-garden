# Resilience Patterns Guide: Timeout Pattern

## Timeout Pattern

### Operation Timeout

```typescript
async function withTimeout<T>(
  operation: () => Promise<T>,
  timeoutMs: number,
  errorMessage: string = 'Operation timed out'
): Promise<T> {
  return Promise.race([
    operation(),
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new TimeoutError(errorMessage)), timeoutMs)
    )
  ]);
}

class TimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TimeoutError';
  }
}

// Usage
try {
  const result = await withTimeout(
    () => slowService.call(),
    5000,  // 5 second timeout
    'Slow service timed out'
  );
} catch (error) {
  if (error instanceof TimeoutError) {
    console.error('Operation timed out');
    // Return fallback or cached data
  }
  throw error;
}
```

### Request-Level Timeout

```typescript
import axios from 'axios';

const client = axios.create({
  timeout: 5000,  // 5 second timeout
  timeoutErrorMessage: 'Request timed out'
});

// Per-request timeout
const response = await client.get('/api/data', {
  timeout: 10000  // Override default
});
```

## Bulkhead Pattern

### Isolate Resources

Prevent one failing component from taking down the entire system.

```typescript
class Bulkhead {
  private activeRequests = 0;

  constructor(
    private maxConcurrent: number,
    private queueSize: number = 0
  ) {}

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    // Check capacity
    if (this.activeRequests >= this.maxConcurrent) {
      throw new Error('Bulkhead is full');
    }

    this.activeRequests++;

    try {
      return await operation();
    } finally {
      this.activeRequests--;
    }
  }

  getStats() {
    return {
      activeRequests: this.activeRequests,
      maxConcurrent: this.maxConcurrent,
      available: this.maxConcurrent - this.activeRequests
    };
  }
}

// Separate bulkheads for different services
const paymentBulkhead = new Bulkhead(10);  // Max 10 concurrent payment calls
const notificationBulkhead = new Bulkhead(50);  // Max 50 concurrent notifications

// Payment call won't affect notification capacity
await paymentBulkhead.execute(() => paymentService.charge(amount));
await notificationBulkhead.execute(() => notificationService.send(email));
```

### Semaphore Bulkhead

```typescript
class Semaphore {
  private permits: number;
  private waiting: Array<() => void> = [];

  constructor(permits: number) {
    this.permits = permits;
  }

  async acquire(): Promise<void> {
    if (this.permits > 0) {
      this.permits--;
      return;
    }

    // Wait for permit
    return new Promise<void>(resolve => {
      this.waiting.push(resolve);
    });
  }

  release(): void {
    const next = this.waiting.shift();
    if (next) {
      next();
    } else {
      this.permits++;
    }
  }

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await operation();
    } finally {
      this.release();
    }
  }
}

const semaphore = new Semaphore(5);  // Max 5 concurrent

await semaphore.execute(async () => {
  return await heavyOperation();
});
```

## Fallback Pattern

### Provide Alternatives

```typescript
async function withFallback<T>(
  primary: () => Promise<T>,
  fallback: () => Promise<T> | T,
  errorFilter?: (error: Error) => boolean
): Promise<T> {
  try {
    return await primary();
  } catch (error) {
    // Only fallback for certain errors
    if (errorFilter && !errorFilter(error)) {
      throw error;
    }

    console.warn('Primary failed, using fallback', error);
    return await fallback();
  }
}

// Usage examples

// Fallback to cache
const user = await withFallback(
  () => userService.fetchFromDB(userId),
  () => cache.get(`user:${userId}`)
);

// Fallback to default
const recommendations = await withFallback(
  () => recommendationService.get(userId),
  () => getDefaultRecommendations()
);

// Fallback chain
async function getUserWithFallback(userId: string): Promise<User> {
  return await withFallback(
    // Try primary database
    () => primaryDB.users.findById(userId),
    // Fallback to replica
    () => withFallback(
      () => replicaDB.users.findById(userId),
      // Fallback to cache
      () => cache.get(`user:${userId}`)
    )
  );
}
```

