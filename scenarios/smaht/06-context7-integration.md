# Scenario 6: Context7 External Documentation Integration

## Overview

Demonstrates how wicked-smaht automatically enriches context with external library documentation via Context7 when detecting library-related queries.

## Setup

**Prerequisites**:
- wicked-smaht installed
- wicked-garden plugin with Context7 MCP integration (optional - graceful degradation)
- Active session with wicked-smaht hooks enabled

**Initial State**:
- Clean session (no prior context)
- Context7 cache empty
- Working on a new React project

## User Flow

### Step 1: Implementation Query

**User**: "How do I use the useEffect hook in React to fetch data?"

**wicked-smaht behavior**:
1. Hook intercepts prompt (UserPromptSubmit)
2. Router analyzes: IMPLEMENTATION intent (confidence: 0.75)
3. Decides: FAST path (short, focused query)
4. Fast path assembler selects adapters: ["search", "kanban", "context7"]
5. Context7 adapter:
   - Extracts libraries: ["react"]
   - Cache lookup: MISS
   - Resolves library ID: "react" → "/facebook/react"
   - Queries Context7 docs: "useEffect hook fetch data"
   - Receives 5 documentation snippets
   - Caches results (TTL: 1 hour)
   - Returns ContextItems

**Context injected**:
```markdown
# Context Briefing (fast)

## Situation
**Intent**: implementation (confidence: 0.75)
**Entities**: useEffect, React

## Relevant Context

### Code & Docs
- **FetchHook.tsx:15**: Custom hook using useEffect for data fetching

### External Docs
- **React: useEffect Hook**: The useEffect Hook lets you perform side effects in function components...
- **React: Fetching Data**: Learn how to fetch data with useEffect and handle loading states...
- **React: useEffect Dependencies**: Understanding the dependency array for optimal re-renders...
```

**Claude response**:
- Provides React best practices from Context7
- References local code patterns
- Suggests implementation approach

**Latency**: ~350ms (cache miss, external API call)

---

### Step 2: Similar Query (Cache Hit)

**User**: "What about cleanup in useEffect for data fetching?"

**wicked-smaht behavior**:
1. Router: RESEARCH intent (confidence: 0.82)
2. Fast path: ["search", "mem", "context7"]
3. Context7 adapter:
   - Extracts: ["react"] (same library)
   - Cache lookup: PARTIAL HIT (different query, but related)
   - New query to Context7
   - Caches new results

**Context injected**:
```markdown
### External Docs
- **React: Cleanup Functions**: Learn how to clean up side effects to prevent memory leaks...
- **React: AbortController with useEffect**: Canceling fetch requests when component unmounts...
```

**Latency**: ~150ms (library ID cached, only docs query needed)

---

### Step 3: Comparison Query (Multiple Libraries)

**User**: "Should I use React Query or SWR for data fetching instead?"

**wicked-smaht behavior**:
1. Router: RESEARCH intent (confidence: 0.88)
2. Fast path: ["search", "mem", "context7"]
3. Context7 adapter:
   - Extracts: ["react", "swr"] (two libraries)
   - Parallel queries:
     - "react" → cache HIT (from Step 1)
     - "swr" → cache MISS → query Context7
   - Returns combined results

**Context injected**:
```markdown
### External Docs
- **React Query: Getting Started**: Powerful data synchronization for React applications...
- **SWR: Introduction**: React Hooks library for data fetching by Vercel...
- **SWR: Features**: Revalidation, focus tracking, and request deduplication...
```

**Latency**: ~200ms (one cache hit, one new query)

---

### Step 4: Graceful Degradation (Context7 Unavailable)

**Scenario**: Context7 MCP integration is not available or times out

**User**: "How to configure Express middleware?"

**wicked-smaht behavior**:
1. Router: IMPLEMENTATION intent
2. Fast path: ["search", "kanban", "context7"]
3. Context7 adapter:
   - Extracts: ["express"]
   - Resolves library ID: TIMEOUT (5s)
   - Logs warning to stderr
   - Returns empty list
4. Fast path continues with other sources

**Context injected**:
```markdown
### Code & Docs
- **server.ts:10**: Express app configuration with middleware
- **auth.middleware.ts**: Authentication middleware implementation

### Uncertainties
*Unavailable sources: context7*
```

**Claude response**:
- Still provides helpful answer using local code context
- No mention of Context7 failure (graceful)

**Latency**: ~5s (timeout, then continues)

---

## Edge Cases

### No Library Detected

**User**: "What's the best way to structure my code?"

**Context7 adapter**:
- Extracts: [] (no libraries)
- Returns immediately with empty list
- No external API calls

**Result**: Other adapters provide context, no Context7 contribution.

---

### Multiple Versions (Future)

**User**: "How does useEffect work in React 17 vs React 18?"

**Current behavior**:
- Queries latest React docs only
- Claude synthesizes comparison from knowledge

**Future enhancement**:
- Extract versions: "react@17", "react@18"
- Query both: "/facebook/react/v17", "/facebook/react/v18"
- Provide version-specific docs

---

## Cache Behavior

### Cache Warmup

After several queries about React:

```
~/.something-wicked/wicked-garden/local/wicked-smaht/cache/context7/
├── index.json
└── data/
    ├── a1b2c3d4.json  # react + "useEffect hook fetch data"
    ├── e5f6g7h8.json  # react + "cleanup in useEffect"
    ├── i9j0k1l2.json  # swr + general query
    └── ...
```

**index.json**:
```json
{
  "a1b2c3d4": {
    "library_id": "/facebook/react",
    "query": "How do I use the useEffect hook in React to fetch data?",
    "cached_at": "2025-01-15T10:30:00Z",
    "item_count": 5
  },
  ...
}
```

### TTL Expiration

