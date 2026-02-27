# Schema Caching Pattern

Cache file schemas and analysis results with automatic invalidation when source files change.

## When to Use

- Caching CSV/Excel column schemas
- Storing file analysis results
- Any data derived from a source file

## Pattern

```python
from cache import namespace

def get_schema(file_path: str):
    cache = namespace("my-plugin")
    cache_key = f"schema:{file_path}"

    # Try cache first
    schema = cache.get(cache_key)
    if schema:
        return schema

    # Cache miss - analyze and store
    schema = analyze_file(file_path)
    cache.set(cache_key, schema, source_file=file_path)
    return schema
```

## How It Works

1. `source_file` parameter tracks the file's mtime and size
2. On `get()`, if file changed, returns `None` (cache miss)
3. Caller regenerates and re-caches the data

## Benefits

- Zero manual invalidation needed
- Data always fresh when source changes
- Transparent to calling code

## Example: CSV Schema Cache

```python
def get_csv_schema(csv_path: str):
    cache = namespace("numbah-crunchah")

    schema = cache.get(f"schema:{csv_path}")
    if schema:
        return schema

    # Analyze CSV structure
    import pandas as pd
    df = pd.read_csv(csv_path, nrows=100)
    schema = {
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "row_count_sample": len(df)
    }

    cache.set(f"schema:{csv_path}", schema, source_file=csv_path)
    return schema
```
