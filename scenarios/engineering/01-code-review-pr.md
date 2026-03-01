---
name: code-review-pr
title: Pull Request Code Review
description: Comprehensive code review of a feature branch before merging
type: review
difficulty: basic
estimated_minutes: 10
---

# Pull Request Code Review

This scenario demonstrates using wicked-engineering to perform a thorough code review on a feature branch, catching issues before they reach main.

## Setup

Create a project with existing code and a new feature with common issues:

```bash
# Create test project
mkdir -p ~/test-wicked-engineering/review-test
cd ~/test-wicked-engineering/review-test
git init

# Create existing user service (good patterns)
mkdir -p src/services
cat > src/services/userService.ts << 'EOF'
import { Database } from '../db';
import { NotFoundError } from '../errors';

export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: Date;
}

export class UserService {
  constructor(private db: Database) {}

  async findById(id: string): Promise<User> {
    const user = await this.db.users.findUnique({ where: { id } });
    if (!user) {
      throw new NotFoundError(`User ${id} not found`);
    }
    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    return this.db.users.findUnique({ where: { email } });
  }

  async update(id: string, data: Partial<User>): Promise<User> {
    const user = await this.findById(id);
    return this.db.users.update({
      where: { id },
      data: { ...data, updatedAt: new Date() }
    });
  }
}
EOF

# Commit initial code
git add -A
git commit -m "Initial user service"

# Create feature branch with code that needs review
git checkout -b feature/add-order-service

# Create order service with intentional issues
cat > src/services/orderService.ts << 'EOF'
import { Database } from '../db';

export class OrderService {
  db: Database;  // Issue: should be private

  constructor(db: Database) {
    this.db = db;
  }

  // Issue: No input validation
  async createOrder(userId: string, items: any[], total: number) {
    // Issue: No null check on user lookup
    const user = await this.db.users.findUnique({ where: { id: userId } });

    // Issue: Using any[] type
    const order = await this.db.orders.create({
      data: {
        userId: user.id,  // Will throw if user is null
        items: JSON.stringify(items),
        total: total,
        status: 'pending',
        createdAt: new Date()
      }
    });

    return order;
  }

  // Issue: N+1 query pattern
  async getOrdersWithItems(userId: string) {
    const orders = await this.db.orders.findMany({ where: { userId } });

    for (const order of orders) {
      // N+1: Separate query for each order
      const items = await this.db.orderItems.findMany({
        where: { orderId: order.id }
      });
      order.items = items;
    }

    return orders;
  }

  // Issue: No error handling for external call
  async processPayment(orderId: string, paymentInfo: any) {
    const order = await this.db.orders.findUnique({ where: { id: orderId } });

    // Issue: Direct external API call without error handling
    const response = await fetch('https://payment-api.example.com/charge', {
      method: 'POST',
      body: JSON.stringify({
        amount: order.total,
        ...paymentInfo  // Issue: Spreading unknown input to external API
      })
    });

    // Issue: No response validation
    const result = await response.json();

    await this.db.orders.update({
      where: { id: orderId },
      data: { status: 'paid', paymentId: result.id }
    });

    return result;
  }
}
EOF

# Stage the changes
git add -A
```

## Steps

### 1. Review Uncommitted Changes

```bash
/wicked-engineering:review
```

**Expected**: Without specifying a path, the review should detect uncommitted changes and focus on `src/services/orderService.ts`.

### 2. Compare With Established Patterns

The review should note that `orderService.ts` deviates from patterns in the existing `userService.ts`:
- UserService uses `private` for db field
- UserService throws NotFoundError for missing entities
- UserService has proper TypeScript types

### 3. Request Security-Focused Analysis

```bash
/wicked-engineering:review src/services/orderService.ts --focus security
```

**Expected**: Security review should flag:
- Spreading unknown input to external API (`...paymentInfo`)
- No input validation on `createOrder`
- External API call without proper error handling

### 4. Request Performance Analysis

```bash
/wicked-engineering:review src/services/orderService.ts --focus performance
```

**Expected**: Performance review should identify:
- N+1 query pattern in `getOrdersWithItems`
- Suggestion to use include/join or batch query

## Expected Outcome

```markdown
## Code Review: src/services/orderService.ts

### Summary
**Needs Work** - Several issues found that should be addressed before merge.

### Strengths
- Follows existing file organization pattern
- Methods have clear single responsibilities
- Uses dependency injection for database

### Issues Found

#### Critical
- **Null reference risk** in `createOrder:14` - User lookup result not checked before accessing `.id`
- **Security vulnerability** in `processPayment:42` - Spreading untrusted input to external API

#### Suggestions
- **Use `private` modifier** for `db` field - Matches established pattern in UserService
- **Replace `any[]` type** in `createOrder` - Define `OrderItem` interface
- **Fix N+1 query** in `getOrdersWithItems` - Use include or batch query
- **Add error handling** for payment API - Wrap in try/catch, validate response

### Recommendations
1. Add null check: `if (!user) throw new NotFoundError(...)`
2. Define explicit types for items and paymentInfo
3. Refactor getOrdersWithItems to use single query with include
4. Wrap payment API call in try/catch with proper error handling
5. Validate payment API response before using result.id
```

## Success Criteria

- [ ] Review identifies uncommitted changes automatically
- [ ] Critical issues (null reference, security) are flagged as Critical
- [ ] Pattern deviations from existing code are noted
- [ ] N+1 query pattern is identified in performance review
- [ ] Security focus catches untrusted input issues
- [ ] Recommendations are actionable with specific file locations
- [ ] Review compares against existing codebase patterns

## Value Demonstrated

**Problem solved**: Code reviews are often inconsistent and miss issues that cause production bugs. Reviewers get fatigued and focus on style over substance.

**Real-world value**:
- **Catch bugs before merge**: Null reference would cause runtime crash
- **Security awareness**: Untrusted input spreading is a common vulnerability
- **Performance issues**: N+1 queries cause slow page loads
- **Pattern consistency**: Maintains codebase quality over time

This replaces ad-hoc reviews where issues slip through, leading to post-merge fixes, production incidents, and accumulated technical debt. The senior engineering perspective catches issues that junior reviewers might miss.
