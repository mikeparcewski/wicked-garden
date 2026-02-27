# Component Design Patterns

Common patterns for organizing and structuring system components.

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

## Facade Pattern

### Structure

```
┌──────────┐
│  Client  │
└────┬─────┘
     │
     │ Simple Interface
     │
┌────▼────────────┐
│     Facade      │
└────┬────┬───┬───┘
     │    │   │
┌────▼┐ ┌─▼─┐ ┌▼────┐
│Sub1 │ │S2 │ │ S3  │ (Complex Subsystems)
└─────┘ └───┘ └─────┘
```

### Example

```typescript
// Complex Subsystems
class PaymentProcessor {
  async charge(amount: number, token: string): Promise<string> {
    // Complex payment logic
  }
}

class InventoryManager {
  async reserve(productId: string, quantity: number): Promise<void> {
    // Complex inventory logic
  }

  async release(productId: string, quantity: number): Promise<void> {
    // Release reserved inventory
  }
}

class ShippingService {
  async createShipment(order: Order): Promise<string> {
    // Complex shipping logic
  }
}

class NotificationService {
  async sendOrderConfirmation(userId: string, orderId: string): Promise<void> {
    // Send notifications
  }
}

// Facade - Simple Interface
class OrderFacade {
  constructor(
    private payment: PaymentProcessor,
    private inventory: InventoryManager,
    private shipping: ShippingService,
    private notifications: NotificationService
  ) {}

  async createOrder(request: CreateOrderRequest): Promise<Order> {
    // Simple interface hiding complex workflow
    try {
      // Reserve inventory
      for (const item of request.items) {
        await this.inventory.reserve(item.productId, item.quantity);
      }

      // Process payment
      const transactionId = await this.payment.charge(
        request.total,
        request.paymentToken
      );

      // Create order record
      const order = await this.saveOrder({
        ...request,
        transactionId,
        status: 'confirmed'
      });

      // Create shipment
      await this.shipping.createShipment(order);

      // Send confirmation
      await this.notifications.sendOrderConfirmation(
        request.userId,
        order.id
      );

      return order;
    } catch (error) {
      // Rollback on failure
      for (const item of request.items) {
        await this.inventory.release(item.productId, item.quantity);
      }
      throw error;
    }
  }

  private async saveOrder(data: any): Promise<Order> {
    // Save order logic
    return {} as Order;
  }
}

// Client Usage
const orderFacade = new OrderFacade(
  paymentProcessor,
  inventoryManager,
  shippingService,
  notificationService
);

// Simple call, complex workflow hidden
const order = await orderFacade.createOrder({
  userId: 'user123',
  items: [{ productId: 'prod1', quantity: 2 }],
  total: 99.99,
  paymentToken: 'tok_123'
});
```

### When to Use

- Simplify complex subsystems
- Provide unified interface
- Reduce client dependencies
- Hide implementation complexity

### Trade-offs

**Pros**: Simplified interface, loose coupling
**Cons**: Can become a god object

## Strategy Pattern

### Structure

```
┌──────────┐
│ Context  │
└────┬─────┘
     │
     │ Uses
     │
┌────▼────────┐
│  Strategy   │ (Interface)
└────┬────────┘
     │
     │ Implements
     │
  ┌──┼────┬──────┐
  │  │    │      │
┌─▼┐ ┌▼─┐ ┌▼──┐ ┌▼─┐
│S1│ │S2│ │S3 │ │S4│
└──┘ └──┘ └───┘ └──┘
```

### Example

