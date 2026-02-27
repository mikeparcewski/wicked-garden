# Specialist Contract (v4 - Unified)

## Overview

Specialist domains enhance wicked-crew's capabilities through capability-based orchestration. This contract defines how specialists integrate with the crew workflow within the unified wicked-garden plugin.

## Contract Structure

A single `specialist.json` lives at `.claude-plugin/specialist.json` and defines all specialist roles:

```json
{
  "specialists": [
    {
      "name": "wicked-garden",
      "role": "quality-engineering",
      "domain": "qe",
      "description": "Advanced quality engineering with TDD and testing personas",
      "personas": [
        {
          "name": "Test Strategist",
          "focus": "Test planning, coverage analysis, TDD workflow",
          "expertise": ["test scenarios", "coverage analysis", "TDD"],
          "agent": "agents/qe/test-strategist.md"
        },
        {
          "name": "Risk Assessor",
          "focus": "Failure modes, edge cases, risk identification",
          "agent": "agents/qe/risk-assessor.md"
        }
      ],
      "enhances": [
        {
          "phase": "qe",
          "trigger": "crew:phase:started:success",
          "response": "qe:analysis:completed:success",
          "capabilities": ["test_generation", "risk_analysis", "coverage_check"]
        }
      ]
    }
  ]
}
```

## Contract Fields

### Specialist Identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Always `wicked-garden` (unified plugin) |
| `role` | enum | Yes | Role identifier |
| `domain` | string | Yes | Domain within the plugin (e.g., `qe`, `engineering`) |
| `description` | string | Yes | What this specialist does (max 200 chars) |

### Valid Roles

| Role | Domain | Description |
|------|--------|-------------|
| `ideation` | jam | Brainstorming, exploration |
| `business-strategy` | product | ROI, value analysis |
| `product` | product | Requirements, user stories |
| `project-management` | delivery | Delivery tracking |
| `quality-engineering` | qe | Testing, QE |
| `devsecops` | platform | Security, CI/CD |
| `engineering` | engineering | Code implementation |
| `data-engineering` | data | Data, ML |
| `agentic-architecture` | agentic | Agent design, tool composition |
| `brainstorming` | jam | Focus group facilitation |

### Personas

Each persona is a perspective within the specialist role:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `personas[].name` | string | Yes | Persona display name |
| `personas[].focus` | string | Yes | What this persona focuses on |
| `personas[].expertise` | string[] | No | Areas of expertise |
| `personas[].agent` | string | No | Path to agent definition (relative to plugin root) |
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

## Specialist Catalog (8 Roles, 47 Personas)

### jam (Ideation)
- Facilitator: session orchestration, synthesis
- Technical Archetype: implementation feasibility (dynamic)
- User Archetype: user needs, experience (dynamic)
- Business Archetype: value, ROI (dynamic)

### product (Business Strategy + Product)
- Business Strategist: ROI, business impact
- Value Analyst: value proposition, differentiation
- Competitive Analyst: market position, alternatives
- Product Manager: roadmap, priorities
- Requirements Analyst: user stories, specs
- Alignment Lead: cross-team alignment

### delivery (Project Management)
- Delivery Manager: execution, milestones
- Stakeholder Reporter: status reports, communication
- Risk Monitor: risk tracking, mitigation
- Progress Tracker: metrics, velocity

### qe (Quality Engineering)
- QE Orchestrator: routing to quality gates
- Test Strategist: test scenarios, TDD planning
- Risk Assessor: failure modes, edge cases
- Test Automation Engineer: test code, CI integration
- TDD Coach: red-green-refactor guidance
- Code Analyzer: static analysis, testability

### platform (DevSecOps)
- Security Engineer: vulnerabilities, threats
- DevOps Engineer: CI/CD, automation
- Infrastructure Engineer: deployment, scaling
- Release Engineer: versioning, releases

### engineering (Engineering)
- Senior Engineer: code quality, best practices
- Frontend Engineer: React, CSS, browser APIs
- Backend Engineer: APIs, databases, server-side
- Debugger: root cause analysis, profiling

### data (Data Engineering)
- Data Engineer: ETL, pipelines, data quality
- Data Analyst: analysis, visualization
- ML Engineer: models, training, deployment
- Analytics Architect: data architecture, warehousing

### agentic (Agentic Architecture)
- Agent Architect: agent design, tool composition
- Pattern Analyst: anti-pattern detection
- Flow Designer: workflow orchestration
- Capability Auditor: gap analysis
- Integration Specialist: cross-domain coordination

## Specialist Discovery

Crew discovers specialists at startup from the unified specialist.json:

```python
# In smart_decisioning.py
specialist_json = load(".claude-plugin/specialist.json")
for specialist in specialist_json["specialists"]:
    domain = specialist["domain"]
    role = specialist["role"]
    register(domain, role, specialist)
```

## Signal-to-Specialist Mapping

Crew routes signals to specialist domains:

| Signal | Domains |
|--------|---------|
| security | platform |
| performance | engineering, qe |
| product | product |
| ambiguity | jam |
| complexity | delivery |
| data | data |
| infrastructure | platform |
| architecture | engineering, agentic |
| ux | product |
| strategy | product |
| testing | qe |
| agent-design | agentic |

## Fallback Behavior

When a specialist's signals aren't matched, crew uses built-in agents:

| Domain | Fallback Agent |
|--------|----------------|
| jam | facilitator |
| qe | reviewer |
| product | reviewer |
| engineering | implementer |
| platform | implementer |
| delivery | (kanban/todowrite) |
| data | researcher |
| agentic | reviewer |

## Validation

The `/wg-check` command validates specialist.json:

1. Schema compliance
2. Required fields present
3. Persona agents exist at declared paths
4. All domains are valid (18 known domains)
5. No conflicting enhancement triggers
