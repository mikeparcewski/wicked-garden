# Interface Documentation Template

Template for documenting component interfaces, contracts, and integration points.

## Template Structure

```markdown
# Interface Name

## Overview

Brief description of what this interface provides and who uses it.

**Type**: [REST API | GraphQL | gRPC | Event Stream | Library]
**Provider**: [Component Name]
**Consumers**: [List of components that use this interface]
**Stability**: [Stable | Beta | Experimental | Deprecated]

## Contract

### Purpose

What problem does this interface solve? What functionality does it provide?

### Guarantees

What this interface guarantees to consumers:

- Guarantee 1 (e.g., idempotency)
- Guarantee 2 (e.g., response time)
- Guarantee 3 (e.g., data consistency)

### Assumptions

What this interface assumes about consumers:

- Assumption 1 (e.g., authentication)
- Assumption 2 (e.g., rate limits respected)
- Assumption 3 (e.g., proper error handling)

## Operations

### Operation 1: [Name]

**Description**: What this operation does

**Input**:
```typescript
interface Input {
  field1: string;
  field2: number;
  field3?: boolean;  // Optional
}
```

**Output**:
```typescript
interface Output {
  result: string;
  metadata: {
    timestamp: string;
    version: string;
  };
}
```

**Errors**:
- `ERROR_CODE_1`: Description and recovery
- `ERROR_CODE_2`: Description and recovery

**Example**:
```typescript
const result = await interface.operation1({
  field1: "value",
  field2: 42,
  field3: true
});
```

**Performance**:
- Expected latency: < 100ms
- Throughput: 1000 ops/sec

**Idempotency**: [Yes | No | Conditional]

**Side Effects**: [None | List of side effects]

### Operation 2: [Name]

[Same structure]

## Data Types

### Type1

```typescript
interface Type1 {
  id: string;
  name: string;
  status: 'active' | 'inactive' | 'pending';
  metadata: Record<string, any>;
  createdAt: Date;
  updatedAt: Date;
}
```

**Validation Rules**:
- `id`: UUID format
- `name`: 1-100 characters, alphanumeric
- `status`: Must be one of allowed values

**Invariants**:
- `createdAt` <= `updatedAt`
- `status` transitions follow workflow

### Type2

[Same structure]

## Error Handling

### Error Categories

| Category | HTTP Status | Retry | Description |
|----------|-------------|-------|-------------|
| Validation | 400 | No | Invalid input |
| Authentication | 401 | No | Missing/invalid auth |
| Authorization | 403 | No | Insufficient permissions |
| Not Found | 404 | No | Resource doesn't exist |
| Conflict | 409 | No | State conflict |
| Rate Limit | 429 | Yes | Too many requests |
| Server Error | 500 | Yes | Internal error |
| Unavailable | 503 | Yes | Service down |

### Error Response Format

```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: any;
    requestId: string;
    timestamp: string;
  };
}
```

### Example Error

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "User with ID 123 not found",
    "requestId": "req_abc123",
    "timestamp": "2025-01-24T10:00:00Z"
  }
}
```

## Authentication & Authorization

### Authentication Method

[Bearer Token | API Key | OAuth2 | mTLS | None]

**Example**:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Authorization

**Required Permissions**:
- `operation1`: `resource:read`
- `operation2`: `resource:write`
- `operation3`: `resource:admin`

**Scopes**:
- `read`: Read-only access
- `write`: Create and update
- `admin`: Full access including delete

## Versioning

**Current Version**: 2.1.0

**Supported Versions**:
- v1.x: Deprecated, sunset 2026-01-01
- v2.x: Current, stable

**Version Specification**:
[URL | Header | Query Parameter]

**Example**:
```
/api/v2/resources
Accept: application/vnd.api.v2+json
?version=2
```

### Breaking Changes

Documented in [CHANGELOG.md](./CHANGELOG.md)

**v2.0.0**:
- Changed ID format from integer to UUID
- Removed `description` field
- Renamed `user_name` to `username`

## Rate Limiting

**Limits**:
- Authenticated: 1000 requests/hour
- Unauthenticated: 100 requests/hour
- Burst: 20 requests/second

**Headers**:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1611218400
```

**Exceeded Response**:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 3600

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "retryAfter": 3600
  }
}
```

## Service Level Agreement (SLA)

**Availability**: 99.9% uptime

