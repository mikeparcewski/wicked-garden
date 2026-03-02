# Interface Documentation Template - Examples and Tips

Complete User Service interface example and tips for documenting interfaces.

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
