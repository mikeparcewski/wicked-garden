---
name: plugin-development-workflow
title: Real Plugin Development with Progressive Caching
description: Build a realistic data analysis plugin that leverages all three cache modes
type: workflow
difficulty: advanced
estimated_minutes: 8
---

# Real Plugin Development with Progressive Caching

Demonstrates building a realistic data analysis plugin that uses all three cache modes strategically. Shows how wicked-cache enables performance optimization without complexity.

## Setup

Create a realistic data analysis scenario with CSV data and external API.

```bash
# Create sample sales data
cat > /tmp/sales_data.csv << 'EOF'
date,product,quantity,revenue,region
2025-01-15,Laptop,5,6499.95,Northeast
2025-01-15,Mouse,23,574.77,West
2025-01-16,Keyboard,12,1079.88,South
2025-01-17,Monitor,8,2799.92,Midwest
2025-01-18,Laptop,3,3899.97,West
EOF

# Create product catalog
cat > /tmp/products.json << 'EOF'
{
  "Laptop": {"category": "Electronics", "cost": 950, "margin": 0.27},
  "Mouse": {"category": "Accessories", "cost": 12, "margin": 0.52},
  "Keyboard": {"category": "Accessories", "cost": 45, "margin": 0.50},
  "Monitor": {"category": "Electronics", "cost": 210, "margin": 0.40}
}
EOF

echo "✓ Created test data files"
```

## Steps

### 1. Initialize plugin with configuration (Manual Mode)

Plugin configuration that persists across sessions.

```bash
python3 << 'EOF'
import sys
import time
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("sales-analyzer-pro")

# First-time setup: store plugin config
config = cache.get("config:plugin")

if not config:
    print("First run: Initializing plugin configuration...")
    config = {
        "version": "1.0.0",
        "data_dir": "/tmp",
        "analysis_modes": ["summary", "trends", "forecasts"],
        "output_format": "markdown",
        "cache_ttl_seconds": 300  # 5 min for API calls
    }

    cache.set("config:plugin", config, options={"mode": "manual"})
    print(f"✓ Plugin configured (v{config['version']})")
else:
    print(f"✓ Loaded existing config (v{config['version']})")

print(f"  Data directory: {config['data_dir']}")
print(f"  Cache TTL: {config['cache_ttl_seconds']}s")
EOF
```

### 2. Cache CSV schema analysis (File Mode)

Expensive file analysis with automatic invalidation on file changes.

```bash
python3 << 'EOF'
import sys
import time
from pathlib import Path
import json

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("sales-analyzer-pro")

def analyze_csv_schema(file_path):
    """Expensive operation: analyze CSV structure and data types"""
    cache_key = f"schema:{Path(file_path).name}"

    # Check cache first
    schema = cache.get(cache_key)
    if schema:
        print(f"✓ Schema cache HIT for {Path(file_path).name}")
        return schema

    # Cache miss - perform analysis
    print(f"✗ Schema cache MISS - analyzing {Path(file_path).name}...")
    start = time.time()

    # Simulate expensive analysis
    time.sleep(0.3)

    with open(file_path, 'r') as f:
        headers = f.readline().strip().split(',')
        rows = [line.strip().split(',') for line in f]

    schema = {
        "columns": headers,
        "row_count": len(rows),
        "date_range": f"{rows[0][0]} to {rows[-1][0]}" if rows else "N/A",
        "products": list(set(row[1] for row in rows)),
        "regions": list(set(row[4] for row in rows))
    }

    elapsed = time.time() - start

    # Cache with file tracking
    cache.set(cache_key, schema, source_file=file_path)

    print(f"✓ Analysis complete in {elapsed:.2f}s")
    print(f"  {len(schema['columns'])} columns, {schema['row_count']} rows")

    return schema

# First analysis
schema = analyze_csv_schema("/tmp/sales_data.csv")
print(f"\nData coverage: {schema['date_range']}")
print(f"Products: {', '.join(schema['products'])}")
EOF
```

### 3. Repeated schema access (demonstrates file cache hit)

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("sales-analyzer-pro")

# This should hit cache instantly
schema = cache.get("schema:sales_data.csv")

if schema:
    print("✓ Instant schema retrieval from cache")
    print(f"  Regions: {', '.join(schema['regions'])}")
else:
    print("✗ Unexpected cache miss")
EOF
```

### 4. Fetch external enrichment data (TTL Mode)

External API calls cached with TTL to avoid rate limits.

```bash
python3 << 'EOF'
import sys
import time
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("sales-analyzer-pro")

def fetch_market_data(region):
    """Fetch external market data (expensive API call)"""
    cache_key = f"api:market-data:{region}"

    # Check cache first
    data = cache.get(cache_key)
    if data:
        print(f"✓ Market data cache HIT for {region}")
        return data

    # Cache miss - make API call
    print(f"✗ Market data cache MISS - fetching {region}...")
    start = time.time()

    # Simulate API call with network latency
    time.sleep(0.8)

    data = {
        "region": region,
        "market_size_millions": 450,
        "growth_rate": 0.12,
        "competition_index": 0.67,
        "seasonality": "Q4-heavy"
    }

    elapsed = time.time() - start

    # Cache for 5 minutes
    config = cache.get("config:plugin")
    ttl = config.get("cache_ttl_seconds", 300) if config else 300

    cache.set(cache_key, data, options={"mode": "ttl", "ttl_seconds": ttl})

    print(f"✓ API response in {elapsed:.2f}s (cached for {ttl}s)")

    return data