**Performance**:
- P50 latency: < 50ms
- P95 latency: < 200ms
- P99 latency: < 500ms

**Support**:
- Response time: 4 hours
- Resolution time: 24 hours

## Deprecation Policy

1. **Announcement**: 6 months before deprecation
2. **Warnings**: Deprecation headers in responses
3. **Sunset**: Version removed after sunset date

**Deprecation Headers**:
```http
Warning: 299 - "This API version is deprecated"
Sunset: Mon, 01 Jan 2026 00:00:00 GMT
Link: <https://docs.example.com/migration>; rel="deprecation"
```

## Testing

### Contract Tests

```typescript
describe('Interface Contract', () => {
  it('should return correct response format', async () => {
    const response = await api.operation1({
      field1: "test",
      field2: 42
    });

    expect(response).toHaveProperty('result');
    expect(response).toHaveProperty('metadata');
    expect(response.metadata).toHaveProperty('timestamp');
  });

  it('should handle not found error', async () => {
    await expect(
      api.operation1({ field1: "nonexistent", field2: 999 })
    ).rejects.toMatchObject({
      code: 'RESOURCE_NOT_FOUND',
      status: 404
    });
  });
});
```

### Performance Tests

```typescript
describe('Performance', () => {
  it('should respond within 200ms', async () => {
    const start = Date.now();
    await api.operation1({ field1: "test", field2: 42 });
    const duration = Date.now() - start;

    expect(duration).toBeLessThan(200);
  });
});
```

## Examples

### Basic Usage

```typescript
import { APIClient } from '@example/api-client';

const client = new APIClient({
  apiKey: process.env.API_KEY,
  baseURL: 'https://api.example.com'
});

// Create resource
const resource = await client.createResource({
  name: "My Resource",
  status: "active"
});

console.log(resource.id);  // "550e8400-e29b-41d4-a716-446655440000"
```

### Error Handling

```typescript
try {
  const resource = await client.getResource(id);
} catch (error) {
  if (error.code === 'RESOURCE_NOT_FOUND') {
    console.log('Resource not found');
  } else if (error.code === 'RATE_LIMIT_EXCEEDED') {
    const retryAfter = error.retryAfter;
    await sleep(retryAfter * 1000);
    // Retry...
  } else {
    throw error;
  }
}
```

### Pagination

```typescript
let hasMore = true;
let offset = 0;

while (hasMore) {
  const response = await client.listResources({
    limit: 100,
    offset
  });

  process(response.data);

  hasMore = response.pagination.hasMore;
  offset += 100;
}
```

## Client Libraries

**Official Clients**:
- JavaScript/TypeScript: `@example/api-client`
- Python: `example-api-client`
- Go: `github.com/example/api-client-go`

**Community Clients**:
- Ruby: `example-api` (not officially supported)
- Java: `com.example.api-client` (not officially supported)

## Monitoring

### Metrics

Provider should expose:
```
interface_requests_total{operation, status}
interface_request_duration_seconds{operation}
interface_errors_total{operation, error_code}
```

Consumer should track:
```
interface_client_requests_total{operation, status}
interface_client_errors_total{operation, error_code}
interface_circuit_breaker_state{state}
```

### Health Check

```http
GET /health

Response: 200 OK
{
  "status": "healthy",
  "version": "2.1.0",
  "uptime": 3600
}
```

## Migration Guide

### Migrating from v1 to v2

**Breaking Changes**:

1. **ID Format Change**
   ```typescript
   // v1
   const id: number = 123;

   // v2
   const id: string = "550e8400-e29b-41d4-a716-446655440000";
   ```

2. **Field Rename**
   ```typescript
   // v1
   const name = resource.user_name;

   // v2
   const name = resource.username;
   ```

**Step-by-Step**:

1. Update client library to v2-compatible version
2. Update ID handling in your code
3. Update field names
4. Test thoroughly
5. Deploy
6. Monitor for errors

## Changelog

### v2.1.0 (2025-01-20)

**Added**:
- Bulk operations
- Filtering by status

**Fixed**:
- Race condition in concurrent updates

### v2.0.0 (2024-12-01)

**Breaking Changes**:
- Changed ID format to UUID
- Removed `description` field

**Added**:
- Pagination support
- Rate limiting

## Support

**Documentation**: https://docs.example.com/api
**Status Page**: https://status.example.com
**Support Email**: api-support@example.com
**Slack**: #api-support
```

## Example: User Service Interface

```markdown
# User Service Interface

