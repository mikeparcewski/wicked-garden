# API Response Caching Pattern

Cache API responses with time-based expiration (TTL).

## When to Use

- External API calls that are slow or rate-limited
- Data that's acceptable to be slightly stale
- Reducing API costs/load

## Pattern

```python
from cache import namespace

def fetch_docs(query: str):
    cache = namespace("my-plugin")
    cache_key = f"docs:{query}"

    # Try cache first
    result = cache.get(cache_key)
    if result:
        return result

    # Cache miss - fetch and store with TTL
    result = call_api(query)
    cache.set(cache_key, result, options={"mode": "ttl", "ttl_seconds": 300})
    return result
```

## TTL Options

```python
# 5 minute TTL (good for frequently changing data)
cache.set(key, value, options={"mode": "ttl", "ttl_seconds": 300})

# 1 hour TTL (good for stable data)
cache.set(key, value, options={"mode": "ttl", "ttl_seconds": 3600})

# 24 hour TTL (good for rarely changing data)
cache.set(key, value, options={"mode": "ttl", "ttl_seconds": 86400})
```

## How It Works

1. `ttl_seconds` sets expiration time from creation
2. On `get()`, if expired, returns `None` (cache miss)
3. Caller re-fetches and re-caches

## Example: GitHub API Cache

```python
def get_repo_info(owner: str, repo: str):
    cache = namespace("github-integration")
    cache_key = f"repo:{owner}/{repo}"

    info = cache.get(cache_key)
    if info:
        return info

    # Fetch from GitHub API
    import requests
    resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}")
    info = resp.json()

    # Cache for 1 hour
    cache.set(cache_key, info, options={"mode": "ttl", "ttl_seconds": 3600})
    return info
```

## Choosing TTL Values

| Data Type | Suggested TTL | Rationale |
|-----------|---------------|-----------|
| User profiles | 5-15 min | Changes occasionally |
| Repo metadata | 1 hour | Stable but updated |
| Package versions | 24 hours | Releases infrequent |
| Static docs | 1 week | Rarely changes |
