# Component Anti-Patterns

Common mistakes to avoid when designing system components.

## God Object

### Problem

One object does too much, knows too much, or has too many responsibilities.

### Symptoms

```typescript
// Bad: God object
class ApplicationManager {
  // Database operations
  async saveUser(user: User) {}
  async getUser(id: string) {}

  // Payment processing
  async processPayment(payment: Payment) {}
  async refundPayment(id: string) {}

  // Email sending
  async sendWelcomeEmail(email: string) {}
  async sendPasswordReset(email: string) {}

  // Authentication
  async login(email: string, password: string) {}
  async logout(token: string) {}

  // Logging
  log(message: string) {}
  logError(error: Error) {}

  // Configuration
  getConfig(key: string) {}
  setConfig(key: string, value: any) {}

  // File operations
  uploadFile(file: File) {}
  downloadFile(id: string) {}

  // ... 50 more methods
}
```

### Impact

- Difficult to test
- Hard to maintain
- Impossible to understand
- High coupling
- Brittle (changes break everything)

### Solution

Split into focused, single-responsibility components:

```typescript
// Good: Focused components
class UserRepository {
  async save(user: User) {}
  async findById(id: string) {}
}

class PaymentService {
  async process(payment: Payment) {}
  async refund(id: string) {}
}

class EmailService {
  async sendWelcome(email: string) {}
  async sendPasswordReset(email: string) {}
}

class AuthService {
  async login(email: string, password: string) {}
  async logout(token: string) {}
}

class Logger {
  log(message: string) {}
  error(error: Error) {}
}

class ConfigService {
  get(key: string) {}
  set(key: string, value: any) {}
}

class FileService {
  async upload(file: File) {}
  async download(id: string) {}
}
```

## Anemic Domain Model

### Problem

Domain objects with no behavior, just getters and setters. All logic in services.

### Symptoms

```typescript
// Bad: Anemic model
class Order {
  id: string;
  items: OrderItem[];
  status: string;
  total: number;

  // Only getters/setters, no behavior
  getId(): string { return this.id; }
  setId(id: string) { this.id = id; }
  getItems(): OrderItem[] { return this.items; }
  setItems(items: OrderItem[]) { this.items = items; }
  // ... more getters/setters
}

// All logic in service
class OrderService {
  calculateTotal(order: Order): number {
    let total = 0;
    for (const item of order.getItems()) {
      total += item.getPrice() * item.getQuantity();
    }
    order.setTotal(total);
    return total;
  }

  validateOrder(order: Order): boolean {
    if (order.getItems().length === 0) return false;
    if (order.getTotal() < 0) return false;
    return true;
  }

  canCancel(order: Order): boolean {
    return order.getStatus() === 'pending' ||
           order.getStatus() === 'processing';
  }
}
```

### Impact

- Business logic scattered across services
- Difficult to maintain invariants
- Not object-oriented
- Hard to reason about

### Solution

Put behavior in domain objects:

```typescript
// Good: Rich domain model
class Order {
  private constructor(
    private id: string,
    private items: OrderItem[],
    private status: OrderStatus,
    private total: number
  ) {
    this.validateInvariants();
  }

  static create(items: OrderItem[]): Order {
    if (items.length === 0) {
      throw new Error('Order must have at least one item');
    }

    const total = items.reduce((sum, item) => sum + item.subtotal(), 0);

    return new Order(
      generateId(),
      items,
      OrderStatus.PENDING,
      total
    );
  }

  // Business logic in domain object
  calculateTotal(): number {
    return this.items.reduce((sum, item) => sum + item.subtotal(), 0);
  }

  cancel(): void {
    if (!this.canCancel()) {
      throw new Error(`Cannot cancel order in ${this.status} status`);
    }
    this.status = OrderStatus.CANCELLED;
  }

  private canCancel(): boolean {
    return this.status === OrderStatus.PENDING ||
           this.status === OrderStatus.PROCESSING;
  }

  addItem(item: OrderItem): void {
    this.items.push(item);
    this.total = this.calculateTotal();
  }

  private validateInvariants(): void {
    if (this.items.length === 0) {
      throw new Error('Order must have items');
    }
    if (this.total < 0) {
      throw new Error('Order total cannot be negative');
    }
  }

  // Getters only, no setters
  getId(): string { return this.id; }
  getItems(): readonly OrderItem[] { return this.items; }
  getStatus(): OrderStatus { return this.status; }
  getTotal(): number { return this.total; }
}

enum OrderStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  SHIPPED = 'shipped',
  DELIVERED = 'delivered',
  CANCELLED = 'cancelled'
}

// Service is thin, delegates to domain
class OrderService {
  async createOrder(items: OrderItem[]): Promise<Order> {
    const order = Order.create(items);  // Domain logic
    await this.orderRepo.save(order);
    return order;
  }

  async cancelOrder(orderId: string): Promise<void> {
    const order = await this.orderRepo.findById(orderId);
    order.cancel();  // Domain logic
    await this.orderRepo.save(order);
  }
}
```

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

