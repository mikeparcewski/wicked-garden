# API Versioning Guide: Versioning Strategies

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

