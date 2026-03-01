# API Versioning Guide: Breaking Changes

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
```typescript
// V1
const date = response.order_date;

// V2
const date = new Date(response.created_at);
```
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
