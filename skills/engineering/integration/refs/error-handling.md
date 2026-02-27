# Error Handling Guide

Comprehensive patterns and best practices for handling errors in distributed systems and APIs.

## Error Response Format

### Standard Structure

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "value": "not-an-email"
      },
      {
        "field": "age",
        "message": "Must be at least 18",
        "value": 15
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2025-01-24T10:00:00Z",
    "path": "/api/users",
    "method": "POST"
  }
}
```

### Error Components

1. **Code**: Machine-readable error identifier
2. **Message**: Human-readable description
3. **Details**: Specific field-level errors
4. **Request ID**: For tracing/debugging
5. **Timestamp**: When error occurred
6. **Path/Method**: Where error occurred

## HTTP Status Codes

### 4xx Client Errors

```typescript
// 400 Bad Request - Invalid syntax or validation
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "status": 400
  }
}

// 401 Unauthorized - Missing or invalid authentication
{
  "error": {
    "code": "UNAUTHENTICATED",
    "message": "Authentication required",
    "status": 401
  }
}

// 403 Forbidden - Authenticated but not authorized
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You don't have permission to access this resource",
    "status": 403
  }
}

// 404 Not Found - Resource doesn't exist
{
  "error": {
    "code": "NOT_FOUND",
    "message": "User not found",
    "status": 404,
    "resource": {
      "type": "user",
      "id": "123"
    }
  }
}

// 409 Conflict - Resource state conflict
{
  "error": {
    "code": "CONFLICT",
    "message": "User with this email already exists",
    "status": 409,
    "conflicting_field": "email"
  }
}

// 422 Unprocessable Entity - Semantic validation
{
  "error": {
    "code": "UNPROCESSABLE_ENTITY",
    "message": "Cannot delete user with active orders",
    "status": 422,
    "constraint": "has_active_orders"
  }
}

// 429 Too Many Requests - Rate limit exceeded
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "status": 429,
    "retry_after": 3600,
    "limit": 1000,
    "remaining": 0,
    "reset_at": "2025-01-24T11:00:00Z"
  }
}
```

### 5xx Server Errors

```typescript
// 500 Internal Server Error - Unexpected error
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred",
    "status": 500,
    "request_id": "req_abc123"  // For support lookup
  }
}

// 502 Bad Gateway - Invalid upstream response
{
  "error": {
    "code": "BAD_GATEWAY",
    "message": "Payment service unavailable",
    "status": 502,
    "upstream_service": "payment-gateway"
  }
}

// 503 Service Unavailable - Temporarily unavailable
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Service is temporarily unavailable",
    "status": 503,
    "retry_after": 60,
    "reason": "maintenance"
  }
}

