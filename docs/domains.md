# Domains

Wicked Garden is organized into **13 domains**. Each domain ships its own commands, agents, skills, and scenarios. Every domain works independently — the ecosystem is additive, not required.

**Specialist discovery is dynamic.** v6 removed the static `enhances` map. The facilitator skill reads `agents/**/*.md` frontmatter at runtime and matches each agent's description + `subagent_type` to the 9-factor rubric. Add an agent to disk with a `subagent_type: wicked-garden:{domain}:{name}` front-matter line and the facilitator can route to it next session.

## Workflow & Intelligence

### crew — Workflow Engine

The orchestrator. Runs the facilitator (`skills/propose-process/`) to score 9 factors, detect 1 of 7 archetypes, pick specialists from agent frontmatter, select phases from `phases.json`, and set rigor tier. Enforces quality gates via `gate-policy.json`. Tracks artifact convergence through 6 states.

| Command | What It Does |
|---------|-------------|
| `crew:start` | Start a facilitator-driven workflow for any task |
| `crew:execute` | Execute the current phase with adaptive routing |
| `crew:just-finish` | Execute remaining work with maximum autonomy + guardrails |
| `crew:status` | Show project state, phase, and next steps |
| `crew:approve` | Approve a phase gate and advance |
| `crew:gate` | Run QE analysis on a target at configurable rigor |
| `crew:archive` | Archive or unarchive a project |
| `crew:evidence` | Show evidence summary for a task |
| `crew:convergence` | Show artifact convergence lifecycle — states, stalls, verdict |
| `crew:swarm` | Check for quality-crisis swarm trigger |
| `crew:yolo` / `crew:auto-approve` | Grant or revoke APPROVE-verdict auto-advance with guardrails |
| `crew:explain` | Translate jargon-heavy crew output into plain, grade-8 English |
| `crew:retro` | Generate a retrospective from operate-phase data |
| `crew:incident` | Log a production incident linked to the current project |
| `crew:feedback` | Capture user or stakeholder feedback |
| `crew:operate` | Enter and manage the operate phase |
| `crew:profile` | Configure crew preferences |
| `crew:cutover` | Cut an in-flight project to mode-3 formal dispatch |
| `crew:migrate-gates` | Migrate in-flight projects to strict gate enforcement |
| `crew:help` | Show available crew commands |

**v6 Capabilities**:
- **Facilitator rubric** — 9-factor scoring picks specialists and phases inline, no keyword signals
- **Archetype detection** — 7 archetypes (`archetype_detect.py`) drive per-archetype evidence expectations
- **Phase-boundary QE evaluator** — `qe-evaluator` agent replaces `test-strategist` at `testability` and `evidence-quality` gates; reads archetype for per-type test/evidence guidance
- **Challenge gate + contrarian agent** — auto-inserted at complexity ≥ 4; runs a structured steelman of the alternative path
- **Convergence lifecycle** — Designed → Built → Wired → Tested → Integrated → Verified with stall detection; `convergence-verify` gate blocks review approval until every artifact reaches Integrated
- **Semantic reviewer** — extracts numbered AC/FR/REQ from clarify artifacts, emits a Gap Report (`aligned`/`divergent`/`missing`) at the review gate for complexity ≥ 3
- **Gate enforcement** — `gate-policy.json` codifies reviewer × rigor × dispatch-mode. APPROVE / CONDITIONAL / REJECT verdicts are binding
- **BLEND aggregation** — multi-reviewer score = `0.4 × min + 0.6 × avg`
- **Blind reviewer** — reviewers see deliverables + evidence, not prior gate verdicts
- **HMAC dispatch log** — every specialist dispatch signed and appended; orphan gate-results → CONDITIONAL
- **Pre-flip monitoring** — T>7 silent, 1≤T≤7 `PreFlipNotice WARN`, T=0 StrictMode with post-flip latch
- **Yolo guardrails** — full-rigor grants require justification + sentinel; CONDITIONAL needs explicit `--override-gate`
- **Gate-result security** — schema validator, content sanitizer, orphan detection, append-only audit log (rollback via `WG_GATE_RESULT_*` env vars)
- **Persistent process memory + kaizen backlog** — operate retro auto-populates facilitator-context digest for future projects

