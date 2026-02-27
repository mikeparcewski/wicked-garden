---
description: Show available context assembly commands and usage
---

# /wicked-garden:smaht:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-smaht Help

Intelligent context assembly — intercepts prompts and gathers relevant context from memory, search, kanban, crew, and more.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:smaht:smaht [query]` | Gather context from wicked-garden sources before responding |
| `/wicked-garden:smaht:onboard [path]` | Intelligent codebase onboarding using the ecosystem |
| `/wicked-garden:smaht:debug` | Show what context was assembled for recent turns |
| `/wicked-garden:smaht:help` | This help message |

## Quick Start

```
/wicked-garden:smaht:onboard .
/wicked-garden:smaht:debug --turns 3
/wicked-garden:smaht:smaht "how does auth work in this project?"
```

## Examples

### Onboarding
```
/wicked-garden:smaht:onboard ./my-project
/wicked-garden:smaht:onboard . --resume
/wicked-garden:smaht:onboard ./api --skip-index
```

### Context Debugging
```
/wicked-garden:smaht:debug
/wicked-garden:smaht:debug --turns 5 --json
/wicked-garden:smaht:debug --state
```

### Explicit Context Gather
```
/wicked-garden:smaht:smaht "what are the open tasks?"
/wicked-garden:smaht:smaht "explain the payment flow" --deep
```

## How It Works

Smaht routes prompts through three tiers:

| Path | Latency | When |
|------|---------|------|
| **HOT** | <100ms | Continuations, confirmations |
| **FAST** | <1s | Short prompt, high confidence intent |
| **SLOW** | 2-5s | Complex, ambiguous, or novel prompts |

Six adapters query: mem, search, kanban, crew, jam, context7.

## Integration

- **wicked-mem**: Memory recall adapter
- **wicked-search**: Code and document search adapter
- **wicked-kanban**: Task context adapter
- **wicked-crew**: Project phase adapter
- **wicked-jam**: Brainstorming context adapter
```
