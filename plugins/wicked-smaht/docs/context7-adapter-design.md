# Context7 Adapter Design

## Overview

The Context7 adapter integrates external library documentation into wicked-smaht's context assembly pipeline. It queries Context7 via MCP integration to fetch relevant docs for libraries mentioned in user prompts.

## Architecture

### Component Structure

```
scripts/adapters/
├── __init__.py              # ContextItem dataclass
├── context7_adapter.py      # New adapter implementation
├── mem_adapter.py
├── search_adapter.py
└── ...
```

### Data Flow

```
User Prompt
    ↓
Extract Library Names (regex patterns)
    ↓
For each library:
    ├─→ Check Cache (TTL: 1hr)
    │   ├─→ HIT: Return cached ContextItems
    │   └─→ MISS: Continue to query
    ├─→ Resolve Library ID (MCP: resolve-library-id)
    │   └─→ "react" → "/facebook/react"
    ├─→ Query Docs (MCP: query-docs)
    │   └─→ Documentation snippets
    ├─→ Transform to ContextItems
    └─→ Cache Results
    ↓
Return List[ContextItem]
```

## Key Design Decisions

### 1. Graceful Degradation

The adapter must work even when Context7 MCP integration is unavailable:

- **No hard MCP dependency**: Import MCP tools at runtime
- **Fallback library mapping**: Common libraries have hardcoded ID mappings
- **Empty results on failure**: Return `[]` rather than raising exceptions
- **Comprehensive error logging**: Failures logged to stderr but don't break pipeline

### 2. Caching Strategy

File-based cache with TTL invalidation:

```python
~/.something-wicked/wicked-smaht/cache/context7/
├── index.json         # Cache metadata
└── data/
    ├── abc123.json    # Cached results
    └── def456.json
```

**Cache Entry Format**:
```json
{
  "library_id": "/facebook/react",
  "query": "how to use useEffect hook",
  "cached_at": "2025-01-15T10:30:00Z",
  "item_count": 5
}
```

**Benefits**:
- Avoids repeated API calls for same library+query
- 1-hour TTL balances freshness vs performance
- LRU eviction (oldest 10%) when cache exceeds 500 entries
- Survives process restarts

### 3. Library Name Extraction

Multi-pattern heuristic approach:

**Pattern 1: Direct mentions**
```
"How to use React hooks?" → ["react"]
"FastAPI vs Django" → ["fastapi", "django"]
```

**Pattern 2: Package managers**
```
"npm install express" → ["express"]
"pip install fastapi" → ["fastapi"]
```

**Pattern 3: Import statements**
```
"from django.db import models" → ["django"]
"import { useState } from 'react'" → ["react"]
```

**False positive filtering**:
- Skip Python built-ins (os, sys, json, etc.)
- Require minimum 2 characters
- Deduplicate results
- Limit to 5 libraries per query

### 4. Timeout Handling

Aggressive timeouts to maintain fast-path performance:

| Operation | Timeout | Rationale |
|-----------|---------|-----------|
| Library ID resolution | 2.5s | Simple lookup, should be instant |
| Doc query | 2.5s | External API, but cached |
| Total per library | 5s | Parallel queries across libraries |

**Timeout behavior**:
- `asyncio.TimeoutError` raised and caught
- Logged to stderr
- Does not retry (cache will be empty)
- Next query can try again

### 5. ContextItem Transformation

Context7 docs → wicked-smaht format:

```python
ContextItem(
    id="context7:/facebook/react:0",
    source="context7",
    title="React: useEffect Hook",
    summary="The useEffect Hook lets you perform side effects...",
    excerpt="useEffect(() => { /* effect */ }, [deps])",
    relevance=0.85,  # From Context7 ranking
    age_days=0.0,    # External docs are current
    metadata={
        'library_id': '/facebook/react',
        'library_name': 'react',
        'url': 'https://react.dev/reference/...',
        'source_type': 'external_docs',
    }
)
```

**Field mapping**:
- `id`: Unique per result (library_id + index)
- `source`: Always "context7"
- `title`: From doc title or synthesized
- `summary`: First 200 chars of content
- `excerpt`: First 500 chars (for display)
- `relevance`: Context7 score (default 0.7)
- `metadata`: Library context + URL

## Integration Points

### MCP Tools Used

1. **resolve-library-id**
   - Input: Library name + user query
   - Output: Context7 library ID (e.g., "/facebook/react")
   - Fallback: Hardcoded mapping for common libraries

2. **query-docs**
   - Input: Library ID + user query
   - Output: Documentation snippets with scores
   - Fallback: Empty list

### wicked-cache Integration

**Not used** - Context7 adapter implements its own cache:

**Rationale**:
- wicked-cache uses file-based invalidation (mtime)
- Context7 results need TTL-based invalidation
- Custom cache is simpler and more appropriate

**Future**: Could refactor wicked-cache to support TTL mode, then migrate.

### Router Integration

Context7 adapter selected based on intent:

