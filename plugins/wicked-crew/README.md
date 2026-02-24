# wicked-crew

Signal-driven workflow orchestration that analyzes your project description, selects the right phases, and routes to the right specialists automatically -- so you stop managing the process and start shipping.

## Quick Start

```bash
# Install
claude plugin install wicked-crew@wicked-garden

# Start a project -- crew analyzes signals and plans phases
/wicked-crew:start "Migrate auth from sessions to JWT across 3 services"

# Execute the current phase (or /wicked-crew:just-finish for full autonomy)
/wicked-crew:execute
```

## Workflows

### Standard project with phase approval

```bash
/wicked-crew:start "Add caching layer to API endpoints"
# crew detects: performance + infrastructure signals → complexity 4
# phases planned: clarify → design → test-strategy → build → review

/wicked-crew:execute          # clarify phase: wicked-jam engaged for ambiguity
/wicked-crew:approve clarify  # advance to design

/wicked-crew:execute          # design phase: wicked-engineering reviews architecture
/wicked-crew:approve design   # advance to build

/wicked-crew:execute          # build phase: implementation
/wicked-crew:gate             # run QE execution gate
/wicked-crew:approve build    # advance to review
```

### Autonomous mode with guardrails

For well-understood work, skip the approvals and let crew drive:

```bash
/wicked-crew:start "Fix the rate limiting bug on the login endpoint"
/wicked-crew:just-finish

# Crew will:
# - Execute all phases sequentially
# - Engage specialists when signals match
# - Run quality gates at checkpoints
# - Only pause for: deployments, deletions, security decisions
```

### Checking project state mid-flight

```bash
/wicked-crew:status
# Shows: current phase, signals detected, complexity score,
#        specialists engaged, tasks completed, next steps
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-crew:start` | Create a project with signal analysis and phase planning | `/wicked-crew:start "Add OAuth2 support"` |
| `/wicked-crew:execute` | Execute the current phase with adaptive role engagement | `/wicked-crew:execute` |
| `/wicked-crew:just-finish` | Autonomous completion with safety guardrails | `/wicked-crew:just-finish` |
| `/wicked-crew:approve` | Approve a phase and advance to the next | `/wicked-crew:approve clarify` |
| `/wicked-crew:gate` | Run a QE gate (value, strategy, or execution) | `/wicked-crew:gate --gate execution` |
| `/wicked-crew:evidence` | Show evidence collected for a task or project | `/wicked-crew:evidence` |
| `/wicked-crew:status` | Show project state, signals, specialists, and next steps | `/wicked-crew:status` |
| `/wicked-crew:profile` | Configure autonomy, style, and plan-mode preferences | `/wicked-crew:profile --autonomy balanced` |
| `/wicked-crew:archive` | Archive completed or paused projects | `/wicked-crew:archive my-project` |

## When to Use What

| Situation | Command |
|-----------|---------|
| Starting any project | `/start` |
| Stepping through phases with manual control | `/execute` + `/approve` |
| Shipping well-understood work fast | `/start` + `/just-finish` |
| Checking where you are mid-project | `/status` |
| Ensuring quality at a phase boundary | `/gate` |
| Setting up recurring preferences | `/profile` |

## How It Works

### Signal Detection and Phase Planning

When you `/start` a project, crew reads your description and answers three questions:

- **How much could this break?** (Impact: 0-3)
- **Can we undo it easily?** (Reversibility: 0-3)
- **Have we done this before?** (Novelty: 0-3)

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
complexity = impact + min(round(reversibility * novelty * 0.22), 2) + scope + coordination
```

Where scope (0-1) comes from description length and coordination (0-1) from stakeholder mentions. The multiplicative risk premium requires *both* reversibility and novelty to be elevated before adding overhead — novel but reversible work stays fast-tracked.

#### What Complexity Determines

| Score | Phases | Specialists |
|-------|--------|-------------|
| 0-2 | clarify → build → review | Minimal |
| 3-4 | + design, test-strategy | Signal-matched |
| 5-7 | + ideate, test, full gates | All relevant specialists |

Twelve signal categories map to specialists automatically:

| Signal | Keywords | Engages |
|--------|---------|---------|
| Security | auth, encrypt, token, jwt, oauth | wicked-platform, wicked-qe |
| Performance | scale, optimize, cache, latency | wicked-engineering, wicked-qe |
| Ambiguity | maybe, should we, options, tradeoff | wicked-jam |
| Architecture | api contract, cqrs, event-driven | wicked-engineering, wicked-agentic |
| Data | analytics, database, etl, pipeline | wicked-data |
| Infrastructure | deploy, docker, kubernetes, terraform | wicked-platform |
| Compliance | soc2, hipaa, gdpr, pci, audit | wicked-platform |

### Dynamic Phase Injection

Crew re-analyzes at checkpoints (clarify, design, build). If new signals appear or complexity increases after reviewing your artifacts, missing phases are injected in dependency order -- not appended blindly to the end.

### Project Archetypes

Beyond signals, crew detects project type from files like `AGENTS.md`, `CLAUDE.md`, and `package.json`. Infrastructure frameworks, compliance-regulated systems, and monorepo platforms receive an impact bonus and a higher minimum complexity floor, so the scoring reflects what matters for your stack.

### Evidence Tiers

Every phase produces evidence in four tiers:

| Tier | What | Example |
|------|------|---------|
| L1 | Observations | "47 lines changed in auth.js" |
| L2 | Analysis | "No hardcoded secrets found" |
| L3 | Reasoning | "OAuth2 flow meets requirements" |
| L4 | Decisions | "Approved build phase" |

## Agents

| Agent | Role | Used When |
|-------|------|-----------|
| `facilitator` | Requirements and ideation | Clarify phase, no wicked-jam installed |
| `researcher` | Analysis and design | Design phase, no wicked-engineering installed |
| `implementer` | Code generation | Build phase |
| `reviewer` | Quality assurance | Review phase, no specialist installed |
| `orchestrator` | Multi-agent coordination | Complex phases |
| `execution-orchestrator` | Execute phase orchestration | Multi-step execution workflows |
| `qe-orchestrator` | Test strategy orchestration | Test-strategy phase |
| `value-orchestrator` | Value delivery orchestration | Review and evidence phases |
| `delivery-manager` | Sprint management and velocity | Delivery tracking |
| `progress-tracker` | Task completion forecasting | Progress monitoring |
| `stakeholder-reporter` | Multi-stakeholder communication | Status reporting |

## Skills

| Skill | What It Covers |
|-------|---------------|
| `workflow` | Phase lifecycle, approval gates, and phase injection patterns |
| `qe-strategy` | Quality engineering gate patterns (value, strategy, execution) |
| `adaptive` | Signal detection, archetype scoring, and dynamic routing |

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

Archive completed or paused projects to keep `list projects` clean:

```bash
python3 scripts/api.py archive projects my-project
python3 scripts/api.py list projects --include-archived
python3 scripts/api.py unarchive projects my-project
```

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-jam | Multi-perspective brainstorming in clarify and design phases | Built-in facilitator handles clarification inline |
| wicked-engineering | Architecture review, code review, and implementation guidance | Built-in researcher and implementer cover engineering work |
| wicked-qe | Test strategy, code analysis, and QE gates | Basic review agent covers quality checks |
| wicked-platform | Security review, compliance checks, and DevSecOps analysis | Security concerns flagged but not deeply analyzed |
| wicked-product | Business strategy, UX review, and requirements analysis | Generic researcher handles product questions |
| wicked-data | Data engineering review and pipeline analysis | Data-related phases skipped |
| wicked-delivery | Progress tracking, risk monitoring, and stakeholder reporting | Status tracked via task tools only |
| wicked-agentic | Agentic architecture review and safety audit | Agentic patterns not specifically reviewed |
| wicked-kanban | Task persistence and board visualization across sessions | Tasks tracked in-session only, lost on restart |
| wicked-mem | Cross-session memory for decisions, patterns, and outcomes | No memory persistence between sessions |
| wicked-search | Symbol graph for impact analysis and blast radius during build | Grep/Glob used as fallback, no structural understanding |
| wicked-startah | Third-party AI sign-off (Codex, Gemini) at gates and caching | Human review only, repeated context re-queried each run |

## License

MIT
