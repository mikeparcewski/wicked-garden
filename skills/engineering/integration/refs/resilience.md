# Resilience Patterns Guide

Comprehensive guide to building resilient distributed systems with fault tolerance patterns.

## Circuit Breaker Pattern

### Concept

Prevent cascading failures by detecting failures and stopping requests to failing services.

```
CLOSED → OPEN → HALF_OPEN → CLOSED
   ↑                           |
   └───────────────────────────┘
```

**States**:
- **CLOSED**: Normal operation, requests flow through
- **OPEN**: Too many failures, requests fail immediately
- **HALF_OPEN**: Testing if service recovered, limited requests

### Implementation

```typescript
class CircuitBreaker {
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private failureCount = 0;
  private successCount = 0;
  private nextAttempt = Date.now();

  constructor(
    private failureThreshold: number = 5,
    private successThreshold: number = 2,
    private timeout: number = 60000,  // 60 seconds
    private halfOpenMaxCalls: number = 3
  ) {}

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    // Circuit is OPEN
    if (this.state === 'OPEN') {
      if (Date.now() < this.nextAttempt) {
        throw new Error('Circuit breaker is OPEN');
      }
      // Try to recover
      this.state = 'HALF_OPEN';
      this.successCount = 0;
    }

    // HALF_OPEN: Limit concurrent requests
    if (this.state === 'HALF_OPEN' && this.successCount >= this.halfOpenMaxCalls) {
      throw new Error('Circuit breaker is HALF_OPEN');
    }

    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess(): void {
    if (this.state === 'HALF_OPEN') {
      this.successCount++;

      // Enough successes - close circuit
      if (this.successCount >= this.successThreshold) {
        this.state = 'CLOSED';
        this.failureCount = 0;
      }
    } else {
      // Reset failure count on success
      this.failureCount = 0;
    }
  }

  private onFailure(): void {
    this.failureCount++;

    if (this.failureCount >= this.failureThreshold) {
      this.state = 'OPEN';
      this.nextAttempt = Date.now() + this.timeout;
    }
  }

  getState(): string {
    return this.state;
  }

  getStats() {
    return {
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      nextAttempt: this.state === 'OPEN' ? this.nextAttempt : null
    };
  }
}

// Usage
const paymentBreaker = new CircuitBreaker(5, 2, 60000);

try {
  const result = await paymentBreaker.execute(async () => {
    return await paymentService.charge(amount);
  });
} catch (error) {
  if (error.message === 'Circuit breaker is OPEN') {
    // Return cached data or fallback
    return getCachedPaymentStatus();
  }
  throw error;
}
```

### Advanced Circuit Breaker

```typescript
interface CircuitBreakerConfig {
  failureThreshold: number;
  successThreshold: number;
  timeout: number;
  errorFilter?: (error: Error) => boolean;
  onStateChange?: (oldState: string, newState: string) => void;
}

class AdvancedCircuitBreaker {
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private failures: number[] = [];  // Timestamps of failures
  private windowMs: number = 10000;  // 10 second window

  constructor(private config: CircuitBreakerConfig) {}

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    this.cleanOldFailures();

    if (this.state === 'OPEN') {
      if (Date.now() < this.nextAttempt) {
        throw new CircuitBreakerOpenError();
      }
      this.transition('HALF_OPEN');
    }

    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      // Only count certain errors
      if (!this.config.errorFilter || this.config.errorFilter(error)) {
        this.onFailure();
      }
      throw error;
    }
  }

  private cleanOldFailures(): void {
    const cutoff = Date.now() - this.windowMs;
    this.failures = this.failures.filter(ts => ts > cutoff);
  }

  private transition(newState: string): void {
    const oldState = this.state;
    this.state = newState as any;

    if (this.config.onStateChange) {
      this.config.onStateChange(oldState, newState);
    }
  }

  private onFailure(): void {
    this.failures.push(Date.now());

    if (this.failures.length >= this.config.failureThreshold) {
      this.transition('OPEN');
      this.nextAttempt = Date.now() + this.config.timeout;
    }
  }

  private onSuccess(): void {
    if (this.state === 'HALF_OPEN') {
      this.transition('CLOSED');
    }
    this.failures = [];
  }
}
```

## Retry Pattern

### Exponential Backoff

