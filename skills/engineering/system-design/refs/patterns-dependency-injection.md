# Component Design Patterns: Dependency Injection

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
