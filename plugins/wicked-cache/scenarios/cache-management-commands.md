---
name: cache-management-commands
title: Cache Management and Observability
description: Use cache commands to inspect, monitor, and manage cached data across all plugins
type: feature
difficulty: basic
estimated_minutes: 6
---

# Cache Management and Observability

Demonstrates the cache management commands that provide visibility and control over cached data. Essential for debugging, monitoring cache efficiency, and managing cache size.

## Setup

Create realistic cached data across multiple namespaces to demonstrate management commands.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

# Simulate several plugins using cache
plugins = {
    "data-analyzer": [
        ("schema:sales.csv", {"columns": ["id", "amount", "date"], "rows": 1500}),
        ("schema:users.csv", {"columns": ["name", "email", "signup"], "rows": 450}),
        ("profile:large-dataset", {"size_mb": 250, "load_time": 12.5})
    ],
    "doc-search": [
        ("index:api-docs", {"documents": 342, "tokens": 125000}),
        ("index:readme-files", {"documents": 89, "tokens": 45000})
    ],
    "code-review": [
        ("lint:main.py", {"issues": 3, "warnings": 7}),
        ("complexity:utils.py", {"cyclomatic": 15, "cognitive": 22})
    ]
}

for plugin_name, entries in plugins.items():
    cache = namespace(plugin_name)
    for key, value in entries:
        cache.set(key, value, options={"mode": "manual"})

print("✓ Created test cache data across 3 namespaces")
print("  Total entries: 7")
EOF
```

## Steps

### 1. List all cache contents

View everything stored in the cache across all namespaces.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace
import os

print("=== Cache Contents ===")
print()

# Find all namespaces
cache_base = Path.home() / ".something-wicked" / "cache" / "namespaces"
if cache_base.exists():
    namespaces = [d.name for d in cache_base.iterdir() if d.is_dir()]

    for ns in sorted(namespaces):
        cache = namespace(ns)
        entries = cache.list_entries()

        if entries:
            print(f"Namespace: {ns}")
            print(f"{'Key':<30} {'Valid':<8} {'Size':<12} {'Age':<10}")
            print("-" * 70)

            for entry in entries:
                valid_str = "✓" if entry['valid'] else "✗"
                size_str = f"{entry['size']} B"
                age_str = f"{entry['age']}s"
                print(f"{entry['key']:<30} {valid_str:<8} {size_str:<12} {age_str:<10}")

            print()
else:
    print("No cache data found")
EOF
```

### 2. View namespace-specific statistics

Get detailed stats for a specific namespace.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

print("=== Namespace Statistics: data-analyzer ===")
print()

cache = namespace("data-analyzer")
stats = cache.stats()

print(f"Entries: {stats['entry_count']}")
print(f"Total size: {stats['total_size']} bytes ({stats['total_size']/1024:.2f} KB)")
print(f"Cache hits: {stats['hit_count']}")
print(f"Cache misses: {stats['miss_count']}")

if stats['hit_count'] + stats['miss_count'] > 0:
    hit_rate = stats['hit_count'] / (stats['hit_count'] + stats['miss_count']) * 100
    print(f"Hit rate: {hit_rate:.1f}%")

print(f"Oldest entry: {stats['oldest_entry_age']}s ago")
print()

# List specific entries
entries = cache.list_entries()
print(f"Cached items:")
for entry in entries:
    print(f"  - {entry['key']}")
EOF
```

### 3. View global statistics

Aggregate stats across all namespaces.

```bash
python3 << 'EOF'
import sys
from pathlib import Path
import json

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

print("=== Global Cache Statistics ===")
print()

# Load global stats file
stats_file = Path.home() / ".something-wicked" / "cache" / "stats.json"
if stats_file.exists():
    with open(stats_file, "r") as f:
        global_stats = json.load(f)

    total_hits = 0
    total_misses = 0
    total_sets = 0

    print("Per-Namespace Metrics:")
    for ns, data in global_stats.get("namespaces", {}).items():
        print(f"  {ns}:")
        print(f"    Hits: {data.get('hits', 0)}")
        print(f"    Misses: {data.get('misses', 0)}")
        print(f"    Sets: {data.get('sets', 0)}")

        total_hits += data.get('hits', 0)
        total_misses += data.get('misses', 0)
        total_sets += data.get('sets', 0)

    print()
    print("Aggregate:")
    print(f"  Total operations: {total_hits + total_misses}")
    print(f"  Cache hits: {total_hits}")
    print(f"  Cache misses: {total_misses}")
    print(f"  Total sets: {total_sets}")

    if total_hits + total_misses > 0:
        hit_rate = total_hits / (total_hits + total_misses) * 100
        print(f"  Overall hit rate: {hit_rate:.1f}%")
