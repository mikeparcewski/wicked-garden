# Component Documentation Template

Template for documenting individual system components with clear structure and interfaces.

## Template Structure

```markdown
# Component Name

## Overview

Brief description of what this component does and why it exists.

**Type**: [Service | Library | Module | Package]
**Owner**: [Team Name]
**Status**: [Active | Deprecated | Experimental]

## Responsibilities

What this component is responsible for (and not responsible for):

- Responsibility 1
- Responsibility 2
- Responsibility 3

**Not responsible for**:
- What it explicitly doesn't do
- Boundaries with other components

## Architecture

### Component Diagram

```mermaid
graph TD
    Client[Client] --> API[Public API]
    API --> Service[Business Logic]
    Service --> Repo[Repository]
    Repo --> DB[(Database)]

    Service --> Queue[Message Queue]
    Queue --> Worker[Background Worker]
```

### Internal Structure

```
component-name/
├── api/              # Public interfaces
│   ├── handlers/     # HTTP handlers
│   └── routes.ts     # Route definitions
├── domain/           # Business logic
│   ├── entities/     # Domain models
│   ├── services/     # Business services
│   └── errors/       # Domain errors
├── infrastructure/   # External integrations
│   ├── database/     # Database access
│   ├── cache/        # Caching layer
│   └── events/       # Event publishing
└── config/           # Configuration
```

## Public Interface

### API Endpoints

```
GET    /api/resources/:id     - Get resource by ID
POST   /api/resources         - Create new resource
PUT    /api/resources/:id     - Update resource
DELETE /api/resources/:id     - Delete resource
```

### Events Published

```
resource.created      - When a new resource is created
resource.updated      - When a resource is updated
resource.deleted      - When a resource is deleted
```

### Events Consumed

```
user.created         - Initialize resource for new user
payment.completed    - Update resource status
```

## Dependencies

### Required

- **PostgreSQL 14+**: Primary data store
- **Redis 7+**: Caching and session storage
- **RabbitMQ 3.x**: Event messaging

### Optional

- **Elasticsearch 8+**: Full-text search (if search enabled)

### Internal Dependencies

- **auth-service**: For authentication/authorization
- **notification-service**: For sending alerts

## Data Model

### Database Schema

```sql
CREATE TABLE resources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL,
  user_id UUID NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_resources_user_id ON resources(user_id);
CREATE INDEX idx_resources_status ON resources(status);
```

### Domain Model

```typescript
class Resource {
  constructor(
    public id: string,
    public name: string,
    public status: ResourceStatus,
    public userId: string,
    public createdAt: Date,
    public updatedAt: Date
  ) {}

  // Business logic methods
  activate(): void {
    if (this.status !== 'pending') {
      throw new Error('Can only activate pending resources');
    }
    this.status = 'active';
  }

  deactivate(): void {
    if (this.status !== 'active') {
      throw new Error('Can only deactivate active resources');
    }
    this.status = 'inactive';
  }
}

enum ResourceStatus {
  PENDING = 'pending',
  ACTIVE = 'active',
  INACTIVE = 'inactive'
}
```

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/db

# Redis
REDIS_URL=redis://localhost:6379

# Service
PORT=3000
LOG_LEVEL=info

# Feature flags
ENABLE_SEARCH=false
ENABLE_CACHE=true
```

### Configuration File

```yaml
# config/default.yaml
server:
  port: 3000
  timeout: 30000

database:
  pool:
    min: 2
    max: 10
  timeout: 5000

cache:
  ttl: 3600
  enabled: true

features:
  search: false
  notifications: true
```

## API Examples

### Create Resource

```http
POST /api/resources
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "My Resource",
  "userId": "550e8400-e29b-41d4-a716-446655440000"
}

Response: 201 Created
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "name": "My Resource",
  "status": "pending",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "createdAt": "2025-01-24T10:00:00Z",
  "updatedAt": "2025-01-24T10:00:00Z"
}
```

### Get Resource

```http
GET /api/resources/660e8400-e29b-41d4-a716-446655440000
Authorization: Bearer <token>

Response: 200 OK
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "name": "My Resource",
  "status": "active",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "createdAt": "2025-01-24T10:00:00Z",
  "updatedAt": "2025-01-24T10:05:00Z"
}
```

