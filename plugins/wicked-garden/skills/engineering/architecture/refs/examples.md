# Architecture Examples

Real-world architecture examples with complete ADRs and diagrams.

## Example 1: E-Commerce Platform

### Context

Medium-sized online retail platform:
- 50,000 daily users
- 10,000 orders/day
- Integration with payment gateway, shipping
- Mobile + web clients
- Small team (5 developers)

### Architecture Decision

**Chosen**: Modular Monolith with Event-Driven components

**Rationale**:
- Team too small for microservices overhead
- Need quick iteration
- Event-driven for order processing
- Can extract services later

### ADR: Architecture Style

```markdown
# ADR-001: Modular Monolith Architecture

**Status**: Accepted
**Date**: 2025-01-15

## Context

We need to build an e-commerce platform that:
- Handles 50K daily users
- Processes 10K orders/day
- Integrates with external payment and shipping
- Supports web and mobile clients
- Can be built by a 5-person team

Initial launch in 3 months, with plans to scale 3x in first year.

## Decision

We will build a **modular monolith** with event-driven order processing.

Structure:
- Single deployable application
- Clear module boundaries (catalog, cart, orders, users)
- Event bus for async workflows (order processing)
- Shared database with schema-per-module

## Consequences

### Positive

- Faster development (no distributed system complexity)
- Easier debugging and testing
- Simple deployment pipeline
- Lower operational overhead
- Clear module boundaries allow future extraction

### Negative

- All modules deploy together
- Shared database limits independent scaling
- Risk of coupling if not disciplined
- Entire app restarts on deployment

### Mitigation

- Enforce module boundaries via package structure
- Use events for cross-module communication
- Plan extraction points for future microservices
- Monitor module dependencies

## Alternatives Considered

### Microservices

**Pros**: Independent scaling, deployment, technology choices
**Cons**: Operational complexity, distributed debugging, network overhead
**Rejected**: Team size and timeline don't support the overhead

### Traditional Monolith

**Pros**: Simplest approach, proven
**Cons**: No clear boundaries, harder to extract later
**Rejected**: Want clear module separation for future growth

## Migration Path

**Phase 1** (Months 0-6): Modular monolith
**Phase 2** (Months 6-12): Extract payment service (PCI compliance)
**Phase 3** (Months 12-18): Extract order service (independent scaling)

## Research

- [Shopify's Modular Monolith](https://example.com)
- Team survey: 3/5 have microservices experience but prefer starting simple
```

### Component Structure

```
src/
├── modules/
│   ├── catalog/
│   │   ├── domain/
│   │   │   ├── Product.ts
│   │   │   └── Category.ts
│   │   ├── application/
│   │   │   └── ProductService.ts
│   │   ├── infrastructure/
│   │   │   └── ProductRepository.ts
│   │   └── api/
│   │       └── ProductController.ts
│   │
│   ├── cart/
│   │   └── [same structure]
│   │
│   ├── orders/
│   │   └── [same structure]
│   │
│   └── users/
│       └── [same structure]
│
├── shared/
│   ├── events/
│   │   └── EventBus.ts
│   ├── database/
│   │   └── connection.ts
│   └── utils/
│
└── app.ts
```

### System Diagram

```mermaid
graph TD
    subgraph "Clients"
        Web[Web App]
        Mobile[Mobile App]
    end

    subgraph "Modular Monolith"
        API[API Gateway]

        subgraph "Modules"
            Catalog[Catalog Module]
            Cart[Cart Module]
            Orders[Orders Module]
            Users[Users Module]
        end

        Events[Event Bus]

        Catalog --> Events
        Cart --> Events
        Orders --> Events
    end

    subgraph "Data Layer"
        DB[(PostgreSQL)]
        Cache[(Redis)]
    end

    subgraph "External"
        Payment[Payment Gateway]
        Shipping[Shipping API]
    end

    Web --> API
    Mobile --> API
    API --> Catalog
    API --> Cart
    API --> Orders
    API --> Users

    Catalog --> DB
    Cart --> Cache
    Orders --> DB
    Orders --> Payment
    Orders --> Shipping
```

### Order Processing Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API
    participant Cart
    participant Orders
    participant Events
    participant Payment
    participant Email

    C->>API: POST /checkout
    API->>Cart: Get Cart
    Cart-->>API: Cart Items
    API->>Orders: Create Order
    Orders->>DB: Insert Order
    Orders->>Events: Publish OrderCreated
    Orders-->>API: Order ID
    API-->>C: 202 Accepted

    Events->>Payment: Process Payment
    Payment->>External: Charge Card
    External-->>Payment: Success
    Payment->>Events: Publish PaymentCompleted

    Events->>Email: Send Confirmation
    Events->>Orders: Update Status
