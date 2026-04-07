# Brain Chunk Format — Cross-CLI Reference

This document defines the wicked-brain chunk format so any CLI (Claude Code, Codex, Gemini, Copilot) can write chunks that integrate into the shared knowledge graph.

## Chunk File Structure

Each chunk is a Markdown file with YAML frontmatter:

```markdown
---
source: filename.py
source_path: relative/path/to/filename.py
source_type: py
chunk_id: chunks/extracted/relative-path-to-filename.py/chunk-001
content_type:
  - text
contains:
  - keyword1
  - keyword2
  - synonym-of-keyword1
entities:
  systems: [named-systems]
  people: [roles-or-people]
confidence: 0.7
indexed_at: "2026-04-07T12:00:00.000Z"
---

Actual content here in Markdown format.
```

## Required Frontmatter Fields

| Field | Type | Description |
|---|---|---|
| `source` | string | Original filename |
| `source_type` | string | File extension without dot (py, js, md, etc.) |
| `chunk_id` | string | Unique path within the brain directory |
| `content_type` | list | Always `["text"]` for text files |
| `contains` | list | 5-15 keyword tags for FTS5 search |
| `confidence` | float | 0.7 for text extraction, 0.85 for vision |
| `indexed_at` | string | ISO 8601 timestamp in quotes |

## Optional Fields

| Field | Type | Description |
|---|---|---|
| `source_path` | string | Relative path from project root |
| `entities` | dict | Named entities extracted from content |
| `narrative_theme` | string | "So what" summary in 8 words or fewer |
| `memory_id` | string | UUID if this chunk represents a memory |
| `memory_type` | string | episodic, decision, procedural, preference |
| `memory_tier` | string | working, episodic, semantic |
| `ttl_days` | int | Auto-decay after N days (working tier) |

## Brain Directory Layout

```
~/.wicked-brain/
  brain.json                    # Brain identity and links
  raw/                          # Original source files (symlinks)
  chunks/
    extracted/                  # Deterministic extraction from text
      {safe-name}/chunk-NNN.md
    inferred/                   # LLM-generated or working-tier
      {safe-name}/chunk-NNN.md
  wiki/
    concepts/                   # Semantic-tier synthesized articles
    topics/                     # Topic-level wiki articles
  _meta/
    config.json                 # Port, brain path
    log.jsonl                   # Event log
```

## Brain API

All operations go through the HTTP API at `http://localhost:4242/api`:

```bash
# Search
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"search","params":{"query":"authentication","limit":10}}'

# Index a chunk
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"index","params":{"id":"chunk-path","path":"chunk-path","content":"text","brain_id":"wicked-brain"}}'

# Stats
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"stats","params":{}}'

# Health
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"health","params":{}}'
```

## Agent-Driven Ingestion (Any CLI)

Any AI CLI can ingest files into the brain:

1. **Read the file** using the CLI's native file-reading tool
2. **Split into chunks** (Markdown: split on H1/H2; Code: one chunk per file; Other: ~800 word paragraphs)
3. **Write chunk files** to `~/.wicked-brain/chunks/extracted/{safe-name}/chunk-NNN.md`
4. **Index via API**: POST each chunk to the brain server

### Safe Name Convention

Convert file paths to safe chunk directory names:
- Lowercase
- Replace non-alphanumeric characters (except `.` and `-`) with hyphens
- Collapse consecutive hyphens
- Strip leading/trailing hyphens

Example: `scripts/mem/memory.py` -> `scripts-mem-memory.py`

### Tag Expansion

When generating `contains:` tags, expand keywords with synonyms:
- Abbreviations: JWT -> json-web-token, K8s -> kubernetes
- Synonyms: auth -> authentication, DB -> database
- Related concepts: JWT -> tokens, session, security
- Cap at 15 tags per chunk

## Memory Chunks

Memories stored via wicked-garden are indexed as brain chunks at:
- Working tier: `memories/working/mem-{uuid}`
- Episodic tier: `memories/episodic/mem-{uuid}`
- Semantic tier: `memories/semantic/mem-{uuid}`

The brain's `compile` action synthesizes wiki articles from chunk clusters.
The brain's `lint` action auto-decays chunks with expired TTL.