```typescript
// Strategy Interface
interface PricingStrategy {
  calculatePrice(basePrice: number, quantity: number): number;
}

// Concrete Strategies
class RegularPricing implements PricingStrategy {
  calculatePrice(basePrice: number, quantity: number): number {
    return basePrice * quantity;
  }
}

class BulkPricing implements PricingStrategy {
  constructor(private discount: number) {}

  calculatePrice(basePrice: number, quantity: number): number {
    const subtotal = basePrice * quantity;
    if (quantity >= 10) {
      return subtotal * (1 - this.discount);
    }
    return subtotal;
  }
}

class MemberPricing implements PricingStrategy {
  constructor(private memberDiscount: number) {}

  calculatePrice(basePrice: number, quantity: number): number {
    return basePrice * quantity * (1 - this.memberDiscount);
  }
}

class SeasonalPricing implements PricingStrategy {
  constructor(private season: 'peak' | 'off-peak') {}

  calculatePrice(basePrice: number, quantity: number): number {
    const multiplier = this.season === 'peak' ? 1.2 : 0.8;
    return basePrice * quantity * multiplier;
  }
}

// Context
class ShoppingCart {
  private items: Array<{ productId: string; basePrice: number; quantity: number }> = [];

  constructor(private pricingStrategy: PricingStrategy) {}

  addItem(productId: string, basePrice: number, quantity: number): void {
    this.items.push({ productId, basePrice, quantity });
  }

  getTotal(): number {
    return this.items.reduce((total, item) => {
      return total + this.pricingStrategy.calculatePrice(item.basePrice, item.quantity);
    }, 0);
  }

  setPricingStrategy(strategy: PricingStrategy): void {
    this.pricingStrategy = strategy;
  }
}

// Usage
const cart = new ShoppingCart(new RegularPricing());
cart.addItem('prod1', 29.99, 5);
console.log(cart.getTotal());  // Regular pricing

// Switch to bulk pricing
cart.setPricingStrategy(new BulkPricing(0.1));  // 10% discount
console.log(cart.getTotal());  // Bulk pricing

// Switch to member pricing
cart.setPricingStrategy(new MemberPricing(0.15));  // 15% discount
console.log(cart.getTotal());  // Member pricing
```

### When to Use

- Multiple algorithms for same task
- Runtime algorithm selection needed
- Avoid large conditionals
- Encapsulate varying behavior

### Trade-offs

**Pros**: Flexible, testable, follows Open/Closed
**Cons**: More classes, client must know strategies

## Dependency Injection

### Structure

```
┌──────────────┐
│  Container   │
└──────┬───────┘
       │ Resolves
       │
┌──────▼──────────┐
│    Service      │
└──────┬──────────┘
       │ Depends on
       │
┌──────▼──────────┐
│   Dependency    │ (Injected)
└─────────────────┘
```

### Example

```typescript
// Dependencies
interface Logger {
  log(message: string): void;
}

class ConsoleLogger implements Logger {
  log(message: string): void {
    console.log(message);
  }
}

class FileLogger implements Logger {
  constructor(private filename: string) {}

  log(message: string): void {
    fs.appendFileSync(this.filename, message + '\n');
  }
}

// Service with dependencies
class UserService {
  constructor(
    private userRepo: UserRepository,
    private logger: Logger,
    private emailService: EmailService
  ) {}

  async createUser(data: CreateUserDTO): Promise<User> {
    this.logger.log(`Creating user: ${data.email}`);

    const user = await this.userRepo.save(User.create(data));

    await this.emailService.sendWelcome(user.email);

    this.logger.log(`User created: ${user.id}`);

    return user;
  }
}

// DI Container
class Container {
  private services = new Map<string, any>();

  register<T>(token: string, factory: () => T): void {
    this.services.set(token, factory);
  }

  resolve<T>(token: string): T {
    const factory = this.services.get(token);
    if (!factory) {
      throw new Error(`Service ${token} not registered`);
    }
    return factory();
  }
}

// Setup
const container = new Container();

container.register<Logger>('Logger', () => new ConsoleLogger());
container.register<UserRepository>('UserRepository', () => new PostgresUserRepository(db));
container.register<EmailService>('EmailService', () => new EmailService());

container.register<UserService>('UserService', () => {
  return new UserService(
    container.resolve('UserRepository'),
    container.resolve('Logger'),
    container.resolve('EmailService')
  );
});

// Usage
const userService = container.resolve<UserService>('UserService');
await userService.createUser({ email: 'test@example.com', name: 'Test' });
```

### When to Use

- Need loose coupling
- Multiple implementations
- Testability important
- Configuration flexibility

### Trade-offs

**Pros**: Testable, flexible, decoupled
**Cons**: Indirection, learning curve

## Best Practices

### 1. Single Responsibility

Each component should have one reason to change.

### 2. Interface Segregation

Prefer many small interfaces over large ones.

### 3. Dependency Inversion

Depend on abstractions, not concretions.

### 4. Composition over Inheritance

Favor composing objects over class hierarchies.

### 5. Keep It Simple

Don't over-engineer. Start simple, refactor when needed.

### 6. Document Patterns

Make it clear which patterns are used and why.

### 7. Consistent Structure

Use consistent patterns across similar components.

### 8. Test Boundaries

Test component interfaces and contracts.
