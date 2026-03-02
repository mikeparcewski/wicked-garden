# Interface Documentation Template - Operations

Testing, examples, client libraries, monitoring, migration guides, and changelog.

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
