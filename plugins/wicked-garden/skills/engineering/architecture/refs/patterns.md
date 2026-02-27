# Architectural Patterns Catalog

Detailed guide to common architectural patterns with trade-offs and when to use them.

## Layered Architecture

### Structure

```
┌─────────────────────────┐
│   Presentation Layer    │  UI, API Controllers
├─────────────────────────┤
│   Application Layer     │  Use Cases, Business Logic
├─────────────────────────┤
│     Domain Layer        │  Business Rules, Entities
├─────────────────────────┤
│  Infrastructure Layer   │  Database, External Services
└─────────────────────────┘

Dependencies flow downward only
```

### When to Use

- Traditional enterprise applications
- Clear separation of concerns needed
- Team familiar with MVC patterns
- Moderate complexity systems

### Trade-offs

**Pros**:
- Easy to understand and organize
- Clear separation of concerns
- Well-known pattern
- Good for teams new to architecture

**Cons**:
- Can become rigid
- May lead to anemic domain models
- Cross-cutting concerns difficult
- Can create unnecessary layers

### Example

```typescript
// Presentation Layer
class UserController {
  constructor(private userService: UserService) {}

  async createUser(req: Request): Promise<Response> {
    return await this.userService.createUser(req.body);
  }
}

// Application Layer
class UserService {
  constructor(private userRepo: UserRepository) {}

  async createUser(data: CreateUserDTO): Promise<User> {
    const user = new User(data);
    return await this.userRepo.save(user);
  }
}

// Domain Layer
class User {
  constructor(
    public email: string,
    public name: string
  ) {
    this.validate();
  }

  private validate() {
    if (!this.email.includes('@')) {
      throw new Error('Invalid email');
    }
  }
}

// Infrastructure Layer
class PostgresUserRepository implements UserRepository {
  async save(user: User): Promise<User> {
    // Database logic
  }
}
```

## Microservices Architecture

### Structure

```
                  ┌─────────────┐
                  │ API Gateway │
                  └──────┬──────┘
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
│  User     │     │  Order    │     │  Payment  │
│  Service  │     │  Service  │     │  Service  │
└─────┬─────┘     └─────┬─────┘     └─────┬─────┘
      │                 │                  │
┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
│  User DB  │     │  Order DB │     │ Payment DB│
└───────────┘     └───────────┘     └───────────┘
```

### When to Use

- Large, complex systems
- Multiple teams working independently
- Different scaling needs per component
- Polyglot technology requirements

### Trade-offs

**Pros**:
- Independent deployment
- Technology flexibility
- Isolated failures
- Team autonomy
- Scalability per service

**Cons**:
- Operational complexity
- Distributed system challenges
- Network latency
- Testing complexity
- Data consistency issues

### Key Principles

1. **Single Responsibility**: Each service does one thing well
2. **Autonomous**: Independently deployable
3. **API-First**: Well-defined contracts
4. **Decentralized Data**: Own your data
5. **Fault Tolerant**: Handle failures gracefully

## Event-Driven Architecture

### Structure

```
┌──────────┐      ┌──────────────┐      ┌──────────┐
│ Producer │─────▶│ Message Bus  │─────▶│ Consumer │
│ Service  │      │ (Kafka/SQS)  │      │ Service  │
└──────────┘      └──────────────┘      └──────────┘
                         │
                         ├─────────────▶┌──────────┐
                         │              │ Consumer │
                         │              │ Service  │
                         │              └──────────┘
                         │
                         └─────────────▶┌──────────┐
                                        │ Consumer │
                                        │ Service  │
                                        └──────────┘
```

### When to Use

- Asynchronous workflows
- Need for loose coupling
- High scalability requirements
- Complex event processing
- Real-time data streaming

### Trade-offs

**Pros**:
- Loose coupling
- High scalability
- Temporal decoupling
- Easy to add consumers
- Natural audit log

**Cons**:
- Eventual consistency
- Debugging complexity
- Message ordering challenges
- Duplicate processing risk
- Monitoring complexity

### Event Types

