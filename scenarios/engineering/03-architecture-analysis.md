---
name: architecture-analysis
title: Service Architecture Analysis
description: Analyze microservice architecture for design issues and improvements
type: architecture
difficulty: advanced
estimated_minutes: 15
---

# Service Architecture Analysis

This scenario demonstrates using wicked-engineering to analyze the architecture of a microservice system, identify design concerns, and recommend improvements.

## Setup

Create a microservice project with architectural issues:

```bash
# Create test project
mkdir -p ~/test-wicked-engineering/arch-test
cd ~/test-wicked-engineering/arch-test

# Create directory structure
mkdir -p services/{user,order,payment,notification,inventory}
mkdir -p shared/{models,utils,events}
mkdir -p gateway

# User Service
cat > services/user/index.ts << 'EOF'
// User Service - handles user management
import express from 'express';
import { OrderService } from '../order';  // ISSUE: Direct service dependency
import { PaymentService } from '../payment';  // ISSUE: Circular potential

export class UserService {
  private orderService: OrderService;
  private paymentService: PaymentService;

  constructor() {
    // ISSUE: Instantiating other services directly
    this.orderService = new OrderService();
    this.paymentService = new PaymentService();
  }

  async getUser(id: string) {
    const user = await db.users.findById(id);
    // ISSUE: Fetching orders in user service
    user.orders = await this.orderService.getOrdersByUser(id);
    // ISSUE: Fetching payment methods
    user.paymentMethods = await this.paymentService.getPaymentMethods(id);
    return user;
  }

  async deleteUser(id: string) {
    // ISSUE: Orchestrating across services synchronously
    await this.orderService.cancelAllOrders(id);
    await this.paymentService.removePaymentMethods(id);
    await db.users.delete(id);
  }
}
EOF

# Order Service
cat > services/order/index.ts << 'EOF'
// Order Service - handles order management
import { UserService } from '../user';  // ISSUE: Circular dependency!
import { InventoryService } from '../inventory';
import { PaymentService } from '../payment';

export class OrderService {
  async createOrder(userId: string, items: any[]) {
    // ISSUE: Validating user in order service
    const user = await new UserService().getUser(userId);
    if (!user.active) throw new Error('User not active');

    // ISSUE: Direct inventory calls
    for (const item of items) {
      const available = await new InventoryService().checkStock(item.productId);
      if (!available) throw new Error(`Out of stock: ${item.productId}`);
    }

    const order = await db.orders.create({ userId, items });

    // ISSUE: Synchronous payment processing in order creation
    const payment = await new PaymentService().processPayment(
      user.defaultPaymentMethod,
      order.total
    );

    // ISSUE: Synchronous inventory update
    for (const item of items) {
      await new InventoryService().decrementStock(item.productId, item.quantity);
    }

    // ISSUE: Synchronous notification
    await fetch('http://notification-service/send', {
      method: 'POST',
      body: JSON.stringify({ type: 'order_created', userId, orderId: order.id })
    });

    return order;
  }
}
EOF

# Shared models (causing coupling)
cat > shared/models/user.ts << 'EOF'
// ISSUE: Shared model causes tight coupling
export interface User {
  id: string;
  email: string;
  name: string;
  // ISSUE: Order data in user model
  orders?: Order[];
  // ISSUE: Payment data in user model
  paymentMethods?: PaymentMethod[];
  // ISSUE: Notification preferences here
  notificationPrefs: NotificationPrefs;
}

export interface Order {
  id: string;
  userId: string;
  // Full user embedded - circular
  user?: User;
  items: OrderItem[];
  payment?: Payment;
}
EOF

# Gateway with too much logic
cat > gateway/index.ts << 'EOF'
// API Gateway
export class Gateway {
  async handleCheckout(req: Request) {
    // ISSUE: Business logic in gateway
    const user = await fetch('http://user-service/users/' + req.userId);
    const inventory = await fetch('http://inventory-service/check', {
      body: JSON.stringify(req.items)
    });

    // ISSUE: Gateway doing validation
    if (!user.active) {
      return { error: 'User not active' };
    }

    // ISSUE: Gateway doing orchestration
    if (inventory.available) {
      const order = await fetch('http://order-service/orders', {
        method: 'POST',
        body: JSON.stringify(req)
      });

      // ISSUE: Gateway handling payment
      const payment = await fetch('http://payment-service/charge', {
        body: JSON.stringify({ orderId: order.id, amount: order.total })
      });

      return { order, payment };
    }
  }
}
EOF

# Create a simple architecture doc
cat > ARCHITECTURE.md << 'EOF'
# Architecture

## Services
- User Service: User management
- Order Service: Order processing
- Payment Service: Payment handling
- Inventory Service: Stock management
- Notification Service: Email/SMS
- Gateway: API routing

## Communication
Services communicate via HTTP REST calls.
EOF
```

## Steps

### 1. Analyze System Architecture

```bash
/wicked-engineering:arch --scope system
```

**Expected**: System-level analysis should identify:
- Service boundaries and responsibilities
- Coupling between services
- Communication patterns
- Data ownership issues

