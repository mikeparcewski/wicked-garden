# Acceptance Criteria Guide: Fundamentals

What acceptance criteria are, the Given/When/Then format, basic examples, coverage requirements, and writing guidelines.

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
