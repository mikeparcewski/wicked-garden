# Crew Workflow

Crew is the orchestration engine. It analyzes what you're building, detects signals, selects phases, and routes to the right specialists — automatically.

## How It Works

```
Your description
     |
     v
+--------------------------+
|   Smart Decisioning      |
|                          |
|  1. Detect signals       |     security, architecture, data, ux,
|  2. Score complexity     |     performance, compliance, ambiguity...
|  3. Select specialists   |
|  4. Choose phases        |
+--------------------------+
     |
     v
Phase Plan: clarify -> design -> test-strategy -> build -> test -> review
```

One command starts the entire process:

```bash
/wicked-garden:crew:start "Migrate auth from sessions to JWT across 3 services"
```

## Signal Detection

Every project description is analyzed for **signals** — patterns that indicate what kind of expertise is needed:

| Signal | Triggers On | Specialists Engaged |
|--------|------------|-------------------|
| security | auth, encrypt, credentials, JWT, OAuth | platform, qe |
| architecture | system design, component, API contract | engineering, agentic |
| performance | latency, throughput, bottleneck, optimize | engineering, platform |
| data | analytics, pipeline, ETL, database, SQL | data |
| ux | user experience, usability, user flow | product |
| compliance | audit, regulatory, GDPR, HIPAA, SOC2 | platform |
| ambiguity | vague descriptions, multiple interpretations | jam |
| complexity | large scope, cross-cutting, coordination | delivery, engineering |
| content | messaging, copy, creative, branding | jam, product |
| quality | testing, coverage, reliability | qe |

Signals are detected through keyword patterns with confidence scoring. Multiple signals can fire simultaneously — a description mentioning "OAuth migration with compliance requirements" triggers both security and compliance.

## Complexity Scoring

Complexity is scored 0-7 across multiple dimensions:

| Dimension | What It Measures |
|-----------|-----------------|
| Impact | How much production behavior changes |
| Reversibility | How hard to undo |
| Novelty | How new/unfamiliar the pattern is |
| Test complexity | How complex the test strategy needs to be |
| Coordination cost | Cross-domain/cross-team coordination |
| Operational | Deployment/migration/rollback complexity |
| Documentation | How much documentation needs updating |

The score drives phase selection and rigor:

```
Score 0-2: Quick pass
  -> auto-finish mode, build + review only
  -> no user prompts needed

Score 3-4: Standard
  -> clarify + test-strategy + build + test + review
  -> design phase if architecture signals detected

Score 5-7: Full pipeline
  -> all phases, all matched specialists
  -> ideate phase for ambiguous problems
  -> delivery specialist for coordination
```

## Phases

Seven phases available, selected dynamically based on signals and complexity:

| Phase | Purpose | Always Included? |
|-------|---------|-----------------|
| **ideate** | Brainstorm and explore solution space | No (ambiguity/UX signals) |
| **clarify** | Define outcome, acceptance criteria | Yes |
| **design** | Architecture and implementation strategy | No (complexity >= 3) |
| **test-strategy** | Test planning before implementation | No (complexity >= 2) |
| **build** | Implementation with task tracking | Yes |
| **test** | Execute tests, collect evidence | No (complexity >= 2) |
| **review** | Final review with evidence evaluation | Yes |

### Phase Dependencies

```
ideate (optional)
  |
clarify (required)
  |
  +-> design (optional, depends on clarify)
  |     |
  +-> test-strategy (optional, depends on clarify)
  |     |
  +-----+-> build (required, depends on clarify)
              |
              +-> test (optional, depends on build + test-strategy)
              |
              +-> review (required, depends on build)
```

### Checkpoints

At three checkpoints (clarify, design, build), the system re-analyzes signals and can inject new phases mid-flight:

- Design phase reveals security concerns not in the original description? Security specialist gets pulled in.
- Build phase discovers data migration needs? Data specialist and test phase get added.
- Complexity changes based on what's found? Phase plan adjusts.

## Specialists

Eight specialist roles that crew routes to based on signals:

| Specialist | Role | Engaged By |
|-----------|------|-----------|
| engineering | Implementation, architecture, code quality, code transformations | performance, architecture, complexity |
| platform | Security, infrastructure, compliance, plugin diagnostics | security, compliance, infrastructure |
| product | Requirements, UX, customer voice, design review, mockups | product, ux, strategy |
| qe | Testing, quality gates, risk, E2E scenarios | quality, non-trivial work (complexity >= 2) |
| data | Data pipelines, analytics, ML | data signals |
| delivery | Project coordination, cost, rollout | complexity >= 5 |
| agentic | Agent architecture, safety, patterns | architecture signals |
| jam | Brainstorming, diverse perspectives | ambiguity, architecture, complexity >= 4 |

When a recommended specialist isn't available, fallback agents cover the gap:

| Specialist | Fallback Agent |
|-----------|---------------|
| jam | facilitator |
| qe | reviewer |
| product | facilitator |
| engineering | implementer |
| platform | implementer |
| data | researcher |
| agentic | reviewer |

## Auto-Finish Mode

For low-complexity work (score 0-2), crew automatically applies a quick phase plan (build + review) and chains into just-finish mode — no user interaction required.

```bash
# This auto-finishes for simple tasks:
/wicked-garden:crew:start "Fix the typo in the login button"

# To override:
/wicked-garden:crew:start --no-auto-finish "Fix the typo in the login button"
```

## Quick Mode

Skip clarify, design, and test phases — go straight to build + review:

```bash
/wicked-garden:crew:start --quick "Add error handling to the API endpoint"
```

## Just-Finish Mode

Maximum autonomy — execute all remaining phases without stopping for approval:

```bash
/wicked-garden:crew:just-finish
```

## Kanban Integration

Every crew project creates a kanban initiative. Tasks created during phases are automatically grouped under the project on the kanban board. This happens via hooks — no manual tagging needed.

```bash
/wicked-garden:kanban:board-status    # see all projects and tasks
```

## Memory Integration

Crew stores significant decisions and patterns in memory automatically. When you start a new project, relevant memories from past projects surface during the clarify phase.
