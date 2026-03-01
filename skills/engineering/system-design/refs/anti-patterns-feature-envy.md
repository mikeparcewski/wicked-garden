# Component Anti-Patterns: Feature Envy

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