**Agents (10)**: `facilitator`, `phase-executor`, `gate-evaluator`, `independent-reviewer`, `contrarian`, `qe-evaluator`, `qe-orchestrator`, `implementer`, `researcher`, `reviewer`

**When to use**: Any task that benefits from structured delivery — features, migrations, refactors, bug investigations, compliance work. The facilitator adapts rigor to the work: a docs-only change gets minimal tier and self-check gates; a schema migration gets full tier, multi-reviewer panels, and per-archetype evidence demands.

### smaht — Context Assembly

The "brain" of the plugin. Intercepts every prompt via `UserPromptSubmit` and assembles context on demand. v6 replaced v5's push-based briefings with **pull-model** adapters that answer only what the current prompt needs.

| Command | What It Does |
|---------|-------------|
| `smaht:onboard` | Guided codebase walkthrough + brain ingest |
| `smaht:smaht` | On-demand context pull for the current topic |
| `smaht:context` | Build a structured context package for subagents |
| `smaht:debug` | Show what context was assembled and why |
| `smaht:learn` | Cache library docs via Context7 |
| `smaht:libs` | List cached library cheatsheets |
| `smaht:briefing` | Session briefing — what happened since last time |
| `smaht:events-query` | Query the unified event log for cross-domain activity |
| `smaht:events-import` | Import existing domain JSON records into the event log |
| `smaht:collaborate` | Multi-AI CLI collaboration (discover, review, council) |
| `smaht:onboard` | Intelligent codebase onboarding |
| `smaht:help` | Show available smaht commands |

**Behind the scenes**: four-tier routing keeps simple prompts fast and complex ones thorough:
- **HOT** (<100ms): continuations / confirmations → session state only
- **FAST** (<1s): clear-intent prompts → pattern-based adapter fan-out
- **SLOW** (2–5s): complex / ambiguous → full adapter fan-out + history condenser
- **SYNTHESIZE**: complex + risky → agentic synthesis skill before the orchestrator

