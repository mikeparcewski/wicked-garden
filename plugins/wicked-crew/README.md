# wicked-crew

Dynamic workflow orchestration with signal-based specialist routing. Crew adapts phases based on what it discovers -- injecting design when complexity increases, engaging security when it detects infrastructure changes, pulling in brainstorming when ambiguity spikes. This is not a rigid pipeline. It is a responsive delivery system that analyzes your input, plans the right phases, and automatically engages the right specialists at the right time.

## Quick Start

```bash
# Install
claude plugin install wicked-crew@wicked-garden

# Start a new project
/wicked-crew:start "Build user authentication with OAuth2"

# Execute the current phase
/wicked-crew:execute

# Or let it run autonomously
/wicked-crew:just-finish
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-crew:start` | Create a project with signal analysis | `/wicked-crew:start "Add caching layer"` |
| `/wicked-crew:execute` | Execute the current phase | `/wicked-crew:execute` |
| `/wicked-crew:just-finish` | Autonomous completion with guardrails | `/wicked-crew:just-finish` |
| `/wicked-crew:status` | Show project state, signals, specialists | `/wicked-crew:status` |
| `/wicked-crew:approve` | Approve and advance to next phase | `/wicked-crew:approve clarify` |
| `/wicked-crew:gate` | Run quality gate checks | `/wicked-crew:gate` |
| `/wicked-crew:evidence` | Generate evidence reports | `/wicked-crew:evidence` |
| `/wicked-crew:profile` | Configure engagement preferences | `/wicked-crew:profile` |

## How It Works

```
Your Description → Signal Detection → Phase Planning → Specialist Engagement
                      │                    │                    │
                      ├── Security?        ├── clarify          ├── wicked-platform
                      ├── Performance?     ├── design           ├── wicked-engineering
                      ├── Ambiguity?       ├── test-strategy    ├── wicked-jam
                      └── Data?            ├── build            └── wicked-product
                                           ├── test
                                           └── review
```

### Smart Decisioning

When you `/start` a project, crew reads your description and answers three questions:

1. **How much could this break?** (Impact: 0-3)
2. **Can we undo it easily?** (Reversibility: 0-3)
3. **Have we done this before?** (Novelty: 0-3)

These three scores combine into a single complexity number (0-7) that decides how many phases you need and which specialists get called in.

#### The Simple Version

Think of it like a doctor's triage. A paper cut (impact=0, reversible=easy, routine=yes) gets a band-aid. A broken arm (impact=2, reversible=slow, first time=maybe) gets an X-ray, a specialist, and a follow-up plan. Crew does the same thing for code changes.

**Example: "Fix a typo in the README"**
- Impact: 0 — it's a doc file, not executable code
- Reversibility: 0 — trivially reversible
- Novelty: 0 — routine work
- **Complexity: 0** → clarify → build → review (fast track)

**Example: "Migrate auth from sessions to JWT across 3 services"**
- Impact: 3 — touches auth handlers, API endpoints, middleware
- Reversibility: 3 — schema migration + breaking API change
- Novelty: 1 — multi-domain (security + architecture + complexity)
- **Complexity: 7** → full pipeline with design, test-strategy, and all specialists

**Example: "Add a caching layer to the API"**
- Impact: 2 — new middleware + config changes
- Reversibility: 1 — feature-flaggable, rollback mentioned
- Novelty: 1 — two signal domains (performance + infrastructure)
- **Complexity: 4** → adds design and test-strategy phases

#### How Scoring Works

**Impact** looks at *what files you're changing*, not their extension. A `.md` file in `commands/` is executable code (weight 2.0). A `.md` file in `docs/` is documentation (weight 0.5). The scorer uses a 5-tier taxonomy:

| Tier | What | Weight | Examples |
|------|------|--------|----------|
| 1 | Behavior-defining | 2.0 | commands/, hooks.json, Dockerfile, .github/workflows/, Makefile |
| 2 | Source code | 1.5 | src/, scripts/, agents/, SKILL.md |
| 3 | Generic code | 1.0 | .py, .ts, .go, .java, .rs |
| 4 | Test code | 1.0 | tests/, spec/, e2e/ |
| 5 | Low-impact | 0.5/0.0 | README, CHANGELOG, docs/, LICENSE |

Integration keywords (api, endpoint, service, system) add +2 because connecting systems is inherently high-impact.

**Reversibility** balances irreversibility signals against mitigators:
- "Schema migration with breaking API change" → +3 (migration) +3 (breaking change) = very hard to undo
- "Add feature-flagged experiment" → +1 (experiment) -2 (feature flag) = easily reversible

