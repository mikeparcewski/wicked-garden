# Component Documentation Template - Structure

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
```