**Domain Events**: Business occurrences
```json
{
  "eventType": "OrderPlaced",
  "orderId": "123",
  "customerId": "456",
  "timestamp": "2025-01-24T10:00:00Z",
  "items": [...]
}
```

**Integration Events**: Cross-service communication
**Command Events**: Request for action

### Patterns

**Pub/Sub**: One-to-many broadcasting
**Event Sourcing**: Store events as source of truth
**CQRS**: Separate read and write models

## Hexagonal Architecture (Ports & Adapters)

### Structure

```
                    ┌─────────────────┐
                    │   UI Adapter    │
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │        Port (API)           │
              ├─────────────────────────────┤
              │                             │
              │     Business Logic Core     │
              │     (Domain Model)          │
              │                             │
              ├─────────────────────────────┤
              │      Port (Repository)      │
              └──────────────┬──────────────┘
                             │
      ┌──────────────────────┼──────────────────────┐
      │                      │                      │
┌─────▼─────┐         ┌─────▼─────┐         ┌─────▼─────┐
│ Postgres  │         │   Redis   │         │  MongoDB  │
│  Adapter  │         │  Adapter  │         │  Adapter  │
└───────────┘         └───────────┘         └───────────┘
```

### When to Use

- Need to isolate business logic
- Frequent technology changes
- Testing is critical
- Multiple interfaces (API, CLI, Web)

### Trade-offs

**Pros**:
- Business logic isolated
- Technology agnostic core
- Highly testable
- Flexible adapters

**Cons**:
- More abstraction layers
- Initial complexity
- May be overkill for simple apps

### Implementation

```typescript
// Port (Interface)
interface UserRepository {
  save(user: User): Promise<void>;
  findById(id: string): Promise<User>;
}

// Core Domain Logic
class UserService {
  constructor(private repo: UserRepository) {}

  async registerUser(email: string, password: string): Promise<User> {
    // Pure business logic, no infrastructure concerns
    const user = User.create(email, password);
    await this.repo.save(user);
    return user;
  }
}

// Adapter (Implementation)
class PostgresUserRepository implements UserRepository {
  async save(user: User): Promise<void> {
    await db.query('INSERT INTO users ...');
  }

  async findById(id: string): Promise<User> {
    const row = await db.query('SELECT * FROM users WHERE id = ?', [id]);
    return User.fromRow(row);
  }
}

// Another Adapter
class InMemoryUserRepository implements UserRepository {
  private users: Map<string, User> = new Map();

  async save(user: User): Promise<void> {
    this.users.set(user.id, user);
  }

  async findById(id: string): Promise<User> {
    return this.users.get(id);
  }
}
```

## Serverless Architecture

### Structure

```
┌─────────┐      ┌─────────────┐      ┌──────────┐
│ Client  │─────▶│ API Gateway │─────▶│ Lambda 1 │
└─────────┘      └─────────────┘      └────┬─────┘
                                            │
                        ┌───────────────────┤
                        │                   │
                  ┌─────▼─────┐      ┌─────▼─────┐
                  │ DynamoDB  │      │    S3     │
                  └───────────┘      └───────────┘
```

### When to Use

- Variable, unpredictable load
- Event-driven workloads
- Want minimal operations
- Pay-per-use model preferred
- Rapid prototyping

### Trade-offs

**Pros**:
- Auto-scaling
- Pay per execution
- No server management
- Fast deployment
- Built-in high availability

**Cons**:
- Cold start latency
- Vendor lock-in
- Debugging challenges
- Execution time limits
- Stateless constraints

## Clean Architecture

### Structure

```
┌────────────────────────────────────────┐
│         Frameworks & Drivers           │  (External)
│    Web, DB, UI, External Interfaces    │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│      Interface Adapters               │  (Adapters)
│   Controllers, Gateways, Presenters   │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│       Application Business Rules       │  (Use Cases)
│          Use Cases, Services           │
└──────────────┬─────────────────────────┘
               │
┌──────────────▼─────────────────────────┐
│     Enterprise Business Rules          │  (Entities)
│          Domain Entities               │
└────────────────────────────────────────┘

Dependencies point inward
```

### Dependency Rule

