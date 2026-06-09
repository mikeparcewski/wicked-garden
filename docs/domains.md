# Domains

Domains are **skill and agent families** — the discipline expertise wicked-garden ships. They are not an orchestrator and they do not run a workflow on their own.

Work is shaped by the **9 archetypes** (triage, explore, specify, decide, ship, review, incident, build, migrate — see [Archetypes](v11/archetypes.md)). When an archetype's playbook needs domain expertise — a code review, a security scan, a requirements pass, a structural lookup — it **invokes a domain skill or agent** to get it. You can also call any domain command directly, without an archetype, when you just want that capability.

Every command follows the pattern `/wicked-garden:{domain}:{command}`. Every agent declares `subagent_type: wicked-garden:{domain}:{name}` for Task-tool dispatch.

There are **10 domains**: engineering, platform, product, data, jam, search, agentic, persona, delivery, smaht.

---

## engineering — Software Engineering

Senior engineer, solution architect, system designer, backend/frontend specialists, debugger, technical writer, API documentarian, developer-experience and migration engineers. The workhorse for `build` and `migrate` work.

| Command | What It Does |
|---------|-------------|
| `engineering:review` | Code review from a senior engineering perspective |
| `engineering:arch` | Architecture analysis and recommendations |
| `engineering:debug` | Systematic debugging with root cause analysis |
| `engineering:plan` | Review changes against the codebase and plan steps |
| `engineering:patch-plan` | Show what a change would affect without patching |
| `engineering:apply` | Apply patches from a saved JSON file |
| `engineering:rename` | Rename a field/symbol across all usages |
| `engineering:add-field` | Add a field to an entity and propagate it |
| `engineering:remove` | Remove a field and all its usages |
| `engineering:docs` | Generate or improve documentation |
| `engineering:new-generator` | Create a language generator for wicked-patch |

**Agents**: `senior-engineer`, `solution-architect`, `system-designer`, `backend-engineer`, `frontend-engineer`, `debugger`, `technical-writer`, `api-documentarian`, `devex-engineer`, `migration-engineer`

## platform — DevSecOps

SRE, security, compliance, incident response, infrastructure, DevOps, release, auditing, privacy, chaos and observability engineering. Backs `ship`, `incident`, and `review` work.

| Command | What It Does |
|---------|-------------|
| `platform:security` | OWASP vulnerability assessment |
| `platform:compliance` | SOC2/HIPAA/GDPR/PCI checks |
| `platform:audit` | Collect audit evidence |
| `platform:health` | System health and reliability assessment |
| `platform:incident` | Incident response and triage |
| `platform:infra` | Infrastructure review and IaC analysis |
| `platform:actions` | GitHub Actions workflow generation |
| `platform:traces` | Distributed tracing analysis |
| `platform:toolchain` | Discover and query monitoring tools |
| `platform:gh` | GitHub CLI power utilities |
| `platform:assert` | Contract assertions against subprocess outputs |
| `platform:plugin-health` | Health probes against installed plugins |

**Agents**: `security-engineer`, `sre`, `compliance-officer`, `incident-responder`, `infrastructure-engineer`, `devops-engineer`, `release-engineer`, `auditor`, `privacy-expert`, `chaos-engineer`, `observability-engineer`

## product — Product Management & Design

Requirements, UX, customer voice, market/value strategy, accessibility, visual design review. Backs `specify` and `explore` work.

| Command | What It Does |
|---------|-------------|
| `product:elicit` | Requirements elicitation through structured inquiry |
| `product:acceptance` | Define acceptance criteria from requirements |
| `product:listen` | Aggregate customer feedback from available sources |
| `product:analyze` | Analyze feedback for themes and sentiment |
| `product:synthesize` | Generate actionable recommendations |
| `product:align` | Facilitate stakeholder alignment |
| `product:strategy` | ROI, value proposition, competitive analysis |
| `product:ux` | UX flow design and analysis |
| `product:ux-review` | UX and design quality review |
| `product:mockup` | Wireframe and prototype generation |
| `product:screenshot` | Screenshot-based UI review (multimodal) |
| `product:a11y` | WCAG 2.1 AA accessibility audit |

> **Collapsed to skill (cleanup ADR 0002).** Most product commands now load their rubric inline from `skills/product/refs/<name>.md` and apply it directly — no `Task` dispatch hop. Dispatch is kept only where multiple lenses run in parallel: `product:ux-review --focus all` (flows + ui + a11y + research) and `product:strategy --focus all` (market + value).

**Agents**: `product-manager`, `requirements-analyst`, `ux-designer`, `user-researcher`, `market-strategist`, `value-strategist`, `a11y-expert`, `ui-reviewer` — the dispatch-only `ux-analyst`, `user-voice`, and `mockup-generator` were removed when their commands collapsed inline.

## data — Data Engineering

Data analyst, data engineer, ML engineer, and a unified data architect for OLTP + OLAP design.

