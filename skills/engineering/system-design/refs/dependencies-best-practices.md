# Dependency Management Guide: Best Practices

## Best Practices

### 1. Minimize Dependencies

Each component should have as few dependencies as possible.

```typescript
// Bad: Many dependencies
class UserService {
  constructor(
    private dep1,
    private dep2,
    private dep3,
    private dep4,
    private dep5,
    private dep6
  ) {}
}

// Good: Fewer focused dependencies
class UserService {
  constructor(
    private userRepo: UserRepository,
    private eventBus: EventBus
  ) {}
}
```

### 2. Depend on Abstractions

```typescript
// Good: Depend on interface
interface Cache {
  get(key: string): Promise<any>;
  set(key: string, value: any): Promise<void>;
}

class UserService {
  constructor(private cache: Cache) {}
}

// Can swap implementations
const redisCache: Cache = new RedisCache();
const memoryCache: Cache = new MemoryCache();
```

### 3. Use Dependency Injection Container

```typescript
// Container setup
container.register('Database', () => new PostgresDatabase(config));
container.register('Cache', () => new RedisCache(config));
container.register('UserRepository', () => new UserRepository(
  container.resolve('Database')
));
container.register('UserService', () => new UserService(
  container.resolve('UserRepository'),
  container.resolve('Cache')
));

// Usage
const userService = container.resolve<UserService>('UserService');
```

### 4. Document Dependencies

```typescript
/**
 * UserService handles user management operations.
 *
 * Dependencies:
 * - UserRepository: Data access for users
 * - EmailService: Sends user notifications
 * - EventBus: Publishes domain events
 */
class UserService {
  constructor(
    private userRepo: UserRepository,
    private emailService: EmailService,
    private eventBus: EventBus
  ) {}
}
```

### 5. Test with Mocks

```typescript
describe('UserService', () => {
  it('should create user', async () => {
    // Mock dependencies
    const mockRepo: UserRepository = {
      save: jest.fn().mockResolvedValue({ id: '123' }),
      findById: jest.fn(),
      findByEmail: jest.fn()
    };

    const mockEmail: EmailService = {
      sendWelcome: jest.fn().mockResolvedValue(undefined)
    };

    // Test with mocks
    const service = new UserService(mockRepo, mockEmail);
    const user = await service.createUser({ email: 'test@example.com' });

    expect(mockRepo.save).toHaveBeenCalled();
    expect(mockEmail.sendWelcome).toHaveBeenCalledWith('test@example.com');
  });
});
```

### 6. Manage Temporal Dependencies

```typescript
// Lifecycle management
class Application {
  async start() {
    // Start in correct order
    await this.database.connect();
    await this.cache.connect();
    await this.messageQueue.connect();

    // Initialize services after infrastructure
    this.userService = new UserService(this.database, this.cache);
    this.orderService = new OrderService(this.database, this.messageQueue);

    // Start server last
    await this.server.listen(3000);
  }

  async stop() {
    // Stop in reverse order
    await this.server.close();

    await this.orderService.shutdown();
    await this.userService.shutdown();

    await this.messageQueue.disconnect();
    await this.cache.disconnect();
    await this.database.disconnect();
  }
}
```

### 7. Limit Dependency Depth

```typescript
// Bad: Deep dependency chain
A → B → C → D → E → F

// Good: Flatter structure
A → B
A → C
A → D
```

### 8. Package by Component

Organize code by component, not layer:

```
# Bad: Package by layer
src/
  controllers/
  services/
  repositories/

# Good: Package by component
src/
  users/
    user.controller.ts
    user.service.ts
    user.repository.ts
  orders/
    order.controller.ts
    order.service.ts
    order.repository.ts
```

### 9. Use Dependency Graphs

Visualize and analyze dependencies:

```bash
# Generate dependency graph
npx madge --image graph.png src/

# Find circular dependencies
npx madge --circular src/

# Check dependency violations
npx dependency-cruiser src/
```

### 10. Version External Dependencies

```json
{
  "dependencies": {
    "express": "4.18.2",      // Exact version
    "lodash": "^4.17.21",      // Compatible version
    "react": "~18.2.0"         // Patch updates only
  }
}
```

## Dependency Health Metrics

### Coupling

```typescript
// Low coupling (good)
class A {
  constructor(private b: InterfaceB) {}
}

// High coupling (bad)
class A {
  constructor(
    private b: B,
    private c: C,
    private d: D,
    private e: E,
    private f: F
  ) {}
}
```

### Cohesion

```typescript
// High cohesion (good) - related functionality together
class UserService {
  createUser() {}
  updateUser() {}
  deleteUser() {}
}

// Low cohesion (bad) - unrelated functionality
class UtilityService {
  createUser() {}
  sendEmail() {}
  calculateTax() {}
  generateReport() {}
}
```

### Stability

```
Stability = Efferent Coupling / (Efferent + Afferent Coupling)

0 = Most stable (many dependents, few dependencies)
1 = Most unstable (few dependents, many dependencies)
```
