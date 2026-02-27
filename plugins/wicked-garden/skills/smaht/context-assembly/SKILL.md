---
name: context-assembly
description: Intelligent context gathering from wicked-garden sources. Use when resuming projects, researching background, or needing decisions and brainstorms from mem, jam, kanban, search, and crew.
---

# Context Assembly

Gather relevant context before responding using wicked-smaht v2's tiered hybrid architecture.

## When to Use

Use context assembly when:
- Starting work on a complex topic
- Resuming a previous conversation or project
- Needing background on decisions, brainstorms, or code
- Switching between projects or phases

## Quick Reference

```bash
# Gather context (automatic fast/slow path selection)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/v2/orchestrator.py" gather "your query"

# Just route (see path decision without gathering)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/v2/orchestrator.py" route "your query" --json

# Force deep analysis via slow path
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/v2/orchestrator.py" gather "your query" --session my-session
```

## Architecture

| Path | Latency | Adapters | Depth |
|------|---------|----------|-------|
| Hot | <100ms | None (session state only) | Ticket rail: task, decisions, constraints, files |
| Fast | ~500ms | Intent-specific (2-3) | 5 items/source |
| Slow | ~525ms | All adapters (6) | 10 items/source + history |

Router triggers **hot path** for short continuations/confirmations (<30 chars, e.g. "yes", "do it").

Router triggers **slow path** when:
- Low confidence (<0.5) or competing intents
- References conversation history
- Planning/design request
- Novel topic or compound request

## Context Sources

| Source | Plugin | Content |
|--------|--------|---------|
| mem | wicked-mem | Memories, decisions, learnings |
| jam | wicked-jam | Brainstorm sessions, perspectives |
| kanban | wicked-kanban | Tasks, artifacts, projects |
| search | wicked-search | Code symbols, documentation |
| crew | wicked-crew | Project phase, outcomes, constraints |
| context7 | wicked-startah | External documentation (optional) |

## Intent Types

| Type | Prioritizes | Pattern Examples |
|------|-------------|------------------|
| debugging | Recent items, code refs | "fix", "error", "crash" |
| planning | Project context, brainstorms | "design", "strategy", "approach" |
| research | Semantic matches | "what is", "explain", "where" |
| implementation | Tasks, code | "build", "create", "add" |
| review | Code, tasks | "review", "check", "PR" |
| general | Balanced | (default fallback) |

## Briefing Format

```markdown
# Context Briefing

## Situation
**Intent**: research (confidence: 0.85)
**Entities**: router.py, FastPathAssembler

## Relevant Context

### Memories
- **Auth decision**: Use JWT with 1h expiry...

### Code & Docs
- **router.py**: Intent detection with regex patterns...
```

## Automatic Enrichment

Context is gathered automatically via hooks:
- **SessionStart**: Initial session context
- **UserPromptSubmit**: Per-turn context injection
