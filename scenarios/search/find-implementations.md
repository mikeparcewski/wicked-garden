---
name: find-implementations
title: Find Implementations from Specifications
description: Trace from specification sections to implementing code
type: workflow
difficulty: intermediate
estimated_minutes: 10
---

# Find Implementations from Specifications

## Setup

Create a specification document and implementing code:

```bash
# Create test directory
mkdir -p /tmp/wicked-impl-test/docs
mkdir -p /tmp/wicked-impl-test/src

# Create specification document
cat > /tmp/wicked-impl-test/docs/spec.md << 'EOF'
# Feature Specification

## User Authentication

Users authenticate via username/password. The system validates credentials
and issues JWT tokens for subsequent requests. The Authenticator class
handles validation and the TokenService manages JWT tokens.

## Payment Processing

Payments are processed through Stripe integration. The PaymentGateway
handles charge creation and refunds. The StripeAdapter wraps the Stripe API.

## Notification System

Users receive notifications via email and push. The NotificationService
dispatches messages based on user preferences. EmailDispatcher and
PushDispatcher handle the actual delivery.
EOF

# Create implementing code
cat > /tmp/wicked-impl-test/src/auth.py << 'EOF'
import jwt

class Authenticator:
    """Implements User Authentication section."""

    def validate_credentials(self, username: str, password: str) -> bool:
        """Validate username and password."""
        pass

class TokenService:
    """Manages JWT tokens."""

    def issue_token(self, user_id: int) -> str:
        """Issue a new JWT token."""
        return jwt.encode({"user_id": user_id}, "secret")

    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token."""
        return jwt.decode(token, "secret")
EOF

cat > /tmp/wicked-impl-test/src/payments.py << 'EOF'
class PaymentGateway:
    """Implements Payment Processing section."""

    def create_charge(self, amount: int, customer_id: str):
        """Create a charge."""
        pass

    def process_refund(self, charge_id: str):
        """Process a refund."""
        pass

class StripeAdapter:
    """Wraps Stripe API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
EOF

cat > /tmp/wicked-impl-test/src/notifications.py << 'EOF'
class NotificationService:
    """Implements Notification System section."""

    def send_notification(self, user_id: int, message: str, channel: str):
        """Send notification via specified channel."""
        pass

class EmailDispatcher:
    """Handles email delivery."""

    def send(self, to: str, subject: str, body: str):
        pass

class PushDispatcher:
    """Handles push notification delivery."""

    def send(self, device_token: str, payload: dict):
        pass
EOF
```

## Steps

1. Index the project:
   ```
   /wicked-search:index /tmp/wicked-impl-test
   ```

2. Find code implementing "Payment Processing":
   ```
   /wicked-search:impl "Payment Processing"
   ```

3. Find code implementing "User Authentication":
   ```
   /wicked-search:impl "User Authentication"
   ```

4. Verify bidirectional tracing - find docs for PaymentGateway:
   ```
   /wicked-search:refs PaymentGateway
   ```

## Expected Outcome

1. **Indexing**:
   - Spec document parsed into sections
   - Code symbols extracted
   - Cross-references detected between spec sections and code classes

2. **Implementation search**:
   - `/impl "Payment Processing"` returns:
     - PaymentGateway class with methods
     - StripeAdapter class
     - payments.py file location

   - `/impl "User Authentication"` returns:
     - Authenticator class with methods
     - TokenService class
     - auth.py file location

3. **Reference search**:
   - `/refs PaymentGateway` returns spec.md with "Payment Processing" section
   - Shows context: which section mentions this class

## Success Criteria

- [ ] Spec document indexed and parsed into sections
- [ ] All code symbols detected and indexed
- [ ] `/impl "Payment Processing"` returns PaymentGateway and StripeAdapter
- [ ] `/impl "User Authentication"` returns Authenticator and TokenService
- [ ] `/impl "Notification System"` returns NotificationService and dispatchers
- [ ] `/refs PaymentGateway` returns spec.md with context
- [ ] Bidirectional tracing works: spec → code and code → spec
- [ ] Multiple classes per section correctly linked

## Value Demonstrated

**Problem solved**: Requirements live in separate documents from code. Teams struggle to:
- Verify that all requirements are implemented
- Find which code implements a specific requirement
- Update code when requirements change
- Prove compliance during audits

**Why this matters**:

**Onboarding scenario**: New developer joins team
- Reads: "Payment Processing" spec section
- Runs: `/impl "Payment Processing"`
- Sees: Exact classes and methods that implement it
- Result: Understanding in minutes, not hours

**Compliance scenario**: Auditor asks about authentication
- Question: "Show me the authentication implementation"
- Runs: `/impl "User Authentication"`
- Shows: Complete implementation with file locations
- Result: Instant compliance proof

**Refactoring scenario**: Need to update payment processing
- Runs: `/impl "Payment Processing"`
- Gets: All classes involved
- Runs: `/blast-radius PaymentGateway` (see next scenario)
- Result: Safe, informed refactoring

**Gap analysis**: Product manager reviews features
- Checks each spec section with `/impl`
- Identifies: Which requirements lack implementation
- Result: Visibility into development progress

The automatic linking means specifications and code stay connected with zero manual maintenance.
