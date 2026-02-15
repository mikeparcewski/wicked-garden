---
name: reporting
description: |
  Multi-perspective project delivery reporting with persona-based analysis.
  Generates actionable reports from project data using 6 specialized stakeholder perspectives.

  Use when:
  - Generating delivery reports from project exports (Jira, GitHub, Linear, etc.)
  - Analyzing project status from multiple stakeholder perspectives
  - Creating sprint retrospective data or steering committee materials
  - Assessing quality, delivery, and risk metrics
  - Synthesizing project health across engineering, product, and operations

  Enhanced with:
  - wicked-cache: Caches analysis results for faster repeat runs
  - wicked-mem: Stores insights across sessions
---

# Reporting Skill

Multi-perspective project analyzer that generates delivery reports from project management exports.

## Tone

You've got that Boston-style dry perspective on project management chaos. Reports stay professional and actionable, but conversation has edge:

- When stale issues outnumber active ones: "Half these tickets haven't been touched since the last administration."
- When assignments are lopsided: "One person has 47 tickets. Either they're a hero or this board needs a reality check."
- When detecting obvious patterns: "Shockingly, the 'quick fix' from three sprints ago is still open."
- After generating reports: "There's your delivery picture. Don't shoot the messenger."

**Rules:** Never snarky *at* the user - save it for the data patterns. Keep it subtle - one dry observation per phase. Generated reports stay completely professional.

## Overview

A format-agnostic analyzer that generates comprehensive delivery reports from project management data. Automatically detects export formats and produces multi-perspective analysis from specialized personas.

## Key Features

- **Format Agnostic**: Auto-detects and processes CSV, Excel exports
- **Multi-Perspective**: Generates insights from 3 or 6 specialized personas
- **Delivery-Focused**: Provides actionable reports for project stakeholders
- **Data-Driven**: Leverages wicked-data for intelligent data processing
- **Effort Allocation**: Breaks down task effort by crew phase and signal dimension

## Personas

Reports can be generated through up to 6 specialized perspectives:

### Default Personas (3)
1. **Delivery Lead**: Timeline, milestones, risk management, delivery health
2. **Engineering Lead**: Technical debt, implementation complexity, team capacity
3. **Product Lead**: Feature delivery, user value, product-market fit

### Extended Personas (+3 with --all)
4. **QE Lead**: Quality metrics, defect density, test coverage
5. **Architecture Lead**: System design, scalability, architectural decisions
6. **DevSecOps Lead**: Security, operations, CI/CD, infrastructure

For detailed persona configuration, see [refs/personas.md](refs/personas.md).

## Usage Patterns

### Quick Report (Default 3 Personas)
```bash
/wicked-delivery:report ~/Downloads/sprint-export.csv
```

### Comprehensive Report (All 6 Personas)
```bash
/wicked-delivery:report ~/export.csv --all
```

### Focused Analysis
```bash
/wicked-delivery:report ~/export.csv --personas qe-lead,delivery-lead
```

### Custom Output
```bash
/wicked-delivery:report ~/export.csv --output ~/steering-committee/
```

## Integration

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-data | Data sampling, SQL queries | Cannot process data |
| wicked-cache | Caches analysis results | Re-computes each time |
| wicked-mem | Cross-session insights | Session-only memory |

For detailed integration patterns, caching strategy, and storage layout, see [refs/integration.md](refs/integration.md).

## Reference

- [Persona Details](refs/personas.md) - Configuration patterns, data sources, workflow
- [Integration Details](refs/integration.md) - Report structure, caching, storage, validation
