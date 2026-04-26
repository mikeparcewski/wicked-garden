---
description: Show all available wicked-garden domains and commands
---

# /wicked-garden:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# Wicked Garden Help

The Wicked Garden Marketplace — an AI-native SDLC workflow with 19 command domains covering engineering, product, delivery, quality, and more.

## Domains

| Domain | Description | Key Commands |
|--------|-------------|--------------|
| **agentic** | Design, review, and audit agentic AI systems | `agentic:design`, `agentic:review`, `agentic:audit` |
| **crew** | Dynamic multi-phase workflow engine with specialist routing | `crew:start`, `crew:execute`, `crew:gate`, `crew:activity` |
| **data** | Data analysis and ontology recommendations | `data:analyze`, `data:pipeline`, `data:ml` |
| **delivery** | Multi-perspective delivery reporting and metrics | `delivery:report`, `delivery:rollout`, `delivery:experiment` |
| **engineering** | Architecture, code review, debugging, docs, planning, and code transformations | `engineering:review`, `engineering:debug`, `engineering:arch` |
| **jam** | AI-powered brainstorming with dynamic focus groups | `jam:council`, `jam:brainstorm`, `jam:quick` |
| **mem** | Persistent memory — store decisions, recall context | `wicked-brain:memory`, `wicked-brain:query` |
| **platform** | Security, infrastructure, compliance, CI/CD, incidents, and plugin diagnostics | `platform:security`, `platform:compliance`, `platform:incident` |
| **product** | Requirements, customer feedback, strategy, UX, and design review | `product:acceptance`, `product:analyze`, `product:strategy` |
| **search** | Structural code search, lineage, and codebase intelligence | `search:blast-radius`, `search:lineage`, `search:hotspots` |
| **smaht** | Intelligent context assembly from all sources | `smaht:briefing`, `smaht:state`, `smaht:events-import` |

## Quick Start

### Start a Project
```
/wicked-garden:crew:start "build a user authentication system"
```

### Onboard to a Codebase
```
wicked-brain:agent onboard .
```

### Search Code
```
wicked-brain:search "handlePayment"
```

### Review Code
```
/wicked-garden:engineering:review ./src
```

### Brainstorm
```
/wicked-garden:jam:brainstorm "API design approaches"
```

### Store a Decision
Use `wicked-brain:memory` to store a decision directly.

## How It Works

1. **smaht** assembles context from memory, search, and crew for every prompt
2. **crew** orchestrates multi-phase workflows and routes to specialist domains
3. **Specialist domains** (engineering, platform, product, qe, data, delivery, agentic, jam) provide deep expertise
4. **Utility domains** (mem, search, patch, observability) provide tools and infrastructure
5. **All state** persists across sessions via mem, search indexes, and native tasks

## Getting Domain Help

Run `/wicked-garden:{domain}:{command}` for any command. Use `/wicked-garden:help` to return to this overview.
```
