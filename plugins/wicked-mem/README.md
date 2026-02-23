# wicked-mem

Typed memory with signal-based recall — session 47 automatically remembers why you chose JWT without polluting session 3's CSS fix, because memories only inject when your question signals relevance.

## Quick Start

```bash
# Install — memory starts working automatically via hooks
claude plugin install wicked-mem@wicked-garden

# Store an explicit decision
/wicked-mem:store "Use PostgreSQL for ACID transactions, not MySQL" --type decision --tags database

# Recall relevant context before starting new work
/wicked-mem:recall "database"
```

After install, memory works without any commands. Commits trigger learning extraction, task completions capture what you learned, and old memories decay naturally.

## Workflows

### Automatic Learning from Commits

You commit a bug fix. The Stop hook fires and extracts the decision embedded in your work:

```
Commit: "fix: validate JWT expiry before refreshing token"

Memory extracted:
  [decision] JWT tokens must be validated before refresh, not after
  tags: auth, jwt, security
  importance: high (security-related)
  project: my-api
```

Next week, in a new session, you ask about authentication:

```
"How should we handle token refresh?"
```

Memory searches for auth-related context, finds the decision, and injects it before you continue — without you asking.

### Signal-Based Recall: What Gets Injected

Memory doesn't preload everything into every session. It searches on-demand based on signals in your query:

| Query Signal | Memory Search |
|-------------|--------------|
| "How did we handle auth?" | Searches decisions tagged `auth` |
| "What's our usual approach to error handling?" | Searches procedural memories |
| "Why did we choose Redis?" | Searches decisions tagged `redis`, `cache` |
| "Build a login page" | No search — implementation task, not recall signal |

Implementation requests don't trigger memory. Recall-oriented questions do. This keeps context clean on coding tasks while surfacing relevant history when you're making decisions.

### Explicit Memory Management

When you want to capture something the automatic hooks won't catch:

```bash
# Store an architectural decision
/wicked-mem:store "API gateway owns rate limiting, not individual services" \
  --type decision --tags architecture,api

# Store a pattern for how-to reference
/wicked-mem:store "Always use exponential backoff with jitter on retries" \
  --type procedural --tags resilience,networking

# Review all decisions to spot contradictions
/wicked-mem:review decision

# Forget a stale preference
/wicked-mem:forget mem_abc123
```

### Memory Lifecycle

Memories age naturally. You don't need to clean them up manually:

```
effective_ttl = base_ttl × importance_multiplier × access_boost
```

A decision you reference frequently in active work survives indefinitely. A one-off episode from a completed project fades over 90 days. The lifecycle is: `active` → `archived` → `decayed` → `deleted`.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-mem:store` | Store a memory with type and tags | `/wicked-mem:store "Always validate JWT on backend" --type procedural --tags auth` |
| `/wicked-mem:recall` | Search memories semantically | `/wicked-mem:recall "authentication patterns"` |
| `/wicked-mem:review` | Browse and manage memories by category | `/wicked-mem:review decision` |
| `/wicked-mem:stats` | Show memory statistics and type breakdown | `/wicked-mem:stats` |
| `/wicked-mem:forget` | Archive or delete a specific memory | `/wicked-mem:forget mem_abc123` |

## How It Works

### Automatic Lifecycle

| Event | What Happens |
|-------|-------------|
| Session start | Archives old memories, removes fully decayed ones |
| Your prompt | Searches for relevant context when recall signals detected |
| Git commit | Extracts decisions and learnings from commit message and diff |
| Task completion | Captures what you learned from the completed work |
| Session end | Suggests storing learnings from the session |

### Memory Types

| Type | Purpose | Lifespan |
|------|---------|----------|
| **Decision** | Choices made and the rationale behind them | Permanent |
| **Procedural** | How to do things, patterns, best practices | Permanent |
| **Episodic** | What happened, what you learned from it | 90 days |
| **Preference** | User and agent preferences | Permanent |
| **Working** | Current session context | 1 day |

### Storage

File-based storage at `~/.something-wicked/memory/` — human-readable Markdown with YAML frontmatter. No database required.

```
~/.something-wicked/memory/
├── core/                    # Global memories (cross-project)
└── projects/{project}/      # Project-specific memories
    ├── episodic/            # What happened (90-day TTL)
    ├── procedural/          # How to do things
    ├── decisions/           # Choices and rationale
    └── working/             # Session context (1-day TTL)
```

## Agents

| Agent | When Invoked |
|-------|-------------|
| `memory-recaller` | When you ask recall-oriented questions |
| `memory-learner` | After task completion, to capture learnings |
| `memory-archivist` | Session start, to clean up stale memories |

## Skills

| Skill | What It Does |
|-------|-------------|
| `memory` | Guidance for storing, recalling, and managing memory across sessions |

## Data API

This plugin exposes data via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| memories | list, get, search, stats | Structured memories by type (episodic, decision, procedural, preference) |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-mem/{source}/{verb}
```

Or directly via CLI:
```bash
python3 scripts/api.py {verb} {source} [--limit N] [--offset N] [--query Q]
```

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-smaht | Memories auto-injected into context based on prompt signals | Manual `/recall` before each session |
| wicked-startah | Cached memory lookups — faster repeated searches | Re-searches storage each time |
| wicked-search | Cross-reference memories with code symbols and files | No code linking to memories |
| wicked-kanban | Auto-capture learnings from completed task descriptions | Manual storage after each task |

## License

MIT
