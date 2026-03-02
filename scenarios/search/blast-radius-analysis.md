---
name: blast-radius-analysis
title: Impact Analysis Before Refactoring
description: Analyze dependencies and dependents to assess refactoring risk
type: workflow
difficulty: advanced
estimated_minutes: 15
---

# Impact Analysis Before Refactoring

## Setup

Create a codebase with interconnected classes demonstrating inheritance, method calls, and imports:

```bash
# Create test directory
mkdir -p /tmp/wicked-blast-test/src
mkdir -p /tmp/wicked-blast-test/docs

# Core infrastructure with base class
cat > /tmp/wicked-blast-test/src/database.py << 'EOF'
class DatabaseConnection:
    """Core database connection."""

    def connect(self):
        pass

    def disconnect(self):
        pass

    def query(self, sql: str):
        pass

class QueryBuilder:
    """Builds SQL queries."""

    def __init__(self, connection: DatabaseConnection):
        self.connection = connection

    def select(self, table: str):
        self.connection.query(f"SELECT * FROM {table}")
EOF

# Base repository class
cat > /tmp/wicked-blast-test/src/base_repo.py << 'EOF'
from database import DatabaseConnection, QueryBuilder

class BaseRepository:
    """Base repository with common operations."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.query_builder = QueryBuilder(db)

    def connect(self):
        self.db.connect()

    def disconnect(self):
        self.db.disconnect()
EOF

# Repository layer that inherits from BaseRepository
cat > /tmp/wicked-blast-test/src/repositories.py << 'EOF'
from base_repo import BaseRepository

class UserRepository(BaseRepository):
    """User data access."""

    def find_by_id(self, user_id: int):
        self.connect()
        result = self.query_builder.select("users")
        self.disconnect()
        return result

class OrderRepository(BaseRepository):
    """Order data access."""

    def find_by_user(self, user_id: int):
        self.connect()
        result = self.query_builder.select("orders")
        self.disconnect()
        return result
EOF

# Service layer that uses repositories
cat > /tmp/wicked-blast-test/src/services.py << 'EOF'
from repositories import UserRepository, OrderRepository

class UserService:
    """User business logic."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def get_user(self, user_id: int):
        return self.user_repo.find_by_id(user_id)

class OrderService:
    """Order business logic."""

    def __init__(self, order_repo: OrderRepository):
        self.order_repo = order_repo

    def get_user_orders(self, user_id: int):
        return self.order_repo.find_by_user(user_id)
EOF

# API layer that uses services
cat > /tmp/wicked-blast-test/src/api.py << 'EOF'
from services import UserService, OrderService

class UserAPI:
    """User API endpoints."""

    def __init__(self, user_service: UserService, order_service: OrderService):
        self.user_service = user_service
        self.order_service = order_service

    def get_user_profile(self, user_id: int):
        user = self.user_service.get_user(user_id)
        orders = self.order_service.get_user_orders(user_id)
        return {"user": user, "orders": orders}
EOF

# Documentation that references code
cat > /tmp/wicked-blast-test/docs/architecture.md << 'EOF'
# Architecture

## Database Layer

The `DatabaseConnection` class handles raw database operations:
- `connect()` - establishes connection
- `disconnect()` - closes connection
- `query()` - executes SQL

The `QueryBuilder` wraps SQL query construction.

## Repository Layer

All repositories inherit from `BaseRepository` which provides:
- Connection management via `connect()` and `disconnect()`
- Query building via `QueryBuilder`

Implementations:
- `UserRepository` - user data access
- `OrderRepository` - order data access

## Service Layer

Business logic lives in `UserService` and `OrderService`.

## API Layer

`UserAPI` exposes endpoints to external clients.
EOF
```

## Steps

1. Index the project:
   ```
   /wicked-garden:search:index /tmp/wicked-blast-test
   ```

2. Analyze blast radius of DatabaseConnection (core infrastructure):
   ```
   /wicked-garden:search:blast-radius DatabaseConnection
   ```

3. Analyze blast radius of UserService (high-level service):
   ```
   /wicked-garden:search:blast-radius UserService
   ```

4. Analyze blast radius with deeper traversal:
   ```
   /wicked-garden:search:blast-radius DatabaseConnection --depth 3
   ```

## Expected Outcomes

- DatabaseConnection has a wide blast radius: changes propagate through QueryBuilder, BaseRepository, UserRepository, OrderRepository, UserService, OrderService, and UserAPI
- UserService has a narrow blast radius: only UserAPI directly depends on it
- Depth parameter controls how many layers of transitive dependents are shown
- Both dependencies (what a symbol uses) and dependents (what uses it) are reported
- Documentation references from architecture.md included in analysis
- Core infrastructure components show higher risk than high-level services

## Success Criteria

- [ ] Blast radius analysis runs for each queried symbol
- [ ] DatabaseConnection shows wide impact across multiple layers (repos, services, API)
- [ ] UserService shows narrow impact (only UserAPI depends on it)
- [ ] Both direct and transitive dependents identified
- [ ] Depth parameter controls traversal depth
- [ ] Dependencies (what the symbol uses) correctly identified
- [ ] Documentation references included in blast radius
- [ ] Impact assessment reflects actual coupling level

## Value Demonstrated

**Problem solved**: Developers fear refactoring because they cannot assess the risk. "What will break if I change this?" requires manual code archaeology.

**Why this matters**:
- **Pre-refactoring risk assessment**: See that DatabaseConnection impacts 6+ classes before touching it
- **Safe incremental changes**: Confirm UserService has only 1 dependent, make the change confidently
- **Technical debt prioritization**: Identify which components have the widest impact
- **Test planning**: Blast radius shows exactly what needs testing after a change
