# API Versioning Guide: Migration Strategies

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

