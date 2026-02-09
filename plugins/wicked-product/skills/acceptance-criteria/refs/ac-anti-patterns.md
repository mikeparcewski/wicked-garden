# Acceptance Criteria Anti-Patterns

Common mistakes to avoid when writing acceptance criteria.

## Anti-Pattern 1: Vague Language

### Bad Example
```
AC1: User can log in successfully
AC2: Error is shown when something goes wrong
AC3: System performs well under load
```

**Problems**:
- "Successfully" - what does success look like?
- "Something goes wrong" - what specific error condition?
- "Performs well" - what metric? What threshold?

### Good Example
```
AC1: Given valid email/password
     When user submits login form
     Then user is redirected to dashboard within 2 seconds

AC2: Given invalid password
     When user submits login form
     Then error message "Invalid credentials" is displayed
     And login form remains visible

AC3: Given 1000 concurrent users
     When users make requests
     Then 95th percentile response time < 2 seconds
```

## Anti-Pattern 2: Implementation Details

### Bad Example
```
AC1: User service calls authentication API with JWT token
AC2: Database transaction is committed after validation
AC3: React component re-renders when state changes
```

**Problems**:
- Specifies HOW instead of WHAT
- Ties acceptance to implementation
- Not testable from user perspective

### Good Example
```
AC1: Given valid credentials
     When user submits login
     Then user gains access to protected resources

AC2: Given valid data
     When user saves record
     Then record is persisted and retrievable

AC3: Given data update
     When change occurs
     Then UI reflects updated data within 1 second
```

## Anti-Pattern 3: Missing Context (Given)

### Bad Example
```
AC1: When user clicks save, then record is saved
AC2: When error occurs, then message is shown
```

**Problems**:
- No precondition specified
- Ambiguous starting state
- Hard to reproduce for testing

### Good Example
```
AC1: Given user on edit form with valid changes
     When user clicks save
     Then record is updated in database

AC2: Given user on form with required field empty
     When user clicks save
     Then error message "Field X is required" is shown
```

## Anti-Pattern 4: Compound Criteria

### Bad Example
```
AC1: User can register, log in, update profile, and delete account
```

**Problems**:
- Multiple behaviors in one criterion
- Hard to test atomically
- Unclear if partial success is acceptable

### Good Example
```
AC1: Given valid registration data
     When user submits registration form
     Then account is created and confirmation email sent

AC2: Given valid credentials
     When user submits login
     Then user is authenticated and redirected to dashboard

AC3: Given logged-in user with profile changes
     When user saves profile
     Then changes are persisted and confirmation shown

AC4: Given logged-in user
     When user requests account deletion
     Then account is deactivated and confirmation email sent
```

## Anti-Pattern 5: Untestable Outcomes

### Bad Example
```
AC1: System is user-friendly
AC2: Design is intuitive
AC3: Performance is acceptable
AC4: Code is maintainable
```

**Problems**:
- Subjective criteria
- No measurable outcome
- Cannot verify programmatically

### Good Example
```
AC1: Given new user on home page
     When user attempts common task
     Then task is completable without help documentation
     And 80% of test users complete task in < 2 minutes

AC2: Given user on navigation menu
     When user looks for feature X
     Then feature X is findable in < 3 clicks
     And labeled with expected terminology

AC3: Given 1000 concurrent requests
     When system is under load
     Then p95 response time < 2 seconds
     And error rate < 1%

AC4: Given new developer on codebase
     When developer adds new feature
     Then code follows documented patterns
     And passes automated linting checks
```

## Anti-Pattern 6: Testing Instructions Instead of Acceptance

### Bad Example
```
AC1: QE should test happy path and error cases
AC2: Verify all edge cases are handled
AC3: Run load tests with 1000 users
```

**Problems**:
- Describes test process, not acceptance
- Tells QE what to do, not what success is
- Belongs in test plan, not acceptance criteria

### Good Example
```
AC1: Given valid input
     When user performs action
     Then expected outcome occurs

AC2: Given invalid input
     When user performs action
     Then appropriate error message is shown

AC3: Given 1000 concurrent users
     When system is under load
     Then system remains responsive (p95 < 2s)
```

## Anti-Pattern 7: Missing "Then" (No Observable Outcome)

### Bad Example
```
AC1: Given user on form, when user enters data
AC2: Given valid credentials, when user logs in
```

**Problems**:
- No expected outcome specified
- Cannot determine success/failure
- Incomplete specification

### Good Example
```
AC1: Given user on form
     When user enters data
     Then data is validated in real-time with visual feedback

AC2: Given valid credentials
     When user logs in
     Then user is authenticated and redirected to dashboard
```

## Anti-Pattern 8: Too Granular (Over-Specification)

### Bad Example
```
AC1: Button text is "Submit" in 14pt Arial font
AC2: Error message is red with hex code #FF0000
AC3: Input field border is 1px solid gray
AC4: Padding is exactly 16px on all sides
```

**Problems**:
- Design details, not behavior
- Brittle (breaks with design changes)
- Not user-facing value

### Good Example
```
AC1: Given user on form
     When user clicks primary action button
     Then form is submitted

AC2: Given validation error
     When error is displayed
     Then error message is visually distinct from normal text
     And clearly associated with the problematic field
```

## Anti-Pattern 9: No Prioritization

### Bad Example
```
AC1: User can log in
AC2: User can change theme color
AC3: User can export data to CSV
AC4: User can enable dark mode
```

**Problems**:
- All criteria treated equally
- Unclear what's critical vs nice-to-have
- Hard to make trade-off decisions

### Good Example
```
AC1 [P0]: Given valid credentials
          When user logs in
          Then user gains access to system

AC2 [P1]: Given logged-in user
          When user requests data export
          Then CSV file is generated and downloaded

AC3 [P2]: Given logged-in user
          When user toggles theme
          Then UI switches between light and dark mode

AC4 [P2]: Given user in settings
          When user selects accent color
          Then UI applies selected color to interactive elements
```

## Anti-Pattern 10: Ambiguous Pronouns and References

### Bad Example
```
AC1: When they click it, then it updates
AC2: When this happens, that should occur
AC3: System does the right thing
```

**Problems**:
- Unclear who/what is referenced
- Ambiguous actions and outcomes
- Not specific enough to implement or test

### Good Example
```
AC1: Given user viewing record detail page
     When user clicks "Save" button
     Then record is updated in database

AC2: Given validation error occurs
     When form is submitted
     Then error message is displayed below the invalid field

AC3: Given user submits form with valid data
     When server receives request
     Then HTTP 200 response is returned with created resource
```

## Checklist: Avoid These Anti-Patterns

- [ ] No vague language ("successfully", "properly", "well")
- [ ] No implementation details (APIs, databases, frameworks)
- [ ] Every criterion has Given (context)
- [ ] One testable behavior per criterion
- [ ] Observable, measurable outcomes
- [ ] Describes acceptance, not test instructions
- [ ] Always includes Then (expected outcome)
- [ ] Behavioral, not design specifications
- [ ] Prioritized (P0/P1/P2)
- [ ] No ambiguous pronouns ("it", "they", "this")

## Summary

Good acceptance criteria are:
- **Specific**: Clear context, action, outcome
- **Testable**: Observable and verifiable
- **Behavioral**: What happens, not how it's built
- **Independent**: One testable thing per criterion
- **Prioritized**: Criticality indicated
- **Complete**: Given/When/Then format
