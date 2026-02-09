# Explanation Examples

Real-world examples of effective code explanations.

## Example 1: Component Explanation

### Request
"Explain the UserRepository class"

### Response

```markdown
## Component: UserRepository

**Location**: `src/repositories/user_repository.py:15-89`

### Purpose
Handles all database operations for User entities. Acts as the single source of truth for user data persistence and retrieval.

### Context

**Problem Solved**:
Business logic (services) shouldn't know about database details. Repository pattern provides a clean interface for data operations.

**Design Rationale**:
Follows the Repository pattern used throughout this codebase. Separates domain logic from data access, making it easy to swap databases or add caching later.

**Tradeoffs**:
- **Chosen**: Clean separation, testability (can mock repository)
- **Sacrificed**: Slightly more code than direct DB calls, another layer to maintain

### Key Responsibilities

1. **CRUD Operations**
   - `create(user)` - Insert new user
   - `get_by_id(id)` - Fetch by primary key
   - `update(user)` - Modify existing user
   - `delete(id)` - Remove user

2. **Query Operations**
   - `find_by_email(email)` - Login lookups
   - `search(filters)` - Advanced queries with pagination

### Important Methods

#### `get_by_id(user_id: str) -> Optional[User]`
**Purpose**: Fetches a user by their unique ID
**When to use**: When you have the ID (e.g., from a JWT token)
**Example**:
```python
user = user_repo.get_by_id("123")
if user:
    print(user.name)
```

#### `find_by_email(email: str) -> Optional[User]`
**Purpose**: Looks up user by email address
**When to use**: During login, password reset
**Example**:
```python
user = user_repo.find_by_email("alice@example.com")
if user and user.verify_password(password):
    # Login successful
```

### Dependencies

**Requires**:
- `Database` - Connection pool and query execution
- `User` - Domain model for data mapping

**Used By**:
- `AuthService` - For login/registration
- `UserService` - For profile management
- `AdminService` - For user administration

### Example Usage

From `tests/repositories/test_user_repository.py:34`:
```python
def test_create_and_retrieve():
    # Create a user
    user = User(id="123", name="Alice", email="alice@example.com")
    repo.create(user)

    # Retrieve it
    retrieved = repo.get_by_id("123")
    assert retrieved.name == "Alice"
```

### Testing
**Test file**: `tests/repositories/test_user_repository.py`
**Key test cases**:
- Create/read/update/delete operations
- Query with filters and pagination
- Duplicate email handling (should raise)
- Not found cases return None

### Related
- **Similar pattern**: `PostRepository`, `CommentRepository` - all follow same structure
- **See also**: `BaseRepository` (lines 1-30) - shared query building logic
- **Next**: Explore `AuthService` to see how repositories are used in business logic
```

---

## Example 2: Flow Explanation

### Request
"Walk me through the login flow"

### Response

```markdown
## Flow: User Login

### Overview
User submits email and password via POST to `/auth/login`. System validates credentials, creates a session token (JWT), and returns it to the client for subsequent authenticated requests.

### Participants
- `LoginController` - Receives HTTP request
- `AuthService` - Orchestrates authentication logic
- `UserRepository` - Retrieves user data
- `TokenService` - Creates and signs JWT

### Step-by-Step

#### Step 1: Request Reception
**Location**: `src/routes/auth.py:23`
**Action**: HTTP POST received

```python
@router.post("/login")
def login(credentials: LoginRequest):
    return auth_service.authenticate(
        credentials.email,
        credentials.password
    )
```

**Explanation**: Route handler delegates to AuthService. No business logic here (controllers are thin).

#### Step 2: User Lookup
**Location**: `src/services/auth_service.py:45`
**Action**: Fetch user by email

```python
user = user_repository.find_by_email(email)
if not user:
    raise InvalidCredentialsError()
```

**Explanation**: Check if user exists. Don't reveal whether email or password was wrong (security - prevents email enumeration).

#### Step 3: Account Checks
**Location**: `src/services/auth_service.py:50-54`
**Action**: Verify account status

```python
if user.is_locked:
    raise AccountLockedError()
if not user.is_active:
    raise AccountDisabledError()
```

**Explanation**: Even if password is correct, locked/disabled accounts can't login. Added after 2023 security review.

#### Step 4: Password Verification
**Location**: `src/services/auth_service.py:57`
**Action**: Check password hash

```python
if not user.verify_password(password):
    user.increment_failed_attempts()
    raise InvalidCredentialsError()
```

**Transformation**: Password → bcrypt hash comparison

**Explanation**: Uses bcrypt (not plain text). Failed attempts incremented for rate limiting.

#### Step 5: Token Generation
**Location**: `src/services/auth_service.py:62`
**Action**: Create JWT token

```python
token = token_service.create_token(
    user_id=user.id,
    expires_in=settings.TOKEN_EXPIRY
)
```

**Explanation**: JWT contains user ID and expiration. Client stores this and sends it in future requests.

#### Step 6: Response
**Location**: `src/routes/auth.py:23`
**Action**: Return token to client

```python
return {
    "access_token": token,
    "token_type": "bearer",
    "expires_in": 3600
}
```

### Decision Points

**User exists?**
- If no: Return generic error (don't reveal email invalid)
- If yes: Continue to password check

**Account locked?**
- If yes: Return account locked error
- If no: Continue to password check

**Password correct?**
- If no: Increment failed attempts, return error
- If yes: Generate token and return

### Error Handling

All errors return 401 Unauthorized:
- Invalid email or password
- Account locked
- Account disabled

This prevents attackers from learning which emails are registered.

### Performance Considerations

- Password hashing is slow (by design - bcrypt ~100ms)
- User lookup uses database index on email (fast)
- Rate limiting at API gateway level (not shown here)

### Example Trace

**Scenario**: Alice logs in successfully

```
Input:
  email: alice@example.com
  password: "correct-password"

