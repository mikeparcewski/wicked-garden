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

1. **Index the project:**
   ```
   /wicked-garden:search:index /tmp/wicked-xref-test
   ```

2. **Check import relationships:**
   ```
   /wicked-garden:search:refs UserRepository
   ```
   Should show: user_service.py imports UserRepository

3. **Check inheritance relationships:**
   ```
   /wicked-garden:search:refs BaseRepository
   ```
   Should show: UserRepository inherits from BaseRepository

4. **Check call relationships:**
   ```
   /wicked-garden:search:refs log_operation
   ```
   Should show: get_by_id and find_active_users call log_operation

5. **Check class-method (defines) relationships:**
   ```
   /wicked-garden:search:refs get_by_id
   ```
   Should show: UserRepository defines get_by_id

6. **Check documentation cross-references:**
   ```
   /wicked-garden:search:refs BaseRepository
   ```
   Should also show: architecture.md documents BaseRepository

7. **Find implementations from docs:**
   ```
   /wicked-garden:search:impl "Repository Layer"
   ```

## Expected Outcome

### Import Relationships:
```
user_repo.py --imports--> base.py
user_repo.py --imports_symbol--> BaseRepository
user_repo.py --imports_symbol--> log_operation
user_service.py --imports--> user_repo.py
user_service.py --imports_symbol--> UserRepository
```

### Inheritance Relationships:
```
UserRepository --inherits--> BaseRepository
```

### Call Relationships:
```
get_by_id --calls--> log_operation
get_by_id --calls--> connect
get_by_id --calls--> disconnect
find_active_users --calls--> log_operation
get_user --calls--> get_by_id
list_active --calls--> find_active_users
```

### Defines Relationships:
```
BaseRepository --defines--> connect
BaseRepository --defines--> disconnect
UserRepository --defines--> get_by_id
UserRepository --defines--> find_active_users
UserService --defines--> get_user
UserService --defines--> list_active
```

### Documentation References:
```
architecture.md --documents--> BaseRepository
architecture.md --documents--> UserRepository
architecture.md --documents--> UserService
architecture.md --documents--> log_operation
```

## Success Criteria

- [ ] Import relationships detected between files
- [ ] Import symbol relationships link to specific classes/functions
- [ ] Inheritance relationships detected (UserRepository → BaseRepository)
- [ ] Call relationships detected within methods
- [ ] Class-method (defines) relationships detected
- [ ] Documentation references detected (backticks, function calls)
- [ ] `/refs` shows all relationship types for a symbol
- [ ] Bidirectional navigation works (code ↔ docs)

## Value Demonstrated

**Problem solved**: Understanding code dependencies requires manual tracing through imports, inheritance chains, and call graphs. Documentation quickly becomes disconnected from actual code structure.

**Relationship types detected automatically:**

| Type | Example | Use Case |
|------|---------|----------|
| imports | file → file | Dependency analysis |
| imports_symbol | file → class/function | Specific symbol usage |
| inherits | class → class | Class hierarchy |
| calls | function → function | Call graph analysis |
| defines | class → method | Class structure |
| documents | doc → code | Code-doc traceability |

**Real-world applications:**
- **Refactoring**: Know what breaks when you change a class
- **Onboarding**: Trace from docs to implementation
- **Impact analysis**: See all downstream effects of a change
- **Documentation audit**: Find undocumented code
