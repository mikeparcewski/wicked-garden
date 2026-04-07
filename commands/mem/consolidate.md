---
description: Manually trigger memory consolidation across tiers
argument-hint: ""
allowed-tools: [Bash, Read]
---

# /wicked-garden:mem:consolidate

Run memory consolidation via the brain API. This synthesizes wiki articles from memory chunks and auto-decays expired TTL chunks.

## What It Does

1. **Compile**: Synthesizes wiki articles from related memory chunks. Groups memories by topic/domain and creates consolidated knowledge pages.
2. **Lint**: Auto-decays expired TTL chunks, cleans broken references, and validates chunk integrity.

## Execution

### Step 1: Run brain compile

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"compile","params":{}}'
```

Display the compile results (articles created/updated, chunks consumed).

### Step 2: Run brain lint

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"lint","params":{}}'
```

Display the lint results (expired chunks removed, broken refs fixed, issues found).

### Step 3: Handle brain unavailability

If the brain API is unreachable, display:
> Brain API is not reachable. Start it with `wicked-brain:server` or check brain status.

## Output

Display results from both operations:
- **Compile**: Articles created/updated, memory chunks synthesized
- **Lint**: Expired chunks decayed, broken references cleaned, health issues found

## When to Use

- After long sessions with many working memories
- Periodically to keep memory clean and promote recurring patterns
- Before important sessions where you want consolidated knowledge available
- Note: Working memory consolidation runs automatically on session end
