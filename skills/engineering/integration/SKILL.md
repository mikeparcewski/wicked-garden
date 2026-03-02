---
name: integration
description: |
  Design API contracts, service boundaries, and integration patterns.
  Define how components and services communicate and interoperate.

  Use when: "API design", "service integration", "how do these communicate",
  "API contract", "integration pattern", "REST API", "GraphQL", "event schema"
---

# Integration Skill

Design robust, well-documented integration points between components and services.

## Purpose

Define communication contracts:
- API design (REST, GraphQL, gRPC)
- Event schema definition
- Integration pattern selection
- Error handling and resilience

## Process

### 1. Identify Integration Points

Map communication:
- Component-to-component
- Service-to-service
- Client-to-server
- External integrations
- Event flows

### 2. Choose Pattern

Select approach:
- **Request/Response** - Sync, immediate result
- **Publish/Subscribe** - Async, one-to-many
- **Event Sourcing** - Audit trail, replay
- **API Gateway** - Unified entry point

### 3. Design Contracts

Define specifications:
- OpenAPI for REST
- GraphQL schemas
- Protocol Buffers for gRPC
- Event schemas (JSON Schema)

### 4. Plan Resilience

Handle failures:
- Retry strategies
- Circuit breakers
- Timeouts
- Fallback behaviors

## Output

Creates in `phases/design/`:
```
design/
├── integration/
│   ├── overview.md
│   ├── api-specs/
│   │   ├── openapi.yaml
│   │   └── events.json
│   └── patterns.md
```

## Integration Patterns

### REST API
Resource-oriented, stateless, HTTP verbs.
See [REST API Fundamentals](refs/rest-api-fundamentals.md) and [Responses & Security](refs/rest-api-responses-security.md).

### GraphQL
Flexible queries, strong typing.
See GraphQL guides in refs/ (graphql-graphql-basics.md, graphql-schema-design-patterns.md).

### gRPC
High performance, service-to-service.
See gRPC guides in refs/ (grpc-grpc-overview.md, grpc-implementation-examples.md).

### Event-Driven
Async messaging, pub/sub.
See event schema guides in refs/ (event-schemas-event-structure.md, event-schemas-best-practices.md).

## Error Handling

Standard HTTP status codes:
- 2xx: Success (200 OK, 201 Created, 204 No Content)
- 4xx: Client errors (400, 401, 404, 409)
- 5xx: Server errors (500, 503)

See error handling guides in refs/ (error-handling-error-response-format.md, error-handling-best-practices.md).

## Resilience Patterns

- **Circuit Breaker** - Prevent cascading failures
- **Retry with Backoff** - Exponential retry delays
- **Timeouts** - Fail fast on slow responses
- **Fallbacks** - Graceful degradation

See resilience guides in refs/ (resilience-circuit-breaker-pattern.md, resilience-best-practices.md).

## Versioning

Common strategies:
- URL versioning: `/api/v1/resources`
- Header versioning: `Accept: application/vnd.api+json; version=1`

See versioning guides in refs/ (versioning-versioning-strategies.md, versioning-migration-strategies.md).

## Integration

### With System Design

Takes component boundaries and defines:
- Interfaces between components
- Data contracts
- Communication patterns

### With Data Architecture

Coordinates on:
- API data models
- Event payloads
- Serialization formats

## Events

- `[arch:contract:defined:success]` - API contract created
- `[arch:api:validated:success]` - API spec validated
- `[arch:event:schema:defined:success]` - Event schema documented

## Tips

1. **API-First Design** - Design before implementation
2. **Version from Start** - Plan for evolution
3. **Document Well** - Specs are executable docs
4. **Error Handling** - Comprehensive error responses
5. **Idempotency** - Make operations repeatable safely
6. **Security** - Auth/authz from the beginning

## Reference Materials

- REST API:
  - [Fundamentals](refs/rest-api-fundamentals.md)
  - [Responses & Security](refs/rest-api-responses-security.md)
- GraphQL:
  - [Basics](refs/graphql-graphql-basics.md)
  - [Query Examples](refs/graphql-query-examples.md)
  - [Schema Design](refs/graphql-schema-design-patterns.md)
  - [Error Handling](refs/graphql-error-handling.md)
  - [Best Practices](refs/graphql-best-practices.md)
- gRPC:
  - [Overview](refs/grpc-grpc-overview.md)
  - [Implementation](refs/grpc-implementation-examples.md)
  - [Metadata & Headers](refs/grpc-metadata-headers.md)
  - [Testing](refs/grpc-testing.md)
- Event Schemas:
  - [Event Structure](refs/event-schemas-event-structure.md)
  - [Naming Conventions](refs/event-schemas-event-naming-conventions.md)
  - [Best Practices](refs/event-schemas-best-practices.md)
- Error Handling:
  - [Response Format](refs/error-handling-error-response-format.md)
  - [Error Classes (TS)](refs/error-handling-error-classes-typescript.md)
  - [Retry Strategies](refs/error-handling-retry-strategies.md)
  - [Best Practices](refs/error-handling-best-practices.md)
- Resilience:
  - [Circuit Breaker](refs/resilience-circuit-breaker-pattern.md)
  - [Timeout & Bulkhead](refs/resilience-timeout-pattern.md)
  - [Rate Limiting](refs/resilience-rate-limiting.md)
  - [Best Practices](refs/resilience-best-practices.md)
- Versioning:
  - [Strategies](refs/versioning-versioning-strategies.md)
  - [Migration](refs/versioning-migration-strategies.md)
  - [Breaking Changes](refs/versioning-breaking-changes.md)
- [OpenAPI Template](refs/openapi-template.yaml)
