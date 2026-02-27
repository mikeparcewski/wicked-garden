# Acceptance Criteria Guide

Comprehensive guide to writing clear, testable acceptance criteria for user stories.

## What Are Acceptance Criteria?

Acceptance criteria define the conditions that must be met for a user story to be considered complete. They:
- Establish clear boundaries of the story
- Provide testable conditions
- Align stakeholders on "done"
- Feed directly into QE test scenarios

## The Given/When/Then Format

Standard format for behavior-driven acceptance criteria:

```
Given [context/precondition]
When [action/event]
Then [expected outcome]
```

### Components

1. **Given**: Initial state or context
   - What conditions exist before the action
   - Data state, user role, system state
   - Can have multiple conditions (AND)

2. **When**: The action or event
   - What the user or system does
   - Trigger for the expected outcome
   - Usually a single action

3. **Then**: Expected outcome
   - Observable result
   - State change, UI feedback, system behavior
   - Must be testable/verifiable

## Basic Examples

### Example 1: Login
```
Given a registered user with valid credentials
When they submit the login form with correct email and password
Then they are redirected to their dashboard
```

### Example 2: Error Handling
```
Given a user attempting to log in
When they submit the form with an incorrect password
Then they see an error message "Invalid email or password"
```

### Example 3: Edge Case
```
Given a user account that is locked after 3 failed login attempts
When they try to log in with correct credentials
Then they see "Account locked. Please reset your password."
```

## Coverage Requirements

Every user story should have acceptance criteria covering:

### 1. Happy Path (Required)
The normal, expected flow with valid inputs and conditions.

```
Given a customer with items in their cart
When they proceed to checkout and complete payment
Then their order is confirmed and confirmation email sent
```

### 2. Error Conditions (Required)
Invalid inputs, failed dependencies, system errors.

```
Given a customer at checkout
When payment processing fails
Then they see "Payment failed. Please try again" and cart is preserved
```

### 3. Edge Cases (Recommended)
Boundary conditions, unusual but valid scenarios.

```
Given a customer purchasing exactly at inventory limit
When they complete checkout
Then order succeeds and inventory shows 0 remaining
```

### 4. Non-Functional Requirements (When Applicable)
Performance, security, usability constraints.

```
Given 1000+ search results
When a user searches for products
Then first page loads within 2 seconds
```

## Writing Effective Criteria

### DO: Be Specific
```
GOOD:
Given a user with manager role
When they view the dashboard
Then they see team metrics for their department

BAD:
Given a user
When they log in
Then they see stuff
```

### DO: Make It Testable
```
GOOD:
Then the confirmation email is sent within 5 minutes

BAD:
Then the system works correctly
```

### DO: Focus on Outcomes
```
GOOD:
Then the user sees "Password must be at least 8 characters"

BAD:
Then the validation function returns false
```

### DON'T: Include Implementation Details
```
GOOD:
Then the user's session persists for 24 hours

BAD:
Then a JWT token with 24-hour expiry is stored in localStorage
```

### DON'T: Be Vague
```
GOOD:
Then search returns results sorted by relevance score descending

BAD:
Then search works well
```

## Complex Scenarios

### Multiple Preconditions (AND)
```
Given a user is logged in
  AND they have admin privileges
  AND there are pending approval requests
When they view the admin dashboard
Then they see a list of all pending requests
```

### Alternative Paths (OR)
Write separate criteria:
```
Criterion 1:
Given a user logs in with email
When authentication succeeds
Then they access their dashboard

Criterion 2:
Given a user logs in with Google OAuth
When authentication succeeds
Then they access their dashboard
```

### Cascading Events
```
Given an order is successfully placed
When the payment is confirmed
Then the order status changes to "Processing"
  AND inventory is decremented
  AND confirmation email is sent
  AND seller is notified
```

## Domain-Specific Examples

### Authentication/Authorization

```
Story: Password Reset

1. Given a registered user who forgot their password
   When they submit password reset request with valid email
   Then they receive a reset link via email within 2 minutes

2. Given a user clicks a valid reset link
   When they submit a new password (8+ characters)
   Then their password is updated and they can log in

3. Given a user clicks an expired reset link (>24 hours old)
   When they try to reset password
   Then they see "Link expired. Request a new one."

4. Given a user submits password reset for non-existent email
   When the form is submitted
   Then success message shown (no email sent - security)
```

### E-commerce

```
Story: Shopping Cart

1. Given a customer viewing a product in stock
   When they click "Add to Cart"
   Then item appears in cart with quantity 1

2. Given a customer with item already in cart
   When they add the same item again
   Then cart shows quantity incremented by 1

3. Given a product with limited stock (5 remaining)
   When customer tries to add 10 to cart
   Then only 5 are added and message "Only 5 available" shown

4. Given items in cart for 30+ days
   When customer views cart
   Then price and availability are revalidated
```

### Data Management

