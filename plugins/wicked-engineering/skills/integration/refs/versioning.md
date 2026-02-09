# API Versioning Guide

Comprehensive guide to API versioning strategies, migration patterns, and best practices.

## Versioning Strategies

### URL Versioning

Most common and explicit approach.

```
/api/v1/users
/api/v2/users
```

**Pros**:
- Explicit and visible
- Easy to route
- Browser-friendly
- Easy to test different versions

**Cons**:
- URLs change between versions
- Can't version individual resources differently

**Implementation**:
```typescript
// Express.js
app.use('/api/v1', v1Router);
app.use('/api/v2', v2Router);

// v1Router
v1Router.get('/users/:id', (req, res) => {
  // V1 implementation
  res.json({
    id: user.id,
    name: user.name
  });
});

// v2Router
v2Router.get('/users/:id', (req, res) => {
  // V2 implementation (added email)
  res.json({
    id: user.id,
    name: user.name,
    email: user.email
  });
});
```

### Header Versioning

Version specified in request headers.

```http
GET /api/users/123
Accept: application/vnd.myapi.v2+json
```

or

```http
GET /api/users/123
API-Version: 2
```

**Pros**:
- Clean URLs (don't change)
- Can version per-resource
- RESTful purist preference

**Cons**:
- Less visible
- Harder to test (can't just paste URL)
- More complex routing

**Implementation**:
```typescript
app.get('/api/users/:id', (req, res) => {
  const version = req.headers['api-version'] || '1';

  if (version === '1') {
    return handleV1(req, res);
  } else if (version === '2') {
    return handleV2(req, res);
  }

  res.status(400).json({ error: 'Unsupported API version' });
});
```

### Query Parameter Versioning

```
/api/users?version=2
/api/users?api-version=2
```

**Pros**:
- Simple to implement
- Visible in URL
- Optional parameter

**Cons**:
- Clutters query string
- Not as clean as URL versioning

### Content Negotiation

Using Accept header with custom media type.

```http
GET /api/users/123
Accept: application/vnd.myapi.user.v2+json
```

**Pros**:
- RESTful approach
- Fine-grained control
- Can version per resource type

**Cons**:
- Complex
- Difficult to debug
- Harder for clients to use

## Semantic Versioning

Use semantic versioning for API versions:

```
MAJOR.MINOR.PATCH

2.1.3
```

- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes

### Examples

```
v1.0.0 → v1.1.0   # Added new optional field
v1.1.0 → v1.1.1   # Fixed bug in response
v1.1.1 → v2.0.0   # Removed field (breaking)
```

### In Practice

Most APIs simplify to major version only:

```
/api/v1/users
/api/v2/users
```

Full semantic version in response headers:
```http
HTTP/1.1 200 OK
API-Version: 2.1.3
```

## Backward Compatibility

### Adding Fields (Safe)

```typescript
// V1 Response
{
  "id": "123",
  "name": "Alice"
}

// V2 Response (added email - backward compatible)
{
  "id": "123",
  "name": "Alice",
  "email": "alice@example.com"  // New field
}
```

Clients ignoring unknown fields will continue to work.

### Making Fields Optional (Safe)

```typescript
// V1 Request
{
  "name": "Alice",
  "email": "alice@example.com"  // Required
}

// V2 Request (email optional)
{
  "name": "Alice"
  // email is now optional
}
```

### Adding Optional Parameters (Safe)

```typescript
// V1
GET /api/users?limit=10

// V2 (added sort parameter)
GET /api/users?limit=10&sort=name
```

### Deprecation (Safe)

Mark fields as deprecated but keep them:

```typescript
// V2 Response
{
  "id": "123",
  "name": "Alice",
  "full_name": "Alice Smith",  // New field
  "deprecated_name": "Alice"   // Deprecated, but still present
}
```

## Breaking Changes

### Removing Fields

```typescript
// V1 Response
{
  "id": "123",
  "name": "Alice",
  "age": 30
}

// V2 Response (removed age - BREAKING)
{
  "id": "123",
  "name": "Alice"
  // age removed
}
```

**Solution**: Keep field but deprecate it first.

### Renaming Fields

```typescript
// V1 Response
{
  "user_name": "Alice"
}

// V2 Response (renamed - BREAKING)
{
  "username": "Alice"
}
```

**Solution**: Include both fields temporarily.

### Changing Field Types

```typescript
// V1 Response
{
  "id": 123  // number
}

// V2 Response (changed to string - BREAKING)
{
  "id": "123"  // string
}
```

**Solution**: Create new major version.

### Changing Behavior

```typescript
// V1: Returns 404 if user not found
GET /api/users/999
Response: 404 Not Found

// V2: Returns 200 with null (BREAKING)
GET /api/users/999
Response: 200 OK
{ "user": null }
```

**Solution**: Document clearly and version.

## Migration Strategies

### Dual-Write Pattern

Support multiple versions simultaneously.

```typescript
class UserService {
  async createUser(data: any, version: string): Promise<User> {
    const user = await db.users.create(data);

    // Write to both old and new formats
    if (version === '1') {
      return this.formatV1(user);
    } else if (version === '2') {
      return this.formatV2(user);
    }
  }

  private formatV1(user: User) {
    return {
      id: user.id,
      name: user.name
    };
  }

  private formatV2(user: User) {
    return {
      id: user.id,
      name: user.name,
      email: user.email,
      created_at: user.createdAt
    };
  }
}
```

### Adapter Pattern

Transform between versions.

```typescript
class V1toV2Adapter {
  transform(v1Response: any): any {
    return {
      ...v1Response,
      email: v1Response.user_email,  // Renamed field
      createdAt: v1Response.created_date,  // Renamed field
      metadata: {
        // Restructured
        version: '2.0',
        legacy: true
      }
    };
  }
}

// Usage
app.get('/api/v2/users/:id', async (req, res) => {
  const user = await userServiceV1.getUser(req.params.id);
  const adapted = new V1toV2Adapter().transform(user);
  res.json(adapted);
});
```

### Proxy Pattern

V2 proxies to V1 with transformations.

```typescript
// V2 endpoint delegates to V1
app.get('/api/v2/users/:id', async (req, res) => {
  // Call V1 handler
  const v1Response = await handleV1Request(req);

  // Transform to V2 format
  const v2Response = transformV1toV2(v1Response);

  res.json(v2Response);
});
```

### Deprecation Timeline

```
Month 1-3:  Announce deprecation, V2 available
Month 4-9:  V1 marked deprecated, warnings in responses
Month 10-12: V1 read-only, writes redirect to V2
Month 13+:   V1 removed
```

## Version Management

### Default Version

```typescript
app.use('/api/users', (req, res, next) => {
  // Default to latest version if not specified
  const version = req.headers['api-version'] || '2';
  req.apiVersion = version;
  next();
});
```

### Version Support Matrix

```typescript
const SUPPORTED_VERSIONS = {
  '1': {
    status: 'deprecated',
    sunset: '2026-01-01',
    docs: 'https://docs.example.com/api/v1'
  },
  '2': {
    status: 'current',
    sunset: null,
    docs: 'https://docs.example.com/api/v2'
  },
  '3': {
    status: 'beta',
    sunset: null,
    docs: 'https://docs.example.com/api/v3'
  }
};

app.use((req, res, next) => {
  const version = req.apiVersion;
  const versionInfo = SUPPORTED_VERSIONS[version];

  if (!versionInfo) {
    return res.status(400).json({
      error: 'Unsupported API version',
      supported_versions: Object.keys(SUPPORTED_VERSIONS)
    });
  }

  // Add deprecation warning
  if (versionInfo.status === 'deprecated') {
    res.set('Warning', `299 - "API version ${version} is deprecated. Sunset: ${versionInfo.sunset}"`);
    res.set('Sunset', versionInfo.sunset);
  }

  next();
});
```

### Sunset Header

Communicate deprecation:

```http
HTTP/1.1 200 OK
Warning: 299 - "API v1 is deprecated. Please migrate to v2"
Sunset: Mon, 01 Jan 2026 00:00:00 GMT
Deprecation: true
Link: <https://docs.example.com/migration>; rel="deprecation"
```

## GraphQL Versioning

GraphQL uses schema evolution instead of versioning.

### Field Deprecation

```graphql
type User {
  id: ID!
  name: String!
  fullName: String!  # New field

  # Deprecated field
  user_name: String! @deprecated(reason: "Use 'name' instead")
}
```

### Schema Directives

```graphql
directive @apiVersion(
  added: String!
  deprecated: String
  removed: String
) on FIELD_DEFINITION

type User {
  id: ID!
  name: String! @apiVersion(added: "1.0")
  email: String! @apiVersion(added: "2.0")
  age: Int @apiVersion(added: "1.0", deprecated: "2.0", removed: "3.0")
}
```

## gRPC Versioning

### Package Versioning

```protobuf
// v1/user.proto
syntax = "proto3";
package user.v1;

service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
}

// v2/user.proto
syntax = "proto3";
package user.v2;

service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
}
```

### Field Evolution

```protobuf
message User {
  string id = 1;
  string name = 2;

  // V2: Added email
  string email = 3;

  // V3: Deprecated age (use birthdate instead)
  int32 age = 4 [deprecated = true];
  string birthdate = 5;

  // Never reuse field numbers!
  reserved 6, 7;  // Old fields
  reserved "old_field";
}
```

## Best Practices

### 1. Version from Day One

```typescript
// Don't start with
/api/users

// Start with versioned endpoint
/api/v1/users
```

### 2. Document Breaking Changes

```markdown
# V2 Migration Guide

## Breaking Changes

### User Endpoint

**Changed**: User ID format
- **V1**: Integer ID (`123`)
- **V2**: String UUID (`550e8400-e29b-41d4-a716-446655440000`)

**Migration**: Update client code to handle string IDs.

### Order Endpoint

**Removed**: `order_date` field
**Replaced by**: `created_at` (ISO 8601 timestamp)

**Migration**:
\`\`\`typescript
// V1
const date = response.order_date;

// V2
const date = new Date(response.created_at);
\`\`\`
```

### 3. Provide Migration Tools

```typescript
// Migration script
async function migrateV1toV2() {
  const v1Users = await fetchV1Users();

  for (const user of v1Users) {
    const v2User = {
      id: generateUUID(user.id),  // Convert ID
      name: user.name,
      email: user.email || `user${user.id}@example.com`,  // Add required field
      createdAt: user.created_date.toISOString()  // Convert format
    };

    await createV2User(v2User);
  }
}
```

### 4. Sunset Old Versions

Set clear timelines:

```typescript
const VERSION_LIFECYCLE = {
  'v1': {
    released: '2023-01-01',
    deprecated: '2024-01-01',
    sunset: '2025-01-01'  // 2 years support
  },
  'v2': {
    released: '2024-01-01',
    deprecated: null,
    sunset: null
  }
};
```

### 5. Monitor Version Usage

```typescript
app.use((req, res, next) => {
  const version = req.apiVersion;

  // Track version usage
  metrics.increment('api.version.usage', {
    version,
    endpoint: req.path
  });

  next();
});
```

### 6. Test Backward Compatibility

```typescript
describe('API Compatibility', () => {
  it('V2 should accept V1 request format', async () => {
    const v1Request = {
      user_name: 'Alice',
      user_email: 'alice@example.com'
    };

    const response = await request(app)
      .post('/api/v2/users')
      .send(v1Request);

    expect(response.status).toBe(201);
  });

  it('V2 response should include V1 fields', async () => {
    const response = await request(app)
      .get('/api/v2/users/123')
      .set('Accept-Version', '2');

    // New V2 field
    expect(response.body).toHaveProperty('email');

    // Deprecated V1 field still present
    expect(response.body).toHaveProperty('user_name');
  });
});
```

### 7. Version Discovery

Provide version information endpoint:

```typescript
app.get('/api/versions', (req, res) => {
  res.json({
    versions: [
      {
        version: '1',
        status: 'deprecated',
        released: '2023-01-01',
        deprecated: '2024-01-01',
        sunset: '2025-01-01',
        docs: 'https://docs.example.com/api/v1'
      },
      {
        version: '2',
        status: 'current',
        released: '2024-01-01',
        docs: 'https://docs.example.com/api/v2'
      }
    ],
    current: '2',
    latest: '2'
  });
});
```

### 8. Client SDK Versioning

```typescript
// client-v1.ts
export class APIClientV1 {
  async getUser(id: number): Promise<UserV1> {
    const response = await fetch(`/api/v1/users/${id}`);
    return response.json();
  }
}

// client-v2.ts
export class APIClientV2 {
  async getUser(id: string): Promise<UserV2> {
    const response = await fetch(`/api/v2/users/${id}`);
    return response.json();
  }
}
```

### 9. Graceful Degradation

```typescript
app.get('/api/:version/users/:id', async (req, res) => {
  const { version, id } = req.params;

  const user = await userService.getUser(id);

  // Format based on version
  switch (version) {
    case 'v1':
      return res.json(formatV1(user));
    case 'v2':
      return res.json(formatV2(user));
    default:
      // Unknown version - use latest
      return res.json(formatV2(user));
  }
});
```

### 10. Clear Communication

Announce version changes well in advance:

```markdown
# API Changelog

## [2.0.0] - 2024-06-01

### Breaking Changes
- User IDs changed from integers to UUIDs
- `order_date` field removed, use `created_at` instead

### Added
- Email field to User resource
- Pagination support for all list endpoints

### Deprecated
- V1 API will be sunset on 2025-06-01

## [1.5.0] - 2024-03-01

### Added
- Search endpoint
- Bulk operations

### Fixed
- Date formatting inconsistencies
```

## Version Header Examples

```typescript
// Request
GET /api/users/123
API-Version: 2

// Response
HTTP/1.1 200 OK
API-Version: 2.1.0
API-Supported-Versions: 1, 2
API-Deprecated-Versions: 1
Content-Type: application/json

{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Alice",
  "email": "alice@example.com"
}
```
