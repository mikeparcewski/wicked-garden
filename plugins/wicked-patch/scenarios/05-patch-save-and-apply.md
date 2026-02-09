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
/wicked-patch:add-field \
  --entity Payment \
  --name transactionId \
  --type String \
  --required true \
  --project /tmp/wicked-patch-review \
  --output /tmp/wicked-patch-review/.patches/add-transaction-id/
```

### 3. Review the generated patches

Examine the patch files to understand what changes will be made:

```bash
# List generated patch files
ls -la /tmp/wicked-patch-review/.patches/add-transaction-id/

# View the patch metadata
cat /tmp/wicked-patch-review/.patches/add-transaction-id/manifest.json

# View specific patch content
cat /tmp/wicked-patch-review/.patches/add-transaction-id/add-transactionId-entity.json
```

### 4. Commit patches to version control

Save patches to git for team review:

```bash
cd /tmp/wicked-patch-review
git add .patches/
git commit -m "feat: add transactionId field to Payment entity

Generated patches for review:
- Payment.java: add transactionId field with getter/setter
- PaymentService.java: add validation for transactionId

Requires review before apply.
Related: JIRA-1234"

git log --oneline -n 2
```

### 5. (Simulate) Code review process

In a real workflow, team members would:
- Review the patch files in a pull request
- Verify the changes are correct
- Check for security or compliance issues
- Approve the patches

For this scenario, we simulate approval:

```bash
# Create approval marker
echo "Reviewed-by: senior-dev@example.com" > /tmp/wicked-patch-review/.patches/add-transaction-id/APPROVED
echo "Reviewed-by: tech-lead@example.com" >> /tmp/wicked-patch-review/.patches/add-transaction-id/APPROVED
echo "Date: $(date)" >> /tmp/wicked-patch-review/.patches/add-transaction-id/APPROVED

cat /tmp/wicked-patch-review/.patches/add-transaction-id/APPROVED
```

### 6. Apply approved patches

After approval, apply the patches to the codebase:

```bash
/wicked-patch:apply \
  --patches /tmp/wicked-patch-review/.patches/add-transaction-id/ \
  --project /tmp/wicked-patch-review
```

### 7. Verify changes and commit

Check that patches were applied correctly:

```bash
# Verify field was added
grep -A 5 "transactionId" /tmp/wicked-patch-review/models/Payment.java

# Verify validation was added
grep -A 5 "transactionId" /tmp/wicked-patch-review/services/PaymentService.java

# Commit the applied changes
cd /tmp/wicked-patch-review
git add models/ services/
git commit -m "apply: transactionId field patches

Applied patches from .patches/add-transaction-id/
Approved by: senior-dev, tech-lead

Changes:
- Payment.java: added transactionId field
- PaymentService.java: added transactionId validation"

git log --oneline -n 3
```

### 8. Archive applied patches

Move applied patches to archive for audit trail:

```bash
mkdir -p /tmp/wicked-patch-review/.patches/archive/
mv /tmp/wicked-patch-review/.patches/add-transaction-id/ \
   /tmp/wicked-patch-review/.patches/archive/add-transaction-id-$(date +%Y%m%d)/

ls -la /tmp/wicked-patch-review/.patches/archive/
```

## Expected Outcome

After step 2 (generate with --output), you should see:
```
Patches generated successfully (NOT applied):

Output location: /tmp/wicked-patch-review/.patches/add-transaction-id/

Files created:
- manifest.json (patch metadata and checksums)
- add-transactionId-entity.json (Payment.java changes)
- add-transactionId-service.json (PaymentService.java validation)

To apply these patches, use:
  /wicked-patch:apply --patches .patches/add-transaction-id/

To review patches before applying:
  cat .patches/add-transaction-id/manifest.json
```

After step 3 (review), manifest.json should contain:
```json
{
  "operation": "add-field",
  "entity": "Payment",
  "field": "transactionId",
  "type": "String",
  "required": true,
  "generated_at": "2026-02-05T10:30:00Z",
  "wicked_patch_version": "1.0.0",
  "files_affected": 2,
  "total_changes": 4,
  "patches": [
    {
      "file": "add-transactionId-entity.json",
      "target": "models/Payment.java",
      "changes": 3,
      "checksum": "sha256:abc123..."
    },
    {
      "file": "add-transactionId-service.json",
      "target": "services/PaymentService.java",
      "changes": 1,
      "checksum": "sha256:def456..."
    }
  ],
  "risk_assessment": "LOW",
  "requires_migration": false
}
```

After step 4 (commit), git log should show:
```
a1b2c3d feat: add transactionId field to Payment entity
f4e5d6c Initial payment service setup
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

And PaymentService.java validation should include:
```java
if (payment.getTransactionId() == null || payment.getTransactionId().isEmpty()) {
    throw new IllegalArgumentException("Transaction ID is required");
}
```

After step 7 (final commit), git log should show:
```
g7h8i9j apply: transactionId field patches
a1b2c3d feat: add transactionId field to Payment entity
f4e5d6c Initial payment service setup
```

## Success Criteria

- [ ] Patches generated with --output flag without applying changes
- [ ] Files unchanged after patch generation (only .patches/ directory created)
- [ ] manifest.json contains metadata, checksums, and risk assessment
- [ ] Patches committed to git for review
- [ ] Apply command successfully applied all patches
- [ ] Payment.java has transactionId field with getter/setter
- [ ] PaymentService.java has validation for transactionId
- [ ] Final git commit shows clean history of generate → review → apply
- [ ] Applied patches archived with timestamp

## Value Demonstrated

**Real-world problem**: Direct code changes bypass review processes. In regulated industries (finance, healthcare) or teams with strict compliance, changes must be reviewed before application. Manual change generation is error-prone.

**wicked-patch solution**: Separates patch generation from application. Patches are reviewable artifacts that can be versioned, approved, and audited.

**Workflow benefits**:
- **Generate** patches on dev branch without modifying code
- **Review** patches in pull requests (patch files are human-readable JSON)
- **Approve** patches through standard code review process
- **Apply** patches only after approval
- **Audit** with git history of who approved and when applied

**Time saved**: 15-20 minutes per change (manual code generation, review preparation, documentation) → 3 minutes (automated patch generation)

**Compliance value**:
- Audit trail of all changes (git history of patch generation and application)
- Separation of duties (developer generates, senior engineer approves)
- Reviewable change artifacts (manifest.json shows complete impact)
- Rollback capability (patches can be versioned and reverted)

**Real-world use cases**:
- Financial services: SOX compliance for payment processing changes
- Healthcare: HIPAA-compliant changes to patient data models
- Enterprise: Change Advisory Board (CAB) approval workflows
- Open source: Maintainer review before accepting contributions
- Regulated industries: Documented review process for audit trails