**Novelty** detects unfamiliar territory:
- Explicit markers: "prototype", "greenfield", "first time", "proof of concept"
- Cross-domain scope: 3+ signal categories means you're touching many concerns at once
- Ambiguity: questions and uncertainty signal exploration is needed

**The composite formula** that produces the 0-7 score:

```
complexity = impact + min(max(reversibility, novelty), 2) + scope + coordination
```

Where scope (0-2) comes from description length and coordination (0-1) from stakeholder mentions. The `min(..., 2)` cap prevents risk dimensions alone from dominating.

#### What Complexity Determines

| Score | Phases | Specialists |
|-------|--------|------------|
| 0-2 | clarify → build → review | Minimal |
| 3-4 | + design, test-strategy | Signal-matched |
| 5-7 | + ideate, test, full gates | All relevant specialists engaged |

#### Signals and Specialists

The scorer also detects 12 signal categories that determine which specialists to engage:

| Signal | Detected From | Engages |
|--------|--------------|---------|
| Security | auth, encrypt, token, jwt, oauth | wicked-platform, wicked-qe |
| Performance | scale, optimize, cache, latency | wicked-engineering, wicked-qe |
| Product | requirement, feature, story, customer | wicked-product |
| Compliance | soc2, hipaa, gdpr, pci, audit | wicked-platform |
| Ambiguity | maybe, should we, options, tradeoff | wicked-jam |
| Complexity | integration, migrate, distributed, legacy | wicked-delivery, wicked-engineering |
| Data | analytics, database, etl, pipeline, ml | wicked-data |
| Infrastructure | deploy, docker, kubernetes, terraform | wicked-platform |
| Architecture | design pattern, api contract, cqrs, event-driven | wicked-agentic, wicked-engineering |
| UX | user experience, accessibility, persona, wireframe | wicked-product |
| Reversibility | migration, breaking change, deprecation | wicked-platform, wicked-delivery |
| Novelty | prototype, greenfield, first time, research | wicked-jam, wicked-engineering |

Keywords ending with `*` are stem-matched: `migrat*` catches "migrate", "migration", and "migrating".

#### Project Archetypes

Scoring adjusts based on the **type of project** being changed. Different archetypes have different quality dimensions -- what matters for a content site is different from what matters for infrastructure.

| Archetype | Quality Focus | Impact Bonus | Min Complexity |
|-----------|--------------|--------------|----------------|
| infrastructure-framework | Core execution paths affect all downstream users | +2 | 3 |
| compliance-regulated | Audit trails, policy adherence, and risk documentation | +2 | 3 |
| monorepo-platform | Cross-package impact, shared dependencies, versioning | +2 | 3 |
| content-heavy | Messaging consistency, factual accuracy, brand voice | +1 | 2 |
| ui-heavy | Design consistency, UX coherence, accessibility | +1 | 2 |
| api-backend | Integration surface, contract stability, schema safety | +1 | 2 |
| data-pipeline | Data quality, lineage tracing, downstream effects | +1 | 2 |
| mobile-app | Platform constraints, UX patterns, release cycles | +1 | 2 |
| ml-ai | Model quality, training data, evaluation rigor | +1 | 3 |
| real-time | Latency, concurrency, state synchronization | +1 | 2 |

**How it works**: When starting or executing a project, crew runs a dynamic pre-analysis that reads project files (CLAUDE.md, package.json, etc.), queries memories, and analyzes codebase structure to detect archetypes. This happens BEFORE signal analysis.

**Dynamic archetypes**: Beyond the built-in list, commands can define custom archetypes at runtime via `--archetype-hints`. A marketing team's landing page project can get a "marketing-landing-page" archetype that injects product and UX signals, even though that archetype isn't built-in.

**Holistic merging**: When multiple archetypes are detected, MAX adjustments apply from ALL of them. A project that's both infrastructure-framework AND compliance-regulated gets the highest impact bonus and minimum complexity floor from both.

**Example**: Modifying crew's scoring engine scored 1/7 without archetypes (no file references = zero impact). With infrastructure-framework archetype, it scores 3/7 because core execution path changes inherently have broad downstream impact regardless of code complexity.

### Graceful Degradation

Crew works fully standalone with built-in agents. Specialist plugins enhance it when available:

| If Installed | Enhancement | Without It |
|-------------|-------------|------------|
| wicked-jam | AI brainstorming in clarify | Built-in facilitator |
| wicked-engineering | Architecture + code review | Built-in reviewer |
| wicked-product | Requirements + UX review | Built-in facilitator |
| wicked-platform | Security + CI/CD checks | Built-in implementer |
| wicked-qe | Test strategy + automation | Built-in reviewer |
| wicked-delivery | PMO + risk tracking | Built-in researcher |

