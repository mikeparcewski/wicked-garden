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

| Domain | Description | Help |
|--------|-------------|------|
| **agentic** | Design, review, and audit agentic AI systems | `/wicked-garden:agentic:help` |
| **crew** | Dynamic multi-phase workflow engine with specialist routing | `/wicked-garden:crew:help` |
| **data** | Data analysis and ontology recommendations | `/wicked-garden:data:help` |
| **delivery** | Multi-perspective delivery reporting and metrics | `/wicked-garden:delivery:help` |
| **engineering** | Architecture, code review, debugging, docs, and planning | `/wicked-garden:engineering:help` |
| **jam** | AI-powered brainstorming with dynamic focus groups | `/wicked-garden:jam:help` |
| **kanban** | AI-native task management with automatic sync | `/wicked-garden:kanban:help` |
| **mem** | Persistent memory — store decisions, recall context | `/wicked-garden:mem:help` |
| **observability** | Plugin health monitoring, assertions, and hook traces | `/wicked-garden:observability:help` |
| **patch** | Structural code transformations across the codebase | `/wicked-garden:patch:help` |
| **platform** | Security, infrastructure, compliance, CI/CD, and incidents | `/wicked-garden:platform:help` |
| **product** | Requirements, customer feedback, strategy, and UX | `/wicked-garden:product:help` |
| **qe** | Test planning, scenarios, acceptance testing, and automation | `/wicked-garden:qe:help` |
| **scenarios** | E2E testing with markdown scenarios and CLI tools | `/wicked-garden:scenarios:help` |
| **search** | Structural code search, lineage, and codebase intelligence | `/wicked-garden:search:help` |
| **smaht** | Intelligent context assembly from all sources | `/wicked-garden:smaht:help` |
| **startah** | Issue reporting for bugs and UX friction | `/wicked-garden:startah:help` |
| **workbench** | Dashboard server for visualizing project data | `/wicked-garden:workbench:help` |

## Quick Start

### Start a Project
```
/wicked-garden:crew:start "build a user authentication system"
```

### Onboard to a Codebase
```
/wicked-garden:smaht:onboard .
```

### Search Code
```
/wicked-garden:search:code "handlePayment"
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
```
/wicked-garden:mem:store "chose PostgreSQL for user data" --type decision
```

## How It Works

1. **smaht** assembles context from memory, search, kanban, and crew for every prompt
2. **crew** orchestrates multi-phase workflows and routes to specialist domains
3. **Specialist domains** (engineering, platform, product, qe, data, delivery, agentic, jam) provide deep expertise
4. **Utility domains** (mem, search, kanban, patch, scenarios, workbench, observability, startah) provide tools and infrastructure
5. **All state** persists across sessions via mem, kanban, and search indexes

## Getting Domain Help

Run `/wicked-garden:{domain}:help` for any domain to see its full command list and examples.
```
