---
name: blast-radius-analysis
title: Impact Analysis Before Refactoring
description: Analyze dependencies and dependents to assess refactoring risk
type: workflow
difficulty: advanced
estimated_minutes: 15
timeout: 300
execution: manual
---

# Impact Analysis Before Refactoring

## Setup

Create a codebase with interconnected classes and index it:

```bash
mkdir -p /tmp/wicked-blast-test/src /tmp/wicked-blast-test/docs

cat > /tmp/wicked-blast-test/src/database.py << 'EOF'
class DatabaseConnection:
    def connect(self): pass
    def disconnect(self): pass
    def query(self, sql: str): pass

class QueryBuilder:
    def __init__(self, connection: DatabaseConnection):
        self.connection = connection
    def select(self, table: str):
        self.connection.query(f"SELECT * FROM {table}")
EOF

cat > /tmp/wicked-blast-test/src/base_repo.py << 'EOF'
from database import DatabaseConnection, QueryBuilder
class BaseRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.query_builder = QueryBuilder(db)
    def connect(self): self.db.connect()
    def disconnect(self): self.db.disconnect()
EOF

cat > /tmp/wicked-blast-test/src/repositories.py << 'EOF'
from base_repo import BaseRepository
class UserRepository(BaseRepository):
    def find_by_id(self, user_id: int):
        self.connect(); result = self.query_builder.select("users"); self.disconnect(); return result
class OrderRepository(BaseRepository):
    def find_by_user(self, user_id: int):
        self.connect(); result = self.query_builder.select("orders"); self.disconnect(); return result
EOF

cat > /tmp/wicked-blast-test/src/services.py << 'EOF'
from repositories import UserRepository, OrderRepository
class UserService:
    def __init__(self, user_repo: UserRepository): self.user_repo = user_repo
    def get_user(self, user_id: int): return self.user_repo.find_by_id(user_id)
class OrderService:
    def __init__(self, order_repo: OrderRepository): self.order_repo = order_repo
    def get_user_orders(self, user_id: int): return self.order_repo.find_by_user(user_id)
EOF

cat > /tmp/wicked-blast-test/src/api.py << 'EOF'
from services import UserService, OrderService
class UserAPI:
    def __init__(self, user_service: UserService, order_service: OrderService):
        self.user_service = user_service; self.order_service = order_service
    def get_user_profile(self, user_id: int):
        return {"user": self.user_service.get_user(user_id), "orders": self.order_service.get_user_orders(user_id)}
EOF

cat > /tmp/wicked-blast-test/docs/architecture.md << 'EOF'
# Architecture
DatabaseConnection handles raw db ops. QueryBuilder wraps SQL construction.
All repositories inherit from BaseRepository. UserService and OrderService hold business logic.
UserAPI exposes endpoints to external clients.
EOF
```

Then index the project (this may take a moment):

```
/wicked-garden:search:index /tmp/wicked-blast-test
```

Confirm the index completes successfully before proceeding.

## Steps

1. Analyze blast radius of `DatabaseConnection` (core infrastructure):
   ```
   /wicked-garden:search:blast-radius DatabaseConnection
   ```

2. Analyze blast radius of `UserService` (high-level service):
   ```
   /wicked-garden:search:blast-radius UserService
   ```

3. Analyze blast radius with deeper traversal:
   ```
   /wicked-garden:search:blast-radius DatabaseConnection --depth 3
   ```

## Expected Outcomes

- `DatabaseConnection` shows wide impact: QueryBuilder, BaseRepository, UserRepository, OrderRepository, UserService, OrderService, UserAPI
- `UserService` shows narrow impact: only UserAPI depends on it
- `--depth 3` expands transitive dependents beyond the default depth
- Both dependencies and dependents are reported for each symbol

## Success Criteria

- [ ] Blast radius analysis completes for each queried symbol
- [ ] `DatabaseConnection` shows impact across multiple layers (repos, services, API)
- [ ] `UserService` shows narrow impact (only UserAPI)
- [ ] Depth parameter controls traversal depth
- [ ] Documentation references included in analysis

## Value Demonstrated

**Problem solved**: Developers cannot assess refactoring risk without manual code archaeology.

- Pre-refactoring: see that `DatabaseConnection` impacts 6+ classes before touching it
- Safe changes: confirm `UserService` has only 1 dependent, change confidently
- Test planning: blast radius shows exactly what needs testing after a change
