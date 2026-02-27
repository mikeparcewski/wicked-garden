# Acceptance Criteria Examples

Comprehensive examples of well-written acceptance criteria across different domains.

## Authentication & Authorization

### User Login
```
AC1: Given valid email and password
     When user submits login form
     Then user is redirected to dashboard and session is created

AC2: Given invalid password
     When user submits login form
     Then error message "Invalid credentials" is displayed
     And login form remains visible
     And no session is created

AC3: Given account locked after 3 failed attempts
     When user submits login form
     Then error message "Account locked. Try again in 15 minutes" is displayed
     And account remains locked for 15 minutes

AC4: Given user successfully logged in
     When 30 minutes of inactivity pass
     Then user is logged out automatically
     And redirected to login page with message "Session expired"
```

### Role-Based Access
```
AC1: Given user has "admin" role
     When user navigates to admin panel
     Then admin panel is displayed with full functionality

AC2: Given user has "viewer" role
     When user attempts to access admin panel
     Then access denied message is displayed
     And user is redirected to home page

AC3: Given user has "editor" role
     When user views content list
     Then edit and delete buttons are visible for user's own content only
```

## Data Management

### Create Record
```
AC1: Given user on create form with all required fields filled
     When user clicks "Save"
     Then record is created in database
     And success message "Record created successfully" is displayed
     And user is redirected to record detail page

AC2: Given user on create form with required field empty
     When user clicks "Save"
     Then error message "Field X is required" is displayed
     And form is not submitted
     And user remains on create page

AC3: Given user enters data exceeding field length limit
     When user clicks "Save"
     Then error message "Field X must be less than N characters" is displayed
     And form is not submitted
```

### Search Functionality
```
AC1: Given user enters search term matching 5 records
     When user clicks "Search"
     Then 5 matching records are displayed in results list
     And results are sorted by relevance

AC2: Given user enters search term matching 0 records
     When user clicks "Search"
     Then message "No results found" is displayed
     And search suggestions are shown

AC3: Given user enters search term matching 1000+ records
     When user clicks "Search"
     Then first 20 results are displayed
     And pagination controls are shown
     And total count "1000+ results" is displayed
```

## API Endpoints

### GET Request
```
AC1: Given valid authentication token
     When GET /api/users/{id} is called with existing user ID
     Then HTTP 200 response is returned
     And response body contains user object with expected schema
     And response time is less than 200ms

AC2: Given valid authentication token
     When GET /api/users/{id} is called with non-existent user ID
     Then HTTP 404 response is returned
     And response body contains error message "User not found"

AC3: Given invalid or expired authentication token
     When GET /api/users/{id} is called
     Then HTTP 401 response is returned
     And response body contains error message "Unauthorized"
```

### POST Request
```
AC1: Given valid authentication and valid request body
     When POST /api/users is called
     Then HTTP 201 response is returned
     And response body contains created user object with ID
     And user is persisted in database

AC2: Given valid authentication but invalid request body (missing required field)
     When POST /api/users is called
     Then HTTP 400 response is returned
     And response body contains validation error details
     And no user is created in database

AC3: Given valid authentication but duplicate email
     When POST /api/users is called
     Then HTTP 409 response is returned
     And response body contains error "Email already exists"
```

## E-commerce

### Add to Cart
```
AC1: Given user viewing product with stock available
     When user clicks "Add to Cart"
     Then product is added to cart
     And cart icon shows updated item count
     And success message "Added to cart" is displayed

AC2: Given user viewing product with 0 stock
     When user views product page
     Then "Add to Cart" button is disabled
     And "Out of Stock" message is displayed
     And notification signup option is shown

AC3: Given user adds item already in cart
     When user clicks "Add to Cart"
     Then cart quantity for that item is incremented by 1
     And cart total is updated
```

### Checkout Process
```
AC1: Given user has items in cart and valid payment method
     When user completes checkout
     Then order is created with "Pending" status
     And payment is processed
     And confirmation email is sent
     And user is redirected to order confirmation page

AC2: Given user has items in cart but payment fails
     When user completes checkout
     Then order is created with "Payment Failed" status
     And user sees error message with reason
     And cart is not cleared
     And user can retry payment

AC3: Given user has items in cart but one item became out of stock
     When user proceeds to checkout
     Then checkout is blocked
     And message "Item X is no longer available" is displayed
     And item is removed from cart
```

## Non-Functional Requirements

### Performance
```
AC1: Given 1000 concurrent users
     When users make API requests
     Then 95th percentile response time is less than 2 seconds
     And no requests fail due to timeout

AC2: Given database with 1M records
     When user performs search query
     Then results are returned in less than 1 second
     And pagination is responsive
```

### Security
```
AC1: Given user enters password
     When password is transmitted to server
     Then password is encrypted using TLS
     And password is hashed using bcrypt before storage

AC2: Given user attempts SQL injection in input field
     When form is submitted
     Then malicious input is sanitized
     And no SQL injection occurs
     And attempt is logged
```

### Usability
```
AC1: Given user on mobile device
     When user views application
     Then UI is responsive and fits screen width
     And all interactive elements are tappable (min 44x44px)
     And text is readable without zooming

AC2: Given user using screen reader
     When user navigates application
     Then all images have alt text
     And form fields have associated labels
     And keyboard navigation works for all interactive elements
```

## Edge Cases

### Empty States
```
AC1: Given new user with empty inbox
     When user views inbox
     Then empty state illustration is displayed
     And message "No messages yet" is shown
     And suggestion to compose first message is displayed
```

### Boundary Values
```
AC1: Given input field with max length of 100 characters
     When user enters exactly 100 characters
     Then input is accepted
     And no error is shown

AC2: Given input field with max length of 100 characters
     When user enters 101 characters
     Then only first 100 characters are accepted
     Or error message "Maximum 100 characters" is shown
```

### Concurrent Access
```
AC1: Given two users editing same record simultaneously
     When first user saves changes
     Then changes are saved
     And second user receives notification "Record updated by another user"
     And second user must refresh to see latest version
```

## Common Patterns

### CRUD Operations Template
```
CREATE:
- Given valid data, When submit, Then created and confirmed
- Given invalid data, When submit, Then error shown and not created
- Given duplicate, When submit, Then conflict error shown

READ:
- Given existing ID, When request, Then data returned
- Given non-existent ID, When request, Then 404 error
- Given unauthorized, When request, Then 401 error

UPDATE:
- Given valid changes, When submit, Then updated and confirmed
- Given invalid data, When submit, Then error shown and not updated
- Given stale data, When submit, Then conflict error shown

DELETE:
- Given existing ID, When delete, Then removed and confirmed
- Given non-existent ID, When delete, Then 404 error
- Given dependencies, When delete, Then error shown and not deleted
```
