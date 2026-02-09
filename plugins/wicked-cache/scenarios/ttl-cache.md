---
name: ttl-cache
title: Cache External API Responses with TTL
description: Cache API documentation lookups with time-based expiration to avoid rate limits
type: workflow
difficulty: basic
estimated_minutes: 4
---

# Cache External API Responses with TTL

Demonstrates TTL-based caching for external API responses. Prevents hitting rate limits and improves response time by caching API data for a configurable duration.

## Setup

No setup required - this simulates fetching documentation from an external API.

## Steps

### 1. First API lookup (cache miss - slow)

Simulate an expensive API call to fetch React documentation.

```bash
python3 << 'EOF'
import sys
import time
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("doc-lookup-plugin")
cache_key = "api:react-docs:useEffect"

# Check cache first
doc = cache.get(cache_key)

if doc:
    print(f"✓ CACHE HIT: Retrieved from cache")
    print(f"  Source: {doc['source']}")
else:
    print("✗ CACHE MISS: Fetching from API...")
    start = time.time()

    # Simulate API request with network latency
    time.sleep(1.0)

    doc = {
        "topic": "useEffect Hook",
        "summary": "useEffect runs after render and can handle side effects",
        "signature": "useEffect(setup, dependencies?)",
        "source": "react.dev/reference/react/useEffect",
        "examples": ["Connecting to external system", "Fetching data", "Custom hooks"]
    }

    # Cache for 5 minutes (300 seconds)
    cache.set(cache_key, doc, options={"mode": "ttl", "ttl_seconds": 300})

    elapsed = time.time() - start
    print(f"✓ API response fetched in {elapsed:.2f}s")
    print(f"  Cached for 5 minutes")
    print(f"  Summary: {doc['summary']}")
EOF
```

### 2. Subsequent lookups within TTL (cache hit - fast)

Lookup the same documentation again - should be instant.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("doc-lookup-plugin")
doc = cache.get("api:react-docs:useEffect")

if doc:
    print("✓ CACHE HIT: Retrieved instantly (no API call)")
    print(f"  Topic: {doc['topic']}")
    print(f"  Source: {doc['source']}")
else:
    print("✗ Unexpected cache miss")
EOF
```

### 3. Demonstrate short TTL for testing

Store another entry with very short TTL (5 seconds).

```bash
python3 << 'EOF'
import sys
import time
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("doc-lookup-plugin")

# Store with 5 second TTL for demo
doc = {
    "topic": "useState Hook",
    "summary": "useState adds state to functional components",
    "source": "react.dev/reference/react/useState"
}

cache.set("api:react-docs:useState", doc, options={"mode": "ttl", "ttl_seconds": 5})
print("✓ Stored useState docs with 5-second TTL")

# Immediate retrieval works
result = cache.get("api:react-docs:useState")
print(f"✓ Immediate retrieval: {'SUCCESS' if result else 'FAILED'}")
EOF
```

### 4. Wait for TTL expiration

```bash
echo "Waiting 6 seconds for TTL to expire..."
sleep 6
```

### 5. Verify TTL expiration (cache miss)

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("doc-lookup-plugin")
result = cache.get("api:react-docs:useState")

if result:
    print("✗ UNEXPECTED: Cache should have expired")
else:
    print("✓ TTL EXPIRED: Cache correctly invalidated after 5 seconds")
    print("  (Would trigger fresh API call in real usage)")
EOF
```

### 6. View cache statistics

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("doc-lookup-plugin")
stats = cache.stats()

print("Cache Statistics:")
print(f"  Active entries: {stats['entry_count']}")
print(f"  Total hits: {stats['hit_count']}")
print(f"  Total misses: {stats['miss_count']}")

if stats['hit_count'] + stats['miss_count'] > 0:
    hit_rate = stats['hit_count'] / (stats['hit_count'] + stats['miss_count']) * 100
    print(f"  Hit rate: {hit_rate:.1f}%")
EOF
```

## Expected Outcome

- **First API call**: Cache miss, simulates 1s network delay
- **Second lookup**: Cache hit, instant (<1ms)
- **Short TTL entry**: Works immediately after creation
- **After TTL expires**: Returns None, would trigger fresh API call
- **Statistics**: Track cache efficiency

## Success Criteria

- [ ] TTL mode stores API response correctly
- [ ] Cached data retrieved instantly within TTL window
- [ ] Cache automatically invalidates after TTL expires
- [ ] No API calls needed during TTL window
- [ ] Statistics track hits and misses accurately

## Value Demonstrated

**Avoid rate limiting and reduce latency**: External APIs often have rate limits (e.g., GitHub: 60 requests/hour for unauthenticated, OpenAI docs, package registries). TTL caching prevents:

- Hitting rate limits during development sessions
- Unnecessary network calls for frequently accessed data
- Slow response times from repeated API calls

**Real-world use cases**:
- Documentation lookup plugins (React, Python, etc.)
- Package version checkers (npm, PyPI)
- Code search results (GitHub, Stack Overflow)
- LLM-based analysis results that don't change frequently

**Practical impact**: A 1-second API call becomes <1ms for the duration of the TTL. During a 1-hour session with 50 documentation lookups, this saves ~50 seconds and prevents rate limit issues.
