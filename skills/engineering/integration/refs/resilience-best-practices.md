# Resilience Patterns Guide: Best Practices

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