| Command | What It Does |
|---------|-------------|
| `data:analyze` | Interactive data analysis on files |
| `data:data` | Data profiling and schema validation |
| `data:pipeline` | Data pipeline design and review |
| `data:ml` | ML model review and training pipeline |
| `data:ontology` | Dataset ontology recommendations |

**Agents**: `data-analyst`, `data-engineer`, `data-architect`, `ml-engineer`

## jam — AI Brainstorming

Dynamic focus groups with AI personas plus structured multi-model council sessions using external LLM CLIs. The natural fit for `explore` work.

| Command | What It Does |
|---------|-------------|
| `jam:brainstorm` | Full multi-perspective session with dynamic focus groups |
| `jam:quick` | Lightweight exploration (fewer personas, one round) |
| `jam:council` | Structured multi-model evaluation via external LLM CLIs |
| `jam:perspectives` | Get multiple perspectives on a decision (no synthesis) |
| `jam:thinking` | View individual persona perspectives pre-synthesis |
| `jam:persona` | View a specific persona's contributions |
| `jam:transcript` | View the full conversation transcript |
| `jam:revisit` | Revisit a past brainstorm decision |

**Agents**: `brainstorm-facilitator`, `quick-facilitator`, `council`

## search — Code Intelligence

Structural understanding via tree-sitter — symbol-level, not text search. Blast radius, lineage, and service-map detection. Heavily used during `build`, `migrate`, and `review` to ground changes.

| Command | What It Does |
|---------|-------------|
| `search:index` | Build/rebuild the unified code + document index |
| `search:blast-radius` | Dependencies and dependents of a symbol |
| `search:lineage` | Trace data from UI to DB (or reverse) |
| `search:service-map` | Detect service architecture from infra files |
| `search:hotspots` | Most-referenced symbols |
| `search:categories` | Symbol categories, layers, and directory groupings |
| `search:coverage` | Report lineage coverage |
| `search:sources` | Manage external content sources |
| `search:quality` | Improve index accuracy |
| `search:validate` | Validate index consistency |

> For open-ended symbol and concept search, prefer `wicked-brain:search` / `wicked-brain:query` when the brain index is available; the `search:*` commands cover structural analysis the brain doesn't.

## agentic — Agentic Architecture

Architecture review, safety auditing, pattern advice, performance analysis, framework research — for reviewing and designing AI agent systems.

| Command | What It Does |
|---------|-------------|
| `agentic:review` | Full agentic codebase review with framework detection |
| `agentic:design` | Interactive architecture design guide |
| `agentic:audit` | Trust and safety audit |
| `agentic:frameworks` | Research and compare frameworks |

**Agents**: `architect`, `safety-reviewer`, `pattern-advisor`, `performance-analyst`, `framework-researcher`

## persona — On-Demand Personas

Invoke any specialist persona directly. Define custom personas with personality, constraints, and preferences.

| Command | What It Does |
|---------|-------------|
| `persona:as` | Invoke a named persona to perform a task |
| `persona:define` | Create or update a custom persona |
| `persona:list` | List all available personas |
| `persona:submit` | PR a persona to the built-in registry |

**Agents**: `persona-agent`

## delivery — Delivery Management

Delivery manager, stakeholder reporter, rollout manager, experiment designer, risk and progress tracking, cloud-cost intelligence. Backs `ship` and post-ship reporting.

| Command | What It Does |
|---------|-------------|
| `delivery:rollout` | Progressive rollout plans with risk management |
| `delivery:experiment` | A/B test design with statistical rigor |
| `delivery:report` | Multi-perspective stakeholder reports |
| `delivery:setup` | Configure delivery metrics (cost model, sprint cadence) |

**Agents**: `delivery-manager`, `stakeholder-reporter`, `rollout-manager`, `experiment-designer`, `risk-monitor`, `progress-tracker`, `cloud-cost-intelligence`

## smaht — Context Assembly

On-demand context assembly over wicked-brain and the search index. A pull-model skill — archetypes and subagents call it when they need a briefing, rather than pushing context onto every prompt.

| Command | What It Does |
|---------|-------------|
| `smaht:briefing` | What happened since the last session — recent events and updates |
| `smaht:state` | Snapshot and report current session state |
| `smaht:events-import` | Import existing domain JSON records into the event log |
| `smaht:propose-skills` | Suggest skills worth adding based on observed work |

---

## How archetypes invoke domains

An archetype playbook (`skills/archetype/refs/{archetype}.md`) doesn't hardcode a domain pipeline — it reaches for whatever expertise the work needs:

- A `build` reaches for `engineering` to implement and review, `search` to ground changes, and `wicked-testing` for evidence.
- A `review` reaches for `engineering:review`, `platform:security`, and `agentic:review` depending on the target.
- An `explore` reaches for `jam` to diverge across perspectives.
- A `specify` reaches for `product:elicit` and `product:acceptance`.
- A `ship` reaches for `delivery:rollout` and `platform:health`.

Domains are the *how*; archetypes are the *when* and *what shape*. The two compose — neither replaces the other.
