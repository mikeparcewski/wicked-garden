# Backend Review Checklists

## API Quality Checklist
- [ ] RESTful conventions followed
- [ ] Appropriate HTTP methods and status codes
- [ ] Request/response validation
- [ ] Consistent error responses
- [ ] Pagination for collections
- [ ] Versioning strategy

## Database Quality Checklist
- [ ] Schema normalized appropriately
- [ ] Indexes on query fields
- [ ] Foreign keys and constraints
- [ ] Migrations reversible
- [ ] No N+1 queries
- [ ] Transactions used correctly

## Security Checklist
- [ ] No plaintext passwords
- [ ] Input validation
- [ ] SQL injection prevention
- [ ] Authorization checks
- [ ] Rate limiting
- [ ] Sensitive data not logged

## Common Anti-Patterns

### API Anti-Patterns
- Inconsistent endpoint naming
- Wrong HTTP methods or status codes
- No pagination
- Missing rate limiting
- No versioning
- Not following REST conventions

### Database Anti-Patterns
- Missing indexes on foreign keys
- N+1 query problems
- Not using transactions
- Missing connection pooling
- Non-reversible migrations
- Over-normalization or under-normalization

### Security Anti-Patterns
- Plaintext passwords
- SQL injection vulnerabilities
- Missing authorization checks
- Logging sensitive data (passwords, tokens, SSNs)
- No input validation
- Missing CSRF protection

### Performance Anti-Patterns
- Synchronous external API calls in request path
- No caching for expensive operations
- Not using background jobs
- Missing query optimization
- No connection pooling
- Blocking operations in async code

## Output Template

```markdown
## Backend Review: {Feature/API}

### API Design
{Endpoint structure, conventions}

### Data Model
{Schema design, relationships}

### Database Performance
{Query optimization, indexes}

### Security
{Auth patterns, validation}

### Issues
| Severity | Issue | Location | Fix |
|----------|-------|----------|-----|
| {Level} | {Problem} | {File:line} | {Solution} |

### Recommendations
1. {Priority item}
2. {Secondary item}
```

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

## Tools

- OpenAPI/Swagger for API docs
- EXPLAIN for query plans
- Database migrations (Alembic, Flyway)
- APM tools (DataDog, New Relic)
- Error tracking (Sentry)
- Load testing (Locust, k6)
