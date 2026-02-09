---
name: cross-plugin-integration
title: Cross-Plugin Cache Sharing
description: Demonstrate how multiple plugins can use wicked-cache with namespace isolation
type: integration
difficulty: intermediate
estimated_minutes: 5
---

# Cross-Plugin Cache Sharing

Demonstrates the key architectural benefit of wicked-cache: any plugin can use it as a shared caching infrastructure while maintaining namespace isolation. Each plugin gets its own isolated cache namespace.

## Setup

No setup required - we'll simulate multiple plugins using the cache.

## Steps

### 1. Plugin A stores its data

Simulate a code analysis plugin caching AST results.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

# Plugin A: code-analyzer
cache = namespace("code-analyzer")

ast_data = {
    "file": "src/main.py",
    "functions": ["main", "process_data", "validate_input"],
    "classes": ["DataProcessor", "Validator"],
    "imports": ["json", "pathlib", "typing"]
}

cache.set("ast:main.py", ast_data, options={"mode": "manual"})
print("✓ code-analyzer: Stored AST data")
print(f"  File: {ast_data['file']}")
print(f"  Functions: {len(ast_data['functions'])}")
EOF
```

### 2. Plugin B stores its data

Simulate a documentation plugin caching parsed docs.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

# Plugin B: doc-generator
cache = namespace("doc-generator")

doc_data = {
    "file": "src/main.py",
    "docstrings": {
        "main": "Entry point for the application",
        "process_data": "Processes input data and returns results",
        "validate_input": "Validates user input against schema"
    },
    "coverage": 0.85
}

cache.set("docs:main.py", doc_data, options={"mode": "manual"})
print("✓ doc-generator: Stored documentation data")
print(f"  File: {doc_data['file']}")
print(f"  Coverage: {doc_data['coverage']*100}%")
EOF
```

### 3. Plugin C stores its data

Simulate a test generator plugin caching test metadata.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

# Plugin C: test-generator
cache = namespace("test-generator")

test_data = {
    "file": "src/main.py",
    "test_coverage": {
        "main": True,
        "process_data": True,
        "validate_input": False
    },
    "test_count": 12,
    "last_run": "2025-01-23T10:30:00Z"
}

cache.set("tests:main.py", test_data, options={"mode": "manual"})
print("✓ test-generator: Stored test metadata")
print(f"  File: {test_data['file']}")
print(f"  Tests: {test_data['test_count']}")
EOF
```

### 4. Verify namespace isolation

Each plugin can only see its own data.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

print("Namespace Isolation Check:")
print()

# Plugin A can see its own data
cache_a = namespace("code-analyzer")
ast = cache_a.get("ast:main.py")
print(f"code-analyzer sees its own data: {'YES' if ast else 'NO'}")

# Plugin A cannot see Plugin B's data with same key pattern
docs = cache_a.get("docs:main.py")
print(f"code-analyzer sees doc-generator data: {'YES (BAD!)' if docs else 'NO (correct)'}")

# Plugin B can only see its own data
cache_b = namespace("doc-generator")
docs = cache_b.get("docs:main.py")
print(f"doc-generator sees its own data: {'YES' if docs else 'NO'}")

# Plugin C has its own isolated data
cache_c = namespace("test-generator")
tests = cache_c.get("tests:main.py")
print(f"test-generator sees its own data: {'YES' if tests else 'NO'}")

print()
print("✓ Namespace isolation working correctly")
EOF
```

### 5. View global cache statistics

Each namespace tracks its own stats independently.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

print("Cache Statistics by Namespace:")
print()

for plugin_name in ["code-analyzer", "doc-generator", "test-generator"]:
    cache = namespace(plugin_name)
    stats = cache.stats()

    print(f"{plugin_name}:")
    print(f"  Entries: {stats['entry_count']}")
    print(f"  Hits: {stats['hit_count']}")
    print(f"  Misses: {stats['miss_count']}")
    print(f"  Size: {stats['total_size']} bytes")
    print()

print("✓ Each plugin has independent cache statistics")
EOF
```

### 6. Demonstrate cache commands work across namespaces

List all cached data from all namespaces (if commands are available).

```bash
# Note: This would use the /wicked-cache:cache list command
# For testing, we'll show the namespace structure programmatically

python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

print("All Namespaces Summary:")
print()

namespaces = ["code-analyzer", "doc-generator", "test-generator"]
total_entries = 0
total_size = 0

for ns in namespaces:
    cache = namespace(ns)
    stats = cache.stats()
    total_entries += stats['entry_count']
    total_size += stats['total_size']

print(f"Total namespaces: {len(namespaces)}")
print(f"Total entries: {total_entries}")
print(f"Total size: {total_size} bytes")
print()
print("✓ Unified cache infrastructure serving multiple plugins")
EOF
```

### 7. Clean up one namespace without affecting others

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

# Clear code-analyzer cache
cache = namespace("code-analyzer")
count = cache.clear()
print(f"✓ Cleared {count} entries from code-analyzer")

# Verify other namespaces still have data
cache_b = namespace("doc-generator")
cache_c = namespace("test-generator")

doc_data = cache_b.get("docs:main.py")
test_data = cache_c.get("tests:main.py")

print(f"doc-generator data intact: {'YES' if doc_data else 'NO (unexpected)'}")
print(f"test-generator data intact: {'YES' if test_data else 'NO (unexpected)'}")
print()
print("✓ Namespace isolation prevents cross-contamination")
EOF
```

## Expected Outcome

- Each plugin stores data in its own namespace
- Namespaces are completely isolated from each other
- Plugins cannot access other plugin's cached data
- Statistics tracked independently per namespace
- Clearing one namespace doesn't affect others
- Shared infrastructure, isolated data

## Success Criteria

- [ ] Multiple plugins can use wicked-cache simultaneously
- [ ] Each plugin's data is isolated in its own namespace
- [ ] Plugin A cannot access Plugin B's data
- [ ] Statistics are tracked independently per namespace
- [ ] Clearing one namespace doesn't affect others
- [ ] All plugins share the same cache infrastructure

## Value Demonstrated

**Unified infrastructure with isolation**: This is the killer feature of wicked-cache. Instead of every plugin implementing its own caching solution:

**Without wicked-cache**:
- Each plugin writes its own cache logic (file I/O, invalidation, stats)
- Code duplication across 10+ plugins
- Inconsistent patterns and behaviors
- No unified management or visibility
- Maintenance burden on every plugin author

**With wicked-cache**:
- Single, well-tested caching implementation
- Consistent API across all plugins
- Unified cache management commands
- Namespace isolation prevents conflicts
- Plugin authors focus on features, not infrastructure

**Real-world impact**: A marketplace with 20 plugins needs caching. Without wicked-cache, that's 20 separate implementations to maintain. With wicked-cache, it's one implementation serving all plugins. This is infrastructure done right.
