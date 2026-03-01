# Component Anti-Patterns: God Object

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