## Workflows

### Standard Project

```bash
# 1. Start - analyzes signals, plans phases
/wicked-crew:start "Migrate auth from sessions to JWT"

# 2. Execute each phase
/wicked-crew:execute          # clarify phase
/wicked-crew:approve clarify  # approve and advance
/wicked-crew:execute          # design phase
/wicked-crew:approve design
# ... continues through build, review

# 3. Check status anytime
/wicked-crew:status
```

### Autonomous Mode

```bash
# Start and let it run
/wicked-crew:start "Add caching to API endpoints"
/wicked-crew:just-finish

# Crew will:
# - Execute all phases
# - Engage specialists automatically
# - Run quality gates
# - Only pause for guardrails (deployments, deletions, security)
```

## Built-in Agents

| Agent | Role | Used When |
|-------|------|-----------|
| `facilitator` | Requirements and ideation | Clarify phase, no wicked-jam |
| `researcher` | Analysis and design | Design phase, no wicked-engineering |
| `implementer` | Code generation | Build phase |
| `reviewer` | Quality assurance | Review phase, no specialist |
| `orchestrator` | Multi-agent coordination | Complex phases |
| `execution-orchestrator` | Execute phase orchestration | Multi-step execution workflows |
| `qe-orchestrator` | Test strategy orchestration | Test-strategy phase |
| `value-orchestrator` | Value delivery orchestration | Review and evidence phases |
| `delivery-manager` | Sprint management, velocity | Delivery tracking |
| `progress-tracker` | Task completion forecasting | Progress monitoring |
| `stakeholder-reporter` | Multi-stakeholder communication | Status reporting |

## Evidence Tracking

Every phase produces evidence in 4 tiers:

| Tier | What | Example |
|------|------|---------|
| L1 | Observations | "47 lines changed in auth.js" |
| L2 | Analysis | "No hardcoded secrets found" |
| L3 | Reasoning | "OAuth2 flow meets requirements" |
| L4 | Decisions | "Approved build phase" |

## Configuration

Autonomy modes via `/wicked-crew:profile`:
- **ask-first**: Pause at every decision
- **balanced** (default): Auto-proceed on minor decisions
- **just-finish**: Maximum autonomy with guardrails

## Data API

This plugin exposes data via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| projects | list, get, create, update, archive, unarchive | Crew workflow projects with phase tracking and lifecycle management |
| phases | list, get | Project phase execution history and status |
| signals | list, search, stats | Signal detection library for project analysis |
| feedback | list, stats | Project outcome records and signal accuracy metrics |
| specialists | list, get | Installed specialist plugins with capabilities |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-crew/{source}/{verb}
```

Or directly via CLI:
```bash
python3 scripts/api.py {verb} {source} [--limit N] [--offset N] [--query Q]
```

### Project Archiving

Archive completed or paused projects to keep `list projects` clean:

```bash
# Archive a project
python3 scripts/api.py archive projects my-project

# List only active projects (default)
python3 scripts/api.py list projects

# Include archived projects
python3 scripts/api.py list projects --include-archived

# Unarchive to reactivate
python3 scripts/api.py unarchive projects my-project
```

Phase operations are blocked on archived projects. Archiving is idempotent.

## Integration

| Plugin | What It Adds | Without It |
|--------|-------------|------------|
| wicked-jam | Multi-perspective brainstorming during clarify/design phases | Facilitator agent handles clarification inline |
| wicked-qe | Test strategy, code analysis, and quality gates | Basic review agent covers quality checks |
| wicked-product | Business strategy, UX review, and requirements analysis | Generic researcher handles product questions |
| wicked-platform | Security review, compliance checks, and DevSecOps | Security concerns flagged but not deeply analyzed |
| wicked-engineering | Architecture review, code review, and debugging | Implementer agent handles engineering work |
| wicked-data | Data engineering review and pipeline analysis | Data-related phases skipped |
| wicked-delivery | Progress tracking, risk monitoring, and reporting | Status tracked via task tools only |
| wicked-agentic | Agentic architecture review and safety audit | Agentic patterns not specifically reviewed |
| wicked-kanban | Task persistence and board visualization | Tasks tracked in-session only |
| wicked-mem | Cross-session memory for decisions and patterns | No memory persistence between sessions |
| wicked-search | Code search for impact analysis and blast radius | Grep/Glob used as fallback |
| wicked-startah | Third-party CLI sign-off (Codex, Gemini) and caching | Human review only, no caching |

## License

MIT