## Overview

Provides user management operations for all platform services.

**Type**: REST API
**Provider**: user-service
**Consumers**: auth-service, order-service, notification-service
**Stability**: Stable

## Contract

### Purpose

Centralized user data management and profile operations.

### Guarantees

- User IDs are unique and immutable
- Email addresses are unique across the system
- Responses include all non-sensitive user fields
- Operations are idempotent where applicable

### Assumptions

- Caller is authenticated and authorized
- Email addresses are validated before submission
- Rate limits are respected

## Operations

### GetUser

**Description**: Retrieve user by ID

**Input**:
```typescript
interface GetUserRequest {
  userId: string;  // UUID format
}
```

**Output**:
```typescript
interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'user' | 'guest';
  status: 'active' | 'suspended' | 'deleted';
  createdAt: string;  // ISO 8601
  updatedAt: string;  // ISO 8601
}
```

**Errors**:
- `USER_NOT_FOUND` (404): User with given ID doesn't exist
- `UNAUTHORIZED` (401): Invalid or missing auth token
- `FORBIDDEN` (403): Insufficient permissions

**Example**:
```http
GET /api/users/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <token>

Response: 200 OK
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "alice@example.com",
  "name": "Alice Smith",
  "role": "user",
  "status": "active",
  "createdAt": "2025-01-24T10:00:00Z",
  "updatedAt": "2025-01-24T10:00:00Z"
}
```

**Performance**: P95 < 50ms
**Idempotency**: Yes
**Side Effects**: None

### CreateUser

**Description**: Create a new user account

**Input**:
```typescript
interface CreateUserRequest {
  email: string;        // Valid email, unique
  name: string;         // 1-100 characters
  password: string;     // Min 8 characters
  role?: 'admin' | 'user' | 'guest';  // Default: 'user'
}
```

**Output**:
```typescript
interface CreateUserResponse {
  user: User;
}
```

**Errors**:
- `DUPLICATE_EMAIL` (409): Email already exists
- `VALIDATION_ERROR` (400): Invalid input
- `WEAK_PASSWORD` (400): Password doesn't meet requirements

**Example**:
```http
POST /api/users
Authorization: Bearer <token>
Content-Type: application/json

{
  "email": "bob@example.com",
  "name": "Bob Jones",
  "password": "SecurePass123!"
}

Response: 201 Created
Location: /api/users/660e8400-e29b-41d4-a716-446655440000
{
  "user": {
    "id": "660e8400-e29b-41d4-a716-446655440000",
    "email": "bob@example.com",
    "name": "Bob Jones",
    "role": "user",
    "status": "active",
    "createdAt": "2025-01-24T10:05:00Z",
    "updatedAt": "2025-01-24T10:05:00Z"
  }
}
```

**Performance**: P95 < 200ms
**Idempotency**: No (generates new ID each time)
**Side Effects**:
- Publishes `user.created` event
- Sends welcome email

## Authentication & Authorization

### Authentication

Bearer token required for all endpoints:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Authorization

| Operation | Required Permission |
|-----------|-------------------|
| GetUser | `user:read` (own) or `user:read:all` (any) |
| CreateUser | `user:create` |
| UpdateUser | `user:write` (own) or `user:write:all` (any) |
| DeleteUser | `user:delete` |

## Service Level Agreement (SLA)

**Availability**: 99.9%

**Performance**:
- GET operations: P95 < 50ms
- POST/PUT operations: P95 < 200ms

**Support**:
- Response time: 2 hours
- Resolution time: 8 hours

## Client Library Example

```typescript
import { UserServiceClient } from '@example/user-service-client';

const client = new UserServiceClient({
  baseURL: 'https://api.example.com',
  apiKey: process.env.API_KEY
});

// Get user
const user = await client.getUser('550e8400-...');

// Create user
const newUser = await client.createUser({
  email: 'new@example.com',
  name: 'New User',
  password: 'SecurePass123!'
});
```
```

## Tips for Documenting Interfaces

1. **Be Explicit**: Don't assume consumers understand context
2. **Show Examples**: Real request/response examples
3. **Document Errors**: All possible error conditions
4. **Version Everything**: Track changes over time
5. **Performance Targets**: Set clear expectations
6. **Keep Updated**: Interface docs should match implementation
