---
name: systematic-debugging
title: Systematic Root Cause Analysis
description: Diagnose a production error using systematic debugging methodology
type: debugging
difficulty: intermediate
estimated_minutes: 12
---

# Systematic Root Cause Analysis

This scenario demonstrates using wicked-engineering to systematically diagnose a production error, trace its root cause, and develop a fix.

## Setup

Create a project with an intermittent bug that only occurs under certain conditions:

```bash
# Create test project
mkdir -p ~/test-wicked-engineering/debug-test
cd ~/test-wicked-engineering/debug-test

# Create the service with a subtle bug
mkdir -p src/services src/utils
cat > src/services/inventoryService.ts << 'EOF'
import { Database } from '../db';
import { Cache } from '../cache';
import { calculateDiscount } from '../utils/pricing';

export class InventoryService {
  constructor(
    private db: Database,
    private cache: Cache
  ) {}

  async getProductPrice(productId: string, userId?: string): Promise<number> {
    // Try cache first
    const cacheKey = `price:${productId}`;
    const cachedPrice = await this.cache.get(cacheKey);

    if (cachedPrice) {
      return this.applyUserDiscount(cachedPrice, userId);
    }

    // Fetch from database
    const product = await this.db.products.findUnique({
      where: { id: productId }
    });

    if (!product) {
      throw new Error(`Product ${productId} not found`);
    }

    // Cache for 5 minutes
    await this.cache.set(cacheKey, product.price, 300);

    return this.applyUserDiscount(product.price, userId);
  }

  private async applyUserDiscount(price: number, userId?: string): Promise<number> {
    if (!userId) {
      return price;
    }

    const user = await this.db.users.findUnique({
      where: { id: userId },
      include: { membership: true }
    });

    // BUG: user might be null but we access user.membership
    const discount = calculateDiscount(user.membership?.tier);

    return price * (1 - discount);
  }

  async reserveStock(productId: string, quantity: number): Promise<boolean> {
    const product = await this.db.products.findUnique({
      where: { id: productId }
    });

    if (!product || product.stock < quantity) {
      return false;
    }

    // BUG: Race condition - stock could change between check and update
    await this.db.products.update({
      where: { id: productId },
      data: { stock: product.stock - quantity }
    });

    // Invalidate price cache (stock affects pricing in some cases)
    await this.cache.delete(`price:${productId}`);

    return true;
  }
}
EOF

cat > src/utils/pricing.ts << 'EOF'
export type MembershipTier = 'bronze' | 'silver' | 'gold' | 'platinum';

const DISCOUNT_RATES: Record<MembershipTier, number> = {
  bronze: 0.05,
  silver: 0.10,
  gold: 0.15,
  platinum: 0.20
};

export function calculateDiscount(tier?: MembershipTier): number {
  if (!tier) {
    return 0;
  }

  return DISCOUNT_RATES[tier] ?? 0;
}
EOF

# Create error log sample
cat > error.log << 'EOF'
2024-01-15T14:23:45.123Z ERROR [InventoryService] TypeError: Cannot read properties of null (reading 'membership')
    at InventoryService.applyUserDiscount (src/services/inventoryService.ts:42)
    at InventoryService.getProductPrice (src/services/inventoryService.ts:26)
    at CheckoutController.calculateTotal (src/controllers/checkout.ts:34)
    Request: GET /api/cart/total?userId=usr_deleted_12345
    User-Agent: Mozilla/5.0...

2024-01-15T14:23:46.789Z ERROR [InventoryService] Negative stock detected
    Product: prod_abc123, Stock: -3
    at StockAuditJob.reconcile (src/jobs/stockAudit.ts:18)

2024-01-15T14:24:01.456Z ERROR [InventoryService] TypeError: Cannot read properties of null (reading 'membership')
    at InventoryService.applyUserDiscount (src/services/inventoryService.ts:42)
    at InventoryService.getProductPrice (src/services/inventoryService.ts:26)
    at WishlistService.getPricesForUser (src/services/wishlist.ts:22)
    Request: GET /api/wishlist/usr_guest_session
EOF
```

## Steps

### 1. Start Debug Session with Error Message

```bash
/wicked-engineering:debug "TypeError: Cannot read properties of null (reading 'membership') in InventoryService"
```

**Expected**: The debugger should:
1. Parse the error type and message
2. Read the stack trace from logs
3. Identify the file and line number
4. Read the relevant code
5. Form hypotheses about the root cause

