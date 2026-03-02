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
   /wicked-garden:search:index /tmp/wicked-impl-test
   ```

2. Find code implementing "Payment Processing":
   ```
   /wicked-garden:search:impl "Payment Processing"
   ```

3. Find code implementing "User Authentication":
   ```
   /wicked-garden:search:impl "User Authentication"
   ```

4. Find code implementing "Notification System":
   ```
   /wicked-garden:search:impl "Notification System"
   ```

5. Verify bidirectional tracing for PaymentGateway:
   ```
   /wicked-garden:search:refs PaymentGateway
   ```

## Expected Outcomes

- Spec document parsed into searchable sections (User Authentication, Payment Processing, Notification System)
- Each spec section maps to the correct implementing classes and file locations
- "Payment Processing" maps to PaymentGateway and StripeAdapter in payments.py
- "User Authentication" maps to Authenticator and TokenService in auth.py
- "Notification System" maps to NotificationService, EmailDispatcher, and PushDispatcher in notifications.py
- Bidirectional tracing works: `/refs PaymentGateway` returns spec.md with the relevant section context

## Success Criteria

- [ ] Spec document indexed and parsed into distinct sections
- [ ] `/impl "Payment Processing"` returns PaymentGateway and StripeAdapter
- [ ] `/impl "User Authentication"` returns Authenticator and TokenService
- [ ] `/impl "Notification System"` returns NotificationService, EmailDispatcher, and PushDispatcher
- [ ] `/refs PaymentGateway` returns spec.md showing the Payment Processing section
- [ ] Multiple classes per spec section are correctly linked
- [ ] Bidirectional tracing works (spec to code and code to spec)

## Value Demonstrated

**Problem solved**: Requirements live in separate documents from code. Teams struggle to verify that all requirements are implemented, find which code implements a specific requirement, and prove compliance during audits.

**Why this matters**:
- **Onboarding**: New developer reads spec section, instantly sees implementing code
- **Compliance**: Auditor asks "Show me the authentication implementation", answer is instant
- **Refactoring**: Need to update payment processing, find all involved classes immediately
- **Gap analysis**: Check each spec section to identify unimplemented requirements