// 504 Gateway Timeout - Upstream timeout
{
  "error": {
    "code": "GATEWAY_TIMEOUT",
    "message": "Request to payment service timed out",
    "status": 504,
    "upstream_service": "payment-gateway",
    "timeout_ms": 5000
  }
}
```

## Error Code Categories

### Authentication Errors

```typescript
const AuthErrors = {
  MISSING_TOKEN: {
    code: 'AUTH_001',
    message: 'Authentication token is missing',
    status: 401
  },
  INVALID_TOKEN: {
    code: 'AUTH_002',
    message: 'Authentication token is invalid',
    status: 401
  },
  EXPIRED_TOKEN: {
    code: 'AUTH_003',
    message: 'Authentication token has expired',
    status: 401
  },
  INVALID_CREDENTIALS: {
    code: 'AUTH_004',
    message: 'Invalid email or password',
    status: 401
  }
};
```

### Authorization Errors

```typescript
const AuthzErrors = {
  INSUFFICIENT_PERMISSIONS: {
    code: 'AUTHZ_001',
    message: 'Insufficient permissions',
    status: 403
  },
  RESOURCE_ACCESS_DENIED: {
    code: 'AUTHZ_002',
    message: 'Access to this resource is denied',
    status: 403
  },
  ACCOUNT_SUSPENDED: {
    code: 'AUTHZ_003',
    message: 'Your account has been suspended',
    status: 403
  }
};
```

### Validation Errors

```typescript
const ValidationErrors = {
  REQUIRED_FIELD: {
    code: 'VAL_001',
    message: 'Required field is missing'
  },
  INVALID_FORMAT: {
    code: 'VAL_002',
    message: 'Field has invalid format'
  },
  OUT_OF_RANGE: {
    code: 'VAL_003',
    message: 'Value is out of acceptable range'
  },
  INVALID_CHOICE: {
    code: 'VAL_004',
    message: 'Invalid choice for this field'
  }
};
```

### Business Logic Errors

```typescript
const BusinessErrors = {
  INSUFFICIENT_BALANCE: {
    code: 'BIZ_001',
    message: 'Insufficient account balance',
    status: 422
  },
  ORDER_ALREADY_SHIPPED: {
    code: 'BIZ_002',
    message: 'Cannot modify order that has already shipped',
    status: 422
  },
  PRODUCT_OUT_OF_STOCK: {
    code: 'BIZ_003',
    message: 'Product is out of stock',
    status: 422
  }
};
```

## Field-Level Errors

### Validation Errors

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "code": "INVALID_FORMAT",
        "message": "Must be a valid email address",
        "value": "not-an-email",
        "constraint": {
          "pattern": "^[^@]+@[^@]+\\.[^@]+$"
        }
      },
      {
        "field": "age",
        "code": "OUT_OF_RANGE",
        "message": "Must be between 18 and 120",
        "value": 15,
        "constraint": {
          "min": 18,
          "max": 120
        }
      },
      {
        "field": "items[0].quantity",
        "code": "OUT_OF_RANGE",
        "message": "Must be at least 1",
        "value": 0,
        "path": "items.0.quantity"
      }
    ]
  }
}
```

## Error Classes (TypeScript)

### Base Error Class

```typescript
class AppError extends Error {
  constructor(
    public code: string,
    public message: string,
    public status: number = 500,
    public details?: any,
    public isOperational: boolean = true
  ) {
    super(message);
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }

  toJSON() {
    return {
      error: {
        code: this.code,
        message: this.message,
        status: this.status,
        details: this.details,
        timestamp: new Date().toISOString()
      }
    };
  }
}
```

### Specific Error Classes

```typescript
class ValidationError extends AppError {
  constructor(details: ValidationDetail[]) {
    super(
      'VALIDATION_ERROR',
      'Request validation failed',
      400,
      details
    );
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super(
      'NOT_FOUND',
      `${resource} not found`,
      404,
      { resource, id }
    );
  }
}

class UnauthorizedError extends AppError {
  constructor(message: string = 'Authentication required') {
    super('UNAUTHORIZED', message, 401);
  }
}

class ForbiddenError extends AppError {
  constructor(message: string = 'Access denied') {
    super('FORBIDDEN', message, 403);
  }
}

class ConflictError extends AppError {
  constructor(message: string, field?: string) {
    super('CONFLICT', message, 409, { field });
  }
}

class RateLimitError extends AppError {
  constructor(retryAfter: number) {
    super(
      'RATE_LIMIT_EXCEEDED',
      'Too many requests',
      429,
      { retry_after: retryAfter }
    );
  }
}
```

### Usage

```typescript
// Throw specific errors
if (!user) {
  throw new NotFoundError('User', userId);
}

if (user.role !== 'admin') {
  throw new ForbiddenError('Admin access required');
}

if (await userExists(email)) {
  throw new ConflictError('User with this email already exists', 'email');
}
```

## Error Handler Middleware

### Express.js

