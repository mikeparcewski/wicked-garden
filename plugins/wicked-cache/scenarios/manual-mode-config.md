---
name: manual-mode-config
title: Cache Plugin Configuration with Manual Mode
description: Cache plugin configuration and settings that persist across sessions
type: workflow
difficulty: basic
estimated_minutes: 3
---

# Cache Plugin Configuration with Manual Mode

Demonstrates manual invalidation mode for data that should persist indefinitely until explicitly cleared. Perfect for configuration, preferences, and plugin state that doesn't depend on files or time.

## Setup

No setup required - we'll cache configuration data.

## Steps

### 1. Store plugin configuration

Cache plugin settings that should persist across sessions.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("my-awesome-plugin")

# Store plugin configuration
config = {
    "version": "1.2.0",
    "preferences": {
        "theme": "dark",
        "auto_save": True,
        "max_results": 100
    },
    "api_endpoints": {
        "production": "https://api.example.com",
        "staging": "https://staging-api.example.com"
    },
    "feature_flags": {
        "experimental_search": False,
        "beta_analytics": True
    }
}

# Manual mode = never expires automatically
cache.set("config:main", config, options={"mode": "manual"})

print("✓ Stored plugin configuration")
print(f"  Version: {config['version']}")
print(f"  Theme: {config['preferences']['theme']}")
print(f"  Features: {len(config['feature_flags'])} flags")
EOF
```

### 2. Retrieve configuration in later session

Configuration persists indefinitely - no TTL expiration.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("my-awesome-plugin")

# Retrieve config (will work indefinitely)
config = cache.get("config:main")

if config:
    print("✓ Configuration retrieved from cache")
    print(f"  Version: {config['version']}")
    print(f"  Theme: {config['preferences']['theme']}")
    print(f"  Auto-save: {config['preferences']['auto_save']}")
else:
    print("✗ Configuration not found (unexpected)")
EOF
```

### 3. Update configuration

Modify specific settings and re-cache.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("my-awesome-plugin")

# Get current config
config = cache.get("config:main")

if config:
    # Update preferences
    config['preferences']['max_results'] = 250
    config['feature_flags']['experimental_search'] = True

    # Re-cache with updates
    cache.set("config:main", config, options={"mode": "manual"})

    print("✓ Configuration updated")
    print(f"  Max results: {config['preferences']['max_results']}")
    print(f"  Experimental search: {config['feature_flags']['experimental_search']}")
EOF
```

### 4. Store user session state

Cache temporary state that should persist during a work session.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("my-awesome-plugin")

# Store session state
session = {
    "last_query": "analyze sales data for Q4 2024",
    "recent_files": [
        "/data/sales_2024_q4.csv",
        "/data/customers.json",
        "/reports/analysis.md"
    ],
    "workspace": "/Users/alice/projects/data-analysis",
    "filters": {
        "date_range": "2024-10-01 to 2024-12-31",
        "region": "Northeast",
        "min_amount": 1000
    }
}

cache.set("session:current", session, options={"mode": "manual"})

print("✓ Stored session state")
print(f"  Last query: {session['last_query']}")
print(f"  Recent files: {len(session['recent_files'])}")
print(f"  Workspace: {session['workspace']}")
EOF
```

### 5. Retrieve session state later

Session state persists until explicitly cleared.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("my-awesome-plugin")

session = cache.get("session:current")

if session:
    print("✓ Session state restored")
    print(f"  Last query: {session['last_query']}")
    print(f"  Recent files:")
    for f in session['recent_files']:
        print(f"    - {f}")
    print(f"  Active filters: {list(session['filters'].keys())}")
else:
    print("✗ No session state found")
EOF
```

### 6. Verify manual mode never expires

Wait a bit and confirm data is still valid (unlike TTL mode).

```bash
echo "Waiting 3 seconds..."
sleep 3

python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("my-awesome-plugin")

# Check both config and session
config = cache.get("config:main")
session = cache.get("session:current")

print("Manual mode validation:")
print(f"  Config still valid: {'YES' if config else 'NO'}")
print(f"  Session still valid: {'YES' if session else 'NO'}")
print()
print("✓ Manual mode data never expires automatically")
print("  (Only explicit invalidate() or clear() removes it)")
EOF
```

### 7. Explicitly invalidate when needed

Clear specific cached config when user requests it.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("my-awesome-plugin")

print("Entries before invalidation:")
entries = cache.list_entries()
for e in entries:
    print(f"  - {e['key']}")

# User wants to clear session but keep config
result = cache.invalidate("session:current")
print(f"\n✓ Invalidated session:current")

print("\nEntries after invalidation:")
entries = cache.list_entries()
for e in entries:
    print(f"  - {e['key']}")

# Config still exists
config = cache.get("config:main")
print(f"\nConfig still accessible: {'YES' if config else 'NO'}")
EOF
```

## Expected Outcome

- Configuration data persists indefinitely
- Session state survives across operations
- No automatic expiration (unlike TTL mode)
- No file-based invalidation (unlike file mode)
- Only explicit invalidate() or clear() removes data
- Perfect for settings, preferences, and plugin state

## Success Criteria

- [ ] Manual mode stores data successfully
- [ ] Cached data persists indefinitely (no TTL)
- [ ] Data survives wait periods (unlike TTL mode)
- [ ] No file dependency (unlike file mode)
- [ ] Explicit invalidation works correctly
- [ ] Clear operation removes all manual mode entries

## Value Demonstrated

**Persistent state management**: Manual mode solves the problem of "where do I store plugin configuration and state?" without:

**Common anti-patterns it replaces**:
- Writing config files to disk manually
- Using environment variables inappropriately
- Storing state in global variables (lost on restart)
- Custom JSON file management with locking issues

**Real-world use cases**:
- **Plugin configuration**: Theme, preferences, API keys
- **User session state**: Recent files, search history, workspace settings
- **Feature flags**: Enable/disable experimental features
- **Onboarding state**: Has user completed tutorial?
- **Cache warming data**: Pre-computed lookups that rarely change

**Key difference from other modes**:
- **TTL mode**: "Cache this for 5 minutes" (API responses)
- **File mode**: "Cache until source file changes" (analysis results)
- **Manual mode**: "Cache until I explicitly remove it" (configuration)

**Developer experience**: Simple, persistent key-value storage without filesystem complexity. Just set it and forget it until you need to change it. No expiration surprises, no stale data from file changes.
