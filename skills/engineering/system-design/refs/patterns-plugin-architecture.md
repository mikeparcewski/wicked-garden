# Component Design Patterns: Plugin Architecture

## Plugin Architecture

### Structure

```
┌────────────────────────────┐
│       Core System          │
│  (Minimal, Stable)         │
└────────┬───────────────────┘
         │
         │ Plugin Interface
         │
    ┌────┼────┬────────┬──────┐
    │    │    │        │      │
┌───▼┐ ┌─▼──┐ ┌▼────┐ ┌▼────┐
│P1  │ │ P2 │ │ P3  │ │ P4  │
└────┘ └────┘ └─────┘ └─────┘
```

### Example

```typescript
// Core System
interface Plugin {
  name: string;
  version: string;
  init(app: Application): Promise<void>;
  shutdown(): Promise<void>;
}

class PluginManager {
  private plugins: Map<string, Plugin> = new Map();

  async register(plugin: Plugin): Promise<void> {
    if (this.plugins.has(plugin.name)) {
      throw new Error(`Plugin ${plugin.name} already registered`);
    }

    await plugin.init(this.app);
    this.plugins.set(plugin.name, plugin);
  }

  async unregister(name: string): Promise<void> {
    const plugin = this.plugins.get(name);
    if (!plugin) return;

    await plugin.shutdown();
    this.plugins.delete(name);
  }

  getPlugin(name: string): Plugin | undefined {
    return this.plugins.get(name);
  }
}

// Plugin Implementation
class AuthPlugin implements Plugin {
  name = 'auth';
  version = '1.0.0';

  async init(app: Application): Promise<void> {
    // Register routes
    app.post('/auth/login', this.handleLogin);
    app.post('/auth/logout', this.handleLogout);

    // Register middleware
    app.use(this.authMiddleware);
  }

  async shutdown(): Promise<void> {
    // Cleanup
  }

  private handleLogin = async (req, res) => {
    // Login logic
  };

  private handleLogout = async (req, res) => {
    // Logout logic
  };

  private authMiddleware = async (req, res, next) => {
    // Auth checking
    next();
  };
}

// Usage
const pluginManager = new PluginManager(app);
await pluginManager.register(new AuthPlugin());
await pluginManager.register(new PaymentPlugin());
await pluginManager.register(new NotificationPlugin());
```

### When to Use

- Extensibility is a key requirement
- Third-party extensions needed
- Feature sets vary by deployment
- Plugin marketplace desired

### Trade-offs

**Pros**: Highly extensible, loose coupling
**Cons**: Plugin compatibility, security concerns

## Repository Pattern

### Structure

```
┌─────────────┐
│   Service   │
└──────┬──────┘
       │
       │ Interface
       │
┌──────▼──────┐
│ Repository  │ (Abstraction)
└──────┬──────┘
       │
       │ Implementation
       │
┌──────▼──────┐
│  Database   │
└─────────────┘
```

### Example

```typescript
// Repository Interface
interface UserRepository {
  findById(id: string): Promise<User | null>;
  findAll(filter?: UserFilter): Promise<User[]>;
  save(user: User): Promise<void>;
  delete(id: string): Promise<void>;
}

// Domain Entity
class User {
  constructor(
    public id: string,
    public email: string,
    public name: string,
    public status: 'active' | 'inactive'
  ) {}
}

// Repository Implementation
class PostgresUserRepository implements UserRepository {
  constructor(private db: Database) {}

  async findById(id: string): Promise<User | null> {
    const row = await this.db.queryOne(
      'SELECT * FROM users WHERE id = $1',
      [id]
    );

    return row ? this.mapToEntity(row) : null;
  }

  async findAll(filter?: UserFilter): Promise<User[]> {
    const query = this.buildQuery(filter);
    const rows = await this.db.query(query.sql, query.params);
    return rows.map(row => this.mapToEntity(row));
  }

  async save(user: User): Promise<void> {
    await this.db.query(
      `INSERT INTO users (id, email, name, status)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (id) DO UPDATE
       SET email = $2, name = $3, status = $4`,
      [user.id, user.email, user.name, user.status]
    );
  }

  async delete(id: string): Promise<void> {
    await this.db.query('DELETE FROM users WHERE id = $1', [id]);
  }

  private mapToEntity(row: any): User {
    return new User(row.id, row.email, row.name, row.status);
  }

  private buildQuery(filter?: UserFilter) {
    // Query building logic
    return { sql: '...', params: [] };
  }
}

// Service using repository
class UserService {
  constructor(private userRepo: UserRepository) {}

  async getActiveUsers(): Promise<User[]> {
    const users = await this.userRepo.findAll({ status: 'active' });
    return users;
  }

  async activateUser(id: string): Promise<void> {
    const user = await this.userRepo.findById(id);
    if (!user) throw new Error('User not found');

    user.status = 'active';
    await this.userRepo.save(user);
  }
}
```

### When to Use

- Need to abstract data access
- Multiple data sources possible
- Domain-driven design
- Testing with mock data

### Trade-offs

**Pros**: Decouples business logic from data access
**Cons**: Additional abstraction layer

