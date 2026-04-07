---
description: Manually trigger memory consolidation across tiers
argument-hint: ""
---

# /wicked-garden:mem:consolidate

Run memory consolidation via brain skills. This synthesizes wiki articles from memory chunks and auto-decays expired TTL chunks.

## What It Does

1. **Compile**: Synthesizes wiki articles from related memory chunks (groups by topic, creates knowledge pages)
2. **Lint**: Auto-decays expired TTL chunks, cleans broken references, validates integrity

## Execution

### Step 1: Invoke brain compile skill

```
Skill(skill="wicked-brain-compile")
```

This is an LLM-driven operation that reads memory chunks, identifies concept clusters, and writes wiki articles to `~/.wicked-brain/wiki/concepts/`.

### Step 2: Invoke brain lint skill

```
Skill(skill="wicked-brain-lint")
```

This checks chunk health: expired TTL, broken wikilinks, missing frontmatter fields.

### Step 3: Report results

Display what compile created and what lint cleaned up.

If brain is unavailable, suggest: `wicked-brain-server` to start it.

## When to Use

- After long sessions with many working memories
- Periodically to promote recurring patterns to wiki articles
- Before important sessions where you want consolidated knowledge
- Note: Working memory consolidation runs automatically on session end
