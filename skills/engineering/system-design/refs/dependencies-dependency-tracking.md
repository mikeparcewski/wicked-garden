# Dependency Management Guide: Dependency Tracking

## Dependency Tracking

### Dependency Matrix

Track dependencies between components.

| Component | Depends On |
|-----------|------------|
| UserController | UserService, AuthMiddleware |
| UserService | UserRepository, EmailService |
| OrderService | OrderRepository, UserService, PaymentService |
| PaymentService | PaymentGateway, OrderRepository |

### Dependency Metrics

```typescript
// Calculate coupling metrics
function calculateAfferentCoupling(component: string): number {
  // Number of components that depend on this component
  return dependencies.filter(d => d.dependsOn === component).length;
}

function calculateEfferentCoupling(component: string): number {
  // Number of components this component depends on
  return dependencies.filter(d => d.component === component).length;
}

function calculateInstability(component: string): number {
  const ce = calculateEfferentCoupling(component);
  const ca = calculateAfferentCoupling(component);
  // Instability = Ce / (Ce + Ca)
  // 0 = maximally stable, 1 = maximally unstable
  return ce / (ce + ca);
}
```

## Anti-Patterns

### 1. Circular Dependencies

```typescript
// Bad: Circular dependency
class UserService {
  constructor(private orderService: OrderService) {}
}

class OrderService {
  constructor(private userService: UserService) {}
}

// Fix: Extract common logic or use events
class UserService {
  constructor(private eventBus: EventBus) {}

  async createUser(data: UserData) {
    const user = await this.saveUser(data);
    this.eventBus.publish('user.created', { userId: user.id });
    return user;
  }
}

class OrderService {
  constructor(private eventBus: EventBus) {
    this.eventBus.subscribe('user.created', this.handleUserCreated);
  }

  private handleUserCreated = async (event: UserCreatedEvent) => {
    // Initialize order data for new user
  };
}
```

### 2. God Object

```typescript
// Bad: God object with many dependencies
class ApplicationService {
  constructor(
    private userRepo: UserRepository,
    private orderRepo: OrderRepository,
    private productRepo: ProductRepository,
    private paymentService: PaymentService,
    private emailService: EmailService,
    private smsService: SMSService,
    private notificationService: NotificationService,
    private analyticsService: AnalyticsService,
    private auditService: AuditService
  ) {}
}

// Fix: Split into focused services
class UserService {
  constructor(
    private userRepo: UserRepository,
    private emailService: EmailService
  ) {}
}

class OrderService {
  constructor(
    private orderRepo: OrderRepository,
    private paymentService: PaymentService,
    private notificationService: NotificationService
  ) {}
}
```

### 3. Hidden Dependencies

```typescript
// Bad: Hidden global dependency
class UserService {
  async getUser(id: string) {
    return await globalDatabase.query('SELECT * FROM users WHERE id = $1', [id]);
  }
}

// Fix: Explicit dependency
class UserService {
  constructor(private database: Database) {}

  async getUser(id: string) {
    return await this.database.query('SELECT * FROM users WHERE id = $1', [id]);
  }
}
```

### 4. Dependency on Unstable Components

```typescript
// Bad: Stable component depends on unstable component
class DomainEntity {
  constructor(private uiHelper: UIHelper) {}  // UI is unstable
}

// Fix: Invert dependency with abstraction
interface Formatter {
  format(value: any): string;
}

class DomainEntity {
  constructor(private formatter: Formatter) {}
}

// UI implements the interface
class UIFormatter implements Formatter {
  format(value: any): string {
    // UI-specific formatting
  }
}
```

### 5. Feature Envy

```typescript
// Bad: Component uses another's data extensively
class OrderService {
  async calculateTotal(order: Order): Promise<number> {
    let total = 0;
    for (const item of order.items) {
      const product = await this.productRepo.findById(item.productId);
      total += product.price * item.quantity;
    }
    return total;
  }
}

// Fix: Move logic to data owner
class Order {
  calculateTotal(productPrices: Map<string, number>): number {
    return this.items.reduce((total, item) => {
      const price = productPrices.get(item.productId) || 0;
      return total + (price * item.quantity);
    }, 0);
  }
}
```

## Dependency Resolution Strategies

### 1. Constructor Injection

```typescript
class UserService {
  constructor(
    private userRepo: UserRepository,
    private emailService: EmailService
  ) {}
}

// Wiring
const userService = new UserService(userRepo, emailService);
```

**Pros**: Dependencies explicit, immutable
**Cons**: Can lead to large constructors

### 2. Property Injection

```typescript
class UserService {
  userRepo: UserRepository;
  emailService: EmailService;
}

// Wiring
const userService = new UserService();
userService.userRepo = userRepo;
userService.emailService = emailService;
```

**Pros**: Optional dependencies
**Cons**: Mutable, less explicit

### 3. Method Injection

```typescript
class UserService {
  async createUser(data: UserData, emailService: EmailService) {
    const user = await this.saveUser(data);
    await emailService.sendWelcome(user);
    return user;
  }
}
```

**Pros**: Flexible, explicit per-call
**Cons**: Verbose, repetitive

### 4. Service Locator

```typescript
class ServiceLocator {
  private services = new Map();

  register<T>(name: string, instance: T): void {
    this.services.set(name, instance);
  }

  resolve<T>(name: string): T {
    return this.services.get(name);
  }
}

class UserService {
  async createUser(data: UserData) {
    const emailService = ServiceLocator.resolve<EmailService>('EmailService');
    await emailService.sendWelcome(data.email);
  }
}
```

**Pros**: Decoupled
**Cons**: Hidden dependencies, testing harder