# Fetch for multiple regions
for region in ["Northeast", "West", "Midwest"]:
    market = fetch_market_data(region)
    print(f"  {region}: ${market['market_size_millions']}M market")
EOF
```

### 5. Repeated API access within TTL (demonstrates TTL cache hit)

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("sales-analyzer-pro")

print("Accessing market data again (should hit cache):")
for region in ["Northeast", "West"]:
    data = cache.get(f"api:market-data:{region}")
    if data:
        print(f"✓ {region}: Instant retrieval (no API call)")
    else:
        print(f"✗ {region}: Cache miss (unexpected)")
EOF
```

### 6. Demonstrate file change invalidation

Modify the CSV and see file cache invalidate automatically.

```bash
# Add new data to CSV
echo "2025-01-19,Keyboard,7,629.93,Northeast" >> /tmp/sales_data.csv

python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("sales-analyzer-pro")

# Try to get schema - should be invalidated due to file change
schema = cache.get("schema:sales_data.csv")

if schema:
    print("✗ Using stale schema (unexpected)")
    print(f"  Rows: {schema['row_count']}")
else:
    print("✓ File cache correctly invalidated (file was modified)")
    print("  Plugin would re-analyze to get fresh schema")

    # Re-analyze would happen here
    import time
    start = time.time()
    time.sleep(0.3)

    with open("/tmp/sales_data.csv", 'r') as f:
        headers = f.readline().strip().split(',')
        rows = [line.strip().split(',') for line in f]

    new_schema = {
        "columns": headers,
        "row_count": len(rows),
        "date_range": f"{rows[0][0]} to {rows[-1][0]}",
        "products": list(set(row[1] for row in rows)),
        "regions": list(set(row[4] for row in rows))
    }

    cache.set("schema:sales_data.csv", new_schema, source_file="/tmp/sales_data.csv")

    elapsed = time.time() - start
    print(f"✓ Re-analyzed in {elapsed:.2f}s")
    print(f"  Updated row count: {new_schema['row_count']}")
EOF
```

### 7. View comprehensive plugin statistics

See the full picture of cache usage across all three modes.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("sales-analyzer-pro")

print("=== Sales Analyzer Pro - Cache Report ===")
print()

# List all entries
entries = cache.list_entries()

manual_entries = []
file_entries = []
ttl_entries = []

for entry in entries:
    key = entry['key']
    if key.startswith('config:'):
        manual_entries.append(entry)
    elif key.startswith('schema:'):
        file_entries.append(entry)
    elif key.startswith('api:'):
        ttl_entries.append(entry)

print(f"Configuration (Manual Mode): {len(manual_entries)} entries")
for e in manual_entries:
    print(f"  - {e['key']}")

print(f"\nFile Analysis (File Mode): {len(file_entries)} entries")
for e in file_entries:
    valid = "✓" if e['valid'] else "✗ (stale)"
    print(f"  - {e['key']} {valid}")

print(f"\nAPI Responses (TTL Mode): {len(ttl_entries)} entries")
for e in ttl_entries:
    valid = "✓" if e['valid'] else "✗ (expired)"
    print(f"  - {e['key']} {valid}")

# Performance stats
stats = cache.stats()
print(f"\nPerformance Metrics:")
print(f"  Total cache hits: {stats['hit_count']}")
print(f"  Total cache misses: {stats['miss_count']}")

if stats['hit_count'] + stats['miss_count'] > 0:
    hit_rate = stats['hit_count'] / (stats['hit_count'] + stats['miss_count']) * 100
    print(f"  Hit rate: {hit_rate:.1f}%")

print(f"\nStorage:")
print(f"  Total entries: {stats['entry_count']}")
print(f"  Total size: {stats['total_size']} bytes")
EOF
```

## Expected Outcome

- **Manual mode**: Plugin config persists across sessions
- **File mode**: CSV schema cached until file changes
- **TTL mode**: API responses cached for configured duration
- **Automatic invalidation**: File cache detects changes
- **Performance**: Significant speedup from cache hits
- **Observability**: Clear visibility into cache usage

## Success Criteria

- [ ] Plugin configuration persists (manual mode)
- [ ] CSV schema analysis cached and reused (file mode)
- [ ] File changes trigger cache invalidation
- [ ] API responses cached with TTL (TTL mode)
- [ ] Repeated API calls avoided during TTL window
- [ ] All three modes work together seamlessly
- [ ] Statistics show cache effectiveness

## Value Demonstrated

**Real-world plugin architecture**: This scenario shows how a production plugin would actually use wicked-cache:

**Three modes, three use cases**:
1. **Manual mode** → Plugin configuration, user preferences
2. **File mode** → Expensive file analysis (CSV parsing, AST generation)
3. **TTL mode** → External API calls (market data, documentation)

**Performance impact**:
- CSV analysis: 300ms → <1ms (300x faster on cache hit)
- API calls: 800ms → <1ms (800x faster, plus rate limit protection)
- Configuration: Always instant, never re-fetched

**Developer productivity**:
- **Without cache**: Every operation slow, API rate limits hit constantly
- **With wicked-cache**: Fast, responsive plugin with smart caching

**Code complexity**:
- **Manual implementation**: 200+ lines of cache logic, file I/O, locking
- **With wicked-cache**: 3-line cache check pattern throughout plugin

**This is how infrastructure should work**: Plugin authors focus on business logic (data analysis), not plumbing (cache invalidation strategies). wicked-cache handles the hard parts invisibly.

**Production readiness**: The cache statistics and observability features mean you can monitor cache effectiveness in production, tune TTLs, and debug issues without guesswork.
