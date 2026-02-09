# Context7 Integration - README Section

Add this section to wicked-smaht's README.md under "Integration Table":

---

## External Documentation via Context7

wicked-smaht automatically enriches context with external library documentation when it detects library-related queries. This happens transparently via the Context7 adapter.

### How It Works

When you mention a library in your prompt:

```
"How do I use React hooks for data fetching?"
```

wicked-smaht:
1. Extracts library names ("react")
2. Queries Context7 for relevant documentation
3. Caches results for 1 hour
4. Includes docs in context briefing

### Supported Detection

The adapter recognizes libraries through:

- **Direct mentions**: "How to use React hooks?"
- **Package managers**: "npm install express"
- **Import statements**: "from django.db import models"

### Performance

| Scenario | Latency |
|----------|---------|
| Cache hit | <10ms |
| Cache miss (first query) | ~300ms |
| Library not found | <5ms |

### Cache

Results are cached at:
```
~/.something-wicked/wicked-smaht/cache/context7/
```

**Settings**:
- TTL: 1 hour
- Max entries: 500 (auto-evicts oldest 10%)
- Per-library + query caching

### Graceful Degradation

Context7 integration is **optional**:
- Works without wicked-startah MCP integration
- Falls back to empty results on timeout/error
- Never blocks other context sources
- Failures logged to stderr only

### Integration Table Update

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-mem | Cross-session memory, promoted facts | Session-only facts |
| wicked-jam | Brainstorm context from sessions | Skipped |
| wicked-kanban | Active task awareness | Skipped |
| wicked-search | Code and document search | Skipped |
| wicked-crew | Project phase context | Skipped |
| **wicked-startah (Context7)** | **External library documentation** | **Skipped** |

### When Context7 Helps

**Best for**:
- Learning new libraries
- Debugging library-specific issues
- Comparing library approaches
- Onboarding team members

**Examples**:

1. **Implementation**
   ```
   User: "How to configure Express middleware?"
   Context7: Provides Express.js official docs
   search: Shows local middleware implementations
   Result: Official best practices + local patterns
   ```

2. **Comparison**
   ```
   User: "FastAPI vs Django for REST APIs?"
   Context7: Provides docs for both frameworks
   Result: Compare official features side-by-side
   ```

3. **Debugging**
   ```
   User: "Why is my React useEffect running twice?"
   Context7: React docs on Strict Mode behavior
   mem: Previous discussion about this issue
   Result: Official explanation + team's solution
   ```

### Configuration

No configuration needed! The adapter:
- Auto-detects libraries in prompts
- Uses default cache settings
- Requires no environment variables

To disable (if needed):
- Remove context7 from ADAPTER_RULES in router.py
- Or delete the adapter file

### Troubleshooting

**No Context7 results appearing?**

1. Check library is mentioned explicitly in prompt
2. Verify wicked-startah with Context7 MCP is installed (optional)
3. Check stderr for timeout/error messages
4. Try clearing cache if corrupted

**Cache location**: `~/.something-wicked/wicked-smaht/cache/context7/`

**Manual cache clear**:
```bash
rm -rf ~/.something-wicked/wicked-smaht/cache/context7/
```

### Limitations

Current version:
- Latest library version only (no version-specific docs)
- Exact query matching for cache (no semantic similarity)
- Maximum 3 libraries per query
- 5 results per library

See `docs/context7-adapter-design.md` for future enhancements.

---

## Privacy & Data

Context7 queries:
- Only library names and your query text
- No project code or sensitive data
- Cached locally on your machine
- No telemetry or tracking

External API calls are made to Context7 (via MCP) only when:
- Cache miss occurs
- Library is detected in prompt
- wicked-startah Context7 integration available

All data stays on your machine except the query itself.