```

## Example 2: Real-Time Analytics Platform

### Context

Analytics SaaS for tracking user behavior:
- Ingests millions of events/day
- Real-time dashboards
- Historical reporting
- Multi-tenant

### Architecture Decision

**Chosen**: Lambda Architecture (Batch + Speed layers)

### ADR: Lambda Architecture

```markdown
# ADR-002: Lambda Architecture for Analytics

**Status**: Accepted
**Date**: 2025-01-20

## Context

Building analytics platform with:
- 10M events/day ingestion
- Real-time dashboards (<5s freshness)
- Historical reports (TB-scale data)
- Both need to query same logical data

Conflicting requirements:
- Real-time needs low latency
- Historical needs batch efficiency
- Both need accurate aggregations

## Decision

Implement **Lambda Architecture**:

**Speed Layer**: Real-time processing
- Kafka → Flink → Redis
- Recent data (last 24 hours)
- Approximate aggregations

**Batch Layer**: Historical processing
- S3 → Spark → Parquet
- All data (immutable)
- Accurate aggregations

**Serving Layer**: Unified queries
- Merge results from both layers
- API abstracts the complexity

## Consequences

### Positive

- Real-time and batch workloads optimized separately
- Immutable batch layer (replayable)
- Speed layer handles stragglers
- Scalable to billions of events

### Negative

- Two processing paths to maintain
- Eventual consistency between layers
- More operational complexity
- Duplicate logic risk

### Mitigation

- Share computation logic as libraries
- Automated reconciliation between layers
- Clear data freshness SLAs

## Alternatives Considered

### Pure Streaming (Kappa Architecture)

**Pros**: Single processing path
**Cons**: Hard to replay history, less efficient for large scans
**Rejected**: Historical queries are critical

### Pure Batch

**Pros**: Simpler, accurate
**Cons**: Can't meet real-time SLA
**Rejected**: Real-time is a key differentiator
```

### System Diagram

```mermaid
graph TD
    subgraph "Ingestion"
        Events[Event Stream]
    end

    subgraph "Speed Layer - Real-time"
        Kafka[Kafka]
        Flink[Flink Stream]
        Redis[(Redis)]
    end

    subgraph "Batch Layer - Historical"
        S3[(S3 Raw Data)]
        Spark[Spark Batch]
        Parquet[(Parquet Files)]
    end

    subgraph "Serving Layer"
        API[Query API]
        Dashboard[Dashboard]
    end

    Events --> Kafka
    Events --> S3

    Kafka --> Flink
    Flink --> Redis

    S3 --> Spark
    Spark --> Parquet

    API --> Redis
    API --> Parquet
    Dashboard --> API
```

## Example 3: Multi-Tenant SaaS

### Context

B2B SaaS application:
- 1,000 customer tenants
- Varying sizes (10-10,000 users each)
- Data isolation required
- White-label capability

### Architecture Decision

**Chosen**: Hybrid tenancy model

```markdown
# ADR-003: Hybrid Multi-Tenancy Model

**Status**: Accepted
**Date**: 2025-01-22

## Context

Multi-tenant SaaS with diverse customer sizes:
- Tier 1: Enterprise (10 customers, 5K+ users each)
- Tier 2: Business (100 customers, 100-1K users)
- Tier 3: Starter (1K+ customers, 10-100 users)

Requirements:
- Data isolation (regulatory)
- Cost efficiency
- Performance isolation for large tenants
- White-label for enterprise

## Decision

**Hybrid tenancy model**:

**Tier 1 (Enterprise)**:
- Dedicated database per tenant
- Dedicated app instances
- Custom subdomain
- SLA: 99.9%

**Tier 2 (Business)**:
- Shared database, separate schemas
- Shared app pool
- Tenant subdomain
- SLA: 99.5%

**Tier 3 (Starter)**:
- Shared database, shared schema (tenant_id column)
- Shared app pool
- Shared domain
- SLA: 99%

## Consequences

### Positive

- Cost-effective for small tenants
- Performance isolation for large tenants
- Can customize enterprise deployments
- Clear upgrade path

### Negative

- More infrastructure variants
- Complex tenant routing
- Migration complexity on upgrades

## Implementation

