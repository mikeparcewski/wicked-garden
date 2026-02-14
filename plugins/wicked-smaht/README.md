# wicked-smaht

wicked-smaht is the prefrontal cortex of your Claude Code environment. It intercepts every prompt, detects your intent, and automatically assembles relevant context before Claude responds. You never re-explain context, re-search code, or re-recall decisions.

A confidence-based router analyzes your prompt for debugging, planning, implementation, review, or research patterns, then pulls from 6 sources: memories, active tasks, code symbols, brainstorms, project state, and external docs. High-confidence focused queries get a fast 2-adapter path; complex or ambiguous topics get all 6 adapters. A persistent session condenser tracks your topics and decisions across turns so context survives as conversations grow long.

The more wicked-garden plugins you install, the more sources it draws from -- making every plugin smarter by connecting them through a single context layer that no combination of manual commands can replicate.

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

### Intent Detection

Your prompt is analyzed (no LLM calls, pure pattern matching) to determine what you need:

| Intent | Triggers | What Gets Loaded |
|--------|----------|-----------------|
| Debugging | "fix", "error", "bug" | Related code, past fixes, active tasks |
| Planning | "design", "plan", "strategy" | Project phase, brainstorms, architecture decisions |
| Research | "what is", "explain", "where" | Code symbols, documentation, past learnings |
| Implementation | "build", "create", "add" | Active tasks, code context, past patterns |
| Review | "review", "check", "PR" | Code changes, test coverage, past reviews |

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

Missing plugins are silently skipped - you get context from whatever is available.

### Hot / Fast / Deep Path

| Path | Sources | When Used |
|------|---------|-----------|
| **Hot** | Session state only (no adapters) | Continuations, confirmations ("yes", "do it", "looks good") |
| **Fast** | 2-3 intent-specific adapters | High confidence, focused queries |
| **Deep** | All 6 adapters + history | Complex planning, ambiguous, or novel topics |

The router escalates to the deep path when it detects low confidence, competing intents, or references to past conversations. Short confirmations hit the hot path for instant responses using only the session "ticket rail" (current task, decisions, constraints, active files).

## Example Context Briefing

When you ask "Fix the auth token expiration bug", wicked-smaht generates:

```
Intent: debugging (confidence: 0.85)
Path: Fast (debugging-focused adapters)

From wicked-mem: "Use JWT with 1h expiry, refresh tokens in Redis with 7d TTL"
From wicked-search: auth.py:validate_token() - decodes JWT, checks expiration
From wicked-kanban: Task #12 "Fix auth token validation" - In Progress
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

Works standalone (no-op without other plugins). Enhanced with:

| Plugin | What It Adds |
|--------|-------------|
| wicked-mem | Past decisions, learnings, patterns |
| wicked-kanban | Active tasks, artifacts |
| wicked-search | Code symbols, documentation |
| wicked-crew | Project phase, goals |
| wicked-jam | Brainstorm sessions |
| wicked-startah | External library docs via Context7 |

## License

MIT
