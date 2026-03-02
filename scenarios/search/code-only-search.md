---
name: code-only-search
title: Search Code Symbols Only
description: Filter search to only code, excluding documentation
type: feature
difficulty: basic
estimated_minutes: 5
---

# Search Code Symbols Only

## Setup

Create a project with code and documentation that both mention "cache":

```bash
# Create test directory
mkdir -p /tmp/wicked-code-test/src
mkdir -p /tmp/wicked-code-test/docs

# Create multiple code files
cat > /tmp/wicked-code-test/src/cache.py << 'EOF'
class CacheManager:
    """Manages application cache."""

    def get(self, key: str):
        """Get cached value."""
        pass

    def set(self, key: str, value: any, ttl: int = 300):
        """Set cached value with TTL."""
        pass

    def invalidate(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        pass
EOF

cat > /tmp/wicked-code-test/src/redis_cache.py << 'EOF'
class RedisCache(CacheManager):
    """Redis-backed cache implementation."""

    def connect(self, host: str, port: int):
        """Connect to Redis server."""
        pass
EOF

# Create doc that also mentions cache
cat > /tmp/wicked-code-test/docs/caching.md << 'EOF'
# Caching Strategy

We use CacheManager for all caching needs.
The default TTL is 300 seconds.
Redis is used for distributed caching.
EOF
```

## Steps

1. Index the project:
   ```
   /wicked-garden:search:index /tmp/wicked-code-test
   ```

2. Search code only for "cache":
   ```
   /wicked-garden:search:code cache
   ```

3. Compare with unified search:
   ```
   /wicked-garden:search:search cache
   ```

## Expected Outcome

1. `/code cache` returns ONLY code results:
   - CacheManager class with methods
   - RedisCache class with methods
   - cache.py and redis_cache.py files

2. Documentation file (caching.md) is NOT included in results

3. Results show:
   - Class hierarchy (RedisCache extends CacheManager)
   - Method signatures (get, set, invalidate, connect)
   - File locations

4. `/search cache` returns both code and docs for comparison

## Success Criteria

- [ ] Only code files returned (no .md files)
- [ ] Both cache.py and redis_cache.py found
- [ ] All classes found: CacheManager, RedisCache
- [ ] All methods shown: get, set, invalidate, connect
- [ ] Class hierarchy visible (inheritance relationship)
- [ ] caching.md excluded from code-only results

## Value Demonstrated

**Problem solved**: When debugging or refactoring, developers need to find actual implementations, not documentation mentions. Unified search can return too many doc results when you just need code.

**Why this matters**:
- **Performance debugging**: "Find all cache implementations" → see actual classes, not discussion docs
- **Refactoring**: Need to change cache API → find all cache classes quickly
- **Code review**: "How many places use caching?" → count implementations, not docs
- **API exploration**: Discover available methods on cache classes

Code-only search filters noise and shows implementation details like method signatures, inheritance, and file locations.
