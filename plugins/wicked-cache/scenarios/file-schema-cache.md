---
name: file-schema-cache
title: Cache Expensive CSV Analysis
description: Cache CSV schema analysis with automatic invalidation when source file changes
type: workflow
difficulty: basic
estimated_minutes: 5
---

# Cache Expensive CSV Analysis

Demonstrates file-based cache invalidation for expensive data analysis operations. When you analyze a large CSV file once, the schema is cached and reused until the file changes.

## Setup

Create a realistic test dataset simulating sales data.

```bash
cat > /tmp/sales_2025.csv << 'EOF'
order_id,customer_name,product,quantity,price,order_date,region,payment_method
1001,Alice Johnson,Laptop,1,1299.99,2025-01-15,Northeast,Credit Card
1002,Bob Smith,Mouse,2,24.99,2025-01-15,West,PayPal
1003,Carol Davis,Keyboard,1,89.99,2025-01-16,South,Debit Card
1004,David Wilson,Monitor,2,349.99,2025-01-16,Midwest,Credit Card
1005,Eve Martinez,Laptop,1,1299.99,2025-01-17,West,Credit Card
EOF
```

## Steps

### 1. First analysis (cache miss - slow)

Simulate expensive analysis operation that takes time.

```bash
python3 << 'EOF'
import sys
import time
from pathlib import Path

# Add wicked-cache to path
cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("data-analyzer-plugin")
cache_key = "schema:sales_2025"

# Check cache first
schema = cache.get(cache_key)

if schema:
    print(f"✓ CACHE HIT: Retrieved in <1ms")
    print(f"  Columns: {schema['columns']}")
else:
    print("✗ CACHE MISS: Analyzing file...")
    start = time.time()

    # Simulate expensive analysis (reading CSV, inferring types, profiling data)
    time.sleep(0.5)  # Simulates actual file I/O and processing

    with open("/tmp/sales_2025.csv", "r") as f:
        headers = f.readline().strip().split(",")
        row_count = sum(1 for _ in f)

    schema = {
        "columns": headers,
        "row_count": row_count,
        "file_size_kb": Path("/tmp/sales_2025.csv").stat().st_size / 1024
    }

    elapsed = time.time() - start
    cache.set(cache_key, schema, source_file="/tmp/sales_2025.csv")
    print(f"✓ Analysis complete in {elapsed:.2f}s")
    print(f"  Columns: {schema['columns']}")
    print(f"  Cached for future use")
EOF
```

### 2. Subsequent analyses (cache hit - fast)

Run analysis again - should be instant.

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("data-analyzer-plugin")
schema = cache.get("schema:sales_2025")

if schema:
    print("✓ CACHE HIT: Retrieved instantly")
    print(f"  {len(schema['columns'])} columns, {schema['row_count']} rows")
else:
    print("✗ Unexpected cache miss")
EOF
```

### 3. Modify the source file

Add more data to simulate file updates.

```bash
echo "1006,Frank Lee,Mouse,3,24.99,2025-01-18,Northeast,PayPal" >> /tmp/sales_2025.csv
```

### 4. Analysis after modification (automatic cache invalidation)

Run analysis again - cache should detect file change and re-analyze.

```bash
python3 << 'EOF'
import sys
import time
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("data-analyzer-plugin")
schema = cache.get("schema:sales_2025")

if schema:
    print(f"✓ Using cached schema")
    print(f"  Row count: {schema['row_count']}")
else:
    print("✓ File changed - cache invalidated automatically")
    print("  Re-analyzing...")
    time.sleep(0.5)

    with open("/tmp/sales_2025.csv", "r") as f:
        headers = f.readline().strip().split(",")
        row_count = sum(1 for _ in f)

    schema = {
        "columns": headers,
        "row_count": row_count,
        "file_size_kb": Path("/tmp/sales_2025.csv").stat().st_size / 1024
    }

    cache.set("schema:sales_2025", schema, source_file="/tmp/sales_2025.csv")
    print(f"✓ Updated cache with new schema")
    print(f"  Row count: {schema['row_count']}")
EOF
```

### 5. Verify cache statistics

```bash
python3 << 'EOF'
import sys
from pathlib import Path

cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
sys.path.insert(0, str(cache_path))

from cache import namespace

cache = namespace("data-analyzer-plugin")
stats = cache.stats()

print(f"Cache Statistics:")
print(f"  Entries: {stats['entry_count']}")
print(f"  Hits: {stats['hit_count']}")
print(f"  Misses: {stats['miss_count']}")
print(f"  Hit rate: {stats['hit_count']/(stats['hit_count']+stats['miss_count'])*100:.1f}%")
EOF
```

## Expected Outcome

- **First run**: Cache miss, performs expensive analysis (~500ms)
- **Second run**: Cache hit, instant retrieval (<1ms)
- **After file modification**: Automatic cache invalidation detected
- **Third run**: Cache miss again, re-analyzes with updated data
- **Statistics**: Show hit/miss tracking working correctly

## Success Criteria

- [ ] Initial analysis creates cache entry
- [ ] Subsequent access hits cache (faster retrieval)
- [ ] File modification invalidates cache automatically
- [ ] Re-analysis updates cache with fresh data
- [ ] Statistics accurately track hits and misses

## Value Demonstrated

**Real-world performance optimization**: Expensive operations like CSV schema inference, data profiling, or file parsing only happen once per file version. Changes to source files are automatically detected without manual cache management. This is critical for:

- Data analysis plugins working with large datasets
- Code analysis tools scanning source files
- Documentation generators processing markdown files
- Any plugin that derives data from files

**Time savings**: A 500ms analysis becomes <1ms on cache hit. With hundreds of file accesses per session, this saves significant time and improves user experience.
