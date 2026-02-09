---
name: change-plan-impact-analysis
title: Impact Analysis with Change Planning
description: Preview change impact before making modifications using dry-run planning
type: safety
difficulty: basic
estimated_minutes: 5
---

# Impact Analysis with Change Planning

This scenario demonstrates wicked-patch's safety mechanism: previewing what WOULD be affected by a change before actually making it. Essential for high-risk refactorings or production codebases.

## Setup

Create a realistic e-commerce system with interconnected components:

```bash
# Create project structure
mkdir -p /tmp/wicked-patch-plan/{models,services,controllers,tests}
cd /tmp/wicked-patch-plan

# Product model
cat > models/Product.java << 'EOF'
package com.shop.models;

public class Product {
    private Long id;
    private String name;
    private Double price;
    private Integer stock;

    // Constructor, getters, setters omitted for brevity
}
EOF

# Inventory service
cat > services/InventoryService.java << 'EOF'
package com.shop.services;

import com.shop.models.Product;

public class InventoryService {
    public void updateStock(Product product, int quantity) {
        int newStock = product.getStock() + quantity;
        product.setStock(newStock);
    }

    public boolean isAvailable(Product product) {
        return product.getStock() > 0;
    }

    public void reserveStock(Product product, int quantity) {
        if (product.getStock() < quantity) {
            throw new IllegalStateException("Insufficient stock");
        }
        product.setStock(product.getStock() - quantity);
    }
}
EOF

# Order controller
cat > controllers/OrderController.java << 'EOF'
package com.shop.controllers;

import com.shop.models.Product;
import com.shop.services.InventoryService;

public class OrderController {
    private InventoryService inventoryService;

    public void placeOrder(Product product, int quantity) {
        if (!inventoryService.isAvailable(product)) {
            throw new RuntimeException("Product out of stock");
        }
        inventoryService.reserveStock(product, quantity);
    }
}
EOF

# Test file
cat > tests/InventoryTest.java << 'EOF'
package com.shop.tests;

import com.shop.models.Product;

public class InventoryTest {
    public void testStockUpdate() {
        Product product = new Product();
        product.setStock(10);
        assertEquals(10, product.getStock());
    }

    public void testOutOfStock() {
        Product product = new Product();
        product.setStock(0);
        assertFalse(product.getStock() > 0);
    }
}
EOF

echo "E-commerce project created at /tmp/wicked-patch-plan"
```

## Steps

### 1. Index the codebase

Build the symbol graph to understand dependencies:

```bash
/wicked-search:index /tmp/wicked-patch-plan
```

### 2. Plan: Add a new field

See what would be affected by adding a "reserved" field to track reserved inventory:

```bash
/wicked-patch:plan --entity Product --add-field reserved:Integer --project /tmp/wicked-patch-plan
```

### 3. Plan: Rename a field

Preview the impact of renaming "stock" to "availableQuantity":

```bash
/wicked-patch:plan --symbol stock --new-name availableQuantity --scope Product --project /tmp/wicked-patch-plan
```

### 4. Plan: Remove a field

See what would break if we removed the "price" field:

```bash
/wicked-patch:plan --entity Product --remove-field price --project /tmp/wicked-patch-plan
```

### 5. Compare risk levels

Review the three plans side-by-side to decide which changes are safe:

```bash
cat /tmp/wicked-patch-plan/.patches/plans/add-reserved-plan.txt
cat /tmp/wicked-patch-plan/.patches/plans/rename-stock-plan.txt
cat /tmp/wicked-patch-plan/.patches/plans/remove-price-plan.txt
```

## Expected Outcome

After step 2 (plan add-field), you should see:
```
Change Plan: Add field 'reserved' to Product

Impact Analysis:
├─ Direct changes:
│  └─ models/Product.java (1 file)
│     - Add field declaration: private Integer reserved;
│     - Add getter: getReserved()
│     - Add setter: setReserved(Integer reserved)
│
└─ Dependent code (MAY need updates):
   ├─ services/InventoryService.java
   │  - No automatic changes needed
   │  - Manual review: reserveStock() might benefit from tracking
   └─ tests/InventoryTest.java
      - No automatic changes needed
      - Manual review: Add tests for reserved quantity

Files affected: 1 direct, 2 indirect
Risk level: LOW
Confidence: HIGH (new field, no breaking changes)
```

