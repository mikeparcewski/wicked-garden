# wicked-smaht

Automatic context assembly that detects your intent, queries up to 8 plugin sources in parallel, and injects the right memories, tasks, code symbols, and past decisions before Claude responds -- without you asking for any of it.

A confidence-based router sends simple continuations through a hot path (zero adapter calls, instant), focused queries through a fast path (2-5 intent-specific adapters), and complex or ambiguous prompts through a deep path (all sources plus session history). Intent prediction tracks workflow patterns and pre-loads bonus context for what you'll likely need next. Cross-session memory persists your topics, decisions, and active files so returning to a project picks up where you left off -- even days later.

Every turn shows a visible metrics badge. The more plugins you install, the more sources it draws from.

## Quick Start

```bash
# Install -- works automatically via hooks, no configuration needed
claude plugin install wicked-smaht@wicked-garden
```

After install, wicked-smaht runs on every prompt:
- **Session start**: Loads your active project, tasks, and recent session context
- **Every prompt**: Detects intent, queries installed plugins, injects context before Claude responds

No commands needed for normal use. It just works.

## Workflows

### See what got assembled for a prompt

When you ask "Fix the auth token expiration bug", wicked-smaht generates a context briefing before Claude responds:

```
Intent: debugging (confidence: 0.85)
Path: fast (debugging-focused adapters)

From wicked-mem: "Use JWT with 1h expiry, refresh tokens in Redis with 7d TTL"
From wicked-search: auth.py:validate_token() -- decodes JWT, checks expiration
From wicked-kanban: Task #12 "Fix auth token validation" -- In Progress

Suggestion: Related past decision found: "JWT token strategy"
```

This context is injected before Claude responds, so you get informed answers without re-explaining your stack.

### Cross-session continuity

When you start a new session after a break, wicked-smaht surfaces what was active:

```
Previous sessions:
  - caching, auth (15 turns, 2h ago) -- Fix auth token validation
  - search indexing (8 turns, 1d ago) -- Build unified search index
```

### Force comprehensive context for complex work

```bash
/smaht --deep               # Pull from all 8 sources regardless of intent confidence
/smaht --sources            # Show which adapters were selected and why
/debug --state              # Show turn count, routing stats, and full session state
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/smaht` | Manually gather and display context for the current prompt | `/smaht` |
| `/smaht --deep` | Force comprehensive context assembly from all sources | `/smaht --deep` |
| `/smaht --sources` | Show which adapters were selected and why | `/smaht --sources` |
| `/onboard` | Codebase onboarding walkthrough for new projects | `/onboard` |
| `/debug` | Show session state, routing stats, and context preview | `/debug --state` |

## How It Works

### Intent Detection and Prediction

Your prompt is analyzed with pure pattern matching (no LLM calls) to determine what you need:

| Intent | Trigger Keywords | What Gets Loaded |
|--------|-----------------|-----------------|
| Debugging | "fix", "error", "bug" | Related code, past fixes, active tasks |
| Planning | "design", "plan", "strategy" | Project phase, brainstorms, architecture decisions |
| Research | "what is", "explain", "where" | Code symbols, documentation, past learnings |
| Implementation | "build", "create", "add" | Active tasks, code context, past patterns, delegation hints |
| Review | "review", "check", "PR" | Code changes, test coverage, past reviews |

**Intent prediction** tracks your workflow patterns. After two consecutive implementation turns, review adapters are pre-loaded for the next turn.

### Hot / Fast / Deep Routing

| Path | Sources | When Used |
|------|---------|-----------|
| **Hot** | Session state only, zero adapter calls | Continuations: "yes", "do it", "looks good" |
| **Fast** | 2-5 intent-specific adapters + predicted bonus | High-confidence, focused queries |
| **Deep** | All 8 adapters + session history | Complex, ambiguous, or novel topics |

The router escalates to deep when it detects low confidence, competing intents, or references to past conversations.

### Context Sources

wicked-smaht pulls from whatever plugins you have installed -- missing plugins are silently skipped:

| Source | What It Provides | Required Plugin |
|--------|-----------------|-----------------|
| Memories | Past decisions, learnings, patterns | wicked-mem |
| Tasks | Active work items, blockers | wicked-kanban |
| Code | Symbol definitions, documentation | wicked-search |
| Project | Current phase, goals, outcomes | wicked-crew |
| Brainstorms | Past discussions, perspectives | wicked-jam |
| Library docs | External API documentation | wicked-startah |
| Delegation | Specialist routing hints | wicked-smaht (built-in) |
| Context7 | Live framework documentation | wicked-startah |

### Proactive Suggestions

Each turn surfaces at most one suggestion:
- **Past decisions**: If a relevant decision (relevance > 0.6) is found in memory, it's surfaced
- **Delegation hints**: If a specialist plugin matches the current task, delegation is suggested

### Visible Metrics

Every response includes a metadata badge:

```
<!-- wicked-smaht v2 | path=fast | 3 sources, 0 failed | 142ms | turn=7 -->
```

Use `/debug` for full session metrics including estimated turn savings.

## Data API

This plugin exposes data via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| sessions | list, get, stats | Session state with condensed context and routing history |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-smaht/{source}/{verb}
```

Or directly via CLI:
```bash
python3 scripts/api.py {verb} {source} [--limit N] [--offset N] [--query Q]
```

## Skills

| Skill | What It Covers |
|-------|---------------|
| `context-assembly` | Routing tiers, adapter selection, intent detection, and session memory patterns |

## Integration

Works standalone as session memory. Each additional plugin adds a source to the assembly pipeline.

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-mem | Past decisions, learnings, and patterns surfaced per turn from long-term memory | Session memory only -- context resets on restart |
| wicked-kanban | Active tasks and blockers injected into every relevant response | No task awareness, you re-state your context each session |
| wicked-search | Code symbols and documentation looked up by the search adapter | No code context -- you paste relevant snippets manually |
| wicked-crew | Current project phase, goals, and outcomes pulled automatically | No project awareness, you describe the phase each time |
| wicked-jam | Past brainstorm sessions and decisions recalled by topic | No brainstorm recall -- past discussions stay in chat history |
| wicked-startah | External library docs via Context7 plus delegation routing hints | No external docs, no routing hints for specialist delegation |

## License

MIT
