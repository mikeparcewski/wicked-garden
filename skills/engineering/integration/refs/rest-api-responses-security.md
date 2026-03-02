# REST API Design - Responses, Headers, Security, and Best Practices

Response formats, status codes, headers, advanced patterns, security, and best practices.

## Response Formats

### Success Response Structure

```json
{
  "data": {
    "id": 123,
    "type": "user",
    "attributes": {
      "name": "Alice",
      "email": "alice@example.com"
    },
    "relationships": {
      "organization": {
        "data": { "type": "organization", "id": 456 }
      }
    }
  },
  "meta": {
    "version": "1.0",
    "timestamp": "2025-01-24T10:00:00Z"
  }
}
```

**Simpler Alternative**
```json
{
  "id": 123,
  "name": "Alice",
  "email": "alice@example.com",
  "organization_id": 456
}
```

### Error Response Structure

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
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2025-01-24T10:00:00Z"
  }
}
```

### Collection Response

```json
{
  "data": [
    { "id": 1, "name": "Alice" },
    { "id": 2, "name": "Bob" }
  ],
  "pagination": {
    "total": 150,
    "page": 3,
    "per_page": 20,
    "total_pages": 8
  },
  "links": {
    "self": "/users?page=3",
    "first": "/users?page=1",
    "prev": "/users?page=2",
    "next": "/users?page=4",
    "last": "/users?page=8"
  }
}
```

## Status Codes

### 2xx Success

| Code | Meaning | Use Case |
|------|---------|----------|
| 200 | OK | Successful GET, PUT, PATCH, DELETE with body |
| 201 | Created | Successful POST creating resource |
| 202 | Accepted | Async processing started |
| 204 | No Content | Successful DELETE without body |

### 3xx Redirection

| Code | Meaning | Use Case |
|------|---------|----------|
| 301 | Moved Permanently | Resource URL changed |
| 302 | Found | Temporary redirect |
| 304 | Not Modified | Cached version still valid |

### 4xx Client Errors

| Code | Meaning | Use Case |
|------|---------|----------|
| 400 | Bad Request | Invalid syntax, validation failed |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 405 | Method Not Allowed | GET on POST-only endpoint |
| 409 | Conflict | Resource state conflict |
| 422 | Unprocessable Entity | Semantic validation failed |
| 429 | Too Many Requests | Rate limit exceeded |

### 5xx Server Errors

| Code | Meaning | Use Case |
|------|---------|----------|
| 500 | Internal Server Error | Unexpected error |
| 502 | Bad Gateway | Invalid upstream response |
| 503 | Service Unavailable | Temporary unavailable |
| 504 | Gateway Timeout | Upstream timeout |

## Headers

### Request Headers

```http
# Authentication
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# Content negotiation
Accept: application/json
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate

# Conditional requests
If-None-Match: "686897696a7c876b7e"
If-Modified-Since: Wed, 21 Jan 2025 07:28:00 GMT

# Idempotency
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000

# API Version
Accept: application/vnd.api+json; version=2
```

### Response Headers

```http
# Content type
Content-Type: application/json; charset=utf-8

# Caching
Cache-Control: max-age=3600, must-revalidate
ETag: "686897696a7c876b7e"
Last-Modified: Wed, 21 Jan 2025 07:28:00 GMT

# Rate limiting
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1611218400

# CORS
Access-Control-Allow-Origin: https://example.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type

# Location of created resource
Location: /users/123

# Request tracking
X-Request-ID: req_abc123
```

## Advanced Patterns

### Bulk Operations

```http
# Batch create
POST /users/batch
[
  { "name": "Alice", "email": "alice@example.com" },
  { "name": "Bob", "email": "bob@example.com" }
]

Response: 201 Created
{
  "created": 2,
  "results": [
    { "id": 1, "name": "Alice", "status": "created" },
    { "id": 2, "name": "Bob", "status": "created" }
  ]
}

# Batch update
PATCH /users/batch
[
  { "id": 1, "email": "newalice@example.com" },
  { "id": 2, "email": "newbob@example.com" }
]
```

### Async Operations

```http
# Start long-running job
POST /reports/generate
{ "type": "annual", "year": 2024 }

Response: 202 Accepted
Location: /jobs/abc-123
{
  "job_id": "abc-123",
  "status": "processing",
  "estimated_completion": "2025-01-24T10:05:00Z"
}

# Check status
GET /jobs/abc-123

Response: 200 OK
{
  "job_id": "abc-123",
  "status": "completed",
  "result": {
    "download_url": "/reports/annual-2024.pdf"
  }
}
```

### Webhooks

```http
# Register webhook
POST /webhooks
{
  "url": "https://example.com/webhook",
  "events": ["order.created", "order.fulfilled"],
  "secret": "whsec_abc123"
}

Response: 201 Created
{
  "id": "wh_123",
  "url": "https://example.com/webhook",
  "events": ["order.created", "order.fulfilled"],
  "created_at": "2025-01-24T10:00:00Z"
}
```

## Security

### Authentication

**Bearer Token**
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**API Key**
```http
X-API-Key: pk_live_abc123def456
```

**Basic Auth** (over HTTPS only)
```http
Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
```

### Rate Limiting

```http
Response Headers:
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1611218400
Retry-After: 3600

Response: 429 Too Many Requests
{
  "error": "Rate limit exceeded",
  "retry_after": 3600
}
```

### CORS

```http
# Preflight request
OPTIONS /users
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Authorization

# Preflight response
Access-Control-Allow-Origin: https://example.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400
```

## Best Practices

### 1. Use Proper HTTP Methods

Don't use POST for everything. Match the operation:
- GET for reads
- POST for creates
- PUT for full replacements
- PATCH for partial updates
- DELETE for removals

### 2. Version Your API

```http
# URL versioning
/v1/users
/v2/users

# Header versioning
Accept: application/vnd.api+json; version=2

# Custom header
X-API-Version: 2
```

### 3. Handle Errors Gracefully

Always return:
- Appropriate status code
- Clear error message
- Request ID for tracking
- Actionable guidance

### 4. Document Everything

Use OpenAPI/Swagger specification (see openapi-template.yaml)

### 5. Idempotency

Support idempotency keys for POST/PATCH:
```http
POST /payments
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

### 6. Pagination for Collections

Always paginate large collections. Never return unbounded arrays.

### 7. Use HTTPS

All production APIs must use TLS 1.2+

### 8. Validation

Validate early, fail fast with clear messages

### 9. Consistency

- Consistent naming (camelCase vs snake_case)
- Consistent error format
- Consistent timestamp format (ISO 8601)

### 10. Monitoring

Log all requests with:
- Request ID
- User ID
- Response time
- Status code