## Error Handling

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| RESOURCE_NOT_FOUND | 404 | Resource doesn't exist |
| INVALID_STATUS_TRANSITION | 422 | Invalid state change |
| DUPLICATE_RESOURCE | 409 | Resource already exists |
| UNAUTHORIZED_ACCESS | 403 | User can't access resource |

### Example Error Response

```json
{
  "error": {
    "code": "INVALID_STATUS_TRANSITION",
    "message": "Cannot activate resource in 'inactive' status",
    "details": {
      "current_status": "inactive",
      "requested_status": "active"
    }
  }
}
```

## Performance

### Targets

- **API Response Time**: P95 < 200ms
- **Database Queries**: < 50ms
- **Throughput**: 1000 req/sec

### Optimization Strategies

- Redis caching for frequently accessed resources
- Database connection pooling (max 10)
- Batch processing for bulk operations
- Index on user_id and status columns

## Security

### Authentication

- All endpoints require valid JWT token
- Token verified via auth-service

### Authorization

- Users can only access their own resources
- Admin role can access all resources

### Data Protection

- PII fields encrypted at rest
- Audit log for all modifications
- Rate limiting: 100 req/min per user

## Monitoring

### Metrics

```typescript
// Request metrics
http_requests_total{method, path, status}
http_request_duration_seconds{method, path}

// Business metrics
resources_created_total
resources_by_status{status}

// Error metrics
errors_total{type, code}
```

### Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | Error rate > 5% | Critical |
| Slow Responses | P95 > 500ms | Warning |
| Database Connection Pool | Usage > 80% | Warning |

### Logging

```json
{
  "timestamp": "2025-01-24T10:00:00Z",
  "level": "info",
  "component": "resource-service",
  "action": "create_resource",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "resourceId": "660e8400-e29b-41d4-a716-446655440000",
  "duration_ms": 45
}
```

## Testing

### Unit Tests

```typescript
describe('Resource', () => {
  it('should activate pending resource', () => {
    const resource = new Resource(
      '1',
      'Test',
      ResourceStatus.PENDING,
      'user1',
      new Date(),
      new Date()
    );

    resource.activate();

    expect(resource.status).toBe(ResourceStatus.ACTIVE);
  });

  it('should throw error when activating non-pending resource', () => {
    const resource = new Resource(
      '1',
      'Test',
      ResourceStatus.ACTIVE,
      'user1',
      new Date(),
      new Date()
    );

    expect(() => resource.activate()).toThrow();
  });
});
```

### Integration Tests

```typescript
describe('Resource API', () => {
  it('should create resource', async () => {
    const response = await request(app)
      .post('/api/resources')
      .set('Authorization', `Bearer ${token}`)
      .send({
        name: 'Test Resource',
        userId: userId
      });

    expect(response.status).toBe(201);
    expect(response.body).toHaveProperty('id');
  });
});
```

### Contract Tests

Test integration points with other services.

## Deployment

### Requirements

- Node.js 20 LTS
- 512MB RAM minimum
- 1 CPU core

### Environment

| Environment | Instances | Resources |
|-------------|-----------|-----------|
| Development | 1 | 512MB, 0.5 CPU |
| Staging | 2 | 1GB, 1 CPU |
| Production | 4 | 2GB, 2 CPU |

### Health Check

```http
GET /health

Response: 200 OK
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "message_queue": "healthy"
  }
}
```

## Disaster Recovery

### Backup Strategy

- Database: Daily snapshots, 30-day retention
- Configuration: Stored in Git
- Secrets: Stored in HashiCorp Vault

### Recovery Procedures

1. Restore database from latest snapshot
2. Deploy from last known good version
3. Verify health checks pass
4. Monitor for errors

**RTO**: 2 hours
**RPO**: 24 hours

## Runbooks

### Common Issues

#### High Memory Usage

**Symptoms**: Memory > 80%
**Diagnosis**: Check for connection leaks
**Fix**:
1. Check connection pool metrics
2. Review recent code changes
3. Restart service if necessary

#### Slow Database Queries

**Symptoms**: Query time > 100ms
**Diagnosis**: Check slow query log
**Fix**:
1. Identify slow queries
2. Add appropriate indexes
3. Consider caching frequently accessed data