## Circular Dependencies

### Problem

Component A depends on B, and B depends on A.

### Symptoms

```typescript
// Bad: Circular dependency
// UserService.ts
class UserService {
  constructor(private orderService: OrderService) {}

  async deleteUser(id: string) {
    // Check if user has orders
    const orders = await this.orderService.getUserOrders(id);
    if (orders.length > 0) {
      throw new Error('Cannot delete user with orders');
    }
    await this.userRepo.delete(id);
  }
}

// OrderService.ts
class OrderService {
  constructor(private userService: UserService) {}

  async createOrder(data: OrderData) {
    // Get user details
    const user = await this.userService.getUser(data.userId);
    if (!user) {
      throw new Error('User not found');
    }
    await this.orderRepo.save(order);
  }

  async getUserOrders(userId: string) {
    return await this.orderRepo.findByUserId(userId);
  }
}
```

### Impact

- Initialization problems
- Hard to understand
- Tight coupling
- Can't test independently

### Solution

Break cycle with events, shared interface, or extract common logic:

```typescript
// Solution 1: Use events
class UserService {
  constructor(
    private userRepo: UserRepository,
    private eventBus: EventBus
  ) {}

  async deleteUser(id: string) {
    // Publish event instead of calling OrderService
    const canDelete = await this.eventBus.query('user.can-delete', { userId: id });

    if (!canDelete) {
      throw new Error('Cannot delete user');
    }

    await this.userRepo.delete(id);
    await this.eventBus.publish('user.deleted', { userId: id });
  }
}

class OrderService {
  constructor(
    private orderRepo: OrderRepository,
    private eventBus: EventBus
  ) {
    // Subscribe to events
    this.eventBus.on('user.can-delete', this.handleCanDeleteUser);
    this.eventBus.on('user.deleted', this.handleUserDeleted);
  }

  private handleCanDeleteUser = async (event: any) => {
    const orders = await this.orderRepo.findByUserId(event.userId);
    return orders.length === 0;
  };

  private handleUserDeleted = async (event: any) => {
    // Clean up user's orders
  };
}

// Solution 2: Extract shared logic
interface UserReader {
  findById(id: string): Promise<User | null>;
}

class UserService implements UserReader {
  async findById(id: string): Promise<User | null> {
    return await this.userRepo.findById(id);
  }
}

class OrderService {
  // Depend on interface, not concrete UserService
  constructor(
    private userReader: UserReader,
    private orderRepo: OrderRepository
  ) {}

  async createOrder(data: OrderData) {
    const user = await this.userReader.findById(data.userId);
    if (!user) {
      throw new Error('User not found');
    }
    await this.orderRepo.save(order);
  }
}
```

## Shotgun Surgery

### Problem

One change requires modifying many components.

### Symptoms

```typescript
// Bad: Adding new user status requires changes in many places

// UserService.ts
async updateStatus(id: string, status: string) {
  if (status !== 'active' && status !== 'inactive' && status !== 'suspended') {
    throw new Error('Invalid status');
  }
  // ...
}

// UserController.ts
validateStatus(status: string) {
  const valid = ['active', 'inactive', 'suspended'];
  return valid.includes(status);
}

// UserRepository.ts
findByStatus(status: string) {
  if (!['active', 'inactive', 'suspended'].includes(status)) {
    throw new Error('Invalid status');
  }
  // ...
}

// UserDTO.ts
class UserDTO {
  status: 'active' | 'inactive' | 'suspended';
}

// database/migrations/001_create_users.sql
CREATE TABLE users (
  status VARCHAR(20) CHECK (status IN ('active', 'inactive', 'suspended'))
);
```

### Impact

- High change cost
- Easy to miss updates
- Inconsistencies
- Brittle code

### Solution

Centralize related logic:

```typescript
// Good: Centralized status management

// domain/UserStatus.ts
export enum UserStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  SUSPENDED = 'suspended'
}

export class UserStatusManager {
  private static readonly ALL_STATUSES = Object.values(UserStatus);

  static isValid(status: string): boolean {
    return this.ALL_STATUSES.includes(status as UserStatus);
  }

  static getAllStatuses(): UserStatus[] {
    return this.ALL_STATUSES;
  }

  static canTransition(from: UserStatus, to: UserStatus): boolean {
    const transitions = {
      [UserStatus.ACTIVE]: [UserStatus.INACTIVE, UserStatus.SUSPENDED],
      [UserStatus.INACTIVE]: [UserStatus.ACTIVE],
      [UserStatus.SUSPENDED]: []
    };

    return transitions[from]?.includes(to) || false;
  }
}

// Now components use centralized logic
// UserService.ts
async updateStatus(id: string, status: UserStatus) {
  if (!UserStatusManager.isValid(status)) {
    throw new Error('Invalid status');
  }

  const user = await this.userRepo.findById(id);
  if (!UserStatusManager.canTransition(user.status, status)) {
    throw new Error('Invalid status transition');
  }

  user.status = status;
  await this.userRepo.save(user);
}

// UserController.ts
@Get('/statuses')
getStatuses() {
  return UserStatusManager.getAllStatuses();
}

// Adding new status: Change in ONE place (UserStatus enum)
```

## Feature Envy

### Problem

Method uses more features of another class than its own.

### Symptoms

```typescript
// Bad: OrderService envies Order data
class OrderService {
  calculateShipping(order: Order): number {
    let weight = 0;
    for (const item of order.getItems()) {
      weight += item.getWeight() * item.getQuantity();
    }

    const distance = this.calculateDistance(
      order.getShippingAddress(),
      order.getWarehouseAddress()
    );

    return weight * distance * 0.1;
  }

  validateOrder(order: Order): boolean {
    if (order.getItems().length === 0) return false;

    for (const item of order.getItems()) {
      if (item.getQuantity() <= 0) return false;
      if (item.getPrice() < 0) return false;
    }

    if (!order.getShippingAddress()) return false;

    return true;
  }
}
```

### Impact

- Logic in wrong place
- Tight coupling
- Duplicated logic
- Poor encapsulation

### Solution

Move logic to the class that owns the data:

```typescript
// Good: Move logic to Order
class Order {
  calculateShipping(): number {
    const weight = this.calculateTotalWeight();
    const distance = this.calculateShippingDistance();
    return weight * distance * 0.1;
  }

  private calculateTotalWeight(): number {
    return this.items.reduce(
      (total, item) => total + (item.weight * item.quantity),
      0
    );
  }

  private calculateShippingDistance(): number {
    return this.calculateDistance(
      this.shippingAddress,
      this.warehouseAddress
    );
  }

  validate(): boolean {
    if (this.items.length === 0) return false;

    for (const item of this.items) {
      if (!item.isValid()) return false;
    }

    if (!this.shippingAddress) return false;

    return true;
  }
}

class OrderItem {
  isValid(): boolean {
    return this.quantity > 0 && this.price >= 0;
  }
}

// Service is now thin
class OrderService {
  async createOrder(data: OrderData): Promise<Order> {
    const order = Order.create(data);

    if (!order.validate()) {
      throw new Error('Invalid order');
    }

    const shipping = order.calculateShipping();

    await this.orderRepo.save(order);
    return order;
  }
}
```

## Best Practices to Avoid Anti-Patterns

### 1. Single Responsibility Principle

Each component should have one reason to change.

### 2. Keep Components Small

If a class has more than 200-300 lines, consider splitting it.

### 3. Prefer Composition

Build complex behavior from simple, focused components.

### 4. Test Driven Development

Tests expose design problems early.

### 5. Code Reviews

Another set of eyes catches anti-patterns.

### 6. Refactor Regularly

Don't let anti-patterns accumulate.

### 7. Use Static Analysis

Tools can detect many anti-patterns automatically:

```bash
# TypeScript
npx ts-unused-exports

# Circular dependencies
npx madge --circular src/

# Complexity
npx complexity-report
```

### 8. Document Architectural Decisions

Make design principles explicit in ADRs.

### 9. Pair Programming

Share knowledge and catch issues early.

### 10. Continuous Learning

Stay updated on design patterns and best practices.
