# Error Handling Guide: Error Response Format

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

