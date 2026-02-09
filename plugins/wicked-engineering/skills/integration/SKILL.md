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
See [REST API Guide](refs/rest-api.md) for OpenAPI template.

### GraphQL
Flexible queries, strong typing.
See [GraphQL Guide](refs/graphql.md) for schemas.

### gRPC
High performance, service-to-service.
See [gRPC Guide](refs/grpc.md) for proto definitions.

### Event-Driven
Async messaging, pub/sub.
See [Event Schema Guide](refs/event-schemas.md) for formats.

## Error Handling

Standard HTTP status codes:
- 2xx: Success (200 OK, 201 Created, 204 No Content)
- 4xx: Client errors (400, 401, 404, 409)
- 5xx: Server errors (500, 503)

See [Error Handling Guide](refs/error-handling.md) for response formats.

## Resilience Patterns

- **Circuit Breaker** - Prevent cascading failures
- **Retry with Backoff** - Exponential retry delays
- **Timeouts** - Fail fast on slow responses
- **Fallbacks** - Graceful degradation

See [Resilience Guide](refs/resilience.md) for implementations.

## Versioning

Common strategies:
- URL versioning: `/api/v1/resources`
- Header versioning: `Accept: application/vnd.api+json; version=1`

See [Versioning Guide](refs/versioning.md) for trade-offs.

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

- [REST API Guide](refs/rest-api.md)
- [GraphQL Guide](refs/graphql.md)
- [gRPC Guide](refs/grpc.md)
- [Event Schema Guide](refs/event-schemas.md)
- [Resilience Patterns](refs/resilience.md)
- [Versioning Guide](refs/versioning.md)
- [OpenAPI Template](refs/openapi-template.yaml)
