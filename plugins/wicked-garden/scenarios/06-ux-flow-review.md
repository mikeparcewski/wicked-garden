---
name: ux-flow-review
title: User Flow and Interaction Pattern Review
description: Evaluate user experience flows for a checkout process
type: ux
difficulty: intermediate
estimated_minutes: 10
---

# User Flow and Interaction Pattern Review

This scenario tests wicked-product's UX review capabilities: evaluating user flows, identifying interaction pattern issues, and suggesting improvements for better user experience.

## Setup

Create a multi-step checkout flow to review:

```bash
# Create test project
mkdir -p ~/test-wicked-product/ux-review/src/pages/checkout
cd ~/test-wicked-product/ux-review

# Create checkout flow components
cat > src/pages/checkout/CartPage.tsx <<'EOF'
import React from 'react';
import { useCart } from '@/hooks/useCart';
import { useNavigate } from 'react-router-dom';

export function CartPage() {
  const { items, total, removeItem, updateQuantity } = useCart();
  const navigate = useNavigate();

  if (items.length === 0) {
    return <div>Your cart is empty</div>;
  }

  return (
    <div className="cart-page">
      <h1>Shopping Cart</h1>

      {items.map(item => (
        <div key={item.id} className="cart-item">
          <img src={item.image} />
          <div>{item.name}</div>
          <input
            type="number"
            value={item.quantity}
            onChange={e => updateQuantity(item.id, parseInt(e.target.value))}
          />
          <span>${item.price * item.quantity}</span>
          <span onClick={() => removeItem(item.id)}>Remove</span>
        </div>
      ))}

      <div className="cart-total">
        Total: ${total}
      </div>

      <button onClick={() => navigate('/checkout/shipping')}>
        Continue to Shipping
      </button>
    </div>
  );
}
EOF

cat > src/pages/checkout/ShippingPage.tsx <<'EOF'
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export function ShippingPage() {
  const [form, setForm] = useState({
    firstName: '', lastName: '', address1: '', address2: '',
    city: '', state: '', zip: '', country: 'US'
  });
  const navigate = useNavigate();

  const handleSubmit = () => {
    // No validation shown to user
    if (Object.values(form).some(v => !v)) {
      return; // Silent failure
    }
    navigate('/checkout/payment');
  };

  return (
    <div className="shipping-page">
      <h1>Shipping Address</h1>

      <input placeholder="First Name" value={form.firstName}
        onChange={e => setForm({...form, firstName: e.target.value})} />
      <input placeholder="Last Name" value={form.lastName}
        onChange={e => setForm({...form, lastName: e.target.value})} />
      <input placeholder="Address Line 1" value={form.address1}
        onChange={e => setForm({...form, address1: e.target.value})} />
      <input placeholder="Address Line 2 (Optional)" value={form.address2}
        onChange={e => setForm({...form, address2: e.target.value})} />
      <input placeholder="City" value={form.city}
        onChange={e => setForm({...form, city: e.target.value})} />

      <select value={form.state} onChange={e => setForm({...form, state: e.target.value})}>
        <option value="">Select State</option>
        {/* 50 states */}
      </select>

      <input placeholder="ZIP Code" value={form.zip}
        onChange={e => setForm({...form, zip: e.target.value})} />

      <button onClick={handleSubmit}>Continue to Payment</button>
    </div>
  );
}
EOF

cat > src/pages/checkout/PaymentPage.tsx <<'EOF'
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export function PaymentPage() {
  const [card, setCard] = useState({ number: '', expiry: '', cvv: '', name: '' });
  const [processing, setProcessing] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async () => {
    setProcessing(true);
    try {
      await processPayment(card);
      navigate('/checkout/confirmation');
    } catch (error) {
      // Error not shown to user
      setProcessing(false);
    }
  };

  return (
    <div className="payment-page">
      <h1>Payment</h1>

      <input placeholder="Card Number" value={card.number}
        onChange={e => setCard({...card, number: e.target.value})} />
      <input placeholder="MM/YY" value={card.expiry}
        onChange={e => setCard({...card, expiry: e.target.value})} />
      <input placeholder="CVV" value={card.cvv}
        onChange={e => setCard({...card, cvv: e.target.value})} />
      <input placeholder="Name on Card" value={card.name}
        onChange={e => setCard({...card, name: e.target.value})} />

      <button onClick={handleSubmit} disabled={processing}>
        {processing ? 'Processing...' : 'Place Order'}
      </button>

      {/* No order summary visible */}
      {/* No way to go back and edit */}
    </div>
  );
}
EOF

# Create user research context
cat > user-research.md <<'EOF'
# User Research Notes

## Cart Abandonment Data
- 68% abandon at shipping form
- 23% abandon at payment
- Top complaint: "I couldn't see my total while entering payment"

## User Interviews (n=12)
- "I wanted to change my shipping address but had to start over"
- "I wasn't sure if my order went through"
- "The form didn't tell me what was wrong"
- "I wish I could see my cart the whole time"

## Competitive Analysis
- Amazon: Single-page checkout option
- Shopify: Progress indicator, order summary sidebar
- Stripe Checkout: Inline validation, clear error states
EOF
```

