---
name: patch-save-and-apply
title: Team Review Workflow with Patch Save and Apply
description: Generate patches for review, save to version control, and apply after team approval
type: safety
difficulty: basic
estimated_minutes: 6
---

# Team Review Workflow with Patch Save and Apply

This scenario demonstrates the team collaboration workflow: generate patches, commit them to version control for review, and apply them only after approval. Essential for teams with code review processes or compliance requirements.

## Setup

Create a payment processing service that requires careful review:

```bash
# Create project structure
mkdir -p /tmp/wicked-patch-review/{models,services,config}
cd /tmp/wicked-patch-review

# Initialize git repo for version control
git init
git config user.email "dev@example.com"
git config user.name "Developer"

# Payment model
cat > models/Payment.java << 'EOF'
package com.payments.models;

import java.math.BigDecimal;

public class Payment {
    private Long id;
    private BigDecimal amount;
    private String currency;
    private String status;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public void setAmount(BigDecimal amount) {
        this.amount = amount;
    }

    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
EOF

# Payment service
cat > services/PaymentService.java << 'EOF'
package com.payments.services;

import com.payments.models.Payment;

public class PaymentService {
    public void processPayment(Payment payment) {
        validatePayment(payment);
        // Process payment logic
        payment.setStatus("COMPLETED");
    }

    private void validatePayment(Payment payment) {
        if (payment.getAmount() == null) {
            throw new IllegalArgumentException("Amount is required");
        }
        if (payment.getCurrency() == null) {
            throw new IllegalArgumentException("Currency is required");
        }
    }
}
EOF

# Commit initial state
git add .
git commit -m "Initial payment service setup"

echo "Payment service created at /tmp/wicked-patch-review"
```

## Steps

### 1. Index the codebase

Build the symbol graph for patch generation:

```bash
/wicked-search:index /tmp/wicked-patch-review
```

### 2. Generate patches with output flag

Add a "transactionId" field and save patches for review (do NOT apply):

```bash
/wicked-patch:add-field "models/Payment.java::Payment" --name transactionId --type String --required -o /tmp/wicked-patch-review/.patches/patches.json --verbose
```

### 3. Review the generated patches

Examine the patch files to understand what changes will be made:

```bash
# List generated patch files
ls -la /tmp/wicked-patch-review/.patches/

# View the patch metadata
cat /tmp/wicked-patch-review/.patches/manifest.json
```

**Expected**: manifest.json with change_type, target, files_affected, and patch_count.

### 4. Commit patches to version control

Save patches to git for team review:

```bash
cd /tmp/wicked-patch-review
git add .patches/
git commit -m "feat: add transactionId field to Payment entity

Generated patches for review.
Requires review before apply."

git log --oneline -n 2
```

### 5. (Simulate) Code review process

In a real workflow, team members would review the patch files in a pull request. For this scenario, we simulate approval:

```bash
# Create approval marker
echo "Reviewed-by: senior-dev@example.com" > /tmp/wicked-patch-review/.patches/APPROVED
echo "Date: $(date)" >> /tmp/wicked-patch-review/.patches/APPROVED
cat /tmp/wicked-patch-review/.patches/APPROVED
```

### 6. Apply approved patches

After approval, apply the patches to the codebase:

```bash
/wicked-patch:apply /tmp/wicked-patch-review/.patches/patches.json --skip-git --force
```

### 7. Verify changes and commit

Check that patches were applied correctly:

```bash
# Verify field was added
grep -A 5 "transactionId" /tmp/wicked-patch-review/models/Payment.java

# Commit the applied changes
cd /tmp/wicked-patch-review
git add models/ services/
git commit -m "apply: transactionId field patches

Applied patches from .patches/patches.json
Approved by: senior-dev"

git log --oneline -n 3
```

### 8. Archive applied patches

Move applied patches to archive for audit trail:

```bash
mkdir -p /tmp/wicked-patch-review/.patches/archive/
mv /tmp/wicked-patch-review/.patches/patches.json \
   /tmp/wicked-patch-review/.patches/manifest.json \
   /tmp/wicked-patch-review/.patches/archive/
ls -la /tmp/wicked-patch-review/.patches/archive/
```

## Expected Outcome

After step 2 (generate with -o), you should see:
```
============================================================
GENERATED PATCHES
============================================================

Change: add_field
Target: ...Payment.java::Payment
...

PATCHES:

  Payment.java
    [...] Add field 'transactionId' (String)
    [...] Add getter for 'transactionId'
    [...] Add setter for 'transactionId'

============================================================

Patches saved to /tmp/wicked-patch-review/.patches/patches.json
```

After step 6 (apply), Payment.java should contain:
```java
private String transactionId;

public String getTransactionId() {
    return transactionId;
}

public void setTransactionId(String transactionId) {
    this.transactionId = transactionId;
}
```

After step 7 (final commit), git log should show 3 commits:
```
g7h8i9j apply: transactionId field patches
a1b2c3d feat: add transactionId field to Payment entity
f4e5d6c Initial payment service setup
```

## Success Criteria

- [ ] Patches generated with -o flag without applying changes
- [ ] Files unchanged after patch generation (only .patches/ directory created)
- [ ] manifest.json contains metadata and file list
- [ ] Patches committed to git for review
- [ ] Apply command successfully applied all patches
- [ ] Payment.java has transactionId field with getter/setter
- [ ] Final git commit shows clean history of generate -> review -> apply
- [ ] Applied patches archived

## Value Demonstrated

**Real-world problem**: Direct code changes bypass review processes. In regulated industries or teams with strict compliance, changes must be reviewed before application.

**wicked-patch solution**: Separates patch generation from application. Patches are reviewable artifacts that can be versioned, approved, and audited.

**Compliance value**:
- Audit trail of all changes (git history of patch generation and application)
- Separation of duties (developer generates, senior engineer approves)
- Reviewable change artifacts (manifest.json shows complete impact)
- Rollback capability (patches can be versioned and reverted)
