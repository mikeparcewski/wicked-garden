# Resilience Patterns Guide: Rate Limiting

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

