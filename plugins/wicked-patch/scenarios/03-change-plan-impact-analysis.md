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

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public Double getPrice() { return price; }
    public void setPrice(Double price) { this.price = price; }
    public Integer getStock() { return stock; }
    public void setStock(Integer stock) { this.stock = stock; }
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
/wicked-patch:plan "models/Product.java::Product" --change add_field
```

**Expected**: A PROPAGATION PLAN showing Product.java as the source, direct impacts listing entity fields, and a LOW risk assessment (adding a field is non-breaking).

### 3. Plan: Rename a field

Preview the impact of renaming "stock" to "availableQuantity":

```bash
/wicked-patch:plan "models/Product.java::Product" --change rename_field
```

**Expected**: A PROPAGATION PLAN showing the source symbol and risk assessment. Risk should be MEDIUM or higher (may be HIGH if the graph has no internal references, triggering the no_internal_refs warning path). Cross-file impacts depend on whether the symbol graph resolved method-level references.

### 4. Plan: Remove a field

See what would break if we removed the "price" field:

```bash
/wicked-patch:plan "models/Product.java::Product" --change remove_field
```

**Expected**: A PROPAGATION PLAN with risk level HIGH. The risk assessment should flag that removal is a breaking change. If no internal references to 'price' are found in the graph, the plan includes a WARNING about no_internal_refs.

### 5. Compare risk levels

Review the three plans conceptually. The key insight is:
- **Add field**: LOW risk (non-breaking, additive change)
- **Rename field**: MEDIUM or HIGH risk (HIGH when no internal references found in graph)
- **Remove field**: HIGH risk (always HIGH, breaking change flagged)

## Expected Outcome

After each plan step, you should see a PROPAGATION PLAN block:
```
============================================================
PROPAGATION PLAN
============================================================

Source: Product
  Type: entity
  File: .../Product.java
  Line: N

Direct Impacts (N):
  - symbolName (type) @ filename.java
  ...

Upstream Impacts (N):
  ...

Downstream Impacts (N):
  ...

------------------------------------------------------------
Risk Assessment:
  Risk level: LOW|MEDIUM|HIGH
  Confidence: LOW|MEDIUM|HIGH
  Breaking change: YES|NO
  Test coverage: GOOD|NONE (N test references found)
------------------------------------------------------------
Total: N symbols in N files
============================================================
```

The risk levels should show increasing severity:
1. **add_field** -> LOW risk (non-breaking)
2. **rename_field** -> MEDIUM or HIGH risk (depends on graph reference resolution)
3. **remove_field** -> HIGH risk (always HIGH, marks breaking change: YES)

## Success Criteria

- [ ] Plan command executed without applying any changes
- [ ] Add-field plan showed Product.java as source with risk assessment
- [ ] Rename plan showed risk assessment (MEDIUM or HIGH)
- [ ] Remove plan flagged HIGH risk level with breaking change: YES
- [ ] Risk levels correctly ordered (add LOW < rename MEDIUM/HIGH <= remove HIGH)
- [ ] No files were modified during planning (read-only operation)
- [ ] Each plan included confidence level in risk assessment

## Value Demonstrated

**Real-world problem**: Developers make changes blindly, discovering breaking impacts only after deployment. Refactorings that seem safe cause cascading failures in production.

**wicked-patch solution**: Dry-run planning shows the full blast radius BEFORE making changes. Categorizes risk levels and identifies hidden dependencies.

**Time saved**: 30-60 minutes of impact analysis per change -> 1 minute (automatic analysis)

**Risk reduced**: Prevents production incidents by surfacing breaking changes during planning, not after deployment.
