# Component Design Patterns: Layered Pattern

## Layered Pattern

### Structure

```
┌─────────────────────────┐
│   Presentation Layer    │  Controllers, Views, API
├─────────────────────────┤
│   Application Layer     │  Use Cases, Workflows
├─────────────────────────┤
│     Domain Layer        │  Business Logic, Entities
├─────────────────────────┤
│  Infrastructure Layer   │  Database, External Services
└─────────────────────────┘
```

### Example

```typescript
// Presentation Layer (API Controller)
class UserController {
  constructor(private userService: UserService) {}

  async createUser(req: Request, res: Response) {
    const result = await this.userService.createUser(req.body);
    res.status(201).json(result);
  }
}

// Application Layer (Service)
class UserService {
  constructor(
    private userRepo: UserRepository,
    private emailService: EmailService
  ) {}

  async createUser(data: CreateUserDTO): Promise<User> {
    // Application logic
    const user = User.create(data);
    await this.userRepo.save(user);
    await this.emailService.sendWelcome(user.email);
    return user;
  }
}

// Domain Layer (Entity)
class User {
  constructor(
    public id: string,
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

  static create(data: { email: string; name: string }): User {
    return new User(generateId(), data.email, data.name);
  }
}

// Infrastructure Layer (Repository)
class PostgresUserRepository implements UserRepository {
  async save(user: User): Promise<void> {
    await db.query(
      'INSERT INTO users (id, email, name) VALUES ($1, $2, $3)',
      [user.id, user.email, user.name]
    );
  }
}
```

### When to Use

- Traditional web applications
- Need clear separation of concerns
- Team familiar with MVC
- Moderate complexity

### Trade-offs

**Pros**: Easy to understand, well-known pattern
**Cons**: Can become rigid, may lead to anemic models

## Hexagonal (Ports & Adapters)

### Structure

```
            ┌──────────────┐
            │   REST API   │ (Adapter)
            └──────┬───────┘
                   │
        ┌──────────▼──────────┐
        │    Port (Interface) │
        ├─────────────────────┤
        │                     │
        │   Business Logic    │
        │    (Core Domain)    │
        │                     │
        ├─────────────────────┤
        │ Port (Interface)    │
        └──────────┬──────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
   ┌────▼───┐ ┌───▼────┐ ┌──▼────┐
   │Postgres│ │ Redis  │ │  S3   │ (Adapters)
   └────────┘ └────────┘ └───────┘
```

### Example

```typescript
// Port (Interface)
interface UserRepository {
  save(user: User): Promise<void>;
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
}

// Core Domain (Business Logic)
class UserService {
  constructor(
    private userRepo: UserRepository,  // Depends on port, not adapter
    private emailGateway: EmailGateway
  ) {}

  async registerUser(email: string, name: string): Promise<User> {
    // Pure business logic
    const existing = await this.userRepo.findByEmail(email);
    if (existing) {
      throw new Error('Email already registered');
    }

    const user = User.create(email, name);
    await this.userRepo.save(user);
    await this.emailGateway.sendWelcome(user.email);

    return user;
  }
}

// Adapter (Implementation)
class PostgresUserRepository implements UserRepository {
  async save(user: User): Promise<void> {
    await db.query('INSERT INTO users ...');
  }

  async findById(id: string): Promise<User | null> {
    const row = await db.query('SELECT * FROM users WHERE id = $1', [id]);
    return row ? User.fromRow(row) : null;
  }

  async findByEmail(email: string): Promise<User | null> {
    const row = await db.query('SELECT * FROM users WHERE email = $1', [email]);
    return row ? User.fromRow(row) : null;
  }
}

// Another Adapter (for testing)
class InMemoryUserRepository implements UserRepository {
  private users = new Map<string, User>();

  async save(user: User): Promise<void> {
    this.users.set(user.id, user);
  }

  async findById(id: string): Promise<User | null> {
    return this.users.get(id) || null;
  }

  async findByEmail(email: string): Promise<User | null> {
    for (const user of this.users.values()) {
      if (user.email === email) return user;
    }
    return null;
  }
}
```

### When to Use

- Need to isolate business logic
- Frequent technology changes
- Testing is critical
- Multiple interfaces (API, CLI, Worker)

### Trade-offs

**Pros**: Highly testable, technology-agnostic core
**Cons**: More abstraction, may be overkill for simple apps

