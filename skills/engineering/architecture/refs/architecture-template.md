# Architecture Document Template

Complete template for documenting solution architecture.

## File Structure

```
phases/design/
├── architecture.md          # Main document (use this template)
├── decisions/               # ADRs
│   ├── 001-architecture-style.md
│   ├── 002-tech-stack.md
│   └── 003-data-storage.md
└── diagrams/
    ├── system-context.mmd
    ├── container-diagram.mmd
    └── deployment.mmd
```

## Main Document Template

```markdown
# [System Name] Architecture

**Version**: 1.0
**Date**: YYYY-MM-DD
**Status**: [Draft | Review | Approved]
**Architect**: [Name]

## Executive Summary

2-3 paragraph overview for non-technical stakeholders:
- What the system does
- Key architectural decisions
- Major components
- Technology choices

## System Overview

### Purpose

What problem does this system solve? Who are the users?

### Scope

What's in scope:
- Feature 1
- Feature 2
- Feature 3

What's out of scope:
- Explicitly excluded 1
- Future consideration 2

### Assumptions

- Assumption 1
- Assumption 2
- Assumption 3

### Constraints

- Technical constraints
- Business constraints
- Resource constraints
- Timeline constraints

## Architecture Style

### Selected Style

[Monolithic | Microservices | Serverless | Event-Driven | Layered | Hexagonal]

### Rationale

Why this style fits:
- Requirement alignment
- Team capabilities
- Scale needs
- Deployment model

See [ADR-001: Architecture Style](decisions/001-architecture-style.md)

## System Context

### External Systems

```mermaid
graph TD
    User[Users] -->|HTTPS| System[Our System]
    System -->|REST| PaymentGateway[Payment Gateway]
    System -->|GraphQL| ThirdPartyAPI[Third Party API]
    System -->|SMTP| EmailService[Email Service]
```

### Actors

| Actor | Role | Interactions |
|-------|------|--------------|
| End User | Primary user | Web/mobile interface |
| Admin | System operator | Admin dashboard |
| External System | Integration | API calls |

## Container View

High-level component architecture:

```mermaid
graph TD
    subgraph "Frontend"
        Web[Web Application]
        Mobile[Mobile App]
    end

    subgraph "Backend"
        API[API Gateway]
        Auth[Auth Service]
        Core[Core Service]
        Worker[Background Workers]
    end

    subgraph "Data"
        DB[(Database)]
        Cache[(Cache)]
        Queue[Message Queue]
    end

    Web --> API
    Mobile --> API
    API --> Auth
    API --> Core
    Core --> DB
    Core --> Cache
    Core --> Queue
    Queue --> Worker
```

## Components

### Component 1: [Name]

**Purpose**: What it does

**Responsibilities**:
- Responsibility 1
- Responsibility 2
- Responsibility 3

**Technology**: [Language/Framework]

**Interfaces**:
- REST API on port 8080
- Publishes events to topic X
- Consumes events from topic Y

**Dependencies**:
- Database
- Cache
- External API

**Data**: What data it owns

**Scale**: Expected load and scaling approach

### Component 2: [Name]

[Same structure]

## Data Architecture

### Data Stores

| Store | Type | Purpose | Technology |
|-------|------|---------|------------|
| Primary DB | Relational | Transactional data | PostgreSQL 14 |
| Cache | Key-Value | Session, frequently accessed | Redis 7 |
| Search | Document | Full-text search | Elasticsearch 8 |
| Blob Storage | Object | Files, images | S3 |

See [ADR-003: Database Choice](decisions/003-database-choice.md)

### Data Flow

```mermaid
sequenceDiagram
    Client->>API: Create Order
    API->>Database: Insert Order
    Database-->>API: Order ID
    API->>Queue: Order Created Event
    API-->>Client: Success
    Queue->>Worker: Process Order
    Worker->>External: Call Payment API
