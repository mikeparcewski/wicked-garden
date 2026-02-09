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
/wicked-patch:plan --symbol status --new-name orderStatus --scope Order --project /tmp/wicked-patch-rename
```

### 3. Execute the rename

Rename status to orderStatus across all languages:

```bash
/wicked-patch:rename --symbol status --new-name orderStatus --scope Order --project /tmp/wicked-patch-rename
```

### 4. Review generated patches

Check what changes were detected:

```bash
ls -la /tmp/wicked-patch-rename/.patches/
cat /tmp/wicked-patch-rename/.patches/rename-status-*.json
```

### 5. Apply the patches

Update all files with the new symbol name:

```bash
/wicked-patch:apply --patches /tmp/wicked-patch-rename/.patches/ --project /tmp/wicked-patch-rename
```

### 6. Verify cross-language consistency

Check that all references were updated:

```bash
# Java - should use orderStatus everywhere
grep -n "orderStatus" /tmp/wicked-patch-rename/backend/src/Order.java

# TypeScript - interface and all usages
grep -n "orderStatus" /tmp/wicked-patch-rename/frontend/src/order.ts

# Python - test assertions
grep -n "order_status" /tmp/wicked-patch-rename/tests/test_order.py

# Verify old name is gone
! grep -r "\.status" /tmp/wicked-patch-rename/ --include="*.java" --include="*.ts" --include="*.py"
```

## Expected Outcome

After step 2 (plan), you should see:
```
Rename Plan: status → orderStatus (scope: Order)

Impact Analysis:
- backend/src/Order.java: 7 references
  - Line 5: field declaration
  - Line 8: getter return
  - Line 12: setter parameter
  - Line 16: comparison in isPending()
  - Line 20, 21: validation logic

- frontend/src/order.ts: 6 references
  - Line 3: interface property
  - Line 7, 11: filter conditions
  - Line 15: property assignment

- tests/test_order.py: 5 references
  - Line 7, 8, 12, 13, 18: test assertions and assignments

Total: 18 references across 3 files, 3 languages
Risk: MEDIUM (references in conditionals require testing)
```

After step 3 (rename), you should see:
```
Generated patches:
- rename-status-java.json (7 changes in Order.java)
- rename-status-typescript.json (6 changes in order.ts)
- rename-status-python.json (5 changes in test_order.py)

Language-specific transformations applied:
- Java: status → orderStatus (camelCase preserved)
- TypeScript: status → orderStatus (camelCase preserved)
- Python: status → order_status (snake_case conversion)

Patches saved to: /tmp/wicked-patch-rename/.patches/
```

After step 5 (apply), files should show:

**Java Order.java**:
```java
private String orderStatus;

public String getOrderStatus() {
    return orderStatus;
}

public boolean isPending() {
    return "PENDING".equals(orderStatus);
}
```

**TypeScript order.ts**:
```typescript
export interface Order {
  id: number;
  orderStatus: string;
  amount: number;
}
// ... all references updated to orderStatus
```

**Python test_order.py**:
```python
order.order_status = "PENDING"
self.assertEqual(order.order_status, "PENDING")
```

## Success Criteria

- [ ] Symbol graph correctly identified all references across 3 languages
- [ ] Plan showed accurate count (18 references in 3 files)
- [ ] Java uses camelCase: `orderStatus`
- [ ] TypeScript uses camelCase: `orderStatus`
- [ ] Python uses snake_case: `order_status`
- [ ] No occurrences of old name `.status` remain in code
- [ ] Getter/setter method names updated (getOrderStatus, setOrderStatus)
- [ ] All comparison and assignment operations preserved correctly

## Value Demonstrated

**Real-world problem**: Renaming a field in one language doesn't update frontend/backend/test code automatically. Developers must manually search across codebases, risking missed references that cause runtime errors.

**wicked-patch solution**: Automatically finds and renames ALL references across multiple languages, respecting each language's naming conventions (camelCase vs snake_case).

**Time saved**: 20-30 minutes per rename (manual find/replace across repos, grep verification, testing) → 2 minutes (one command)

**Risk reduced**: Eliminates missed references (e.g., renaming in backend but forgetting frontend, causing API contract mismatches). Prevents production bugs from stale field names.

**Real-world use cases**:
- Refactoring legacy code with unclear naming
- Aligning frontend/backend field names during API redesign
- Standardizing terminology across team codebases