Step 1: POST /auth/login received
Step 2: UserRepository finds user ID=123 for alice@example.com
Step 3: Account checks pass (not locked, is active)
Step 4: Password hash matches ✓
Step 5: TokenService creates JWT: "eyJhbGc..."
Step 6: Return {"access_token": "eyJhbGc...", "expires_in": 3600}

Client stores token, uses in Authorization: Bearer eyJhbGc...
```

### Testing
**Test file**: `tests/services/test_auth_service.py:78-134`
**Coverage**:
- Successful login
- Invalid email
- Invalid password
- Locked account
- Disabled account
- Failed attempt tracking

### Related Flows
- **Similar to**: API key authentication (`/auth/api-key`)
- **Triggers**: Session creation, "last login" timestamp update
- **Triggered by**: Login form submission, mobile app login
```

---

## Example 3: Pattern Explanation

### Request
"What's the pattern with all these Service classes?"

### Response

```markdown
## Pattern: Service Layer

### Recognition

You'll know you're looking at the Service Layer pattern when you see:
- Classes named `*Service` (AuthService, UserService, etc.)
- Controllers/routes that delegate to services
- Services that orchestrate repositories and other services
- Business logic separated from HTTP/presentation concerns

**Examples in this codebase**:
- `src/services/auth_service.py` - Authentication and authorization
- `src/services/user_service.py` - User profile management
- `src/services/notification_service.py` - Email and push notifications
- `src/services/payment_service.py` - Payment processing

### Purpose

**Problem**:
Business logic shouldn't be in controllers (hard to test, couples to HTTP) or repositories (mixes domain logic with data access).

**Solution**:
Separate layer that contains business rules, coordinates repositories, and can be used by multiple interfaces (HTTP API, CLI, background jobs).

### Structure

```
Controller (routes)
    ↓ delegates to
Service (business logic)
    ↓ uses
Repository (data access)
    ↓ queries
Database
```

**Key Elements**:
1. **Controllers** - Thin, handle HTTP concerns (parsing, status codes)
2. **Services** - Thick, contain all business logic and validation
3. **Repositories** - Data access only, no business rules

### Implementation

**In this codebase**:

```python
# Controller: routes/user.py
@router.post("/users")
def create_user(request: CreateUserRequest):
    # No logic here, just delegate
    user = user_service.create(request)
    return {"id": user.id}

# Service: services/user_service.py
class UserService:
    def create(self, request):
        # Business logic here
        if not self._is_valid_email(request.email):
            raise ValidationError("Invalid email")

        # Check business rules
        if user_repo.email_exists(request.email):
            raise ConflictError("Email taken")

        # Coordinate multiple operations
        user = User(**request.dict())
        user_repo.create(user)
        email_service.send_welcome(user.email)

        return user
```

**Variations**:
- Some services are thin (just delegate to repository)
- Complex services orchestrate multiple repositories
- Services can call other services (e.g., UserService → EmailService)

### Advantages

- **Testability**: Can test business logic without HTTP layer
- **Reusability**: Same service used by API, CLI, background jobs
- **Separation**: HTTP concerns ≠ business logic ≠ data access
- **Maintainability**: Logic grouped by domain (users, payments, etc.)

### Cautions

**When to use**:
- Applications with business logic (not just CRUD)
- Multiple interfaces to same logic (API + CLI + jobs)
- Need to test business rules without HTTP

**When to avoid**:
- Very simple CRUD apps (might be overkill)
- Extremely high performance needs (extra layer adds minimal overhead)

### Evolution

**v1.0**: Business logic in controllers
- Problem: Hard to test, duplicated in CLI

**v2.0**: Introduced service layer
- Migration: Moved logic from controllers to services
- Result: Tests became faster, CLI reused API logic

**v3.0** (current): Added base service class
- Shared utilities (logging, error handling)
- Consistent patterns across all services

### Related Patterns
- **Alternative**: Transaction Script (simpler, no layer separation)
- **Combines with**: Repository Pattern (services use repositories)
- **See also**: Domain-Driven Design (services can contain domain logic)
```

---

## Key Takeaways

### Good Explanations

1. **Start with purpose** - What does this do?
2. **Provide context** - Why does this exist?
3. **Show mechanics** - How does it work?
4. **Include examples** - Concrete instances
5. **Connect concepts** - Related patterns/components
6. **Suggest next steps** - What to explore next

### Common Pitfalls

- **Too abstract**: "This handles business logic" (not helpful)
- **Too detailed**: Line-by-line of 200 lines (overwhelming)
- **No context**: Explains "how" without "why"
- **Jargon-heavy**: Uses terms without defining them

### Context Adaptation

- **For beginners**: More background, simpler analogies
- **For experts**: Focus on novel/unique aspects
- **For debugging**: Emphasize state changes and edge cases
- **For modification**: Show extension points and test coverage