### 2. Analyze Order Service Module

```bash
/wicked-engineering:arch services/order --scope module
```

**Expected**: Module analysis should identify:
- Direct dependencies on other services
- Circular dependency with UserService
- Synchronous orchestration antipattern

### 3. Request Data Architecture Analysis

For systems with complex data relationships, spawn the data architect:

```bash
/wicked-engineering:arch --scope system
```

Then request data-specific analysis of the shared models.

## Expected Outcome

```markdown
## Architecture Analysis: Microservice System

### Overview
A microservice architecture with 6 services handling e-commerce functionality.
Current design has significant coupling issues that undermine microservice benefits.

### Current Architecture

#### Structure
```
services/
  user/          -> depends on: order, payment
  order/         -> depends on: user, inventory, payment, notification
  payment/       -> standalone
  inventory/     -> standalone
  notification/  -> standalone
gateway/         -> orchestrates all services
shared/
  models/        -> shared types (coupling source)
```

#### Key Components
| Component | Responsibility | Dependencies |
|-----------|----------------|--------------|
| UserService | User CRUD | OrderService, PaymentService |
| OrderService | Order lifecycle | UserService, InventoryService, PaymentService |
| Gateway | API routing | All services |

#### Patterns Used
- Shared kernel: Common models in shared/ (causing coupling)
- Synchronous orchestration: HTTP calls for all service interaction
- Distributed monolith: Services tightly coupled via direct calls

### Assessment

#### Concerns

##### Critical: Circular Dependencies
- **UserService <-> OrderService** - User imports Order, Order imports User
- **Impact**: Cannot deploy independently, shared failure modes
- **Evidence**: `services/user/index.ts:3` imports OrderService

##### Critical: Synchronous Orchestration
- **Order creation** performs 5+ synchronous service calls
- **Impact**: Single slow/failed service fails entire operation
- **Evidence**: `services/order/index.ts:15-35` - sequential await chain

##### High: Gateway Business Logic
- **Gateway performs validation and orchestration**
- **Impact**: Gateway becomes bottleneck, logic duplication
- **Evidence**: `gateway/index.ts:10-25` - user validation in gateway

##### High: Shared Data Model
- **User model contains Order and Payment data**
- **Impact**: Changes require coordinated deployments
- **Evidence**: `shared/models/user.ts:7-12` - Order[] in User interface

##### Medium: Anemic Services
- **InventoryService and PaymentService have no domain logic**
- **Impact**: Logic scattered across callers instead of domain owner

### Recommendations

#### Quick Wins
1. **Remove circular imports** - Use interfaces/events instead of direct service imports
2. **Move gateway logic to services** - Gateway should only route, not validate

#### Strategic Changes

##### 1. Introduce Event-Driven Communication
Replace synchronous calls with events for non-critical paths:

```
Order Created -> Event Bus
  -> Notification Service (async)
  -> Analytics Service (async)
  -> Inventory Service (async if eventual consistency OK)
```

##### 2. Define Clear Service Boundaries
| Service | Owns | Receives Events | Publishes Events |
|---------|------|-----------------|------------------|
| User | User data | OrderCompleted | UserCreated, UserDeleted |
| Order | Order data | UserDeleted | OrderCreated, OrderShipped |
| Payment | Payment data | OrderCreated | PaymentCompleted |

##### 3. Implement Saga Pattern for Order Creation
Replace synchronous orchestration with saga:
```
1. CreateOrder (Order Service)
2. ReserveStock (Inventory) - compensate: ReleaseStock
3. ProcessPayment (Payment) - compensate: Refund
4. ConfirmOrder (Order)
```

##### 4. Split Shared Models
- Each service owns its model
- Use anti-corruption layer for cross-service data
- Share only IDs/references, not full objects

### Trade-offs
| Decision | Pros | Cons |
|----------|------|------|
| Event-driven | Loose coupling, resilience | Eventual consistency, debugging complexity |
| Saga pattern | Reliable distributed transactions | Implementation complexity |
| Service-owned models | Independent deployment | Data duplication |
```

## Success Criteria

- [ ] Circular dependencies correctly identified
- [ ] Synchronous orchestration flagged as antipattern
- [ ] Gateway business logic identified as concern
- [ ] Shared model coupling explained
- [ ] Service boundaries evaluated
- [ ] Event-driven architecture recommended
- [ ] Saga pattern suggested for order flow
- [ ] Trade-offs clearly articulated
- [ ] Recommendations prioritized (quick wins vs strategic)

## Value Demonstrated

**Problem solved**: Architecture reviews are often informal and miss systemic issues. Problems compound until the system is too coupled to change safely.

**Real-world value**:
- **Catch coupling early**: Circular dependencies prevent independent deployment
- **Identify antipatterns**: Synchronous orchestration causes cascading failures
- **Guide evolution**: Clear path from current state to target architecture
- **Enable decisions**: Trade-offs help team choose appropriate solutions

This replaces architecture that evolves accidentally into a "distributed monolith" with intentional design decisions. The analysis provides concrete evidence (file:line references) rather than vague concerns.
