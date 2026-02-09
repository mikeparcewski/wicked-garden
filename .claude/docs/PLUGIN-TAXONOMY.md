# Plugin Taxonomy

## Overview

Plugins fall into two categories:

1. **Utility Plugins** — Tools agents use dynamically
2. **Specialist Plugins** — Role-based enhancers with personas

## Utility Plugins

These are capabilities, not phases. Agents invoke them as needed.

### wicked-cache
**Purpose**: Caching infrastructure for performance

- Plugin detection caching
- Analysis result caching
- Cross-session data persistence

**Used by**: All agents, orchestrator

### wicked-kanban
**Purpose**: Task and workflow state management

- Kanban board for task tracking
- Agent behavior control
- Project/initiative organization

**Used by**: Orchestrator, all specialists

### wicked-mem
**Purpose**: Memory and context persistence

- Cross-session memory
- Decision recall
- Learning storage

**Used by**: All agents

### wicked-search
**Purpose**: Unified code and document search

- Codebase exploration
- Documentation search
- Symbol/reference lookup

**Used by**: Research agents, analysts

### wicked-browse
**Purpose**: Browser automation and accessibility

- Screenshot capture
- Accessibility audits
- Web scraping
- UI testing

**Used by**: QE agents, DevSecOps

### wicked-numbers
**Purpose**: Data analysis with DuckDB

- Large dataset processing
- SQL queries on local files
- Data quality analysis

**Used by**: PMO, Analyst agents

---

## Specialist Plugins

Role-based plugins with multiple personas. Each enhances crew's capabilities.

### Core Specialists (Ship with Ecosystem)

#### wicked-jam
**Role**: Brainstorming and ideation

**Personas**:
- Creative Explorer
- Devil's Advocate
- Domain Expert (dynamic)
- Pragmatist

**Enhances**: Clarify phase

**Hooks**:
- Subscribes: `crew:clarify:started`
- Publishes: `jam:brainstorm:completed`

---

#### wicked-product (renamed from wicked-lens)
**Role**: Business and customer value focus

**Personas**:
- Business Strategist
- Customer Advocate
- Value Analyst
- Competitive Analyst

**Enhances**: Design decisions, review phases

**Hooks**:
- Subscribes: `crew:design:decisions`, `crew:review:started`
- Publishes: `strategy:assessment:completed`

---

#### wicked-delivery (renamed from wicked-pissah-pmo)
**Role**: Reporting and delivery tracking

**Personas**:
- Delivery Manager
- Stakeholder Reporter
- Risk Monitor
- Progress Tracker

**Enhances**: Status, retrospectives, reporting

**Hooks**:
- Subscribes: `crew:phase:completed`, `crew:project:completed`
- Publishes: `pmo:report:generated`

---

### Advanced Specialists (Optional Enhancers)

#### wicked-qe
**Role**: Advanced quality engineering

**Personas**:
- Test Strategist
- Risk Assessor
- Performance Analyst
- Edge Case Hunter
- Automation Engineer

**Enhances**: Stage gates, test planning, coverage

**Hooks**:
- Subscribes: `crew:gate:review:requested`, `crew:build:tests:needed`
- Publishes: `qe:strategy:completed`, `qe:gate:verdict`

**Key Capability**: Interjects in stage gates with advanced analysis

---

#### wicked-engineering
**Role**: Full-stack engineering skills

**Personas**:
- Frontend Engineer
- Backend Engineer
- Database Specialist
- API Designer
- Performance Engineer

**Enhances**: Build phase, architecture decisions

**Hooks**:
- Subscribes: `crew:build:started`, `crew:design:architecture`
- Publishes: `appeng:implementation:completed`

---

#### wicked-product
**Role**: Product management skills

**Personas**:
- Product Manager
- UX Researcher
- Requirements Analyst
- Prioritization Expert

**Enhances**: Requirements, prioritization, user stories

**Hooks**:
- Subscribes: `crew:clarify:started`, `crew:design:requirements`
- Publishes: `product:requirements:completed`

---

#### wicked-platform (expanded from wicked-git-ops)
**Role**: Security, CI/CD, infrastructure

**Personas**:
- Security Engineer
- DevOps Engineer
- Infrastructure Architect
- Release Engineer
- Incident Responder

**Enhances**: Build, deploy, security review

**Hooks**:
- Subscribes: `crew:build:completed`, `crew:review:security`
- Publishes: `devsecops:scan:completed`, `devsecops:deploy:ready`

---

#### wicked-compliance
**Role**: Compliance, audit, governance

**Personas**:
- Compliance Officer
- Audit Specialist
- Policy Enforcer
- Risk Assessor

**Enhances**: All phases (policy overlay)

**Hooks**:
- Subscribes: `crew:*` (monitors all)
- Publishes: `compliance:check:completed`, `compliance:violation:detected`

---

#### wicked-analyst
**Role**: Documentation and research

**Personas**:
- Technical Writer
- Research Analyst
- Knowledge Manager
- Documentation Specialist

**Enhances**: Research, documentation tasks

**Hooks**:
- Subscribes: `crew:research:needed`, `crew:docs:needed`
- Publishes: `analyst:research:completed`, `analyst:docs:generated`

---

## Plugin Status

| Plugin | Status | Action |
|--------|--------|--------|
| wicked-cache | Exists | Keep as utility |
| wicked-kanban | Exists | Keep as utility |
| wicked-mem | Exists | Keep as utility |
| wicked-search | Exists | Keep as utility |
| wicked-browse | Exists | Keep as utility |
| wicked-numbers | Exists | Keep as utility |
| wicked-jam | Exists | Update with new personas |
| wicked-product | Exists | Pivot to business/customer value |
| wicked-delivery | Exists | Reporting and delivery tracking |
| wicked-platform | Exists | Security, CI/CD, infrastructure |
| wicked-qe | Exists | Enhance as advanced specialist |
| wicked-engineering | New | Create as specialist |
| wicked-compliance | New | Create as specialist |
| wicked-analyst | New | Create as specialist |

---

## Reuse Strategy

Don't build everything — orchestrate existing capabilities:

### Existing Claude Code Plugins
- `superpowers` — Enhanced shell capabilities
- `testing` plugins — Test runners, frameworks
- `linting` plugins — Code quality tools

### MCP Servers
- Git operations
- Database access
- External APIs

### External Tools
- Linters (eslint, ruff, etc.)
- Test frameworks (jest, pytest, etc.)
- Security scanners (semgrep, etc.)

The wicked ecosystem orchestrates these, not replaces them.
