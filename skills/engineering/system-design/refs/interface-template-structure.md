# Interface Documentation Template - Structure

Template for documenting component interfaces, contracts, and integration points. Covers overview, contracts, operations, data types, error handling, and auth.

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
```