### 2. Follow the Data Flow

The debugger agent should trace:
- Where does `userId` come from? (API request)
- What happens when userId is invalid? (User lookup returns null)
- Is null handled before accessing `.membership`? (No)

### 3. Identify Contributing Factors

```markdown
### Contributing Factors
1. **Deleted users**: User IDs from old sessions reference deleted accounts
2. **Guest sessions**: Guest users have placeholder IDs that don't exist
3. **Missing null check**: Code assumes user always exists if userId provided
```

### 4. Investigate Second Error

```bash
/wicked-engineering:debug "Negative stock detected for product"
```

**Expected**: The debugger should identify the race condition in `reserveStock`:
- Read-then-update pattern is not atomic
- Concurrent requests can both pass the stock check
- Both then decrement, causing negative stock

## Expected Outcome

```markdown
## Debug Analysis: TypeError in InventoryService

### Symptom
TypeError when accessing `.membership` on null value in applyUserDiscount

### Root Cause
The `applyUserDiscount` method assumes the user exists when `userId` is provided,
but the user lookup can return null for:
1. Deleted user accounts (historical session data)
2. Guest session placeholder IDs
3. Invalid/malformed user IDs

### Evidence
- `src/services/inventoryService.ts:42` - `user.membership?.tier` but `user` itself is null
- Error logs show requests with `userId=usr_deleted_*` and `userId=usr_guest_*`
- No null check between user lookup and property access

### Fix
Add null check before accessing user properties:

```typescript
private async applyUserDiscount(price: number, userId?: string): Promise<number> {
  if (!userId) {
    return price;
  }

  const user = await this.db.users.findUnique({
    where: { id: userId },
    include: { membership: true }
  });

  // Handle non-existent users gracefully
  if (!user) {
    return price; // No discount for invalid users
  }

  const discount = calculateDiscount(user.membership?.tier);
  return price * (1 - discount);
}
```

### Prevention
1. Add integration test with deleted user ID
2. Add test with guest session ID
3. Consider logging when invalid userId is provided for monitoring
```

---

```markdown
## Debug Analysis: Negative Stock Race Condition

### Symptom
Products showing negative stock values after concurrent purchases

### Root Cause
The `reserveStock` method uses a read-then-update pattern that is not atomic.
When two concurrent requests both pass the stock check, both decrement the
stock, potentially going negative.

### Evidence
- `src/services/inventoryService.ts:52-60` - Separate SELECT then UPDATE
- Stock check: `product.stock < quantity` passes for both requests
- Both requests then run: `stock = product.stock - quantity`
- If original stock was 2 and both want 2, result is -2

### Fix
Use atomic update with conditional:

```typescript
async reserveStock(productId: string, quantity: number): Promise<boolean> {
  // Atomic update only if sufficient stock
  const result = await this.db.products.updateMany({
    where: {
      id: productId,
      stock: { gte: quantity }  // Only update if enough stock
    },
    data: {
      stock: { decrement: quantity }
    }
  });

  if (result.count === 0) {
    return false;  // Not enough stock or product not found
  }

  await this.cache.delete(`price:${productId}`);
  return true;
}
```

### Prevention
1. Add load test for concurrent stock reservation
2. Add database constraint: `CHECK (stock >= 0)`
3. Consider using database transactions for multi-table updates
```

## Success Criteria

- [ ] Debugger parses error message and identifies file/line
- [ ] Stack trace is followed to understand call chain
- [ ] Data flow is traced (where userId comes from)
- [ ] Root cause correctly identified (missing null check)
- [ ] Multiple contributing factors identified (deleted users, guests)
- [ ] Fix provided with correct code
- [ ] Prevention recommendations included
- [ ] Race condition correctly diagnosed as separate issue
- [ ] Atomic update solution provided for race condition

## Value Demonstrated

**Problem solved**: Debugging intermittent production errors is time-consuming and often involves guesswork. Developers add logging, deploy, wait for reproduction, repeat.

**Real-world value**:
- **Systematic approach**: Follows structured methodology instead of random poking
- **Root cause focus**: Doesn't just fix the symptom, understands why it happens
- **Prevention mindset**: Recommends tests and constraints to prevent recurrence
- **Pattern recognition**: Identifies common issues like race conditions

This replaces hours of debugging with a structured 15-minute analysis. The systematic approach catches issues (like the race condition) that might be missed when focused on just the immediate error.