```typescript
import { Request, Response, NextFunction } from 'express';

function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Log error
  console.error('Error:', {
    name: err.name,
    message: err.message,
    stack: err.stack,
    request_id: req.id,
    path: req.path,
    method: req.method,
    user: req.user?.id
  });

  // AppError with known structure
  if (err instanceof AppError) {
    return res.status(err.status).json({
      error: {
        code: err.code,
        message: err.message,
        details: err.details,
        request_id: req.id,
        timestamp: new Date().toISOString(),
        path: req.path,
        method: req.method
      }
    });
  }

  // Validation errors (e.g., from express-validator)
  if (err.name === 'ValidationError') {
    return res.status(400).json({
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        details: err.errors,
        request_id: req.id
      }
    });
  }

  // Database errors
  if (err.name === 'MongoError' || err.name === 'SequelizeError') {
    // Don't expose database details
    return res.status(500).json({
      error: {
        code: 'DATABASE_ERROR',
        message: 'A database error occurred',
        request_id: req.id
      }
    });
  }

  // Unknown errors
  res.status(500).json({
    error: {
      code: 'INTERNAL_ERROR',
      message: 'An unexpected error occurred',
      request_id: req.id,
      timestamp: new Date().toISOString()
    }
  });
}

// Use in Express app
app.use(errorHandler);
```

## Async Error Handling

### Wrapper Function

```typescript
// Wrap async route handlers
function asyncHandler(fn: Function) {
  return (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}

// Use in routes
app.get('/users/:id', asyncHandler(async (req, res) => {
  const user = await userService.findById(req.params.id);

  if (!user) {
    throw new NotFoundError('User', req.params.id);
  }

  res.json({ user });
}));
```

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

## Best Practices

### 1. Use Specific Error Codes

```typescript
// Good
throw new ValidationError([
  { field: 'email', code: 'INVALID_FORMAT', message: '...' }
]);

// Bad
throw new Error('Validation failed');
```

### 2. Include Request ID

Always include request ID for tracing:
```typescript
res.status(500).json({
  error: {
    message: 'Internal error',
    request_id: req.id  // Client can provide this to support
  }
});
```

### 3. Don't Expose Sensitive Details

```typescript
// Bad - exposes database structure
{
  "error": "ER_DUP_ENTRY: Duplicate entry 'user@example.com' for key 'users.email_unique'"
}

// Good - sanitized message
{
  "error": {
    "code": "CONFLICT",
    "message": "User with this email already exists"
  }
}
```

### 4. Distinguish Client vs Server Errors

```typescript
if (error.status >= 400 && error.status < 500) {
  // Client error - safe to show details
  return error.message;
} else {
  // Server error - hide details
  return 'An unexpected error occurred';
}
```

### 5. Provide Actionable Messages

```typescript
// Bad
{ "error": "Invalid input" }

// Good
{
  "error": {
    "message": "Email address is required and must be in valid format",
    "field": "email",
    "example": "user@example.com"
  }
}
```

### 6. Handle Async Errors

Always catch async errors:
```typescript
// Good
app.get('/users', asyncHandler(async (req, res) => {
  const users = await userService.findAll();
  res.json({ users });
}));

// Bad - unhandled promise rejection
app.get('/users', async (req, res) => {
  const users = await userService.findAll();
  res.json({ users });
});
```

### 7. Centralized Error Handling

Use middleware for consistent error responses:
```typescript
app.use(errorHandler);
```

### 8. Log Appropriately

```typescript
// Error severity levels
logger.error('Critical error', error);  // Requires immediate attention
logger.warn('Recoverable error', error); // Should be monitored
logger.info('Expected error', error);    // Part of normal flow
```

### 9. Graceful Degradation

```typescript
try {
  const recommendations = await recommendationService.get(userId);
  return recommendations;
} catch (error) {
  // Log error but don't fail the request
  logger.warn('Recommendations unavailable', error);
  return []; // Return empty array as fallback
}
```

### 10. Test Error Scenarios

```typescript
describe('User creation', () => {
  it('should return 409 for duplicate email', async () => {
    await createUser({ email: 'test@example.com' });

    const response = await request(app)
      .post('/users')
      .send({ email: 'test@example.com' });

    expect(response.status).toBe(409);
    expect(response.body.error.code).toBe('CONFLICT');
  });
});
```