else:
    print("No global statistics found")
EOF
```

### 4. Clear a specific namespace

Remove all cached data for one plugin without affecting others.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

print("Clearing namespace: doc-search")
cache = namespace("doc-search")

# Show before
entries_before = cache.list_entries()
print(f"Before: {len(entries_before)} entries")

# Clear
cleared = cache.clear()
print(f"✓ Cleared {cleared} entries")

# Verify
entries_after = cache.list_entries()
print(f"After: {len(entries_after)} entries")

# Verify other namespaces unaffected
other_cache = namespace("data-analyzer")
other_entries = other_cache.list_entries()
print(f"Other namespace (data-analyzer) still has {len(other_entries)} entries")
EOF
```

### 5. Invalidate specific entries

Remove individual cache entries by key.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("data-analyzer")

print("Before invalidation:")
entries = cache.list_entries()
for e in entries:
    print(f"  - {e['key']}")

# Invalidate specific entry
result = cache.invalidate("schema:sales.csv")
print(f"\n✓ Invalidated 'schema:sales.csv': {'success' if result else 'not found'}")

print("\nAfter invalidation:")
entries = cache.list_entries()
for e in entries:
    print(f"  - {e['key']}")

print(f"\nRemaining entries: {len(entries)}")
EOF
```

### 6. Monitor cache efficiency

Simulate usage and track hit/miss rates.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("monitoring-test")

print("=== Cache Efficiency Test ===")
print()

# Set some data
cache.set("test:1", {"data": "value1"}, options={"mode": "manual"})
cache.set("test:2", {"data": "value2"}, options={"mode": "manual"})

# Simulate access pattern
print("Access pattern:")
cache.get("test:1")  # hit
print("  - Access test:1 (hit)")

cache.get("test:1")  # hit
print("  - Access test:1 (hit)")

cache.get("test:2")  # hit
print("  - Access test:2 (hit)")

cache.get("test:3")  # miss
print("  - Access test:3 (miss)")

cache.get("test:4")  # miss
print("  - Access test:4 (miss)")

cache.get("test:1")  # hit
print("  - Access test:1 (hit)")

# Check stats
stats = cache.stats()
print()
print("Results:")
print(f"  Hits: {stats['hit_count']}")
print(f"  Misses: {stats['miss_count']}")
print(f"  Hit rate: {stats['hit_count']/(stats['hit_count']+stats['miss_count'])*100:.1f}%")
print()
print("✓ Cache efficiency tracking working")
EOF
```

## Expected Outcome

- List command shows all cached data across namespaces
- Stats show hit/miss rates and cache sizes
- Clear operations are namespace-scoped
- Invalidation works for specific keys
- Monitoring reveals cache effectiveness
- Management operations don't affect other namespaces

## Success Criteria

- [ ] Can list all cache contents across namespaces
- [ ] Namespace-specific stats are accurate
- [ ] Global stats aggregate correctly
- [ ] Clear operation removes all entries in namespace
- [ ] Invalidate removes specific cache entries
- [ ] Hit/miss tracking reflects actual access patterns
- [ ] Other namespaces unaffected by operations

## Value Demonstrated

**Observability and control**: Production caching needs monitoring and management. wicked-cache provides:

**Debugging capabilities**:
- Inspect cached data to debug stale data issues
- Verify cache invalidation is working correctly
- Check if cache keys are being used properly

**Performance monitoring**:
- Track hit/miss rates to measure cache effectiveness
- Identify hot data vs cold data
- Optimize cache TTLs based on access patterns

**Operational management**:
- Clear problematic caches without restarting
- Monitor cache size to prevent disk issues
- Namespace isolation for safe cleanup

**Real-world scenarios**:
- "Why is my plugin using stale data?" → List cache and verify entries
- "Is caching actually helping?" → Check hit rates
- "Cache taking too much space" → Clear old namespaces
- "Need to force refresh" → Invalidate specific keys

**Developer experience**: Instead of blind caching, you have full visibility into what's cached, how it's performing, and tools to manage it. This is essential for production-ready infrastructure.