**Six adapters** (v6): `domain`, `brain`, `events`, `context7`, `tools`, `delegation`. The v4 `mem` / `search` / `kanban` / `crew` / `jam` adapters were consolidated into `domain` + `brain` + `events`. Intent classification is an inline heuristic in `hooks/scripts/prompt_submit.py` (the v5 `router.py` intent classifier was deleted in #428).

**Brain as primary knowledge layer**: when wicked-brain is installed, the brain adapter queries the FTS5 index first. Budget enforcer source priority: `mem=10, search=9, brain=8, crew=6, context7=4, jam=3, tools=2, delegation=1`.

### mem — Cross-Session Memory

Decisions, patterns, and preferences persist across sessions. 3-tier store with auto-consolidation. Phase-aware recall weights memories by affinity to the current crew phase.

| Command | What It Does |
|---------|-------------|
| `mem:store` | Save a decision, pattern, or preference |
| `mem:recall` | Search memories by query |
| `mem:review` | Browse and manage memories |
| `mem:stats` | Show memory statistics |
| `mem:forget` | Archive or delete a memory |
| `mem:consolidate` | Manually trigger cross-tier consolidation |
| `mem:retag` | Backfill search tags on existing memories |
| `mem:help` | Show available memory commands |

**Agents (3)**: `memory-archivist`, `memory-learner`, `memory-recaller`

**3 tiers**: working (transient, auto-consolidates) → episodic (sprint-level) → semantic (durable project knowledge, prioritized in recall). Phase affinity: during `build`, `design` and `clarify` memories boost 1.5×; during `test-strategy`, test patterns boost.

### search — Code Intelligence

Structural understanding across 73 languages via tree-sitter. Not text search — symbol-level intelligence with blast radius, lineage, and service-map detection.

| Command | What It Does |
|---------|-------------|
| `search:code` | Find functions, classes, methods by name |
| `search:refs` | Find where a symbol is referenced |
| `search:blast-radius` | Dependencies and dependents of a symbol |
| `search:impact` | Reverse-lineage analysis for a change |
| `search:lineage` | Trace data from UI to DB (or reverse) |
| `search:service-map` | Detect service architecture from infra files |
| `search:hotspots` | Most-referenced symbols |
| `search:categories` | Symbol categories, layers, and directory groupings |
| `search:docs` | Search documents (PDF, markdown, Office) |
| `search:impl` | Find code implementing a documented feature |
| `search:scout` | Quick pattern reconnaissance (no index required) |
| `search:sources` | Manage external content sources |
| `search:index` | Build/rebuild the code index |
| `search:stats` | Show index statistics |
| `search:validate` | Validate index consistency |
| `search:quality` | Run quality crew to improve index accuracy |
| `search:coverage` | Report lineage coverage |
| `search:search` | Search across all code and documents |
| `search:help` | Show available search commands |

Lifecycle scoring (`lifecycle_scoring.py`) ranks results by phase affinity, recency, traceability, and gate status. RRF is opt-in for multi-ranker fusion.

**Requires**: tree-sitter (auto-detected). Falls back to grep-based search without it.

### jam — AI Brainstorming

Dynamic focus groups with AI personas plus structured multi-model council sessions using external LLM CLIs.

| Command | What It Does |
|---------|-------------|
| `jam:brainstorm` | Full multi-perspective session |
| `jam:quick` | Lightweight exploration (fewer personas, one round) |
| `jam:council` | Multi-model evaluation using external LLM CLIs |
| `jam:perspectives` | Get multiple perspectives on a decision |
| `jam:thinking` | View individual persona perspectives pre-synthesis |
| `jam:transcript` | View full conversation transcript |
| `jam:persona` | View a specific persona's contributions |
| `jam:revisit` | Revisit a past brainstorm decision |
| `jam:help` | Show available jam commands |

**Agents (2)**: `brainstorm-facilitator` (renamed from `facilitator` in v6.3.2 to avoid collision with crew's facilitator), `council`

Structured consensus protocol with explicit dissent tracking: proposals → cross-review → synthesis with clustered agreements + classified dissents (strong / moderate / mild).

---

## Specialist Disciplines

Specialists are discovered by the facilitator reading `agents/**/*.md` frontmatter. Every agent declares `subagent_type: wicked-garden:{domain}:{name}` for Task-tool routing.

### engineering — Software Engineering

Senior engineer, solution architect, system designer, backend/frontend specialists, debugger, technical writer, API documentarian, developer-experience engineer, migration engineer.

| Command | What It Does |
|---------|-------------|
| `engineering:review` | Multi-pass code review with domain routing |
| `engineering:arch` | Architecture analysis and recommendations |
| `engineering:debug` | Systematic debugging with root cause analysis |
| `engineering:docs` | Generate or improve documentation |
| `engineering:plan` | Review changes against codebase and plan steps |
| `engineering:rename` | Rename a field/symbol across all usages |
| `engineering:add-field` | Add a field to an entity and propagate |
| `engineering:remove` | Remove a field and all its usages |
| `engineering:apply` | Apply patches from a saved JSON file |
| `engineering:patch-plan` | Show what a change would affect without patching |
| `engineering:new-generator` | Create a language generator for wicked-patch |
| `engineering:help` | Show available engineering commands |

**Agents (10)**: `senior-engineer`, `solution-architect`, `system-designer`, `backend-engineer`, `frontend-engineer`, `debugger`, `technical-writer`, `api-documentarian`, `devex-engineer`, `migration-engineer`

### product — Product Management & Design

Requirements analysis, UX, customer voice, market / value strategy, accessibility, visual design review. v6 consolidated several overlapping roles (business-strategist → market-strategist, value-analyst + alignment-lead → value-strategist, feedback-analyst + customer-advocate → user-voice, visual-reviewer → ui-reviewer) and added `ux-analyst`.

| Command | What It Does |
|---------|-------------|
| `product:elicit` | Requirements elicitation through structured inquiry |
| `product:listen` | Aggregate customer feedback from available sources |
| `product:analyze` | Analyze feedback for themes and sentiment |
| `product:synthesize` | Generate actionable recommendations |
| `product:acceptance` | Define acceptance criteria from requirements |
| `product:align` | Facilitate stakeholder alignment |
| `product:strategy` | ROI, value proposition, competitive analysis |
| `product:ux-review` | UX and design quality review |
| `product:review` | Design system consistency review |
| `product:mockup` | Wireframe and prototype generation |
| `product:ux` | UX flow design and analysis |
| `product:screenshot` | Screenshot-based UI review (multimodal) |
| `product:a11y` | WCAG 2.1 AA accessibility audit |
| `product:help` | Show available product commands |

**Agents (11)**: `product-manager`, `requirements-analyst`, `ux-designer`, `ux-analyst`, `user-researcher`, `user-voice`, `market-strategist`, `value-strategist`, `a11y-expert`, `ui-reviewer`, `mockup-generator`

### platform — DevSecOps

SRE, security, compliance, incident response, infrastructure, DevOps, release, auditing, privacy. v6 added `chaos-engineer` and `observability-engineer` for resilience and SLI/SLO work.

| Command | What It Does |
|---------|-------------|
| `platform:security` | OWASP vulnerability assessment |
| `platform:compliance` | SOC2/HIPAA/GDPR/PCI checks |
| `platform:audit` | Collect audit evidence |
| `platform:health` | System health and reliability assessment |
| `platform:incident` | Incident response and triage |
| `platform:actions` | GitHub Actions workflow generation |
| `platform:infra` | Infrastructure review and IaC analysis |
| `platform:errors` | Error pattern analysis |
| `platform:traces` | Distributed tracing analysis |
| `platform:gh` | GitHub CLI power utilities |
| `platform:toolchain` | Discover and query monitoring tools |
| `platform:logs` | View operational logs |
| `platform:plugin-debug` | View/set plugin log verbosity |
| `platform:plugin-health` | Health probes against installed plugins |
| `platform:plugin-traces` | Query hook execution traces |
| `platform:assert` | Contract assertions against subprocess outputs |
| `platform:help` | Show available platform commands |

**Agents (11)**: `security-engineer`, `sre`, `compliance-officer`, `incident-responder`, `infrastructure-engineer`, `devops-engineer`, `release-engineer`, `auditor`, `privacy-expert`, `chaos-engineer`, `observability-engineer`

### qe — Quality Engineering

Test strategist, test designer, automation engineer, risk assessor, testability reviewer, code analyzer, continuous quality monitor, production quality engineer, requirements quality analyst, contract testing engineer, and the v6 additions: `semantic-reviewer` (spec-to-code alignment) and `qe-evaluator` (phase-boundary evidence evaluator).

v6 consolidated the former three-agent acceptance pipeline (`acceptance-test-writer` / `executor` / `reviewer`) into a single `test-designer` that owns Write → Execute → Analyze → Verdict in one role. `tdd-coach` folded into `test-strategist`.

| Command | What It Does |
|---------|-------------|
| `qe:qe` | Full quality engineering review |
| `qe:scenarios` | Generate test scenarios from requirements |
| `qe:acceptance` | Evidence-gated acceptance testing (Write → Execute → Review) |
| `qe:automate` | Generate test code from scenarios |
| `qe:qe-plan` | Comprehensive test plan generation |
| `qe:qe-review` | Review test quality and coverage |
| `qe:run` | Execute an E2E test scenario |
| `qe:list` | List available scenarios with tool status |
| `qe:check` | Validate scenario file format |
| `qe:setup` | Install required CLI tools |
| `qe:report` | File issues from test failures |
| `qe:help` | Show available qe commands |

**Agents (11)**: `test-strategist`, `test-designer`, `test-automation-engineer`, `testability-reviewer`, `semantic-reviewer`, `risk-assessor`, `requirements-quality-analyst`, `code-analyzer`, `continuous-quality-monitor`, `production-quality-engineer`, `contract-testing-engineer`

### data — Data Engineering

Data analyst, data engineer, ML engineer, unified data architect (v6 merged `engineering:data-architect` + `data:analytics-architect` into `data:data-architect` for the full OLTP + OLAP design).

| Command | What It Does |
|---------|-------------|
| `data:analyze` | Interactive data analysis on files |
| `data:numbers` | DuckDB SQL on CSV/Excel (10GB+, plain English) |
| `data:data` | Data profiling and schema validation |
| `data:analysis` | Alias for `data:analyze` |
| `data:pipeline` | Data pipeline design and review |
| `data:ml` | ML model review and training pipeline |
| `data:ontology` | Dataset ontology recommendations |
| `data:help` | Show available data commands |

**Agents (4)**: `data-analyst`, `data-engineer`, `data-architect`, `ml-engineer`

### delivery — Delivery Management

Delivery manager, stakeholder reporter, rollout manager, experiment designer, risk monitor, progress tracker, and unified cloud-cost intelligence (v6 merged `finops-analyst` + `cost-optimizer`).

| Command | What It Does |
|---------|-------------|
| `delivery:report` | Multi-perspective stakeholder reports |
| `delivery:setup` | Configure delivery metrics (cost model, sprint cadence) |
| `delivery:rollout` | Progressive rollout plans with risk management |
| `delivery:experiment` | A/B test design with statistical rigor |
| `delivery:process-health` | Surface process memory — kaizen status, unresolved action items |
| `delivery:help` | Show available delivery commands |

**Agents (7)**: `delivery-manager`, `stakeholder-reporter`, `rollout-manager`, `experiment-designer`, `risk-monitor`, `progress-tracker`, `cloud-cost-intelligence`

### agentic — Agentic Architecture

Architecture reviewer, safety auditor, pattern advisor, performance analyst, framework researcher. For reviewing and designing AI agent systems.

| Command | What It Does |
|---------|-------------|
| `agentic:review` | Full agentic codebase review |
| `agentic:design` | Interactive architecture design guide |
| `agentic:audit` | Trust and safety audit |
| `agentic:ask` | Ask about agentic patterns and frameworks |
| `agentic:frameworks` | Research and compare frameworks |
| `agentic:help` | Show available agentic commands |

**Agents (5)**: `architect`, `safety-reviewer`, `pattern-advisor`, `performance-analyst`, `framework-researcher`

### persona — On-Demand Personas

Invoke any specialist persona directly without crew or jam. Define custom personas with personality, constraints, memories, and preferences.

| Command | What It Does |
|---------|-------------|
| `persona:as` | Invoke a named persona to perform a task |
| `persona:define` | Create or update a custom persona |
| `persona:list` | List all available personas |
| `persona:submit` | PR a persona to the built-in registry |

**Agents (1)**: `persona-agent`

---

## Cross-Cutting Capabilities

Skills and modules that apply across all domains:

| Capability | What It Does |
|-----------|-------------|
| **propose-process** | The facilitator rubric. Scores 9 factors, detects archetype, picks specialists + phases, sets rigor tier, emits `process-plan.md` and the full task chain |
| **adopt-legacy** | Detects v5 project markers and transforms them idempotently to v6 format |
| **workflow** | v6 entry-point skill documenting interaction modes, rigor tiers, phase plan, and gate-policy reviewer assignment |
| **acceptance-testing** | Evidence-gated three-stage pipeline: Writer designs plans, Executor runs + captures evidence, Reviewer renders verdict |
| **unified-search** | Routes code + document queries to the right backend (brain FTS5, tree-sitter, grep) |
| **deliberate** | Critical-thinking framework applied before work. Challenges assumptions, finds root causes, spots adjacent opportunities |
| **multi-model** | Multi-LLM council reviews using external CLIs (Codex, Gemini, OpenCode) |
| **smaht** | On-demand context assembly over wicked-brain + unified-search |
| **cross-phase intelligence** | Traceability, artifact states, verification protocol, impact analysis, convergence lifecycle, knowledge graph, phase-aware memory |
| **deliberate** | Five-lens critical thinking — use before committing to an approach |
