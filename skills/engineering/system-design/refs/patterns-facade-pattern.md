# Component Design Patterns: Facade Pattern

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