```python
ADAPTER_RULES = {
    IntentType.RESEARCH: ["search", "mem", "context7"],  # NEW
    IntentType.IMPLEMENTATION: ["search", "kanban", "context7"],  # NEW
    IntentType.DEBUGGING: ["search", "mem"],  # No Context7
    ...
}
```

**Logic**: Add "context7" to rules where library docs are valuable.

## Error Handling

### Error Categories

1. **MCP Unavailable** (ImportError)
   - Graceful: Return empty list
   - Log: Not logged (expected in some environments)
   - Impact: Adapter skipped, other sources used

2. **Library Not Found**
   - Graceful: Return empty list for that library
   - Log: No logging (common case)
   - Impact: Try remaining libraries

3. **Timeout** (asyncio.TimeoutError)
   - Graceful: Return partial results
   - Log: Warning to stderr
   - Impact: Continue with other libraries

4. **API Error** (Exception)
   - Graceful: Return partial results
   - Log: Warning with exception message
   - Impact: Continue with other libraries

5. **Cache Corruption**
   - Graceful: Remove corrupted entry, query fresh
   - Log: Warning to stderr
   - Impact: Single query degraded, no session impact

### Error Propagation

**Never raise to caller** - All exceptions caught and logged:

```python
try:
    items = await _query_context7(lib_name, prompt)
except asyncio.TimeoutError:
    print(f"Warning: timeout for {lib_name}", file=sys.stderr)
except Exception as e:
    print(f"Warning: query failed: {e}", file=sys.stderr)
```

## Performance Characteristics

### Fast Path Target: <500ms

| Component | Latency | Cache Hit | Cache Miss |
|-----------|---------|-----------|------------|
| Extract libraries | <1ms | N/A | N/A |
| Cache lookup | <5ms | ✓ | - |
| Resolve library ID | - | - | ~100ms |
| Query docs | - | - | ~200ms |
| Transform results | <1ms | N/A | N/A |
| **Total (1 library)** | **<10ms** | **~300ms** |

**Optimization strategies**:
1. Cache hits dominate (1hr TTL)
2. Parallel library queries (3 max)
3. Short timeouts prevent slow tail
4. Limit results to 5 per library

### Cache Efficiency

Expected hit rates:

- **Same prompt**: 100% (exact match)
- **Similar prompts**: 0% (cache key includes full query)
- **Same library**: Varies by query diversity

**Trade-off**: Broader cache keys (library only) would increase hits but reduce relevance.

**Decision**: Narrow keys (library + query) for accuracy.

## Testing Strategy

### Unit Tests

1. **Library extraction**
   - Various prompt formats
   - False positive filtering
   - Edge cases (empty, malformed)

2. **Cache operations**
   - Set/get cycle
   - TTL expiration
   - LRU eviction
   - Corruption handling

3. **Error handling**
   - Timeout simulation
   - MCP unavailable
   - Malformed responses

### Integration Tests

1. **End-to-end with mock MCP**
   - Resolve library ID
   - Query docs
   - Transform to ContextItems

2. **Cache persistence**
   - Write to disk
   - Read from disk
   - Survive process restart

### Manual Testing

1. **Live MCP integration**
   - Real Context7 queries
   - Latency measurement
   - Result quality assessment

2. **Graceful degradation**
   - Disable MCP
   - Verify empty results
   - Check logging

## Code Structure

### Main Entry Point

```python
async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """
    Public API matching other adapters.

    Returns:
        List of ContextItems from Context7 docs
    """
```

### Supporting Functions

```python
async def _query_context7(library_name: str, query: str) -> List[ContextItem]:
    """Orchestrates library ID resolution and doc query."""

async def _resolve_library_id(library_name: str, query: str) -> Optional[str]:
    """Calls MCP resolve-library-id tool."""

async def _query_docs(library_id: str, query: str) -> List[Dict[str, Any]]:
    """Calls MCP query-docs tool."""

def _extract_library_names(prompt: str) -> List[str]:
    """Regex-based library name extraction."""
```

### Cache Class

```python
class Context7Cache:
    """File-based TTL cache for Context7 results."""

    def get(self, library_id: str, query: str) -> Optional[List[ContextItem]]
    def set(self, library_id: str, query: str, items: List[ContextItem])
    def clear(self)
```

## Configuration

### Constants

```python
CACHE_DIR = Path.home() / ".something-wicked" / "wicked-smaht" / "cache" / "context7"
CACHE_TTL_SECONDS = 3600  # 1 hour
MAX_CACHE_ENTRIES = 500
```

### Tunables

| Parameter | Current | Rationale | Tuning Guide |
|-----------|---------|-----------|--------------|
| TTL | 1 hour | Balance freshness/perf | Increase for stable docs |
| Max entries | 500 | ~10MB cache size | Increase if disk permits |
| Timeout | 5s | Fast path budget | Decrease for stricter latency |
| Max libraries | 3 | Limit external calls | Increase for broader context |
| Results per lib | 5 | Limit context size | Increase if tokens allow |

