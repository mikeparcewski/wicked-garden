---
name: cross-reference-detection
title: Automatic Cross-Reference Detection
description: Detect imports, calls, inheritance, and doc references automatically
type: feature
difficulty: intermediate
estimated_minutes: 8
---

# Automatic Cross-Reference Detection

Test the full range of cross-reference detection: imports, function calls, class inheritance, class-method relationships, and documentation references.

## Setup

Create a multi-file codebase with various relationship types:

```bash
# Create test directory
mkdir -p /tmp/wicked-xref-test/src
mkdir -p /tmp/wicked-xref-test/docs

# Base class with methods
cat > /tmp/wicked-xref-test/src/base.py << 'EOF'
class BaseRepository:
    """Base repository with common operations."""

    def connect(self):
        """Establish database connection."""
        pass

    def disconnect(self):
        """Close database connection."""
        pass

def log_operation(operation: str):
    """Log a repository operation."""
    print(f"Operation: {operation}")
EOF

# Derived class that imports and inherits
cat > /tmp/wicked-xref-test/src/user_repo.py << 'EOF'
from base import BaseRepository, log_operation

class UserRepository(BaseRepository):
    """Repository for user data."""

    def get_by_id(self, user_id: int):
        log_operation("get_by_id")
        self.connect()
        # fetch user
        self.disconnect()
        return {"id": user_id}

    def find_active_users(self):
        log_operation("find_active_users")
        return []
EOF

# Service that uses the repository
cat > /tmp/wicked-xref-test/src/user_service.py << 'EOF'
from user_repo import UserRepository

class UserService:
    """Service layer for user operations."""

    def __init__(self):
        self.repo = UserRepository()

    def get_user(self, user_id: int):
        return self.repo.get_by_id(user_id)

    def list_active(self):
        return self.repo.find_active_users()
EOF

# Documentation that references code
cat > /tmp/wicked-xref-test/docs/architecture.md << 'EOF'
# System Architecture

## Repository Layer

The `BaseRepository` class provides common database operations:
- `connect()` establishes the connection
- `disconnect()` closes the connection

The `UserRepository` extends BaseRepository for user-specific queries.

## Service Layer

The `UserService` class provides business logic on top of repositories.

## Logging

All operations are logged via `log_operation()`.
EOF
```

## Steps

1. Index the project:
   ```
   /wicked-garden:search:index /tmp/wicked-xref-test
   ```

2. Find all references to UserRepository:
   ```
   /wicked-garden:search:refs UserRepository
   ```

3. Find all references to BaseRepository:
   ```
   /wicked-garden:search:refs BaseRepository
   ```

4. Find all references to log_operation:
   ```
   /wicked-garden:search:refs log_operation
   ```

5. Find all references to get_by_id:
   ```
   /wicked-garden:search:refs get_by_id
   ```

6. Find implementations for the Repository Layer doc section:
   ```
   /wicked-garden:search:impl "Repository Layer"
   ```

## Expected Outcomes

- Import relationships detected: user_repo.py imports from base.py, user_service.py imports from user_repo.py
- Inheritance detected: UserRepository extends BaseRepository
- Call relationships detected: get_by_id calls log_operation, connect, disconnect; get_user calls get_by_id
- Class-method (defines) relationships detected: BaseRepository defines connect/disconnect, UserRepository defines get_by_id/find_active_users
- Documentation references detected: architecture.md mentions BaseRepository, UserRepository, UserService, log_operation
- Bidirectional navigation works: code symbols link to docs and docs link back to code

## Success Criteria

- [ ] Import relationships detected between files (user_repo.py to base.py, user_service.py to user_repo.py)
- [ ] Symbol-level import relationships link to specific classes and functions
- [ ] Inheritance relationship detected (UserRepository extends BaseRepository)
- [ ] Call relationships detected within methods (log_operation calls, connect/disconnect calls)
- [ ] Class-method (defines) relationships detected for all classes
- [ ] Documentation references detected from architecture.md to code symbols
- [ ] `/refs` returns all relationship types for a given symbol
- [ ] Bidirectional navigation works (code to docs and docs to code)

## Value Demonstrated

**Problem solved**: Understanding code dependencies requires manual tracing through imports, inheritance chains, and call graphs. Documentation quickly becomes disconnected from actual code structure.

**Real-world applications:**
- **Refactoring**: Know what breaks when you change a class
- **Onboarding**: Trace from docs to implementation
- **Impact analysis**: See all downstream effects of a change
- **Documentation audit**: Find undocumented code
