# Component Anti-Patterns: Big Ball of Mud

## Big Ball of Mud

### Problem

No clear architecture. Everything coupled to everything.

### Symptoms

```typescript
// Bad: No structure, everything mixed
// UserController.ts
class UserController {
  async createUser(req, res) {
    // Validation in controller
    if (!req.body.email) {
      return res.status(400).json({ error: 'Email required' });
    }

    // Database access in controller
    const existing = await db.query(
      'SELECT * FROM users WHERE email = $1',
      [req.body.email]
    );

    if (existing) {
      return res.status(409).json({ error: 'Email exists' });
    }

    // Business logic in controller
    const hashedPassword = await bcrypt.hash(req.body.password, 10);

    // More database access
    const result = await db.query(
      'INSERT INTO users (email, password) VALUES ($1, $2) RETURNING *',
      [req.body.email, hashedPassword]
    );

    // Email sending in controller
    await sendGrid.send({
      to: req.body.email,
      subject: 'Welcome',
      html: '<h1>Welcome!</h1>'
    });

    // Direct cache access
    await redis.set(`user:${result.id}`, JSON.stringify(result));

    res.status(201).json(result);
  }
}
```

### Impact

- Impossible to test
- Can't swap dependencies
- Violates single responsibility
- Tightly coupled
- Hard to maintain

### Solution

Introduce clear layers and separation of concerns:

```typescript
// Good: Layered architecture
// Presentation Layer
class UserController {
  constructor(private userService: UserService) {}

  async createUser(req: Request, res: Response) {
    try {
      const user = await this.userService.createUser(req.body);
      res.status(201).json(user);
    } catch (error) {
      if (error instanceof ValidationError) {
        res.status(400).json({ error: error.message });
      } else if (error instanceof ConflictError) {
        res.status(409).json({ error: error.message });
      } else {
        res.status(500).json({ error: 'Internal error' });
      }
    }
  }
}

// Application Layer
class UserService {
  constructor(
    private userRepo: UserRepository,
    private emailService: EmailService,
    private cache: Cache
  ) {}

  async createUser(data: CreateUserDTO): Promise<User> {
    // Validation
    this.validate(data);

    // Check for duplicates
    const existing = await this.userRepo.findByEmail(data.email);
    if (existing) {
      throw new ConflictError('Email already exists');
    }

    // Create user (domain logic)
    const user = User.create(data);

    // Persist
    await this.userRepo.save(user);

    // Send email
    await this.emailService.sendWelcome(user.email);

    // Cache
    await this.cache.set(`user:${user.id}`, user);

    return user;
  }

  private validate(data: CreateUserDTO): void {
    if (!data.email) {
      throw new ValidationError('Email required');
    }
    if (!data.password || data.password.length < 8) {
      throw new ValidationError('Password must be at least 8 characters');
    }
  }
}

// Domain Layer
class User {
  private constructor(
    private id: string,
    private email: string,
    private passwordHash: string
  ) {}

  static async create(data: CreateUserDTO): Promise<User> {
    const hashedPassword = await bcrypt.hash(data.password, 10);
    return new User(generateId(), data.email, hashedPassword);
  }
}

// Infrastructure Layer
class PostgresUserRepository implements UserRepository {
  async save(user: User): Promise<void> {
    await db.query(
      'INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)',
      [user.id, user.email, user.passwordHash]
    );
  }

  async findByEmail(email: string): Promise<User | null> {
    const row = await db.query(
      'SELECT * FROM users WHERE email = $1',
      [email]
    );
    return row ? User.fromRow(row) : null;
  }
}
```

## Leaky Abstraction

### Problem

Implementation details leak through the abstraction.

### Symptoms

```typescript
// Bad: Leaky abstraction
interface UserRepository {
  // SQL query leaking through interface
  query(sql: string, params: any[]): Promise<any>;

  // Database-specific pagination
  findAll(offset: number, limit: number): Promise<any>;

  // Redis-specific method
  flushCache(): Promise<void>;
}

// Forces consumers to know about SQL
const users = await userRepo.query(
  'SELECT * FROM users WHERE email = $1',
  [email]
);
```

### Impact

- Can't swap implementations
- Tied to specific technology
- Breaks abstraction principle
- Hard to test

### Solution

Hide implementation details behind clean interface:

```typescript
// Good: Clean abstraction
interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  findAll(filter?: UserFilter): Promise<User[]>;
  save(user: User): Promise<void>;
  delete(id: string): Promise<void>;
}

interface UserFilter {
  role?: UserRole;
  status?: UserStatus;
  createdAfter?: Date;
}

// Implementation details hidden
class PostgresUserRepository implements UserRepository {
  async findByEmail(email: string): Promise<User | null> {
    const row = await this.db.query(
      'SELECT * FROM users WHERE email = $1',
      [email]
    );
    return row ? this.mapToUser(row) : null;
  }

  async findAll(filter?: UserFilter): Promise<User[]> {
    const query = this.buildQuery(filter);
    const rows = await this.db.query(query.sql, query.params);
    return rows.map(row => this.mapToUser(row));
  }

  // Helper methods private
  private buildQuery(filter?: UserFilter) {
    // SQL building logic hidden
  }

  private mapToUser(row: any): User {
    // Mapping logic hidden
  }
}

// Consumer doesn't know about SQL
const user = await userRepo.findByEmail('test@example.com');
const activeUsers = await userRepo.findAll({ status: 'active' });
```