**Tenant Resolver Middleware**:
```typescript
async function resolveTenant(req: Request): Promise<Tenant> {
  const hostname = req.hostname;

  // Enterprise: custom domain
  if (hostname.endsWith('.enterprise.com')) {
    return await enterpriseRepo.findByDomain(hostname);
  }

  // Business/Starter: subdomain
  const subdomain = hostname.split('.')[0];
  return await tenantRepo.findBySubdomain(subdomain);
}

async function connectDatabase(tenant: Tenant): Promise<Connection> {
  switch (tenant.tier) {
    case 'enterprise':
      return dedicatedPool.get(tenant.id);
    case 'business':
      return sharedPool.schema(tenant.schema);
    case 'starter':
      return sharedPool.where({ tenant_id: tenant.id });
  }
}
```
```

### Tenant Routing

```mermaid
graph TD
    Request[Incoming Request]

    Request --> Router{Tenant Resolver}

    Router -->|enterprise.acme.com| Ent[Enterprise Pool]
    Router -->|acme.app.com| Bus[Business Pool]
    Router -->|shared.app.com| Start[Starter Pool]

    Ent --> DB1[(Dedicated DB)]
    Bus --> DB2[(Shared DB<br/>Schema: acme)]
    Start --> DB3[(Shared DB<br/>WHERE tenant_id)]
```

## Example 4: Financial Trading Platform

### Context

Real-time trading platform:
- <50ms latency requirement
- High availability (99.99%)
- Regulatory compliance
- Complex event processing

### Architecture Decision

**Chosen**: CQRS + Event Sourcing

### ADR: Event Sourcing for Audit

```markdown
# ADR-004: Event Sourcing for Trade Audit Trail

**Status**: Accepted
**Date**: 2025-01-18

## Context

Regulatory requirements:
- Complete audit trail of all trades
- Point-in-time state reconstruction
- Immutable records
- 7-year retention

Performance requirements:
- <50ms trade execution
- High read throughput for positions
- Complex queries on trade history

## Decision

Implement **Event Sourcing** with **CQRS**:

**Write Side**:
- Store events in append-only log
- Events are source of truth
- Fast writes to event store

**Read Side**:
- Materialized views for queries
- Optimized for different use cases
- Eventually consistent

## Event Store

PostgreSQL with append-only table:
```sql
CREATE TABLE events (
  id SERIAL PRIMARY KEY,
  stream_id UUID NOT NULL,
  event_type VARCHAR(100) NOT NULL,
  event_data JSONB NOT NULL,
  metadata JSONB,
  version INTEGER NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(stream_id, version)
);
```

## Read Models

Multiple projections:
- `current_positions`: Latest state
- `trade_history`: Queryable trades
- `risk_metrics`: Aggregated risk
- `compliance_view`: Regulatory reporting

## Consequences

### Positive

- Complete audit trail (regulatory requirement)
- Point-in-time reconstruction
- Optimized read models
- Natural event replay
- Temporal queries easy

### Negative

- Eventually consistent reads
- More storage (all events kept)
- Projection rebuilding complexity
- Schema evolution challenges

## Alternatives

### Traditional CRUD

**Rejected**: Can't reconstruct history, audit trail requires separate logging

### Change Data Capture

**Rejected**: Not all databases in stack support, harder to reason about
```

### Event Flow

```mermaid
sequenceDiagram
    participant Trader
    participant Command
    participant Events
    participant Projection
    participant Query

    Trader->>Command: PlaceTrade
    Command->>Events: TradeSubmitted
    Command->>Events: TradeValidated
    Command->>Events: TradeExecuted
    Command-->>Trader: Trade ID

    Events->>Projection: Update Positions
    Events->>Projection: Update History
    Events->>Projection: Update Risk

    Trader->>Query: Get Positions
    Query->>Projection: Read View
    Projection-->>Query: Current State
    Query-->>Trader: Positions
```

## Pattern Matching Guide

| Example | Pattern | Why |
|---------|---------|-----|
| E-Commerce | Modular Monolith | Small team, known domain, future extraction |
| Analytics | Lambda Architecture | Real-time + historical, different optimization |
| SaaS | Hybrid Tenancy | Cost + isolation balance |
| Trading | Event Sourcing + CQRS | Audit + performance |

## Key Takeaways

1. **Start Simple**: E-commerce example chose monolith over microservices
2. **Match Requirements**: Analytics needed both real-time and batch
3. **Consider Trade-offs**: SaaS balanced cost vs isolation
4. **Regulatory Matters**: Trading chose event sourcing for compliance
5. **Team Size**: Architecture should match team capabilities
6. **Evolution Path**: All examples planned for future changes

## Common Mistakes

### Over-Engineering Early

Bad: "Let's use microservices for this 3-person startup"
Good: "Start with a modular monolith, extract later"

### Ignoring Non-Functional Requirements

Bad: Choosing CQRS because it's cool
Good: Choosing CQRS for audit/performance requirements

### No Evolution Plan

Bad: "This is the final architecture"
Good: "Phase 1: Monolith, Phase 2: Extract high-change services"

### Copying Without Understanding

Bad: "Netflix uses microservices, so should we"
Good: "Our requirements are X, so pattern Y fits"
