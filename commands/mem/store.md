---
description: Store a new memory
argument-hint: "<content>" [--type episodic|decision|procedural|preference] [--tier working|episodic|semantic] [--tags tag1,tag2]
---

# /wicked-garden:mem:store

Store a memory for persistence across sessions via the brain API.

## Arguments

Parse the arguments from: $ARGUMENTS

The first quoted string is the content. Extract a short title (5-10 words) from the content.

- `content` (required): The memory content to store (first quoted string)
- `--type`: Memory type - episodic (default), decision, procedural, preference
- `--tier`: Consolidation tier - working, episodic (default), semantic. Auto-detected from type/importance when omitted.
- `--tags`: Comma-separated tags for categorization
- `--importance`: low, medium (default), high

## Execution

### Step 1: Determine tier from type and importance

Use these defaults when `--tier` is not specified:

| Type | Default Tier |
|------|-------------|
| `episodic` | episodic |
| `decision` | semantic |
| `procedural` | episodic |
| `preference` | semantic |

If `--importance high` is specified, promote to `semantic` tier regardless.

### Step 2: Generate a UUID

```bash
python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || python -c "import uuid; print(uuid.uuid4())"
```

### Step 3: Write the chunk file

Use the Write tool to create the file at `$HOME/.wicked-brain/memories/{tier}/mem-{uuid}.md` with this format:

```markdown
---
source: wicked-mem
memory_type: {type}
memory_tier: {tier}
title: "{title}"
tags:
  - tag1
  - tag2
  - auto-tag1
  - auto-tag2
importance: {importance}
indexed_at: "{ISO-8601 timestamp}"
---

{content}
```

### Step 4: Index via brain API

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"index","params":{"id":"memories/{tier}/mem-{uuid}","path":"memories/{tier}/mem-{uuid}","content":"{searchable text: title + content + tags joined}","brain_id":"wicked-brain"}}'
```

If the brain API is unreachable, report that the chunk file was written but indexing failed. Suggest running `wicked-brain:ingest` to index later.

## Memory Type Guidelines

| Type | Use When | TTL | Auto Tier |
|------|----------|-----|-----------|
| `episodic` | Recording what happened, debugging sessions, test results | 90 days | episodic |
| `decision` | Architectural choices, technology selections, trade-offs | Permanent | semantic |
| `procedural` | How-to knowledge, patterns, workflows | Permanent | episodic |
| `preference` | User/project preferences, coding style | Permanent | semantic |

## Tier Guidelines

| Tier | Purpose | Recall Weight |
|------|---------|---------------|
| `working` | Transient session context, auto-consolidated on session end | 0.8x |
| `episodic` | Sprint-level patterns and observations (default) | 1.0x |
| `semantic` | Durable project knowledge, prioritized in search results | 1.3x |

## Tag Generation

When storing a memory, ALWAYS generate 3-5 search tags even if the user doesn't specify `--tags`. Combine user-provided tags with auto-generated ones.

Generate tags that include:
- **Synonyms**: auth/authentication, DB/database, API/endpoint, config/configuration
- **Abbreviations**: JWT, REST, GraphQL, CI/CD, K8s/Kubernetes
- **Related concepts**: "jwt" -> also tag tokens, session, security
- **Domain terms**: specific technology/pattern names mentioned
- **Think**: "what would someone search for to find this memory?"

Example: For content "Chose JWT with 15-minute expiry and httpOnly refresh tokens":
- User tags: `auth, architecture`
- Auto-generated: `jwt, tokens, session, security, authentication, cookies, refresh-token`
- Final: `auth, architecture, jwt, tokens, session, security, authentication, cookies, refresh-token`

Merge user-provided tags with auto-generated tags. Deduplicate.

## Examples

```bash
# Store a decision
/wicked-garden:mem:store "Chose PostgreSQL for transaction support" --type decision --tags database,architecture

# Store a debugging session outcome
/wicked-garden:mem:store "Fixed auth bug: JWT was expiring too early" --type episodic --tags auth,bugfix

# Store a learned pattern
/wicked-garden:mem:store "Use early returns for validation, then happy path" --type procedural --tags code-style
```

## Output

Confirm storage with:
- Memory ID (mem-{uuid})
- Type, tier, and tags
- Chunk file path
- Brain index status (indexed / index failed)
