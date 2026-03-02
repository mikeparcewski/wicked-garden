---
name: onboarding-unfamiliar-codebase
title: Onboarding to an Unfamiliar Codebase
description: Complete workflow for understanding a new codebase using wicked-search
type: workflow
difficulty: advanced
estimated_minutes: 20
---

# Onboarding to an Unfamiliar Codebase

## Setup

Create a realistic project structure with requirements doc, API spec, and implementation:

```bash
# Create project structure
mkdir -p /tmp/onboarding-demo/docs
mkdir -p /tmp/onboarding-demo/src/{api,services,repositories,models}
mkdir -p /tmp/onboarding-demo/tests

# Requirements document
cat > /tmp/onboarding-demo/docs/requirements.md << 'EOF'
# E-Commerce Platform Requirements

## User Management
Users register with email/password. The UserService handles registration
and the AuthService manages authentication with JWT tokens.

## Product Catalog
Products are managed through ProductService. The ProductRepository
provides database access. Support for categories via CategoryService.

## Order Processing
Orders created through OrderService. Payment processing via PaymentGateway.
Order status tracking with OrderTracker.
EOF

# API specification
cat > /tmp/onboarding-demo/docs/api-spec.md << 'EOF'
# API Specification

## POST /api/users/register
Register new user via UserAPI
- Input: email, password
- Returns: user_id, token

## GET /api/products
List products via ProductAPI
- Optional: category filter
- Returns: product list

## POST /api/orders
Create order via OrderAPI
- Input: product_ids, payment_info
- Returns: order_id, status
EOF

# Implementation files
cat > /tmp/onboarding-demo/src/models/user.py << 'EOF'
class User:
    def __init__(self, email: str):
        self.email = email
        self.id = None
EOF

cat > /tmp/onboarding-demo/src/repositories/user_repository.py << 'EOF'
from models.user import User

class UserRepository:
    def save(self, user: User):
        pass

    def find_by_email(self, email: str):
        pass
EOF

cat > /tmp/onboarding-demo/src/services/auth_service.py << 'EOF'
import jwt

class AuthService:
    def generate_token(self, user_id: int) -> str:
        return jwt.encode({"user_id": user_id}, "secret")

    def verify_token(self, token: str):
        return jwt.decode(token, "secret")
EOF

cat > /tmp/onboarding-demo/src/services/user_service.py << 'EOF'
from repositories.user_repository import UserRepository
from models.user import User

class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def register_user(self, email: str, password: str):
        user = User(email)
        return self.repo.save(user)
EOF

cat > /tmp/onboarding-demo/src/api/user_api.py << 'EOF'
from services.user_service import UserService
from services.auth_service import AuthService

class UserAPI:
    def __init__(self, user_service: UserService, auth_service: AuthService):
        self.user_service = user_service
        self.auth_service = auth_service

    def register(self, email: str, password: str):
        user = self.user_service.register_user(email, password)
        token = self.auth_service.generate_token(user.id)
        return {"user_id": user.id, "token": token}
EOF

cat > /tmp/onboarding-demo/src/services/product_service.py << 'EOF'
class ProductService:
    def list_products(self, category=None):
        pass

class CategoryService:
    def get_categories(self):
        pass
EOF

cat > /tmp/onboarding-demo/src/repositories/product_repository.py << 'EOF'
class ProductRepository:
    def find_all(self):
        pass

    def find_by_category(self, category_id: int):
        pass
EOF

cat > /tmp/onboarding-demo/src/api/product_api.py << 'EOF'
from services.product_service import ProductService

class ProductAPI:
    def __init__(self, product_service: ProductService):
        self.product_service = product_service

    def list_products(self, category=None):
        return self.product_service.list_products(category)
EOF
```

## Steps

### Phase 1: Quick Reconnaissance (no index needed)

1. Scout for API endpoint patterns:
   ```
   /wicked-garden:search:scout api --path /tmp/onboarding-demo
   ```

2. Scout for test patterns:
   ```
   /wicked-garden:search:scout test --path /tmp/onboarding-demo
   ```

3. Scout for database patterns:
   ```
   /wicked-garden:search:scout db --path /tmp/onboarding-demo
   ```

### Phase 2: Build Index

4. Index the entire project:
   ```
   /wicked-garden:search:index /tmp/onboarding-demo
   ```

5. Check index statistics:
   ```
   /wicked-garden:search:stats
   ```

### Phase 3: Understand Requirements

6. Search documentation for "User Management":
   ```
   /wicked-garden:search:docs "User Management"
   ```

7. Find what code implements user management:
   ```
   /wicked-garden:search:impl "User Management"
   ```

8. Explore the UserService class references:
   ```
   /wicked-garden:search:refs UserService
   ```

### Phase 4: Understand Architecture

9. Find UserAPI implementation:
   ```
   /wicked-garden:search:code UserAPI
   ```

10. Understand dependencies of UserAPI:
    ```
    /wicked-garden:search:blast-radius UserAPI
    ```

11. See what uses AuthService:
    ```
    /wicked-garden:search:refs AuthService
    ```

### Phase 5: Plan a New Feature

12. Find existing auth-related code:
    ```
    /wicked-garden:search:code "auth"
    ```

13. Understand UserService dependencies before adding password reset:
    ```
    /wicked-garden:search:blast-radius UserService
    ```

## Expected Outcomes

- Scout commands run immediately without an index and reveal project structure (API patterns, test coverage gaps, database patterns)
- After indexing, stats show accurate file and symbol counts for the entire project
- Documentation search finds the User Management section in requirements.md
- Implementation search traces User Management to UserService, AuthService, and related classes
- References show where UserService is imported and used across the codebase
- Code search finds UserAPI and its full implementation
- Blast radius of UserAPI reveals its dependency chain (UserService, AuthService, UserRepository)
- Blast radius of UserService shows its narrower scope, informing where to add password reset logic
- The full workflow demonstrates progressive understanding: scout, index, explore, plan

## Success Criteria

- [ ] Scout commands run without an index
- [ ] Index completes and stats report accurate file/symbol counts
- [ ] Can trace from requirements document to implementing code
- [ ] Can trace from API spec to API implementation classes
- [ ] Cross-references link documentation mentions to code symbols
- [ ] Blast radius reveals component dependency chains
- [ ] Full stack navigation works: API to Service to Repository to Model
- [ ] Enough information gathered to confidently plan a new feature (password reset)

## Value Demonstrated

**Problem solved**: Onboarding to unfamiliar codebases is slow and frustrating. Developers spend days reading code, asking questions, and making wrong assumptions.

**Why this matters**:

**Traditional onboarding** (2-3 days):
1. Read README (incomplete)
2. Grep through code randomly
3. Ask senior developers questions
4. Read code files sequentially
5. Still confused about architecture

**With wicked-search** (2-3 hours):
- **Hour 1**: Scout patterns for structure overview, index project, read requirements
- **Hour 2**: Trace requirements to implementation, follow API to Service to Repository chains
- **Hour 3**: Find similar features, check blast radius, implement confidently

The plugin transforms onboarding from "survival mode" to "productive contributor" in hours instead of days.