```

## Technology Stack

### Frontend

- **Framework**: React 18
- **State**: Redux Toolkit
- **Styling**: Tailwind CSS
- **Build**: Vite

### Backend

- **Runtime**: Node.js 20 LTS
- **Framework**: Express 4.x
- **Language**: TypeScript 5.x
- **Validation**: Zod

### Data

- **Database**: PostgreSQL 14
- **ORM**: Prisma 5.x
- **Cache**: Redis 7
- **Queue**: RabbitMQ 3.12

### Infrastructure

- **Hosting**: AWS
- **Containers**: Docker
- **Orchestration**: ECS
- **CI/CD**: GitHub Actions

See [ADR-002: Technology Stack](decisions/002-tech-stack.md)

## Cross-Cutting Concerns

### Security

**Authentication**:
- JWT tokens with 15-min expiry
- Refresh tokens with 7-day rotation
- OAuth2 for third-party

**Authorization**:
- Role-based access control (RBAC)
- Resource-level permissions
- API key for service-to-service

**Data Protection**:
- TLS 1.3 in transit
- AES-256 at rest
- PII encryption in database

### Observability

**Logging**:
- Structured JSON logs
- Log levels: ERROR, WARN, INFO, DEBUG
- Centralized in CloudWatch

**Metrics**:
- Request rates, latencies, errors
- Business metrics (orders, revenue)
- Dashboard in Grafana

**Tracing**:
- Distributed tracing with OpenTelemetry
- Trace sampling at 10%

### Error Handling

**Strategy**:
- Fail fast for unrecoverable errors
- Retry with exponential backoff
- Circuit breakers for external calls
- Graceful degradation where possible

**User Errors**: 4xx with helpful messages
**System Errors**: 5xx with correlation ID

### Performance

**Targets**:
- API P95 latency: <200ms
- Page load: <2s
- Database queries: <50ms

**Strategies**:
- Redis caching (5-min TTL)
- Database connection pooling (max 20)
- CDN for static assets
- Lazy loading for images

### Scalability

**Horizontal Scaling**:
- Stateless API servers (2-10 instances)
- Auto-scaling on CPU >70%
- Load balancer with round-robin

**Vertical Limits**:
- Database: t3.large (2 vCPU, 8GB)
- Cache: t3.medium (2 vCPU, 4GB)

**Expected Load**:
- 1000 concurrent users
- 10,000 requests/min
- 100GB data growth/year

### Reliability

**Targets**:
- Availability: 99.9% (43 min downtime/month)
- RTO: 4 hours
- RPO: 1 hour

**High Availability**:
- Multi-AZ deployment
- Database replication (primary + 1 read replica)
- Daily automated backups (30-day retention)

**Disaster Recovery**:
- Database snapshots every 6 hours
- Infrastructure as Code in Git
- Runbook for restore procedures

## Deployment

### Environment Strategy

| Environment | Purpose | Data | Deployment |
|-------------|---------|------|------------|
| Development | Feature work | Synthetic | On commit |
| Staging | Integration testing | Anonymized prod | Daily |
| Production | Live users | Real | On release tag |

### Deployment Architecture

```mermaid
graph TD
    subgraph "AWS Region: us-east-1"
        subgraph "VPC"
            subgraph "Public Subnet"
                ALB[Application Load Balancer]
            end
            subgraph "Private Subnet A"
                API1[API Server 1]
                DB1[(Primary DB)]
            end
            subgraph "Private Subnet B"
                API2[API Server 2]
                DB2[(Replica DB)]
            end
        end
    end

    Internet --> ALB
    ALB --> API1
    ALB --> API2
    API1 --> DB1
    API2 --> DB2
    DB1 -.replicate.-> DB2
```

### Release Process

1. Code merged to main
2. CI runs tests and builds
3. Deploy to staging automatically
4. Manual smoke tests
5. Approve production deployment
6. Blue-green deployment to prod
7. Health check validation
8. Monitor for 30 minutes

### Rollback

- Keep last 3 versions deployed
- Rollback via route change (< 2 min)
- Database migrations are forward-compatible

## Quality Attributes

### Non-Functional Requirements

| Attribute | Target | Measurement |
|-----------|--------|-------------|
| Performance | P95 < 200ms | APM tools |
| Availability | 99.9% | Uptime monitoring |
| Scalability | 10K req/min | Load testing |
| Security | Zero critical vulns | Security scans |
| Maintainability | <2 day bug fix | Issue tracking |
| Testability | >80% coverage | Coverage reports |

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Database scaling limits | High | Medium | Plan for sharding, monitor growth |
| Third-party API downtime | Medium | Low | Circuit breaker, fallback cache |
| Team lacks Kubernetes experience | Medium | High | Use managed ECS instead |
| Cost overruns | High | Medium | Budget alerts, reserved instances |

## Future Considerations

### Known Limitations

- Single region deployment (no geographic distribution)
- Synchronous processing (could be async)
- Monolithic database (might need split)

### Evolution Path

**Phase 1** (Current): Monolithic API
**Phase 2** (6 months): Extract auth service
**Phase 3** (12 months): Event-driven architecture
**Phase 4** (18 months): Multi-region

### Technical Debt

- Legacy authentication code (plan to refactor Q3)
- Inconsistent error handling (standardize in v2)
- Missing API versioning (add before public launch)

## Appendices

### Glossary

- **API**: Application Programming Interface
- **JWT**: JSON Web Token
- **RTO**: Recovery Time Objective

### References

- [System Requirements](../requirements.md)
- [API Documentation](../api/openapi.yaml)
- [Infrastructure as Code](../../infrastructure/)
- [ADRs](decisions/)

### Diagram Legend

```mermaid
graph LR
    Component[Component]
    Database[(Database)]
    External{{External System}}
    Queue[/Queue\]
```

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architect | [Name] | YYYY-MM-DD | |
| Tech Lead | [Name] | YYYY-MM-DD | |
| Engineering Manager | [Name] | YYYY-MM-DD | |
```

## Tips for Using This Template

### Don't Fill Everything

Only include sections relevant to your system:
- Small project: Focus on overview, components, tech stack
- Large project: Full template
- Microservice: Emphasize integration points

### Keep It Current

- Update as decisions change
- Mark outdated sections
- Link to newer ADRs
- Archive old versions

### Make It Scannable

- Use diagrams liberally
- Tables over prose
- Bullet points over paragraphs
- Clear headers

### Link, Don't Duplicate

- Reference ADRs for decisions
- Link to API specs
- Point to runbooks
- Connect to code

### Write for Your Audience

- Executives: Executive summary + risks
- Developers: Components + tech stack
- Operations: Deployment + monitoring
- Security: Security section + data flow