After step 3 (plan rename), you should see:
```
Change Plan: Rename 'stock' → 'availableQuantity' (scope: Product)

Impact Analysis:
├─ Direct changes (18 references):
│  ├─ models/Product.java (3 references)
│  │  - Line 6: field declaration
│  │  - Line 10: getter method name
│  │  - Line 11: setter method name
│  │
│  ├─ services/InventoryService.java (8 references)
│  │  - Line 6, 7: updateStock method calls
│  │  - Line 11: isAvailable condition
│  │  - Line 15, 16, 17: reserveStock logic
│  │
│  ├─ controllers/OrderController.java (2 references)
│  │  - Line 9: availability check (indirect via service)
│  │
│  └─ tests/InventoryTest.java (5 references)
│     - Line 7, 8, 13, 14: test assertions
│
└─ Risk assessment:
   - Breaking change: YES (affects public API)
   - Cross-module impact: HIGH (3 modules depend on this field)
   - Test coverage: GOOD (5 test references found)

Files affected: 4 files, 18 total references
Risk level: MEDIUM
Confidence: HIGH (complete symbol graph available)

Recommendation: Execute during maintenance window
```

After step 4 (plan remove), you should see:
```
Change Plan: Remove field 'price' from Product

Impact Analysis:
├─ Direct changes:
│  └─ models/Product.java
│     - Remove field: private Double price;
│     - Remove getter: getPrice()
│     - Remove setter: setPrice(Double price)
│
└─ BREAKING CHANGES DETECTED:
   ⚠️  No references found in indexed code
   ⚠️  Field exists but appears unused
   ⚠️  Cannot verify external dependencies (APIs, serialization)

Files affected: 1 file
Risk level: HIGH (external dependencies unknown)
Confidence: MEDIUM (may have external usages)

⚠️  WARNING: This field may be used by:
   - REST API clients (JSON serialization)
   - Database mappings (ORM annotations)
   - Report generation tools
   - External integrations

Recommendation: Audit API contracts and database schema before proceeding
```

After step 5 (compare), you should see:
```
Risk Summary:

1. Add 'reserved' field: LOW risk
   ✓ Safe to proceed immediately
   - No breaking changes
   - Optional enhancement

2. Rename 'stock' → 'availableQuantity': MEDIUM risk
   ⚠  Requires coordination
   - 18 references across 4 files
   - Breaking API change
   - Good test coverage (5 tests)

3. Remove 'price' field: HIGH risk
   ⛔ Do NOT proceed without investigation
   - External dependencies unknown
   - May break API contracts
   - Needs database migration review
```

## Success Criteria

- [ ] Plan command executed without applying any changes
- [ ] Add-field plan identified direct changes (Product.java only)
- [ ] Rename plan counted all 18 references across 4 files
- [ ] Remove plan flagged HIGH risk due to external dependencies
- [ ] Risk levels correctly assessed (LOW/MEDIUM/HIGH)
- [ ] No files were modified during planning (dry-run mode)
- [ ] Plan outputs saved to `.patches/plans/` directory
- [ ] Confidence levels provided for each analysis

## Value Demonstrated

**Real-world problem**: Developers make changes blindly, discovering breaking impacts only after deployment. Refactorings that seem safe cause cascading failures in production.

**wicked-patch solution**: Dry-run planning shows the full blast radius BEFORE making changes. Categorizes risk levels and identifies hidden dependencies.

**Time saved**: 30-60 minutes of impact analysis per change → 1 minute (automatic analysis)

**Risk reduced**: Prevents production incidents by surfacing breaking changes during planning, not after deployment.

**Real-world use cases**:
- Pre-deployment impact analysis for refactorings
- Evaluating technical debt cleanup efforts
- Assessing risk before major version upgrades
- Code review preparation (share plan outputs with team)
- Compliance and audit trails (document what would change)