After 1 hour:
- Next query triggers cache validation
- Expired entry detected
- New query to Context7
- Cache refreshed

### Cache Eviction

When cache exceeds 500 entries:
- Oldest 10% evicted (50 entries)
- Sorted by cached_at timestamp
- Both index and data files removed

---

## Performance Metrics

### Latency by Scenario

| Scenario | Cache State | Latency | Breakdown |
|----------|-------------|---------|-----------|
| First query | Empty | 350ms | Extract (1ms) + Resolve (100ms) + Query (200ms) + Transform (1ms) |
| Same library, diff query | Partial | 150ms | Extract (1ms) + Cache hit ID (5ms) + Query (100ms) |
| Exact cache hit | Full | 8ms | Extract (1ms) + Cache lookup (5ms) + Transform (1ms) |
| Timeout | N/A | 5s | Timeout waiting for Context7 |

### Cache Hit Rates

After warmup session (10 queries):
- Exact match: 20% (same prompt)
- Library ID: 80% (same library, different query)
- Full miss: 20%

---

## Integration with Other Adapters

### Combined Context Example

**Query**: "How to fetch data in React with error handling?"

**Sources**:
1. **search**: Local error handling utilities
2. **mem**: Previous decision about error strategy
3. **context7**: React docs on useEffect and error boundaries

**Briefing**:
```markdown
## Relevant Context

### Memories
- **Decision**: Use error boundaries for component-level error handling

### Code & Docs
- **ErrorBoundary.tsx:20**: Custom error boundary component
- **useErrorHandler.ts:5**: Hook for error state management

### External Docs
- **React: Error Boundaries**: Catch JavaScript errors anywhere in component tree...
- **React: useEffect Error Handling**: Best practices for async errors in effects...
```

**Value**: Combines local patterns with official documentation for comprehensive guidance.

---

## User Experience

### Transparent Operation

Users never explicitly invoke Context7 - it's automatic:
- No special commands
- No configuration needed
- Failures are silent (graceful degradation)
- Results blend with other sources

### Quality Indicators

Users can identify Context7 results by:
- **Source label**: "External Docs" in briefing
- **Metadata**: URLs to official documentation
- **Freshness**: age_days = 0.0 (always current)

### Feedback Loop

If Context7 results are not helpful:
- Users can ignore them (other sources available)
- Context7 adapter learns nothing (no feedback mechanism yet)
- Future: Could track usefulness via interaction patterns

---

## Developer Workflow

### Local Development

1. User asks about a library
2. Context7 provides official docs
3. search adapter provides local implementations
4. User sees both: "what the docs say" vs "how we use it"

### Debugging

1. User encounters library-specific error
2. Context7 provides troubleshooting docs
3. mem adapter recalls similar past issues
4. User gets both: "official solutions" + "what worked for us"

### Learning

1. New team member asks about library usage
2. Context7 provides learning resources
3. jam adapter shows past architectural discussions
4. User gets: "how to learn" + "why we chose it"

---

## Success Criteria

### Functional

- ✓ Extract libraries from 90%+ of prompts containing them
- ✓ Cache hit rate >70% after warmup
- ✓ Graceful degradation when Context7 unavailable
- ✓ No crashes or exceptions propagated

### Performance

- ✓ Cache hit: <10ms overhead
- ✓ Cache miss: <500ms for common libraries
- ✓ Timeout: <5s hard limit
- ✓ No impact on fast path when libraries not detected

### Quality

- ✓ Results relevant to query (Context7 ranking)
- ✓ No false positives (Python built-ins filtered)
- ✓ Version-appropriate docs (for now: latest only)
- ✓ Correct library attribution in metadata

---

## Troubleshooting

### Context7 Results Not Appearing

**Check**:
1. Library mentioned in prompt?
2. Context7 MCP integration installed?
3. Check stderr for timeout/error messages
4. Verify cache not corrupted: `ls ~/.something-wicked/wicked-garden/local/wicked-smaht/cache/context7/`

**Fix**:
- Explicit library mention: "using React hooks"
- Install wicked-garden with Context7
- Clear cache if corrupted

### Wrong Library Detected

**Example**: "I need to import os" → incorrectly tries to query "os" docs

**Current**: Filtered in skip_list
**If missed**: Returns empty (library not in Context7)
**Impact**: Minimal (just empty results)

### Cache Filling Up

**Symptom**: Disk space usage
**Expected**: ~10-20MB for 500 entries
**Fix**: Cache auto-evicts oldest 10%
**Manual**: Delete `~/.something-wicked/wicked-garden/local/wicked-smaht/cache/context7/`

---

## Future Enhancements

### 1. Semantic Cache Keys

Allow fuzzy matching:
- "React hooks" and "React Hooks guide" → same cache entry
- Requires embedding similarity
- Higher hit rate

### 2. Multi-version Support

Extract version from prompt:
- "React 17 useEffect" → "/facebook/react/v17"
- "Next.js 14 app router" → "/vercel/next.js/v14"

### 3. Cross-library Synthesis

Combine docs for comparison:
- "React vs Vue" → synthesized comparison
- "Migrate from Express to FastAPI" → migration guide

### 4. Feedback Loop

Track which Context7 results are useful:
- User clicks on suggested code
- User references doc in follow-up
- Adjust relevance scoring

---

## Summary

Context7 integration provides **automatic enrichment** of context with external library documentation:

**Strengths**:
- Zero-effort for users (automatic)
- Fast with caching (8ms cache hit)
- Graceful degradation (never blocks)
- Complements local context

**Trade-offs**:
- Cache miss latency (350ms)
- Narrow cache keys (query-specific)
- Latest version only (for now)
- Requires MCP integration

**Best for**:
- Learning new libraries
- Debugging library-specific issues
- Comparing library approaches
- Onboarding new developers
