# Resilience Patterns Guide: Circuit Breaker Pattern

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

