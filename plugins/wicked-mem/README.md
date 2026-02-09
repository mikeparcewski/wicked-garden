# wicked-mem

Typed memory (decisions, patterns, preferences, episodes) with signal-based recall and automatic decay. Unlike built-in memory that bloats context with everything, wicked-mem only surfaces memories when your question signals relevance -- so session 47 remembers why you chose JWT without polluting session 3's CSS fix. It learns from your work automatically and never makes you repeat yourself.

## Quick Start

```bash
# Install - starts working immediately via hooks
claude plugin install wicked-mem@wicked-garden

# Store a decision
/wicked-mem:store "Use PostgreSQL for ACID transactions" --type decision --tags database

# Recall relevant memories
/wicked-mem:recall "database"

# Check what's remembered
/wicked-mem:stats

# Review a category
/wicked-mem:review decision
```

After install, memory works automatically:
- **Commits** trigger learning extraction
- **Task completions** capture what you learned
- **Questions about past decisions** pull relevant memories
- **Old memories** decay naturally based on importance and access

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-mem:store` | Store a memory with type and tags | `/wicked-mem:store "Always validate JWT on backend" --type procedural --tags auth` |
| `/wicked-mem:recall` | Search memories semantically | `/wicked-mem:recall "authentication patterns"` |
| `/wicked-mem:review` | Browse and manage memories by category | `/wicked-mem:review decision` |
| `/wicked-mem:stats` | Show memory statistics | `/wicked-mem:stats` |
| `/wicked-mem:forget` | Archive or delete a memory | `/wicked-mem:forget mem_abc123` |

## How It Works

### Automatic Lifecycle

Hooks handle everything - no commands needed in normal workflow:

| Event | What Happens |
|-------|-------------|
| Session start | Archives old memories, cleans up decayed ones |
| Your prompt | Searches memories when you ask about past decisions |
| Git commit | Extracts decisions and learnings automatically |
| Task completion | Captures what you learned |
| Session end | Suggests storing learnings from completed work |

### Memory Types

| Type | Purpose | Lifespan |
|------|---------|----------|
| **Decision** | Choices made and rationale | Permanent |
| **Procedural** | How to do things, patterns | Permanent |
| **Episodic** | What happened, what we learned | 90 days |
| **Preference** | User/agent preferences | Permanent |
| **Working** | Current session context | 1 day |

### When Context Gets Injected

Memory doesn't preload everything. It searches **on-demand** based on signals in your query:

- "How did we handle auth?" → searches for auth-related decisions
- "What's our usual approach to..." → searches procedural memories
- "Build a login page" → no memory search (implementation, not recall)

### Decay Strategy

Memories fade naturally. Important, frequently-accessed memories last longer:

```
effective_ttl = base_ttl x importance_multiplier x access_boost
```

Lifecycle: `active` → `archived` → `decayed` → `deleted`

## Storage

File-based storage at `~/.something-wicked/memory/` - human-readable Markdown with YAML frontmatter. No database required.

```
~/.something-wicked/memory/
├── core/                    # Global memories
└── projects/{project}/      # Project-specific
    ├── episodic/            # What happened (90-day TTL)
    ├── procedural/          # How to do things
    ├── decisions/           # Choices and rationale
    └── working/             # Session context (1-day TTL)
```

## Agents

| Agent | When Invoked |
|-------|-------------|
| `memory-recaller` | User asks recall-oriented questions |
| `memory-learner` | After task completion |
| `memory-archivist` | Session start, maintenance |

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-smaht | Auto-injects memories into context | Manual `/recall` only |
| wicked-cache | Faster repeated searches | Re-searches each time |
| wicked-search | Index memories for code cross-references | No code linking |
| wicked-kanban | Auto-capture learnings from completed tasks | Manual storage |

## License

MIT
