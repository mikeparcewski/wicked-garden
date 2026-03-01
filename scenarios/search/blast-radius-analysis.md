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
   /wicked-search:index /tmp/wicked-blast-test
   ```

2. Analyze blast radius of DatabaseConnection (core infrastructure):
   ```
   /wicked-search:blast-radius DatabaseConnection
   ```

3. Analyze blast radius of QueryBuilder (mid-level utility):
   ```
   /wicked-search:blast-radius QueryBuilder
   ```

4. Analyze blast radius of UserService (high-level service):
   ```
   /wicked-search:blast-radius UserService
   ```

5. Compare with deeper analysis:
   ```
   /wicked-search:blast-radius DatabaseConnection --depth 3
   ```

## Expected Outcome

### Relationship Graph (from indexing):
```
Import relationships:
base_repo.py --imports--> database.py
base_repo.py --imports_symbol--> DatabaseConnection
base_repo.py --imports_symbol--> QueryBuilder
repositories.py --imports--> base_repo.py
repositories.py --imports_symbol--> BaseRepository
services.py --imports--> repositories.py
api.py --imports--> services.py

Inheritance relationships:
UserRepository --inherits--> BaseRepository
OrderRepository --inherits--> BaseRepository

Call relationships:
QueryBuilder.select --calls--> query
BaseRepository.connect --calls--> connect (DatabaseConnection)
UserRepository.find_by_id --calls--> connect, select, disconnect
UserService.get_user --calls--> find_by_id
UserAPI.get_user_profile --calls--> get_user, get_user_orders

Defines relationships:
DatabaseConnection --defines--> connect, disconnect, query
BaseRepository --defines--> connect, disconnect
UserRepository --defines--> find_by_id
UserService --defines--> get_user

Documentation references:
architecture.md --documents--> DatabaseConnection, QueryBuilder
architecture.md --documents--> BaseRepository, UserRepository, OrderRepository
architecture.md --documents--> UserService, OrderService, UserAPI
```

### DatabaseConnection Analysis:
```
Blast Radius for: DatabaseConnection

Dependencies (what it uses):
[None - leaf node]

Dependents (what uses it):
Direct (depth 1):
- QueryBuilder (imports_symbol)
- BaseRepository (via QueryBuilder)

Indirect (depth 2):
- UserRepository (inherits BaseRepository)
- OrderRepository (inherits BaseRepository)

Indirect (depth 3):
- UserService, OrderService (imports)
- UserAPI (imports)

Documentation:
- architecture.md (documents)

Impact Assessment: HIGH RISK
- Core infrastructure component
- 6+ transitive dependents
- Changes propagate to all layers
```

### BaseRepository Analysis:
```
Blast Radius for: BaseRepository

Dependencies (what it uses):
- DatabaseConnection (imports_symbol)
- QueryBuilder (imports_symbol)

Dependents (what uses it):
Direct:
- UserRepository (inherits)
- OrderRepository (inherits)

Indirect:
- UserService, OrderService, UserAPI

Documentation:
- architecture.md (documents)

Impact Assessment: HIGH RISK
- Inheritance means changes affect all subclasses
- Method changes (connect/disconnect) affect all repositories
```

### UserService Analysis:
```
Blast Radius for: UserService

Dependencies (what it uses):
- UserRepository (imports_symbol)

Dependents (what uses it):
- UserAPI (imports_symbol, calls get_user)

Documentation:
- architecture.md (documents)

Impact Assessment: LOW RISK
- 1 direct dependent
- High-level service, limited blast radius
```

## Success Criteria

- [ ] Blast radius analysis runs for each symbol
- [ ] Import relationships detected (file → file, symbol → symbol)
- [ ] Inheritance relationships detected (subclass → superclass)
- [ ] Call relationships detected (method → method across classes)
- [ ] Defines relationships detected (class → method)
- [ ] Documentation references detected (doc → code symbols)
- [ ] Dependencies correctly identified (what the symbol uses)
- [ ] Direct dependents correctly identified (depth 1)
- [ ] Indirect dependents correctly identified (depth 2+)
- [ ] Depth parameter controls traversal depth
- [ ] Impact assessment reflects actual coupling
- [ ] Core components show wider blast radius than high-level services
- [ ] Results include file locations and relationship types

## Value Demonstrated

**Problem solved**: Developers fear refactoring because they can't assess the risk. Questions like "What will break if I change this?" require manual code archaeology.

**Why this matters**:

**Pre-refactoring risk assessment**:
- Question: "Should I refactor DatabaseConnection?"
- Run: `/blast-radius DatabaseConnection`
- See: 6 dependent classes across 4 files
- Decision: High risk - needs careful planning and testing

**Safe incremental changes**:
- Question: "Can I safely change UserService?"
- Run: `/blast-radius UserService`
- See: 1 dependent (UserAPI)
- Decision: Low risk - make the change confidently

**Technical debt prioritization**:
- Run blast radius on core utilities
- Identify: Which components have the widest impact
- Prioritize: Improve high-blast-radius components first

**Onboarding safety**:
- New dev: "Can I change this function?"
- Run: `/blast-radius FunctionName`
- Learn: Impact scope before making changes
- Result: Confident contributions without fear

**Real-world scenarios**:

1. **Database migration**: Changing DatabaseConnection → see all affected code
2. **API redesign**: Changing UserAPI → minimal blast radius, safe to refactor
3. **Breaking change assessment**: Quantify impact before making breaking changes
4. **Test planning**: Blast radius shows what needs testing

The analysis prevents "change paralysis" by making impact visible and quantifiable.
