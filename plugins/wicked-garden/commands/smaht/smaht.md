---
description: Gather intelligent context from wicked-garden sources before responding
argument-hint: [query] [--deep]
---

# /wicked-garden:smaht-smaht

Gather and display intelligent context from wicked-garden sources.

## Usage

```
/smaht [query]           # Gather context (fast path if simple)
/smaht --deep [query]    # Force slow path (all sources, history)
/smaht --sources         # Show available sources and their status
```

## Instructions

### 1. Parse Arguments

- `query` (optional): Focus query for context gathering
- `--deep`: Force slow path (all adapters, 2s timeout, history context)
- `--sources`: Show source status instead of gathering

### 2. Gather Context

Run the v2 orchestrator:

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/v2/orchestrator.py gather "{query}" --session {session_id}
```

For sources check:
```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/v2/orchestrator.py route "{query}" --json
```

### 3. Display Results

Show the context briefing in a clear format:

```markdown
## Wicked Smaht Context

**Path**: fast/slow
**Intent**: {detected_intent} (confidence: {score})
**Sources**: {sources_queried}
**Latency**: {ms}ms

{briefing content}
```

### 4. Context Injection

The context briefing is automatically added to the conversation context via UserPromptSubmit hook for Claude to use.

## Examples

```
/smaht                     # General session context
/smaht authentication      # Context about auth
/smaht --deep caching      # Force deep analysis on caching
/smaht --sources           # Check routing decision
```