```typescript
interface RetryConfig {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
  jitter?: boolean;
  retryableErrors?: (error: Error) => boolean;
}

async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  config: RetryConfig
): Promise<T> {
  let lastError: Error;
  let delay = config.initialDelayMs;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;

      // Check if error is retryable
      if (config.retryableErrors && !config.retryableErrors(error)) {
        throw error;
      }

      // Last attempt - throw error
      if (attempt === config.maxRetries) {
        throw error;
      }

      // Add jitter to prevent thundering herd
      const jitter = config.jitter
        ? Math.random() * delay * 0.1
        : 0;

      const sleepTime = Math.min(delay + jitter, config.maxDelayMs);

      console.log(`Retry attempt ${attempt + 1}/${config.maxRetries} in ${sleepTime}ms`);

      await sleep(sleepTime);

      // Exponential backoff
      delay *= config.backoffMultiplier;
    }
  }

  throw lastError!;
}

// Helper
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Usage
const result = await retryWithBackoff(
  () => externalService.call(),
  {
    maxRetries: 3,
    initialDelayMs: 1000,
    maxDelayMs: 10000,
    backoffMultiplier: 2,
    jitter: true,
    retryableErrors: (error) => {
      return error.code === 'NETWORK_ERROR' ||
             error.code === 'TIMEOUT' ||
             error.status === 503;
    }
  }
);
```

### Retry with Circuit Breaker

```typescript
class ResilientClient {
  private circuitBreaker: CircuitBreaker;

  constructor(
    private service: any,
    breakerConfig: any,
    private retryConfig: RetryConfig
  ) {
    this.circuitBreaker = new CircuitBreaker(breakerConfig);
  }

  async call<T>(operation: () => Promise<T>): Promise<T> {
    return await this.circuitBreaker.execute(async () => {
      return await retryWithBackoff(operation, this.retryConfig);
    });
  }
}

// Usage
const client = new ResilientClient(
  paymentService,
  { failureThreshold: 5, timeout: 60000 },
  { maxRetries: 3, initialDelayMs: 1000 }
);

const result = await client.call(() => paymentService.charge(amount));
```

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

## Rate Limiting

### Token Bucket

```typescript
class TokenBucket {
  private tokens: number;
  private lastRefill: number;

  constructor(
    private capacity: number,
    private refillRate: number,  // tokens per second
  ) {
    this.tokens = capacity;
    this.lastRefill = Date.now();
  }

  tryConsume(tokens: number = 1): boolean {
    this.refill();

    if (this.tokens >= tokens) {
      this.tokens -= tokens;
      return true;
    }

    return false;
  }

  private refill(): void {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;  // seconds
    const newTokens = elapsed * this.refillRate;

    this.tokens = Math.min(this.capacity, this.tokens + newTokens);
    this.lastRefill = now;
  }

  getAvailableTokens(): number {
    this.refill();
    return this.tokens;
  }
}

// Usage
const rateLimiter = new TokenBucket(100, 10);  // 100 capacity, 10 per second

if (rateLimiter.tryConsume()) {
  await processRequest();
} else {
  throw new Error('Rate limit exceeded');
}
```

### Sliding Window

```typescript
class SlidingWindowRateLimiter {
  private requests: number[] = [];

  constructor(
    private limit: number,
    private windowMs: number
  ) {}

  tryAcquire(): boolean {
    const now = Date.now();
    const cutoff = now - this.windowMs;

    // Remove old requests
    this.requests = this.requests.filter(ts => ts > cutoff);

    if (this.requests.length < this.limit) {
      this.requests.push(now);
      return true;
    }

    return false;
  }

  getRemaining(): number {
    const now = Date.now();
    const cutoff = now - this.windowMs;
    this.requests = this.requests.filter(ts => ts > cutoff);
    return Math.max(0, this.limit - this.requests.length);
  }

  getResetTime(): number {
    if (this.requests.length === 0) {
      return Date.now();
    }
    return this.requests[0] + this.windowMs;
  }
}

// Usage
const limiter = new SlidingWindowRateLimiter(1000, 60000);  // 1000 req/min

if (limiter.tryAcquire()) {
  await processRequest();
} else {
  const resetTime = limiter.getResetTime();
  throw new RateLimitError(resetTime);
}
```

## Health Checks

### Service Health

