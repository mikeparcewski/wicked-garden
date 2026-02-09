# Orchestration Architecture (v3)

## Core Concept

**Not workflow templates** — capability-based smart orchestration.

Crew determines what specialists are needed based on:
- User input analysis
- Project context
- Available plugins

## Plugin Taxonomy

### Utility Plugins (Dynamic, Agent-Used)

These plugins are tools that agents use dynamically based on their actions:

| Plugin | Purpose | Used By |
|--------|---------|---------|
| `wicked-cache` | Caching infrastructure | All agents (performance) |
| `wicked-kanban` | Task management | Orchestrator, specialists |
| `wicked-mem` | Memory/context persistence | All agents (continuity) |
| `wicked-search` | Code + document search | Research, analysis agents |
| `wicked-browse` | Browser automation, a11y | QE, DevSecOps agents |
| `wicked-numbers` | Data analysis (DuckDB) | PMO, Analyst agents |

**Key**: These are NOT phases — they're capabilities agents invoke as needed.

### Specialist Plugins (Role-Based, Optional Enhancers)

Each specialist plugin:
- Has multiple **personas** (perspectives within the role)
- Publishes and subscribes to **hooks/events**
- **Enhances** crew's built-in capabilities when available

#### Core Specialists (Shipping Now)

| Plugin | Role | Enhances |
|--------|------|----------|
| `wicked-jam` | Brainstorming, ideation | Clarify phase |
| `wicked-product` | Business/customer value, value cases | Design decisions |
| `wicked-delivery` | Reporting, delivery tracking | Status, retrospectives |

#### Advanced Specialists (Optional)

| Plugin | Role | Enhances |
|--------|------|----------|
| `wicked-qe` | Advanced stage gates, testing personas | Gate reviews |
| `wicked-engineering` | Full-stack engineering skills | Build phase |
| `wicked-platform` | Security, CI/CD, infrastructure | Build, review phases |
| `wicked-compliance` | Compliance, audit, governance | All phases (policy) |
| `wicked-analyst` | Documentation, research | Research, documentation |

## Crew's Built-In Capabilities

Crew has minimal built-in capabilities that specialists enhance:

```
┌─────────────────────────────────────────────────────────────┐
│                     wicked-crew                              │
├─────────────────────────────────────────────────────────────┤
│ Orchestrator Skill                                          │
│ ├── Phase rules (what each phase needs)                     │
│ ├── Smart decisioning (what specialists to engage)          │
│ └── Gate enforcement (simplified reviews)                   │
├─────────────────────────────────────────────────────────────┤
│ Built-in Subagents (fallback when no specialists)           │
│ ├── Facilitator (basic clarify)                             │
│ ├── Researcher (basic design research)                      │
│ ├── Reviewer (basic code review)                            │
│ └── Implementer (basic build)                               │
├─────────────────────────────────────────────────────────────┤
│ Hook Listeners                                              │
│ ├── Phase transitions                                       │
│ ├── Specialist responses                                    │
│ └── Gate decisions                                          │
└─────────────────────────────────────────────────────────────┘
```

### Degradation Model

```
Specialist available? → Use specialist (enhanced)
Specialist unavailable? → Use built-in subagent (minimal)
```

Example:
- `wicked-qe` installed → Advanced stage gates with testing personas
- `wicked-qe` not installed → Crew's built-in reviewer does simplified review

## Smart Decisioning

Crew analyzes user input to determine:

1. **Complexity** → How many specialists needed?
2. **Domain** → Which specialists relevant?
3. **Risk** → Should compliance/security engage?

### User Commands

```bash
# Basic - crew decides
/wicked-crew:start "Add user authentication"

# With hints - crew considers
/wicked-crew:start --qe advanced "Payment integration"
/wicked-crew:start --personas security,compliance "PII handling"

# Explicit workflow - user overrides
/wicked-crew:start --workflow security-focused "Auth system"
```

### Decision Factors