**Inner layers don't know about outer layers**
- Entities don't know about use cases
- Use cases don't know about controllers
- Controllers know about use cases

### When to Use

- Long-lived applications
- Complex business rules
- Need maximum testability
- Want framework independence

## CQRS (Command Query Responsibility Segregation)

### Structure

```
                    ┌──────────┐
                    │  Client  │
                    └─────┬────┘
                          │
              ┌───────────┴───────────┐
              │                       │
         ┌────▼─────┐           ┌────▼────┐
         │ Commands │           │ Queries │
         │  (Write) │           │  (Read) │
         └────┬─────┘           └────┬────┘
              │                      │
         ┌────▼─────┐           ┌────▼────┐
         │ Write DB │           │ Read DB │
         │ (Normal) │───sync───▶│(Denorm) │
         └──────────┘           └─────────┘
```

### When to Use

- Different read/write patterns
- High read/write ratio
- Complex queries needed
- Performance critical
- Event sourcing

### Trade-offs

**Pros**:
- Optimized reads and writes separately
- Scalability
- Clear separation
- Flexibility in models

**Cons**:
- Eventual consistency
- More complex
- Sync overhead
- Duplicate data

## Service Mesh

### Structure

```
┌─────────────────────────────────────────┐
│          Service Mesh Control Plane     │
│              (Istio, Linkerd)           │
└────────────┬────────────────────────────┘
             │ Configuration
┌────────────┼────────────────────────────┐
│            │                            │
│   ┌────────▼────────┐   ┌──────────┐   │
│   │  Service A      │   │ Service B│   │
│   │  ┌──────────┐   │   │┌────────┐│   │
│   │  │ Business │   │   ││Business││   │
│   │  │  Logic   │   │   ││ Logic  ││   │
│   │  └──────────┘   │   │└────────┘│   │
│   │  ┌──────────┐   │   │┌────────┐│   │
│   │  │  Sidecar │◄──┼───┼┤Sidecar ││   │
│   │  │  Proxy   │   │   ││ Proxy  ││   │
│   │  └──────────┘   │   │└────────┘│   │
│   └─────────────────┘   └──────────┘   │
└─────────────────────────────────────────┘
```

### When to Use

- Microservices at scale
- Need observability
- Complex routing/security
- Polyglot services

### Provides

- Service discovery
- Load balancing
- Circuit breaking
- Encryption (mTLS)
- Distributed tracing
- Traffic management

## Pattern Selection Guide

| Requirement | Recommended Pattern |
|-------------|-------------------|
| Simple CRUD app | Layered |
| Enterprise monolith | Clean/Hexagonal |
| Multiple teams | Microservices |
| Async workflows | Event-Driven |
| Minimal ops | Serverless |
| High read/write split | CQRS |
| Polyglot services | Microservices + Service Mesh |
| Domain complexity | Domain-Driven Design + Hexagonal |
| Variable load | Serverless or Event-Driven |
| Strict consistency | Layered or Monolithic |

## Anti-Patterns to Avoid

### Big Ball of Mud
Everything coupled, no clear structure
**Fix**: Introduce layers or hexagonal

### Golden Hammer
Using one pattern for everything
**Fix**: Match pattern to problem

### Analysis Paralysis
Over-architecting before understanding
**Fix**: Start simple, evolve

### Distributed Monolith
Microservices that must deploy together
**Fix**: Better boundaries or merge services

### Premature Optimization
Choosing complex patterns too early
**Fix**: YAGNI - start simple

## Combining Patterns

Patterns often work together:

- **Microservices + Event-Driven**: Services communicate via events
- **Hexagonal + DDD**: Isolated domain logic
- **CQRS + Event Sourcing**: Events as source of truth
- **Layered + Clean**: Clean architecture within layers
- **Microservices + Service Mesh**: Manage service complexity

## Evolution Strategy

```
Phase 1: Modular Monolith (Layered/Hexagonal)
    ↓
Phase 2: Extract High-Change Services
    ↓
Phase 3: Microservices for Core
    ↓
Phase 4: Event-Driven for Integration
    ↓
Phase 5: CQRS for Performance
```

Start simple, evolve based on real pain points.
