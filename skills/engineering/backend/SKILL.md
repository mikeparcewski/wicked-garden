---
name: backend
description: |
  Backend engineering specialist for APIs, databases, server-side patterns,
  data modeling, scalability, and integrations. Use for API design, database
  questions, or backend-specific concerns.
---

# Backend Skill

Specialized backend engineering guidance for APIs, databases, and server-side systems.

## When to Use

- Designing APIs (REST, GraphQL)
- Database schema or query questions
- Server-side architecture
- Data modeling
- Authentication and authorization
- Scalability and performance
- User says "backend", "API", "database", "server"

## Key Focus Areas

### API Design
- RESTful conventions (resources, methods, status codes)
- GraphQL schema design
- API versioning strategies
- Request/response validation
- Error handling and messaging
- Pagination and filtering
- Rate limiting

### Database Patterns
- Schema design and normalization
- Indexing strategies
- Query optimization
- Transaction management
- Connection pooling
- Migration best practices
- N+1 query prevention

### Data Modeling
- Entity definition
- Relationship modeling (1:1, 1:N, N:M)
- Data types and constraints
- Validation rules
- Audit trails

### Authentication & Authorization
- Password hashing (bcrypt, argon2)
- JWT or session management
- OAuth2 / OIDC patterns
- RBAC (Role-Based Access Control)
- API key management

### Performance & Scalability
- Query optimization and EXPLAIN plans
- Caching strategies (Redis, memcached)
- Background jobs (Celery, Bull)
- Database read replicas
- Horizontal scaling

### Integration Patterns
- External API resilience (retry, timeout, circuit breaker)
- Webhook handling with retry
- Message queue patterns
- Idempotency for critical operations

## Review Process

Use comprehensive checklists for:
- API quality (REST conventions, validation, versioning)
- Database quality (schema, indexes, transactions)
- Security (auth, validation, injection prevention)

See [refs/checklists.md](refs/checklists.md) for detailed checklists, anti-patterns, and output templates.

## Code Patterns

Common backend patterns for:
- API endpoints with auth and validation
- Query optimization and N+1 prevention
- Authentication and authorization
- External API integration with resilience
- Caching strategies

See [refs/patterns.md](refs/patterns.md) for code examples and best practices.

## Notes

- Always hash passwords (never plaintext)
- Validate all input at API boundaries
- Use transactions for multi-step operations
- Index foreign keys and query fields
- Use background jobs for slow operations
