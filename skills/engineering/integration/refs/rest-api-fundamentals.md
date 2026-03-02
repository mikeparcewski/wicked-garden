# REST API Design - Fundamentals

Core principles, resource design, HTTP methods, and query parameters for RESTful APIs.

## Core Principles

### REST Constraints

1. **Client-Server**: Separation of concerns
2. **Stateless**: Each request contains all necessary information
3. **Cacheable**: Responses explicitly indicate cacheability
4. **Uniform Interface**: Consistent resource access
5. **Layered System**: Client doesn't know if connected to end server
6. **Code on Demand** (optional): Server can extend client functionality

## Resource Design

### Resource Naming

**Use Nouns, Not Verbs**
```
Good: GET /users/123
Bad:  GET /getUser/123

Good: POST /orders
Bad:  POST /createOrder
```

**Use Plural Nouns**
```
Good: /users, /products, /orders
Bad:  /user, /product, /order
```

**Hierarchical Resources**
```
/users/123/orders          # User's orders
/orders/456/items          # Order's line items
/organizations/789/users   # Organization's users
```

**Keep URLs Shallow**
```
Good: /users/123/orders
Avoid: /organizations/789/departments/456/teams/123/users
Better: /teams/123/users
```

### Resource Relationships

**One-to-Many**
```
GET /users/123/orders       # List user's orders
GET /users/123/orders/456   # Specific order for user
```

**Many-to-Many**
```
GET /courses/123/students   # Students in course
GET /students/456/courses   # Courses for student
```

**Nested vs. Flat**
```
# Nested (good for context)
GET /users/123/orders

# Flat with filter (good for querying)
GET /orders?user_id=123

# Use both for flexibility
```

## HTTP Methods

### Standard CRUD Operations

| Method | Operation | Idempotent | Safe |
|--------|-----------|------------|------|
| GET | Read | Yes | Yes |
| POST | Create | No | No |
| PUT | Replace | Yes | No |
| PATCH | Update | No | No |
| DELETE | Delete | Yes | No |

### GET - Retrieve Resources

```http
# Get collection
GET /users
Response: 200 OK
[
  { "id": 1, "name": "Alice" },
  { "id": 2, "name": "Bob" }
]

# Get single resource
GET /users/1
Response: 200 OK
{ "id": 1, "name": "Alice", "email": "alice@example.com" }

# Resource not found
GET /users/999
Response: 404 Not Found
{ "error": "User not found" }
```

### POST - Create Resources

```http
POST /users
Content-Type: application/json

{
  "name": "Charlie",
  "email": "charlie@example.com"
}

# Success
Response: 201 Created
Location: /users/3
{
  "id": 3,
  "name": "Charlie",
  "email": "charlie@example.com",
  "created_at": "2025-01-24T10:00:00Z"
}

# Validation error
Response: 400 Bad Request
{
  "error": "Validation failed",
  "details": {
    "email": "Invalid email format"
  }
}

# Conflict
Response: 409 Conflict
{
  "error": "User with this email already exists"
}
```

### PUT - Replace Resource

```http
# Complete replacement
PUT /users/3
Content-Type: application/json

{
  "name": "Charles",
  "email": "charles@example.com"
}

Response: 200 OK
{
  "id": 3,
  "name": "Charles",
  "email": "charles@example.com",
  "updated_at": "2025-01-24T11:00:00Z"
}

# Create if not exists (optional)
PUT /users/999
Response: 201 Created
```

### PATCH - Partial Update

```http
PATCH /users/3
Content-Type: application/json

{
  "email": "new-email@example.com"
}

Response: 200 OK
{
  "id": 3,
  "name": "Charles",
  "email": "new-email@example.com",
  "updated_at": "2025-01-24T12:00:00Z"
}
```

### DELETE - Remove Resource

```http
DELETE /users/3

# Success with response body
Response: 200 OK
{
  "message": "User deleted successfully"
}

# Success without response body
Response: 204 No Content

# Already deleted (idempotent)
Response: 204 No Content

# Cannot delete (has dependencies)
Response: 409 Conflict
{
  "error": "Cannot delete user with active orders"
}
```

## Query Parameters

### Filtering

```http
# Single filter
GET /products?category=electronics

# Multiple filters
GET /products?category=electronics&price_min=100&price_max=500

# Array values
GET /products?tags=sale&tags=featured
GET /products?tags=sale,featured

# Complex filters
GET /orders?status=pending,processing&created_after=2025-01-01
```

### Sorting

```http
# Single field
GET /users?sort=name

# Descending
GET /users?sort=-created_at

# Multiple fields
GET /users?sort=last_name,first_name
GET /users?sort=-created_at,name
```

### Pagination

**Offset-Based**
```http
GET /users?limit=20&offset=40

Response: 200 OK
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 40,
    "has_more": true
  },
  "links": {
    "next": "/users?limit=20&offset=60",
    "prev": "/users?limit=20&offset=20"
  }
}
```

**Cursor-Based** (better for large datasets)
```http
GET /users?limit=20&cursor=eyJpZCI6MTIzfQ

Response: 200 OK
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTQzfQ",
    "has_more": true
  },
  "links": {
    "next": "/users?limit=20&cursor=eyJpZCI6MTQzfQ"
  }
}
```

### Field Selection (Sparse Fieldsets)

```http
# Select specific fields
GET /users?fields=id,name,email

Response: 200 OK
[
  { "id": 1, "name": "Alice", "email": "alice@example.com" },
  { "id": 2, "name": "Bob", "email": "bob@example.com" }
]

# Exclude fields
GET /users?exclude=password,ssn
```

### Search

```http
# Simple search
GET /products?q=laptop

# Full-text search with filters
GET /articles?q=kubernetes&tags=devops&published_after=2024-01-01
```
