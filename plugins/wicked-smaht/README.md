# wicked-smaht

AI session memory that learns how you work. wicked-smaht remembers what you were doing across sessions, detects your intent from every prompt, and pre-loads exactly the context you need -- before you ask for it. No re-explaining, no re-searching, no lost context.

A confidence-based router analyzes your prompt for debugging, planning, implementation, review, or research patterns, then pulls from 8 sources in parallel. Intent prediction anticipates what you'll need next based on workflow patterns (e.g., after two implementation turns, pre-loads review context). Cross-session memory persists your topics, decisions, and active files so returning to a project picks up where you left off -- even days later.

Every turn shows visible metrics: which sources were queried, how many items were pre-loaded, and what latency path was used. The `/debug` command reveals turn savings estimates and session state. The more plugins you install, the more sources it draws from -- but it works standalone as a session memory system.

## Quick Start

```bash
# Install - that's it, works automatically via hooks
claude plugin install wicked-smaht@wicked-garden
```

After install, wicked-smaht runs automatically:
- **On session start**: Loads your active project, tasks, and session context
- **On every prompt**: Detects your intent, pulls relevant context from installed plugins

No commands needed for normal use. It just works.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/smaht` | Manually gather context | `/smaht` |
| `/smaht --deep` | Force comprehensive context from all sources | `/smaht --deep` |
| `/smaht --sources` | Show which adapters were selected and why | `/smaht --sources` |
| `/onboard` | Codebase onboarding walkthrough | `/onboard` |
| `/debug` | Show session state, routing stats, context preview | `/debug --state` |

## How It Works

### Cross-Session Memory

When you end a session, wicked-smaht persists a summary: topics discussed, decisions made, active files, and current task. When you start a new session, it loads recent sessions so you never lose context:

```
Previous sessions:
  - caching, auth (15 turns, 2h ago) — Fix auth token validation
  - search indexing (8 turns, 1d ago) — Build unified search index
```

This works standalone -- no other plugins required.

### Intent Detection & Prediction

Your prompt is analyzed (no LLM calls, pure pattern matching) to determine what you need:

| Intent | Triggers | What Gets Loaded |
|--------|----------|-----------------|
| Debugging | "fix", "error", "bug" | Related code, past fixes, active tasks |
| Planning | "design", "plan", "strategy" | Project phase, brainstorms, architecture decisions |
| Research | "what is", "explain", "where" | Code symbols, documentation, past learnings |
| Implementation | "build", "create", "add" | Active tasks, code context, past patterns, delegation hints |
| Review | "review", "check", "PR" | Code changes, test coverage, past reviews |

**Intent prediction** tracks your workflow patterns and pre-loads bonus context for what's likely next. For example, after two consecutive implementation turns, review adapters are pre-loaded for the next turn.

### Context Sources

wicked-smaht pulls from whatever plugins you have installed:

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

Missing plugins are silently skipped -- you get context from whatever is available.

### Hot / Fast / Deep Path

| Path | Sources | When Used |
|------|---------|-----------|
| **Hot** | Session state only (no adapters) | Continuations, confirmations ("yes", "do it", "looks good") |
| **Fast** | 2-5 intent-specific adapters + predicted bonus | High confidence, focused queries |
| **Deep** | All 8 adapters + history | Complex planning, ambiguous, or novel topics |

The router escalates to the deep path when it detects low confidence, competing intents, or references to past conversations. Short confirmations hit the hot path for instant responses using only the session "ticket rail" (current task, decisions, constraints, active files).

### Proactive Suggestions

Each turn may include at most one suggestion based on detected patterns:

- **Past decisions**: If a relevant decision (relevance > 0.6) is found in memory, it's surfaced
- **Delegation hints**: If a specialist plugin matches the current task, delegation is suggested

### Visible Metrics

Every prompt response includes a metadata badge showing what happened:

```
<!-- wicked-smaht v2 | path=fast | 3 sources, 0 failed | 142ms | turn=7 -->
```

Use `/debug` to see full session metrics including estimated turn savings.

## Example Context Briefing

When you ask "Fix the auth token expiration bug", wicked-smaht generates:

```
Intent: debugging (confidence: 0.85)
Path: Fast (debugging-focused adapters)

From wicked-mem: "Use JWT with 1h expiry, refresh tokens in Redis with 7d TTL"
From wicked-search: auth.py:validate_token() - decodes JWT, checks expiration
From wicked-kanban: Task #12 "Fix auth token validation" - In Progress

Suggestion: Related past decision found: "JWT token strategy"
```

This context is injected before Claude responds, so you get informed answers without re-explaining.

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

## Integration

Works standalone as session memory. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-mem | Past decisions, learnings, patterns surfaced per-turn | Session memory only, no long-term recall |
| wicked-kanban | Active tasks, blockers in context | No task awareness |
| wicked-search | Code symbols, documentation lookup | No code context |
| wicked-crew | Project phase, goals, outcomes | No project awareness |
| wicked-jam | Past brainstorm sessions and decisions | No brainstorm recall |
| wicked-startah | External library docs via Context7 + delegation routing | No external docs, no delegation hints |

## License

MIT