```typescript
interface HealthCheck {
  name: string;
  check: () => Promise<boolean>;
  timeout?: number;
  critical?: boolean;
}

class HealthChecker {
  private checks: HealthCheck[] = [];

  register(check: HealthCheck): void {
    this.checks.push(check);
  }

  async checkHealth(): Promise<HealthStatus> {
    const results = await Promise.all(
      this.checks.map(async (check) => {
        const startTime = Date.now();
        try {
          const timeout = check.timeout || 5000;
          const healthy = await withTimeout(
            check.check,
            timeout,
            `${check.name} health check timed out`
          );

          return {
            name: check.name,
            healthy,
            responseTime: Date.now() - startTime,
            critical: check.critical || false
          };
        } catch (error) {
          return {
            name: check.name,
            healthy: false,
            error: error.message,
            responseTime: Date.now() - startTime,
            critical: check.critical || false
          };
        }
      })
    );

    const criticalFailure = results.some(r => !r.healthy && r.critical);
    const allHealthy = results.every(r => r.healthy);

    return {
      status: criticalFailure ? 'unhealthy' : allHealthy ? 'healthy' : 'degraded',
      checks: results,
      timestamp: new Date().toISOString()
    };
  }
}

// Setup
const healthChecker = new HealthChecker();

healthChecker.register({
  name: 'database',
  check: async () => {
    await db.query('SELECT 1');
    return true;
  },
  timeout: 3000,
  critical: true
});

healthChecker.register({
  name: 'redis',
  check: async () => {
    await redis.ping();
    return true;
  },
  timeout: 2000,
  critical: false
});

// Endpoint
app.get('/health', async (req, res) => {
  const health = await healthChecker.checkHealth();
  const statusCode = health.status === 'healthy' ? 200 : 503;
  res.status(statusCode).json(health);
});
```

## Graceful Degradation

### Feature Flags

```typescript
class FeatureFlags {
  private flags: Map<string, boolean> = new Map();

  constructor(private fallbackEnabled: boolean = false) {}

  isEnabled(feature: string): boolean {
    return this.flags.get(feature) ?? this.fallbackEnabled;
  }

  enable(feature: string): void {
    this.flags.set(feature, true);
  }

  disable(feature: string): void {
    this.flags.set(feature, false);
  }
}

const features = new FeatureFlags(false);

// Gracefully degrade when recommendation service fails
async function getRecommendations(userId: string): Promise<Product[]> {
  if (!features.isEnabled('recommendations')) {
    return getDefaultRecommendations();
  }

  try {
    return await recommendationService.get(userId);
  } catch (error) {
    // Disable feature temporarily
    features.disable('recommendations');
    setTimeout(() => features.enable('recommendations'), 60000);  // Re-enable after 1 min

    return getDefaultRecommendations();
  }
}
```

## Best Practices

### 1. Combine Patterns

```typescript
class ResilientService {
  private circuitBreaker: CircuitBreaker;
  private bulkhead: Bulkhead;

  constructor() {
    this.circuitBreaker = new CircuitBreaker(5, 2, 60000);
    this.bulkhead = new Bulkhead(10);
  }

  async call<T>(operation: () => Promise<T>): Promise<T> {
    return await this.bulkhead.execute(async () => {
      return await this.circuitBreaker.execute(async () => {
        return await retryWithBackoff(operation, {
          maxRetries: 3,
          initialDelayMs: 1000,
          maxDelayMs: 5000,
          backoffMultiplier: 2
        });
      });
    });
  }
}
```

### 2. Monitor Everything

```typescript
class MonitoredCircuitBreaker extends CircuitBreaker {
  private metrics = {
    successCount: 0,
    failureCount: 0,
    timeoutCount: 0,
    rejectedCount: 0
  };

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    try {
      const result = await super.execute(operation);
      this.metrics.successCount++;
      return result;
    } catch (error) {
      if (error.message === 'Circuit breaker is OPEN') {
        this.metrics.rejectedCount++;
      } else if (error instanceof TimeoutError) {
        this.metrics.timeoutCount++;
      } else {
        this.metrics.failureCount++;
      }
      throw error;
    }
  }

  getMetrics() {
    return { ...this.metrics, ...this.getStats() };
  }
}
```

### 3. Test Failure Scenarios

```typescript
describe('Resilience', () => {
  it('should open circuit after threshold failures', async () => {
    const breaker = new CircuitBreaker(3, 2, 1000);
    const failingOp = () => Promise.reject(new Error('Fail'));

    // Trigger failures
    for (let i = 0; i < 3; i++) {
      await expect(breaker.execute(failingOp)).rejects.toThrow();
    }

    expect(breaker.getState()).toBe('OPEN');

    // Should reject immediately
    await expect(breaker.execute(() => Promise.resolve('ok')))
      .rejects.toThrow('Circuit breaker is OPEN');
  });
});
```

### 4. Set Appropriate Timeouts

```typescript
const timeouts = {
  database: 3000,      // 3s
  cache: 500,          // 500ms
  externalAPI: 10000,  // 10s
  internalService: 5000 // 5s
};
```

### 5. Use Jitter

Prevent thundering herd by adding randomness to retries:
```typescript
const jitter = Math.random() * delay * 0.1;
await sleep(delay + jitter);
```
