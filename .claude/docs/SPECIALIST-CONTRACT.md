# Specialist Plugin Contract (v3)

## Overview

Specialist plugins enhance wicked-crew's capabilities through capability-based orchestration. This contract defines how specialists integrate with the crew workflow.

## Contract Structure

Each specialist exposes a `specialist.json` in `.claude-plugin/`:

```json
{
  "specialist": {
    "name": "wicked-qe",
    "role": "quality-engineering",
    "description": "Advanced quality engineering with TDD and testing personas"
  },

  "personas": [
    {
      "name": "Test Strategist",
      "focus": "Test planning, coverage analysis, TDD workflow",
      "expertise": ["test scenarios", "coverage analysis", "TDD"],
      "agent": "agents/test-strategist.md"
    },
    {
      "name": "Risk Assessor",
      "focus": "Failure modes, edge cases, risk identification",
      "agent": "agents/risk-assessor.md"
    }
  ],

  "enhances": [
    {
      "phase": "qe",
      "trigger": "crew:phase:started:success",
      "response": "qe:analysis:completed:success",
      "capabilities": ["test_generation", "risk_analysis", "coverage_check"]
    }
  ],

  "hooks": {
    "subscribes": [
      "crew:phase:started:success",
      "crew:phase:completed:success"
    ],
    "publishes": [
      "qe:analysis:completed:success",
      "qe:risk:identified:warning"
    ]
  }
}
```

## Contract Fields

### Specialist Identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `specialist.name` | string | Yes | Plugin name (matches plugin.json) |
| `specialist.role` | enum | Yes | Role identifier |
| `specialist.description` | string | Yes | What this specialist does (max 200 chars) |

### Valid Roles

| Role | Description | Example |
|------|-------------|---------|
| `ideation` | Brainstorming, exploration | wicked-jam |
| `business-strategy` | ROI, value analysis | wicked-product |
| `project-management` | Delivery tracking | wicked-delivery |
| `quality-engineering` | Testing, QE | wicked-qe |
| `devsecops` | Security, CI/CD | wicked-platform |
| `engineering` | Code implementation | wicked-engineering |
| `architecture` | System design | wicked-arch |
| `ux` | User experience | wicked-ux |
| `product` | Product management | wicked-product |
| `compliance` | Governance, audit | wicked-compliance |
| `data-engineering` | Data, ML | wicked-data |

### Personas

Each persona is a perspective within the specialist role:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `personas[].name` | string | Yes | Persona display name |
| `personas[].focus` | string | Yes | What this persona focuses on |
| `personas[].expertise` | string[] | No | Areas of expertise |
| `personas[].agent` | string | No | Path to agent definition |
| `personas[].dynamic` | boolean | No | Whether persona is generated dynamically |

### Enhancement Points