## Change Log

### v2.0.0 (2025-01-20)

**Breaking Changes**:
- Changed resource ID from integer to UUID
- Removed `description` field

**Added**:
- Status field with workflow
- Event publishing

**Fixed**:
- Race condition in concurrent updates

### v1.1.0 (2024-12-15)

**Added**:
- Search functionality
- Bulk operations

## References

- [API Documentation](docs/api.md)
- [Database Schema](docs/schema.sql)
- [Architecture Decision Records](docs/adr/)
- [Source Code](https://github.com/example/resource-service)

## Contact

- **Team**: Platform Team
- **Slack**: #platform-team
- **On-call**: platform-oncall@example.com
- **JIRA**: PLAT project
```

## Example: Auth Component

```markdown
# Authentication Component

## Overview

Handles user authentication, authorization, and session management for all services in the platform.

**Type**: Service
**Owner**: Security Team
**Status**: Active

## Responsibilities

- User authentication (login/logout)
- JWT token generation and validation
- Session management
- Password reset flows
- OAuth2 integration (Google, GitHub)

**Not responsible for**:
- User profile management (handled by user-service)
- Authorization policies (policies defined in each service)
- Password storage (delegated to identity provider)

## Public Interface

### API Endpoints

```
POST /auth/login              - Authenticate user
POST /auth/logout             - End user session
POST /auth/refresh            - Refresh access token
POST /auth/forgot-password    - Initiate password reset
GET  /auth/verify             - Verify token validity
```

### Events Published

```
auth.user.logged_in     - User successfully logged in
auth.user.logged_out    - User logged out
auth.password.reset     - Password was reset
auth.token.refreshed    - Access token refreshed
```

## Dependencies

### Required

- **PostgreSQL 14+**: Session storage
- **Redis 7+**: Token blacklist and rate limiting
- **Email Service**: For password reset emails

### Internal Dependencies

- **user-service**: Fetch user credentials

## Data Model

```typescript
interface Session {
  id: string;
  userId: string;
  token: string;
  refreshToken: string;
  expiresAt: Date;
  createdAt: Date;
  userAgent: string;
  ipAddress: string;
}

interface TokenPayload {
  sub: string;        // User ID
  email: string;
  role: string;
  exp: number;        // Expiration
  iat: number;        // Issued at
}
```

## Configuration

```yaml
jwt:
  secret: ${JWT_SECRET}
  accessTokenTTL: 900      # 15 minutes
  refreshTokenTTL: 604800  # 7 days

rateLimit:
  login: 5                  # 5 attempts per minute
  passwordReset: 3          # 3 attempts per hour

oauth:
  google:
    clientId: ${GOOGLE_CLIENT_ID}
    clientSecret: ${GOOGLE_CLIENT_SECRET}
```

## Security

### Authentication Flow

1. Client sends credentials
2. Service validates against user-service
3. Generate JWT access token (15min TTL)
4. Generate refresh token (7day TTL)
5. Store session in database
6. Return tokens to client

### Token Refresh Flow

1. Client sends refresh token
2. Validate refresh token
3. Check if token is blacklisted
4. Generate new access token
5. Return new access token

### Security Measures

- Bcrypt for password hashing (cost factor: 10)
- Rate limiting on login endpoint
- Token blacklist for logout
- HTTPS only
- CORS restrictions

## Performance

**Targets**:
- Login: P95 < 300ms
- Token validation: P95 < 50ms

**Optimization**:
- Redis caching for token validation
- Database connection pooling
- Async email sending

## Monitoring

**Key Metrics**:
- Login success/failure rate
- Token validation rate
- Session duration
- Password reset requests

**Alerts**:
- Login failure rate > 20%
- Token validation errors > 5%
```

## Tips for Using Template

### Do Include

- Clear responsibilities
- All interfaces (APIs, events, etc.)
- Dependencies
- Configuration
- Security considerations
- Monitoring approach

### Don't Include

- Implementation details (that's in code)
- Every single function
- Speculative future features
- Information better suited for ADRs

### Keep Updated

- Review quarterly
- Update on major changes
- Link to current source code
- Mark deprecated features
