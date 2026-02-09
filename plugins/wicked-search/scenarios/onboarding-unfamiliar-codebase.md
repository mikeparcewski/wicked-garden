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

## Scenario: New Developer's First Day

You're a new developer joining the team. You need to understand the codebase and implement a new feature.

## Steps

### Phase 1: Quick Reconnaissance (NO INDEX)

1. Get a quick overview of patterns:
   ```
   /wicked-search:scout error-handling
   /wicked-search:scout test-patterns
   /wicked-search:scout api-endpoints
   ```

2. Assess: "Is there test coverage? How's error handling?"

### Phase 2: Deep Understanding (BUILD INDEX)

3. Index the entire project:
   ```
   /wicked-search:index /tmp/onboarding-demo
   ```

4. Check index statistics:
   ```
   /wicked-search:stats
   ```

### Phase 3: Understand Requirements

5. Search documentation for "User Management":
   ```
   /wicked-search:docs "User Management"
   ```

6. Find what code implements user management:
   ```
   /wicked-search:impl "User Management"
   ```

7. Explore the UserService class:
   ```
   /wicked-search:refs UserService
   ```

### Phase 4: Understand Architecture

8. Trace API endpoint to implementation:
   ```
   /wicked-search:code UserAPI
   ```

9. Understand dependencies of UserAPI:
   ```
   /wicked-search:blast-radius UserAPI
   ```

10. See what uses AuthService:
    ```
    /wicked-search:refs AuthService
    ```

### Phase 5: Feature Implementation Planning

**Task**: Implement password reset functionality

11. Find existing auth-related code:
    ```
    /wicked-search:code "auth"
    ```

12. Check API spec for related endpoints:
    ```
    /wicked-search:docs "api"
    ```

13. Understand UserService dependencies:
    ```
    /wicked-search:blast-radius UserService
    ```

## Expected Outcome

### After Scout (30 seconds):
- Overview of codebase structure
- Test coverage assessment
- Error handling patterns identified

### After Indexing (1-2 minutes):
- Full knowledge graph built
- All symbols indexed
- Cross-references detected

### After Exploration (5-10 minutes):
- Understand: User Management → UserService → UserAPI flow
- Understand: AuthService generates tokens
- Understand: UserRepository handles persistence
- See: Full dependency graph

### Feature Implementation (10+ minutes):
- Know where to add password reset logic
- See all related components
- Understand blast radius of changes
- Identify which docs need updating

## Success Criteria

- [ ] Scout commands run without index in <5 seconds
- [ ] Index completes and stats show file/symbol counts
- [ ] Can trace from requirements doc to implementing code
- [ ] Can trace from API spec to API implementation
- [ ] Cross-references link docs to code symbols
- [ ] Blast radius shows component dependencies
- [ ] Can navigate full stack: API → Service → Repository
- [ ] Understand where to add new feature (password reset)

## Value Demonstrated

**Problem solved**: Onboarding to unfamiliar codebases is slow and frustrating. Developers spend days reading code, asking questions, and making wrong assumptions.

**Traditional onboarding** (2-3 days):
1. Read README (incomplete)
2. Grep through code randomly
3. Ask senior developers questions
4. Read code files sequentially
5. Make mental notes (forget by tomorrow)
6. Still confused about architecture

**With wicked-search** (2-3 hours):

**Hour 1 - Reconnaissance**:
- Scout patterns: Get code structure overview
- Index project: Build knowledge graph
- Read requirements: Understand what system does

**Hour 2 - Deep Dive**:
- Trace requirements → implementation
- Follow API → Service → Repository
- Understand component relationships
- See actual code structure

**Hour 3 - Feature Work**:
- Find similar features
- Check blast radius
- Implement confidently
- Know what to test

**Real-world impact**:

**Scenario 1: Bug fix assigned**
- Old way: "Where's the auth code?" → 30 minutes of searching
- New way: `/code AuthService` → found in 5 seconds

**Scenario 2: Understanding feature**
- Old way: Read 10 files, still confused about flow
- New way: `/impl "User Management"` → see entire stack

**Scenario 3: Adding new endpoint**
- Old way: Copy-paste from similar endpoint, hope it's correct
- New way: `/blast-radius UserAPI` → understand impact before coding

**Scenario 4: Documentation questions**
- Old way: "Does this match the spec?" → read docs, read code, compare
- New way: `/refs UserService` → see which docs mention it automatically

**Metrics**:
- Time to first commit: 3 days → 4 hours
- Questions to senior devs: 20+ → 5
- Wrong assumptions: Many → Few
- Confidence level: Low → High

The plugin transforms onboarding from "survival mode" to "productive contributor" in hours instead of days.
