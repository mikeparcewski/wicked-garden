---
name: incremental-indexing
title: Incremental Index Updates
description: Detect file changes and only re-index modified files
type: feature
difficulty: intermediate
estimated_minutes: 10
---

# Incremental Index Updates

## Setup

Create initial content and index it:

```bash
# Create and index initial content
mkdir -p /tmp/wicked-incr-test/src

cat > /tmp/wicked-incr-test/src/service.py << 'EOF'
class OrderService:
    """Service for managing orders."""

    def create_order(self, items: list):
        """Create a new order."""
        pass
EOF

cat > /tmp/wicked-incr-test/src/repository.py << 'EOF'
class OrderRepository:
    """Database access for orders."""

    def save(self, order):
        """Save order to database."""
        pass
EOF

# Initial index
# /wicked-search:index /tmp/wicked-incr-test
```

## Steps

1. Index the initial project:
   ```
   /wicked-search:index /tmp/wicked-incr-test
   ```

2. Check initial stats:
   ```
   /wicked-search:stats
   ```

3. Modify service.py to add a new method:
   ```bash
   cat > /tmp/wicked-incr-test/src/service.py << 'EOF'
   class OrderService:
       """Service for managing orders."""

       def create_order(self, items: list):
           """Create a new order."""
           pass

       def cancel_order(self, order_id: int):
           """Cancel an existing order."""
           pass

       def get_order_status(self, order_id: int) -> str:
           """Get current order status."""
           return "pending"
   EOF
   ```

4. Re-index the project:
   ```
   /wicked-search:index /tmp/wicked-incr-test
   ```

5. Search for the new method:
   ```
   /wicked-search:code cancel_order
   ```

6. Check updated stats:
   ```
   /wicked-search:stats
   ```

## Expected Outcome

1. **Initial index**: Both files indexed, all symbols extracted

2. **After modification**:
   - PostToolUse hook detects service.py was modified via Write tool
   - File marked as "stale" in `~/.something-wicked/search/stale_files.json`

3. **Re-indexing**:
   - Only service.py is re-processed (not repository.py)
   - Faster than full index
   - New methods (cancel_order, get_order_status) appear in index

4. **Stats show**:
   - Last update timestamp
   - File count: 2
   - Symbol count increased
   - Incremental update indicator

## Success Criteria

- [ ] Initial index processes both files
- [ ] PostToolUse hook marks service.py as stale when modified
- [ ] Re-index is faster than initial full index
- [ ] Only modified file (service.py) is re-processed
- [ ] New methods (cancel_order, get_order_status) searchable
- [ ] Unchanged file (repository.py) not re-processed
- [ ] `/stats` shows last update time and file counts
- [ ] Search finds new symbols immediately after re-index

## Value Demonstrated

**Problem solved**: Full re-indexing large codebases is slow. Developers make small changes but have to wait for complete re-indexing to search new code.

**Why this matters**:
- **Rapid iteration**: Change a file → re-index in seconds, not minutes
- **Large codebases**: 1000+ file projects become practical
- **Developer experience**: No waiting for full re-index after small changes
- **CI/CD integration**: Fast incremental updates in build pipelines

Real-world impact:
- **Before**: Modify one file → wait 2 minutes for full re-index
- **After**: Modify one file → wait 3 seconds for incremental update

The PostToolUse hook automatically detects Write operations and marks files stale - zero manual tracking required.
