# Error Handling Guide: Retry Strategies

## Retry Strategies

### Exponential Backoff

```typescript
async function retry<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries: number;
    initialDelay: number;
    maxDelay: number;
    backoffMultiplier: number;
    retryableErrors?: string[];
  }
): Promise<T> {
  let lastError: Error;
  let delay = options.initialDelay;

  for (let attempt = 0; attempt <= options.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      // Check if error is retryable
      if (options.retryableErrors) {
        const isRetryable = options.retryableErrors.includes(error.code);
        if (!isRetryable) {
          throw error;
        }
      }

      // Last attempt - throw error
      if (attempt === options.maxRetries) {
        throw error;
      }

      // Wait before retry
      await sleep(delay);

      // Exponential backoff
      delay = Math.min(
        delay * options.backoffMultiplier,
        options.maxDelay
      );

      console.log(`Retry attempt ${attempt + 1}/${options.maxRetries}`);
    }
  }

  throw lastError!;
}

// Usage
const result = await retry(
  () => externalApi.call(),
  {
    maxRetries: 3,
    initialDelay: 1000,
    maxDelay: 10000,
    backoffMultiplier: 2,
    retryableErrors: ['NETWORK_ERROR', 'TIMEOUT']
  }
);
```

### Circuit Breaker

```typescript
class CircuitBreaker {
  private failures = 0;
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private nextAttempt: number = Date.now();

  constructor(
    private threshold: number,
    private timeout: number,
    private resetTimeout: number
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() < this.nextAttempt) {
        throw new Error('Circuit breaker is OPEN');
      }
      this.state = 'HALF_OPEN';
    }

    try {
      const result = await Promise.race([
        fn(),
        this.timeoutPromise()
      ]);

      this.onSuccess();
      return result as T;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess() {
    this.failures = 0;
    this.state = 'CLOSED';
  }

  private onFailure() {
    this.failures++;

    if (this.failures >= this.threshold) {
      this.state = 'OPEN';
      this.nextAttempt = Date.now() + this.resetTimeout;
    }
  }

  private timeoutPromise(): Promise<never> {
    return new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Timeout')), this.timeout)
    );
  }
}

// Usage
const breaker = new CircuitBreaker(
  5,      // threshold: 5 failures
  5000,   // timeout: 5 seconds
  60000   // reset after: 60 seconds
);

try {
  const result = await breaker.execute(() => externalApi.call());
} catch (error) {
  // Handle circuit open or failure
}
```

## Error Logging

### Structured Logging

```typescript
import winston from 'winston';

const logger = winston.createLogger({
  format: winston.format.json(),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'error.log', level: 'error' })
  ]
});

function logError(error: Error, context?: any) {
  const logData = {
    message: error.message,
    name: error.name,
    stack: error.stack,
    ...context
  };

  if (error instanceof AppError) {
    logData.code = error.code;
    logData.status = error.status;
    logData.details = error.details;
    logData.isOperational = error.isOperational;
  }

  logger.error(logData);
}

// Usage
try {
  await processOrder(orderId);
} catch (error) {
  logError(error, {
    operation: 'processOrder',
    orderId,
    userId: req.user.id,
    request_id: req.id
  });
  throw error;
}
```

