# Component Anti-Patterns: Circular Dependencies

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