## Future Enhancements

### 1. Semantic Cache Keys

**Current**: Exact query match required for cache hit
**Proposed**: Use embedding similarity for fuzzy matching

Benefits:
- Higher cache hit rate
- Better query paraphrasing support

Challenges:
- Requires embedding model
- More complex cache lookup

### 2. Result Ranking

**Current**: Use Context7 scores as-is
**Proposed**: Re-rank based on prompt context

Benefits:
- More relevant results for composite queries
- Better integration with wicked-smaht's intent system

Challenges:
- Requires LLM or semantic model
- Increases latency

### 3. Multi-version Support

**Current**: Latest version only
**Proposed**: Allow version-specific queries

Example:
```
"React 17 useEffect" → /facebook/react/v17
"React 18 useEffect" → /facebook/react/v18
```

Benefits:
- Accurate for legacy projects
- Supports migration scenarios

Challenges:
- Version extraction from prompt
- More cache entries

### 4. Cross-library Context

**Current**: Each library queried independently
**Proposed**: Combine results for comparative queries

Example:
```
"React vs Vue component syntax" → Compare snippets
```

Benefits:
- Better for decision-making queries
- Richer context for tradeoff analysis

Challenges:
- Complex result synthesis
- Requires comparison logic

## Migration Path

### Phase 1: Basic Integration (Current)

- Implement adapter with fallback library map
- File-based TTL cache
- Regex-based library extraction
- Graceful degradation

### Phase 2: MCP Integration

- Connect to actual Context7 MCP tools
- Real-time library ID resolution
- Live documentation queries
- Telemetry/logging

### Phase 3: Optimization

- Semantic cache keys
- Result re-ranking
- Performance tuning based on metrics
- Enhanced library detection

### Phase 4: Advanced Features

- Multi-version support
- Cross-library synthesis
- Integration with wicked-crew workflows
- Custom library definitions

## Success Metrics

### Performance

- Cache hit rate: >70% after warmup
- P50 latency: <100ms (cached)
- P95 latency: <500ms (uncached)
- Timeout rate: <5%

### Quality

- Library detection accuracy: >90%
- Relevant results: >80% (manual review)
- False positives: <10%
- User satisfaction: Qualitative feedback

### Reliability

- Graceful degradation: 100% (never crash)
- Cache corruption: Auto-recovery
- MCP failures: Logged, not propagated
- Session impact: None (source is optional)

## Appendix A: Example Flows

### Example 1: React Hook Query

**Prompt**: "How do I use the useEffect hook in React?"

**Flow**:
1. Extract libraries: ["react"]
2. Check cache: MISS
3. Resolve ID: "react" → "/facebook/react"
4. Query docs: "useEffect hook" → 5 snippets
5. Transform to ContextItems
6. Cache results
7. Return to fast path assembler

**Result**:
```
### External Docs (Context7)
- **React: useEffect Hook**: The useEffect Hook lets you perform side effects...
- **React: useEffect Dependencies**: Learn about the dependency array...
```

### Example 2: Comparison Query

**Prompt**: "FastAPI vs Django for REST APIs"

**Flow**:
1. Extract libraries: ["fastapi", "django"]
2. Check cache: Both MISS
3. Parallel queries:
   - "fastapi" → "/tiangolo/fastapi" → 5 snippets
   - "django" → "/django/django" → 5 snippets
4. Transform all to ContextItems
5. Cache both
6. Return 10 total items

**Result**:
```
### External Docs (Context7)
- **FastAPI: First Steps**: FastAPI is a modern, fast web framework...
- **Django: REST Framework**: Django REST framework is a powerful toolkit...
```

### Example 3: Graceful Degradation

**Prompt**: "How to configure Express middleware?"

**Flow**:
1. Extract libraries: ["express"]
2. Check cache: MISS
3. Resolve ID: TIMEOUT
4. Log warning to stderr
5. Return empty list
6. Fast path continues with other sources

**Result**: No Context7 results, but search and mem adapters still provide context.

## Appendix B: Implementation Checklist

- [x] Create `context7_adapter.py` with standard async query interface
- [x] Implement `Context7Cache` with TTL and LRU eviction
- [x] Add `_extract_library_names()` with multi-pattern detection
- [x] Add `_resolve_library_id()` with fallback mapping
- [x] Add `_query_docs()` with MCP integration stub
- [x] Implement graceful error handling throughout
- [x] Add comprehensive docstrings
- [ ] Update `__init__.py` to include context7_adapter
- [ ] Update router.py ADAPTER_RULES to include context7
- [ ] Write unit tests for library extraction
- [ ] Write unit tests for cache operations
- [ ] Write integration tests with mock MCP
- [ ] Add Context7 to fast_path.py adapter loading
- [ ] Add Context7 to source_labels in fast_path.py
- [ ] Document in wicked-smaht README.md
- [ ] Add scenario demonstrating Context7 integration
- [ ] Performance benchmark vs other adapters
- [ ] Manual testing with real MCP integration