```
Story: CSV Export

1. Given a user with data in the system
   When they click "Export to CSV"
   Then CSV file downloads with all accessible records

2. Given a dataset with 50,000+ records
   When user requests export
   Then async job starts and user receives email with download link

3. Given user has no data to export
   When they click "Export to CSV"
   Then message "No data available to export" is shown

4. Given export includes sensitive fields
   When user downloads CSV
   Then data is properly escaped and formatted for Excel
```

### Search/Filter

```
Story: Product Search

1. Given a user enters search term "laptop"
   When they submit search
   Then results show all products matching "laptop" sorted by relevance

2. Given a user enters search with no matches
   When they submit search
   Then "No results found. Try different keywords" message shown

3. Given a user applies multiple filters (category: Electronics, price: $500-$1000)
   When they view results
   Then only products matching ALL filters are shown

4. Given search returns 500+ results
   When user views results
   Then first page (25 items) loads within 2 seconds with pagination
```

## Non-Functional Requirements

Include when relevant to the story:

### Performance
```
Given a search query
When user submits
Then results appear within 2 seconds for 95th percentile
```

### Security
```
Given a user attempting to access admin panel
When they are not logged in as admin
Then they see 403 Forbidden and are logged for security audit
```

### Usability
```
Given a user on mobile device
When they view the checkout form
Then all fields are touch-friendly (44x44px minimum) and properly labeled
```

### Accessibility
```
Given a screen reader user
When they navigate the form
Then all fields have proper ARIA labels and validation errors are announced
```

### Reliability
```
Given payment gateway is temporarily unavailable
When user attempts checkout
Then they see "Payment processing unavailable. Try again in a few minutes"
  AND order is not created
  AND cart is preserved
```

## Acceptance Criteria Checklist

Before finalizing criteria, verify:

- [ ] All criteria use Given/When/Then format
- [ ] Happy path is covered
- [ ] At least one error condition is covered
- [ ] Edge cases are identified
- [ ] Each criterion is independently testable
- [ ] Outcomes are observable and verifiable
- [ ] No implementation details included
- [ ] Clear enough for QE to write test scenarios
- [ ] Aligned with story's benefit/value
- [ ] No ambiguous terms ("works well", "fast", "good")

## Common Mistakes

### Mistake 1: Too Vague
```
BAD:
Then the system should work correctly

GOOD:
Then the user sees confirmation message "Order placed successfully"
  AND order appears in order history
```

### Mistake 2: Implementation-Focused
```
BAD:
Then a POST request is sent to /api/orders endpoint

GOOD:
Then the order is saved and confirmation email sent
```

### Mistake 3: Multiple Actions in When
```
BAD:
When user enters email, clicks submit, and waits for response

GOOD:
Given user has entered valid email
When they click submit
Then confirmation message appears
```

### Mistake 4: Untestable Outcomes
```
BAD:
Then the user experience is improved

GOOD:
Then page load time is reduced from 5s to under 2s
```

### Mistake 5: Missing Context
```
BAD:
When submit button clicked
Then error shown

GOOD:
Given user has not filled required email field
When they click submit
Then error "Email is required" shown below email field
```

## Integration with Testing

Acceptance criteria directly map to test scenarios:

### Story Acceptance Criteria
```
Given a customer with valid payment info
When they complete checkout
Then order is created with status "Processing"
```

### QE Test Scenario
```
Test: Successful Checkout Flow
Setup: Create test customer with saved credit card
Steps:
  1. Add item to cart
  2. Proceed to checkout
  3. Confirm payment details
  4. Submit order
Expected: Order created with status "Processing"
Cleanup: Delete test order and customer
```

## Template for Structured Documentation

```markdown
## Acceptance Criteria

### Functional Requirements

**Happy Path**:
1. Given {normal conditions}, When {action}, Then {expected outcome}

**Error Handling**:
2. Given {error condition}, When {action}, Then {error message/handling}

**Edge Cases**:
3. Given {boundary condition}, When {action}, Then {graceful handling}

### Non-Functional Requirements

**Performance**:
- Response time: {metric}
- Throughput: {metric}

**Security**:
- Authorization: {requirement}
- Data protection: {requirement}

**Usability**:
- Accessibility: {requirement}
- Mobile support: {requirement}
```

## Linking to Test Scenarios

Acceptance criteria should reference test scenarios:

```markdown
**Acceptance Criteria**:
1. Given valid input, When submit, Then success
   → See: phases/qe/test-scenarios.md#test-auth-001

2. Given invalid input, When submit, Then error shown
   → See: phases/qe/test-scenarios.md#test-auth-002
```

## Review Process

When reviewing acceptance criteria:

1. **Completeness**: Does it cover all story aspects?
2. **Testability**: Can QE write automated tests?
3. **Clarity**: Is it unambiguous?
4. **Independence**: Can each be verified separately?
5. **Alignment**: Does it match the story's benefit?

## Resources

- **User Story Template**: `refs/user-story-template.md`
- **Test Scenario Mapping**: See wicked-qe plugin
- **Examples**: Real-world criteria in project history
