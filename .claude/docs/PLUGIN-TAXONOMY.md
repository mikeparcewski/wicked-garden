# Domain Taxonomy

## Overview

The wicked-garden plugin organizes capabilities into 18 domains. Domains fall into two categories:

1. **Utility Domains** -- Tools agents use dynamically
2. **Specialist Domains** -- Role-based enhancers with personas

## Utility Domains

These are capabilities, not phases. Agents invoke them as needed.

### cache (wicked-startah)
**Purpose**: Caching infrastructure for performance

- Plugin detection caching
- Analysis result caching
- Cross-session data persistence

**Used by**: All agents, orchestrator

### kanban
**Purpose**: Task and workflow state management

- Kanban board for task tracking
- Agent behavior control
- Project/initiative organization

**Used by**: Orchestrator, all specialists

### mem
**Purpose**: Memory and context persistence

- Cross-session memory
- Decision recall
- Learning storage

**Used by**: All agents

### search
**Purpose**: Unified code and document search

- Codebase exploration
- Documentation search
- Symbol/reference lookup
- Blast-radius impact analysis
- Data lineage tracing

**Used by**: Research agents, analysts

### workbench
**Purpose**: Dashboards and data visualization

- Plugin health dashboards
- Metric visualization
- Data gateway for TypeScript consumers

**Used by**: Delivery, reporting agents

### scenarios
**Purpose**: E2E acceptance testing

- Markdown scenario orchestration
- CLI tool wrappers (curl, playwright, k6, etc.)
- Step-by-step test execution

**Used by**: QE agents, CI pipelines

### patch
**Purpose**: Bulk code transformations

- Multi-file find-and-replace
- AST-aware refactoring
- Migration scripts

**Used by**: Engineering agents

---

## Specialist Domains

Role-based domains with multiple personas. Each enhances crew's capabilities via `specialist.json`.

### jam (Ideation)

**Personas**: Facilitator, Technical Archetype, User Archetype, Business Archetype

**Enhances**: Clarify phase

**Events**: `jam:brainstorm:started`, `jam:brainstorm:completed`, `jam:insight:captured`

---

### product (Business Strategy + Product Management)

**Personas**: Business Strategist, Value Analyst, Competitive Analyst, Product Manager, Requirements Analyst

**Enhances**: Design decisions, review phases, requirements

**Events**: `product:requirements:gathered`, `product:story:written`, `product:acceptance:defined`

---

### delivery (Project Management)

**Personas**: Delivery Manager, Stakeholder Reporter, Risk Monitor, Progress Tracker

**Enhances**: Status, retrospectives, reporting

**Events**: `delivery:report:generated`, `delivery:risk:identified`, `delivery:milestone:reached`

---

### qe (Quality Engineering)

**Personas**: QE Orchestrator, Test Strategist, Risk Assessor, Test Automation Engineer, TDD Coach, Code Analyzer

**Enhances**: Stage gates, test planning, coverage

**Events**: `qe:analysis:completed`, `qe:scenario:generated`, `qe:risk:identified`

---

### engineering (Full-Stack Engineering)

**Personas**: Senior Engineer, Frontend Engineer, Backend Engineer, Debugger

**Enhances**: Build phase, architecture decisions

**Events**: `engineering:review:completed`, `engineering:implementation:completed`

---

### platform (DevSecOps)

**Personas**: Security Engineer, DevOps Engineer, Infrastructure Engineer, Release Engineer

**Enhances**: Build, deploy, security review

**Events**: `platform:scan:completed`, `platform:vulnerability:found`, `platform:deployment:ready`

---

### data (Data Engineering)

**Personas**: Data Engineer, Data Analyst, ML Engineer, Analytics Architect

**Enhances**: Data pipelines, analytics, ML support

**Events**: `data:analysis:completed`, `data:pipeline:designed`, `data:quality:assessed`

---

### agentic (Agentic Architecture)

**Personas**: Agent Architect, Pattern Analyst, Flow Designer, Capability Auditor, Integration Specialist

**Enhances**: Agent design, plugin architecture, tool composition

**Events**: `agentic:review:completed`, `agentic:pattern:identified`

---

## Domain Organization

All domains live in the single wicked-garden plugin, organized by type:

```
wicked-garden/
├── commands/{domain}/       # Slash commands
├── agents/{domain}/         # Subagents
├── skills/{domain}/         # Expertise modules
├── scripts/{domain}/        # APIs and utilities
└── scenarios/{domain}/      # Acceptance tests
```

### Command Namespace

```bash
/wicked-garden:{domain}:{command}    # e.g., /wicked-garden:crew:start
```

### Agent Subagent Type

```
wicked-garden:{domain}/{agent}       # e.g., wicked-garden:qe/test-strategist
```

---

## Reuse Strategy

Don't build everything -- orchestrate existing capabilities:

### MCP Servers
- Context7 for external documentation
- Git operations

### External Tools
- Linters (eslint, ruff, etc.)
- Test frameworks (jest, pytest, etc.)
- Security scanners (semgrep, trivy, etc.)

The wicked-garden plugin orchestrates these, not replaces them.
