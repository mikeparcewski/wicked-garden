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
# Create initial content
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
```

## Steps

1. Index the initial project:
   ```
   /wicked-garden:search:index /tmp/wicked-incr-test
   ```

2. Check initial stats:
   ```
   /wicked-garden:search:stats
   ```

3. Modify service.py to add new methods:
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
   /wicked-garden:search:index /tmp/wicked-incr-test
   ```

5. Search for the new method:
   ```
   /wicked-garden:search:code cancel_order
   ```

6. Check updated stats:
   ```
   /wicked-garden:search:stats
   ```

## Expected Outcomes

- Initial index processes both files and extracts all symbols
- After modification and re-index, re-indexing is faster than the initial full index
- New methods (cancel_order, get_order_status) are searchable immediately after re-index
- Stats show updated symbol counts reflecting the added methods
- Unchanged file (repository.py) is not unnecessarily re-processed

## Success Criteria

- [ ] Initial index processes both files successfully
- [ ] Re-index completes faster than initial full index
- [ ] New methods (cancel_order, get_order_status) found by code search after re-index
- [ ] Stats show increased symbol count after re-index
- [ ] Unchanged file (repository.py) is not re-processed
- [ ] Search finds new symbols immediately after re-index

## Value Demonstrated

**Problem solved**: Full re-indexing large codebases is slow. Developers make small changes but have to wait for complete re-indexing to search new code.

**Why this matters**:
- **Rapid iteration**: Change a file, re-index in seconds, not minutes
- **Large codebases**: 1000+ file projects remain practical with incremental updates
- **Developer experience**: No waiting for full re-index after small changes
- **CI/CD integration**: Fast incremental updates in build pipelines