How the specialist enhances crew phases:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enhances[].phase` | enum | Yes | Phase being enhanced |
| `enhances[].trigger` | string | Yes | Event that activates specialist |
| `enhances[].response` | string | Yes | Event emitted when done |
| `enhances[].capabilities` | string[] | No | What this enhancement provides |

Valid phases: `clarify`, `research`, `design`, `qe`, `gate`, `build`, `review`, `*`

### Hooks

Event subscriptions and publications:

| Field | Type | Description |
|-------|------|-------------|
| `hooks.subscribes` | string[] | Events this specialist listens for |
| `hooks.publishes` | string[] | Events this specialist emits |

Event format: `[namespace:entity:action:status]`

## Complete Specialist Catalog (11)

### wicked-jam (Ideation)

```json
{
  "specialist": {
    "name": "wicked-jam",
    "role": "ideation",
    "description": "AI-powered brainstorming with dynamic focus groups"
  },
  "personas": [
    { "name": "Facilitator", "focus": "session orchestration, synthesis", "dynamic": false },
    { "name": "Technical Archetype", "focus": "implementation feasibility", "dynamic": true },
    { "name": "User Archetype", "focus": "user needs, experience", "dynamic": true },
    { "name": "Business Archetype", "focus": "value, ROI", "dynamic": true }
  ]
}
```

### wicked-product (Business Strategy)

```json
{
  "specialist": {
    "name": "wicked-product",
    "role": "business-strategy",
    "description": "Business value analysis, ROI calculation, competitive positioning"
  },
  "personas": [
    { "name": "Business Strategist", "focus": "ROI, business impact" },
    { "name": "Value Analyst", "focus": "value proposition, differentiation" },
    { "name": "Competitive Analyst", "focus": "market position, alternatives" },
    { "name": "Market Analyst", "focus": "market research, trends" }
  ]
}
```

### wicked-delivery (Project Management)

```json
{
  "specialist": {
    "name": "wicked-delivery",
    "role": "project-management",
    "description": "Delivery tracking, reporting, risk monitoring"
  },
  "personas": [
    { "name": "Delivery Manager", "focus": "execution, milestones" },
    { "name": "Stakeholder Reporter", "focus": "status reports, communication" },
    { "name": "Risk Monitor", "focus": "risk tracking, mitigation" },
    { "name": "Progress Tracker", "focus": "metrics, velocity" }
  ]
}
```

### wicked-qe (Quality Engineering)

```json
{
  "specialist": {
    "name": "wicked-qe",
    "role": "quality-engineering",
    "description": "TDD workflow, test strategy, quality gates"
  },
  "personas": [
    { "name": "QE Orchestrator", "focus": "routing to quality gates" },
    { "name": "Test Strategist", "focus": "test scenarios, TDD planning" },
    { "name": "Risk Assessor", "focus": "failure modes, edge cases" },
    { "name": "Test Automation Engineer", "focus": "test code, CI integration" },
    { "name": "TDD Coach", "focus": "red-green-refactor guidance" },
    { "name": "Code Analyzer", "focus": "static analysis, testability" }
  ]
}
```

### wicked-platform (DevSecOps)

```json
{
  "specialist": {
    "name": "wicked-platform",
    "role": "devsecops",
    "description": "Security, CI/CD, infrastructure automation"
  },
  "personas": [
    { "name": "Security Engineer", "focus": "vulnerabilities, threats" },
    { "name": "DevOps Engineer", "focus": "CI/CD, automation" },
    { "name": "Infrastructure Engineer", "focus": "deployment, scaling" },
    { "name": "Release Engineer", "focus": "versioning, releases" }
  ]
}
```

### wicked-engineering (Engineering)

```json
{
  "specialist": {
    "name": "wicked-engineering",
    "role": "engineering",
    "description": "Full-stack implementation, debugging, code quality"
  },
  "personas": [
    { "name": "Senior Engineer", "focus": "code quality, best practices" },
    { "name": "Frontend Engineer", "focus": "React, CSS, browser APIs" },
    { "name": "Backend Engineer", "focus": "APIs, databases, server-side" },
    { "name": "Debugger", "focus": "root cause analysis, profiling" }
  ]
}
```

### wicked-arch (Architecture)

```json
{
  "specialist": {
    "name": "wicked-arch",
    "role": "architecture",
    "description": "System design, technical decisions, API contracts"
  },
  "personas": [
    { "name": "Solution Architect", "focus": "end-to-end design" },
    { "name": "System Designer", "focus": "component boundaries" },
    { "name": "Integration Architect", "focus": "API contracts, services" },
    { "name": "Data Architect", "focus": "data models, storage" }
  ]
}
```

### wicked-ux (User Experience)

```json
{
  "specialist": {
    "name": "wicked-ux",
    "role": "ux",
    "description": "User experience, accessibility, design review"
  },
  "personas": [
    { "name": "UX Designer", "focus": "user flows, interactions" },
    { "name": "UI Reviewer", "focus": "visual design, consistency" },
    { "name": "A11y Expert", "focus": "WCAG, accessibility" },
    { "name": "User Researcher", "focus": "user needs, personas" }
  ]
}
```

### wicked-product (Product Management)

```json
{
  "specialist": {
    "name": "wicked-product",
    "role": "product",
    "description": "Requirements, user stories, acceptance criteria"
  },
  "personas": [
    { "name": "Product Manager", "focus": "roadmap, priorities" },
    { "name": "Requirements Analyst", "focus": "user stories, specs" },
    { "name": "Alignment Lead", "focus": "cross-team alignment" }
  ]
}
```

### wicked-compliance (Compliance)

```json
{
  "specialist": {
    "name": "wicked-compliance",
    "role": "compliance",
    "description": "SOC2, HIPAA, GDPR compliance, audit support"
  },
  "personas": [
    { "name": "Compliance Officer", "focus": "regulatory requirements" },
    { "name": "Auditor", "focus": "evidence collection, audit trails" },
    { "name": "Policy Analyst", "focus": "policy interpretation" },
    { "name": "Privacy Expert", "focus": "GDPR, PII protection" }
  ]
}
```

### wicked-data (Data Engineering)

```json
{
  "specialist": {
    "name": "wicked-data",
    "role": "data-engineering",
    "description": "Data pipelines, analytics, ML support"
  },
  "personas": [
    { "name": "Data Engineer", "focus": "ETL, pipelines, data quality" },
    { "name": "Data Analyst", "focus": "analysis, visualization" },
    { "name": "ML Engineer", "focus": "models, training, deployment" },
    { "name": "Analytics Architect", "focus": "data architecture, warehousing" }
  ]
}
```

## Specialist Discovery

Crew discovers specialists at startup:

```python
# In smart_decisioning.py
for plugin in installed_plugins:
    if exists(plugin/.claude-plugin/specialist.json):
        specialist = load(plugin/specialist.json)
        validate(specialist)
        register(specialist)
```

## Signal-to-Specialist Mapping

Crew routes signals to specialists:

| Signal | Specialists |
|--------|-------------|
| security | wicked-platform, wicked-compliance |
| performance | wicked-engineering, wicked-qe |
| product | wicked-product |
| compliance | wicked-compliance |
| ambiguity | wicked-jam |
| complexity | wicked-delivery, wicked-arch |
| data | wicked-data |
| infrastructure | wicked-platform |
| architecture | wicked-arch, wicked-engineering |
| ux | wicked-ux, wicked-product |
| strategy | wicked-product |

## Fallback Behavior

When a specialist is unavailable, crew uses built-in agents:

| Specialist | Fallback Agent |
|------------|----------------|
| wicked-jam | facilitator |
| wicked-qe | reviewer |
| wicked-product | reviewer |
| wicked-engineering | implementer |
| wicked-platform | implementer |
| wicked-compliance | reviewer |
| wicked-delivery | (kanban/todowrite) |
| wicked-product | facilitator |
| wicked-arch | reviewer |
| wicked-ux | reviewer |
| wicked-data | researcher |

## Validation

The `wg-validate` command checks specialist.json:

1. Schema compliance
2. Required fields present
3. Persona agents exist
4. Hook events follow convention `[namespace:entity:action:status]`
5. Skills ≤200 lines
6. No conflicting triggers
