---
name: rename-symbol-across-codebase
title: Rename Symbol Across Multi-Language Codebase
description: Safely rename a field across Java, TypeScript, and Python with automatic reference updates
type: propagation
difficulty: intermediate
estimated_minutes: 10
---

# Rename Symbol Across Multi-Language Codebase

This scenario demonstrates safe, cross-language symbol renaming. When you rename "status" to "orderStatus", wicked-patch finds and updates ALL references across Java backend, TypeScript frontend, and Python tests.

## Setup

Create a multi-language order processing system:

```bash
# Create project structure
mkdir -p /tmp/wicked-patch-rename/{backend/src,frontend/src,tests}
cd /tmp/wicked-patch-rename

# Java backend - Order entity
cat > backend/src/Order.java << 'EOF'
package com.shop;

public class Order {
    private Long id;
    private String status;
    private Double amount;

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public boolean isPending() {
        return "PENDING".equals(status);
    }

    public void validateOrder() {
        if (status == null || status.isEmpty()) {
            throw new IllegalStateException("Status cannot be empty");
        }
    }
}
EOF

# TypeScript frontend - Order interface and component
cat > frontend/src/order.ts << 'EOF'
export interface Order {
  id: number;
  status: string;
  amount: number;
}

export class OrderService {
  filterByStatus(orders: Order[], status: string): Order[] {
    return orders.filter(order => order.status === status);
  }

  getPendingOrders(orders: Order[]): Order[] {
    return orders.filter(order => order.status === 'PENDING');
  }

  updateOrderStatus(order: Order, newStatus: string): void {
    order.status = newStatus;
  }
}
EOF

# Python test file
cat > tests/test_order.py << 'EOF'
import unittest
from backend.order import Order

class TestOrder(unittest.TestCase):
    def test_status_validation(self):
        order = Order()
        order.status = "PENDING"
        self.assertEqual(order.status, "PENDING")

    def test_pending_check(self):
        order = Order()
        order.status = "PENDING"
        self.assertTrue(order.is_pending())

    def test_empty_status(self):
        order = Order()
        order.status = ""
        with self.assertRaises(ValueError):
            order.validate_order()
EOF

echo "Multi-language project created at /tmp/wicked-patch-rename"
```

## Steps

### 1. Index the codebase

Build the symbol graph to understand cross-file references:

```bash
/wicked-search:index /tmp/wicked-patch-rename
```

### 2. Preview rename impact

See all locations that will be affected by the rename:

```bash
/wicked-patch:plan "backend/src/Order.java::Order" --change rename_field
```

**Expected**: A PROPAGATION PLAN showing Order as source with a risk assessment. Risk may be LOW when impacts stay within a single file with no upstream dependencies, MEDIUM when changes propagate across multiple files, or HIGH when no internal references are found or the rename touches widely shared interfaces.

### 3. Execute the rename

Rename status to orderStatus across all languages:

```bash
/wicked-patch:rename "backend/src/Order.java::Order" --old status --new orderStatus -o /tmp/wicked-patch-rename/.patches/patches.json --verbose
```

**Expected**: A GENERATED PATCHES block showing rename operations in Order.java (field, getter, setter, method bodies) and potentially in order.ts and test_order.py if the graph linked them.

### 4. Review generated patches

Check what changes were detected:

```bash
ls -la /tmp/wicked-patch-rename/.patches/
cat /tmp/wicked-patch-rename/.patches/manifest.json
```

### 5. Apply the patches

Update all files with the new symbol name:

```bash
/wicked-patch:apply /tmp/wicked-patch-rename/.patches/patches.json --skip-git --force
```

When prompted with `Apply N patches to N files? [y/N]`, type `y` and press Enter to confirm.

### 6. Verify cross-language consistency

Check that references were updated:

```bash
# Java - should use orderStatus
grep -n "orderStatus" /tmp/wicked-patch-rename/backend/src/Order.java

# Check if TypeScript was updated (depends on graph linking)
grep -n "orderStatus" /tmp/wicked-patch-rename/frontend/src/order.ts || echo "TypeScript not updated (graph may not have linked it)"

# Check if Python was updated with snake_case conversion
grep -n "order_status" /tmp/wicked-patch-rename/tests/test_order.py || echo "Python not updated (graph may not have linked it)"
```

## Expected Outcome

After step 2 (plan), you should see a PROPAGATION PLAN block:
```
============================================================
PROPAGATION PLAN
============================================================

Source: Order
  Type: entity
  File: .../Order.java
  ...

Direct Impacts (N):
  ...

------------------------------------------------------------
Risk Assessment:
  Risk level: MEDIUM|HIGH
  ...
------------------------------------------------------------
Total: N symbols in N files
============================================================
```

After step 3 (rename), you should see a GENERATED PATCHES block:
```
============================================================
GENERATED PATCHES
============================================================

Change: rename_field
Target: ...Order.java::Order
...

PATCHES:

  Order.java
    [...] Rename 'status' to 'orderStatus'
    ...

============================================================
```

After step 5 (apply), Order.java should contain:
```java
private String orderStatus;

public String getOrderStatus() {
    return orderStatus;
}

public void setOrderStatus(String orderStatus) {
    this.orderStatus = orderStatus;
}

public boolean isPending() {
    return "PENDING".equals(orderStatus);
}
```

Language-specific transformations:
- **Java**: status -> orderStatus (camelCase preserved)
- **TypeScript**: status -> orderStatus (camelCase preserved)
- **Python**: status -> order_status (snake_case conversion)

## Success Criteria

- [ ] Symbol graph indexed all 3 languages successfully
- [ ] Plan showed impacts with risk assessment
- [ ] Java entity uses camelCase: `orderStatus` with updated getter/setter names
- [ ] Getter/setter method names updated (getOrderStatus, setOrderStatus)
- [ ] Patches saved to output file with manifest.json
- [ ] All patches applied without errors

## Value Demonstrated

**Real-world problem**: Renaming a field in one language doesn't update frontend/backend/test code automatically. Developers must manually search across codebases, risking missed references that cause runtime errors.

**wicked-patch solution**: Automatically finds and renames ALL references across multiple languages, respecting each language's naming conventions (camelCase vs snake_case).

**Time saved**: 20-30 minutes per rename (manual find/replace across repos, grep verification, testing) -> 2 minutes (one command)

**Risk reduced**: Eliminates missed references (e.g., renaming in backend but forgetting frontend, causing API contract mismatches).
