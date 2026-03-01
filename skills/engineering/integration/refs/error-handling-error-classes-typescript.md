# Error Handling Guide: Error Classes (TypeScript)

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

