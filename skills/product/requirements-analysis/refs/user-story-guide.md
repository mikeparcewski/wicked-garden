# User Story Writing Guide

Comprehensive guide to writing effective user stories.

## The User Story Format

```
As a [persona]
I want [capability]
So that [benefit]
```

### Components

1. **Persona**: Who is the user?
   - Specific role, not generic "user"
   - Represents real user segment
   - Example: "customer", "admin", "support agent"

2. **Capability**: What do they want to do?
   - Action or feature
   - From user's perspective
   - Example: "log in with email", "export report"

3. **Benefit**: Why do they want it?
   - Business value
   - User goal or outcome
   - Example: "so that I can access my account", "so that I can analyze trends"

## INVEST Criteria

Good user stories are:

### Independent
- Can be developed separately
- Minimal dependencies on other stories
- Deliverable on its own

**Bad**: "As a user, I want to see part 2 of the registration flow"
**Good**: "As a new user, I want to create an account so that I can save my preferences"

### Negotiable
- Details can be discussed
- Not a contract
- Room for collaboration

**Bad**: "As a user, I want a dropdown with exactly 5 options using Select2 library"
**Good**: "As a user, I want to select my country so that I see localized content"

### Valuable
- Delivers user/business value
- Clear benefit stated
- Not technical tasks

**Bad**: "As a developer, I want to refactor the database schema"
**Good**: "As a user, I want faster search results so that I can find information quickly"

### Estimable
- Team can estimate effort
- Enough detail to size
- Complexity understood

**Bad**: "As a user, I want a better experience"
**Good**: "As a customer, I want to filter products by price so that I can find items in my budget"

### Small
- Completable in one iteration
- Not too big to manage
- Can be broken down if needed

**Bad**: "As a user, I want a complete e-commerce platform"
**Good**: "As a customer, I want to add items to cart so that I can purchase multiple products"

### Testable
- Clear acceptance criteria
- Can verify completion
- Observable outcome

**Bad**: "As a user, I want a nice-looking UI"
**Good**: "As a user, I want to see my order history so that I can track past purchases"

## Common Personas

### External Users
- **Customer**: Purchases/uses product
- **Visitor**: Browsing, not registered
- **Subscriber**: Paying customer
- **Partner**: External organization

### Internal Users
- **Admin**: System administrator
- **Support Agent**: Customer support
- **Manager**: Oversight/reporting
- **Developer**: System maintenance

### System
- **System**: Automated processes
- **API Consumer**: External system integration

## Examples by Domain

### Authentication
```
As a new customer
I want to register with email and password
So that I can create an account and save my preferences

As a returning customer
I want to log in with my email
So that I can access my account

As a user who forgot password
I want to reset my password via email
So that I can regain access to my account
```

### E-commerce
```
As a customer
I want to search for products by keyword
So that I can find items I'm interested in

As a customer
I want to add items to my cart
So that I can purchase multiple products at once

As a customer
I want to view my order history
So that I can track past purchases and reorder items
```

### Data Management
```
As an admin
I want to export user data to CSV
So that I can analyze trends in Excel

As a support agent
I want to search for customer by email
So that I can quickly help with their inquiry

As a manager
I want to view monthly sales reports
So that I can make informed business decisions
```

### API/Integration
```
As an API consumer
I want to authenticate with API keys
So that I can securely access protected resources

As a system
I want to retry failed webhook deliveries
So that I ensure reliable event delivery

As a developer
I want comprehensive API documentation
So that I can integrate with the service quickly
```

## Story Sizing

### Small (S) - 1-2 days
```
As a user
I want to update my email address
So that I receive notifications at my current email
```

### Medium (M) - 3-5 days
```
As a customer
I want to search products with filters
So that I can narrow results by category, price, and rating
```

### Large (L) - 1-2 weeks
```
As a customer
I want a complete checkout process
So that I can purchase items with payment and shipping
```
*Note: Large stories should be broken down*

## Breaking Down Large Stories

### Original (Too Large)
```
As a customer
I want a complete user profile system
So that I can manage my account
```

### Broken Down
```
US1: As a customer, I want to view my profile
     So that I can see my current information

US2: As a customer, I want to edit my profile details
     So that I can keep my information current

US3: As a customer, I want to upload a profile picture
     So that I can personalize my account

US4: As a customer, I want to change my password
     So that I can maintain account security

US5: As a customer, I want to delete my account
     So that I can remove my data from the system
```

## Common Mistakes

### Mistake 1: Technical Story
**Bad**: "As a developer, I want to upgrade to React 18"
**Fix**: "As a user, I want faster page loads so that I have a better experience"

### Mistake 2: Missing Benefit
**Bad**: "As a user, I want to export data to CSV"
**Fix**: "As a user, I want to export data to CSV so that I can analyze it in Excel"

### Mistake 3: Too Generic
**Bad**: "As a user, I want to use the system"
**Fix**: "As a customer, I want to track my order status so that I know when to expect delivery"

### Mistake 4: Implementation Details
**Bad**: "As a user, I want a Redux store for state management"
**Fix**: "As a user, I want my cart to persist across sessions so that I don't lose my selections"

### Mistake 5: Multiple Capabilities
**Bad**: "As a user, I want to log in, update profile, and delete account"
**Fix**: Split into 3 separate stories

## Acceptance Criteria Template

Every user story should have acceptance criteria:

```
As a [persona]
I want [capability]
So that [benefit]

Acceptance Criteria:
1. Given [context], When [action], Then [outcome]
2. Given [error condition], When [action], Then [error handling]
3. Given [edge case], When [action], Then [graceful behavior]
```

## Full Example

```markdown
### US-123: Customer Registration

**As a** new customer
**I want to** register with email and password
**So that** I can create an account and save my preferences

**Priority**: P0
**Complexity**: M (3-5 days)

**Acceptance Criteria**:
1. Given valid email and password (8+ chars)
   When I submit registration form
   Then account is created and confirmation email sent

2. Given email already registered
   When I submit registration form
   Then error "Email already registered" is shown

3. Given password less than 8 characters
   When I submit registration form
   Then error "Password must be at least 8 characters" is shown

4. Given malformed email address
   When I submit registration form
   Then error "Please enter valid email" is shown

**Dependencies**: Email service integration (US-100)
**Assumptions**: Email verification required before full access
**Open Questions**: Social registration (Google, GitHub)?

**Test Data Requirements**:
- Valid/invalid emails
- Various password lengths and patterns
- Existing registered emails

**Notes**: Consider GDPR compliance for EU users
```

## Template for New Stories

Use this template when creating new user stories:

```markdown
### US-XXX: [Story Title]

**As a** [specific persona]
**I want** [specific capability]
**So that** [specific benefit/value]

**Priority**: [P0/P1/P2]
**Complexity**: [S/M/L]

**Acceptance Criteria**:
1. Given [context], When [action], Then [outcome]
2. Given [error], When [action], Then [handling]

**Dependencies**: [Other stories or systems]
**Assumptions**: [What we're assuming]
**Open Questions**: [Needs clarification]
**Test Data**: [Required for testing]
**Notes**: [Additional context]
```

## Resources

- **Examples**: See `/skills/requirements-analysis/refs/story-examples/` for domain-specific examples
- **Template Script**: Run `${CLAUDE_PLUGIN_ROOT}/scripts/user-story-template.sh` to generate formatted template
- **Validation**: Review stories against INVEST criteria checklist