| Signal | Interpretation | Specialists |
|--------|----------------|-------------|
| "security", "auth", "PII" | Security-sensitive | devsecops, compliance |
| "performance", "scale" | Infrastructure focus | devsecops, appeng |
| "user experience", "flow" | Product focus | product, strategy |
| "compliance", "audit", "SOC2" | Governance need | compliance, analyst |
| Question marks, "maybe" | Ambiguity | jam (brainstorm) |
| Large scope indicators | Complex project | delivery, qe |

## Specialist Plugin Contract

Each specialist plugin exposes:

```yaml
# In plugin.json or specialist.json
specialist:
  role: "quality-engineering"
  personas:
    - name: "Test Strategist"
      focus: "test planning, coverage"
    - name: "Risk Assessor"
      focus: "failure modes, edge cases"
    - name: "Performance Analyst"
      focus: "load testing, benchmarks"

  enhances:
    - phase: "gate"
      trigger: "crew:gate:review:requested"
      response: "qe:gate:review:completed"
    - phase: "build"
      trigger: "crew:build:tests:needed"
      response: "qe:tests:generated"

  hooks:
    subscribes:
      - "crew:phase:*"
      - "crew:gate:*"
    publishes:
      - "qe:strategy:completed"
      - "qe:gate:verdict"
```

## Event Flow

```
User: /wicked-crew:start "Add payment processing"
                │
                ▼
        ┌───────────────┐
        │ Crew Analyzes │
        │ - "payment"   │
        │ - complexity  │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Smart Decision│
        │ Need: security│
        │ Need: qe      │
        │ Need: appeng  │
        └───────┬───────┘
                │
                ▼
    ┌───────────────────────┐
    │ Check Available       │
    │ ✓ wicked-qe           │
    │ ✓ wicked-platform    │
    │ ✗ wicked-engineering       │
    └───────────┬───────────┘
                │
                ▼
    ┌───────────────────────┐
    │ Engage:               │
    │ - wicked-qe (found)   │
    │ - wicked-platform    │
    │ - built-in implementer│
    └───────────────────────┘
```

## Plugin History

> Note: Plugin renames have been completed. The table below records the historical mapping.

| Previous Name | Current Name | Change |
|--------------|-------------|--------|
| `wicked-lens` | `wicked-product` | Pivoted to business/customer value |
| `wicked-pissah-pmo` | `wicked-delivery` | Renamed, kept reporting |
| `wicked-git-ops` | `wicked-platform` | Expanded to full DevSecOps |
| `wicked-appeng` | `wicked-engineering` | Renamed |
| `wicked-devsecops` | `wicked-platform` | Merged into platform |
| `wicked-strategy` | `wicked-product` | Merged into product |

## Reuse Strategy

Not reinventing — orchestrating existing capabilities:

- **Existing Claude Code plugins** (superpowers, etc.) can be used
- **MCP servers** integrate as utility capabilities
- **External tools** (linters, test runners) invoked by specialists

The framework is about **orchestration** — knowing when to use what, not owning everything.

## Phase Model (Simplified)

Crew doesn't enforce rigid phases. It manages:

1. **Clarify** — What are we doing? (Jam enhances)
2. **Research** — What exists? (Search, Analyst enhance)
3. **Design** — How will we do it? (Strategy, Product enhance)
4. **Gate** — Should we proceed? (QE, Compliance enhance)
5. **Build** — Do it (AppEng, DevSecOps enhance)
6. **Review** — Is it right? (QE, Strategy enhance)

Phases can be:
- Skipped (simple tasks)
- Repeated (iteration)
- Parallelized (independent work)
- Enhanced (specialists available)

## Summary

| Aspect | Old (v2) | New (v3) |
|--------|----------|----------|
| Workflows | Template-based | Smart decisioning |
| Plugins | Phase providers | Role-based specialists |
| Phases | Fixed contract | Flexible enhancement |
| Decision | AI selects template | AI selects specialists |
| Fallback | Inline prompts | Built-in subagents |