## Steps

1. **Run User Flow Review**
   ```bash
   /wicked-product:ux-review src/pages/checkout --focus flows
   ```

   **Expected**: The ux-designer should identify:
   - Missing progress indicator
   - No way to navigate back
   - Silent form validation failures
   - Missing order summary on payment page
   - No confirmation/error states

2. **Verify Flow Mapping**

   Check that the analysis maps the user journey:
   ```
   Cart -> Shipping -> Payment -> Confirmation

   Issues at each step:
   - Cart: No indication of next steps
   - Shipping: Silent validation, can't go back
   - Payment: No summary, unclear errors
   - Confirmation: Not reviewed (no component)
   ```

3. **Check State Handling Analysis**

   Should identify missing states:
   - Empty cart state (minimal)
   - Loading states during navigation
   - Error states (no user feedback)
   - Success state (no confirmation UI)
   - Edge case: What if session expires mid-checkout?

4. **Verify Research Integration**
   ```bash
   /wicked-product:ux-review src/pages/checkout --focus research
   ```

   If user-research.md is available, should connect:
   - "68% abandon at shipping" -> validate the form issues
   - "Couldn't see my total" -> missing order summary
   - "Couldn't change address" -> no back navigation

5. **Check Improvement Recommendations**

   Recommendations should be specific:
   ```
   Issue: Silent form validation
   Recommendation:
   1. Add inline validation on blur
   2. Show error messages below each field
   3. Highlight invalid fields with border color
   4. Scroll to first error on submit
   ```

   Not vague like "improve form validation"

## Expected Outcome

- Complete flow analysis from cart to checkout
- Missing states identified
- Specific, actionable improvements
- Priority based on user impact (research-backed)
- Connection to abandonment data

## Success Criteria

- [ ] Identifies all 4 checkout pages/steps
- [ ] Missing progress indicator called out
- [ ] Silent validation failure identified (shipping page)
- [ ] Missing error feedback on payment page noted
- [ ] No back navigation identified as issue
- [ ] Missing order summary on payment page flagged
- [ ] Empty/loading/error states reviewed
- [ ] Recommendations are specific code-level suggestions
- [ ] If research file available, connects to abandonment data
- [ ] Prioritization based on user impact

## Value Demonstrated

**Real-world value**: User flow issues are among the most costly UX problems - they directly impact conversion rates and revenue. A checkout flow with 68% abandonment at shipping is leaving money on the table with every visitor.

wicked-product's `/ux-review --focus flows` acts as an experienced UX designer reviewing your flow for common pitfalls. Unlike automated tools that only check individual pages, this analysis understands the journey: users need to know where they are, where they're going, and be able to recover from mistakes.

The integration with user research data (when available) transforms subjective "this feels wrong" into evidence-based "this is causing abandonment." For teams without dedicated UX researchers, this provides the systematic flow analysis that prevents costly conversion issues.

This replaces expensive UX consultants for flow reviews, while catching the issues that A/B tests would eventually reveal - but before you've lost thousands of customers figuring it out the hard way.
