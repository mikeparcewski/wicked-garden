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

## Expected Outcomes

- Code-only search returns results exclusively from code files (.py), not documentation (.md)
- Both CacheManager and RedisCache classes are found
- All methods discovered: get, set, invalidate, connect
- Inheritance relationship between RedisCache and CacheManager is visible
- File locations shown for each result
- Unified search returns results from both code and docs, confirming the filter works

## Success Criteria

- [ ] Code-only search excludes documentation files (caching.md not in results)
- [ ] Both cache.py and redis_cache.py found
- [ ] CacheManager and RedisCache classes discovered
- [ ] All methods (get, set, invalidate, connect) appear in results
- [ ] Inheritance relationship (RedisCache extends CacheManager) detected
- [ ] Unified search returns both code and doc results for comparison

## Value Demonstrated

**Problem solved**: When debugging or refactoring, developers need to find actual implementations, not documentation mentions. Unified search can return too many doc results when you just need code.

**Why this matters**:
- **Performance debugging**: "Find all cache implementations" returns actual classes, not discussion docs
- **Refactoring**: Need to change cache API, find all cache classes quickly
- **Code review**: "How many places use caching?" counts implementations, not docs
- **API exploration**: Discover available methods on cache classes
