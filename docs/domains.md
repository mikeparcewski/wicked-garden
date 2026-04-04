# Domains

Wicked Garden is organized into 14 domains. Each domain brings its own commands, agents, skills, and scenarios. Every domain works independently — the ecosystem is additive, not required.

## Workflow & Intelligence

### crew — Workflow Engine

The orchestrator. Analyzes your project description, detects signals, scores complexity, selects phases, and routes to specialists automatically. v3.4 adds cross-phase traceability, artifact lifecycle management, verification protocols at gates, project isolation, and impact analysis across phases.

| Command | What It Does |
|---------|-------------|
| `crew:start` | Start a signal-driven workflow for any task |
| `crew:execute` | Execute the current phase with adaptive routing |
| `crew:just-finish` | Execute remaining work with maximum autonomy |
| `crew:status` | Show project state, phase, and next steps |
| `crew:approve` | Approve a phase gate and advance |
| `crew:gate` | Run QE analysis on a target |
| `crew:archive` | Archive or unarchive a project |
| `crew:evidence` | Show evidence summary for a task |
| `crew:profile` | Configure crew preferences |
| `crew:help` | Show available crew commands |

**v3.4 Capabilities**:
- **Traceability**: `traceability.py` creates cross-phase links between artifacts, decisions, and deliverables. BFS traversal finds transitive dependencies. Coverage reports identify orphaned artifacts.
- **Artifact State Machine**: `artifact_state.py` tracks every artifact through a 6-state lifecycle: DRAFT, IN_REVIEW, APPROVED, IMPLEMENTED, VERIFIED, CLOSED.
- **Verification Protocol**: `verification_protocol.py` runs 6-point review checks at gates — completeness, consistency, traceability, quality metrics, dependency satisfaction, and evidence validation.
- **Project Isolation**: `project_registry.py` provides `get_project_filter()` for strict project-scoped queries, preventing cross-project data leakage.
- **Impact Analysis**: `impact_analyzer.py` performs cross-phase impact analysis when artifacts change, identifying downstream effects before they cascade.

**Agents** (7): execution-orchestrator, facilitator, implementer, qe-orchestrator, researcher, reviewer, value-orchestrator

**When to use**: Any task that benefits from structured delivery — features, migrations, refactors, bug investigations. Crew auto-detects complexity: simple tasks finish in minutes, complex ones get the full pipeline.

### smaht — Context Assembly

The brain. Intercepts every prompt and injects relevant context from all domains. You rarely call it directly — it works automatically. v3.4 adds a knowledge graph for entity-relationship tracking across sessions.

| Command | What It Does |
|---------|-------------|
| `smaht:onboard` | Guided codebase walkthrough |
| `smaht:context` | Build structured context for subagents |
| `smaht:debug` | Show what context was assembled |
| `smaht:learn` | Learn a library via ContextSeven docs |
| `smaht:libs` | List cached library cheatsheets |
| `smaht:briefing` | Session briefing — what happened since last time |
| `smaht:events-query` | Query the unified event log for cross-domain activity |
| `smaht:events-import` | Import existing domain JSON records into the event log |
| `smaht:collaborate` | Orchestrate multi-AI CLI collaboration (discover, review, council) |
| `smaht:smaht` | Manually trigger context gathering |
| `smaht:help` | Show available smaht commands |

**Behind the scenes**: Every prompt goes through a three-tier routing system:
- **HOT** (<100ms): Continuation responses get session state only
- **FAST** (<1s): Short prompts with clear intent get 2-5 relevant adapters
- **SLOW** (2-5s): Complex or ambiguous prompts get all 6 adapters + history

**v3.4**: `knowledge_graph.py` maintains a SQLite-backed entity+relationship graph. BFS subgraph traversal connects related concepts across domains and sessions, giving smaht deeper structural awareness beyond keyword matching.

### mem — Cross-Session Memory

Decisions, patterns, and preferences persist across sessions. Memories auto-decay based on age and importance. v3.4 adds phase-aware recall for crew integration.

| Command | What It Does |
|---------|-------------|
| `mem:store` | Save a decision, pattern, or preference |
| `mem:recall` | Search memories by query |
| `mem:review` | Browse and manage memories |
| `mem:stats` | Show memory statistics |
| `mem:forget` | Archive or delete a memory |
| `mem:help` | Show available memory commands |

**Agents** (3): memory-archivist, memory-learner, memory-recaller

**v3.4**: `phase_scoring.py` provides a phase affinity matrix for crew-context recall. When crew is active, memory recall is weighted by phase relevance — architecture decisions surface during design, test patterns surface during test-strategy, deployment notes surface during build.

**Example**: Store "Chose Postgres for transactions" in session 1. In session 47, ask about database decisions and it surfaces automatically. During a crew design phase, it surfaces with higher priority than during build.

### search — Code Intelligence

Structural understanding of your codebase across 73 languages via tree-sitter. Not text search — symbol-level intelligence. v3.4 adds lifecycle-aware scoring for crew-integrated searches.

| Command | What It Does |
|---------|-------------|
| `search:code` | Find functions, classes, methods by name |
| `search:refs` | Find where a symbol is referenced |
| `search:blast-radius` | Analyze dependencies and dependents |
| `search:lineage` | Trace data from UI to database (or reverse) |
| `search:service-map` | Detect service architecture from infra files |
| `search:hotspots` | Find most-referenced symbols |
| `search:impact` | Analyze what changing a symbol would affect |
| `search:docs` | Search documents (PDF, markdown, Office) |
| `search:index` | Build/rebuild the code index |
| `search:scout` | Quick pattern reconnaissance |
| `search:sources` | Manage external content sources |
| `search:categories` | Show symbol categories and layers |
| `search:coverage` | Report lineage coverage |
| `search:stats` | Show index statistics |
| `search:validate` | Validate index consistency |
| `search:quality` | Run quality crew on the index |
| `search:impl` | Find code that implements a documented feature |
| `search:search` | Search across all code and documents |
| `search:help` | Show available search commands |

**v3.4**: `lifecycle_scoring.py` brings 5 scoring strategies for crew-context searches: phase_weighted (boost results relevant to current crew phase), recency_decay (favor recent changes), traceability_boost (promote traced artifacts), gate_status (weight by gate outcomes), and RRF (reciprocal rank fusion across all scorers).

**Requires**: tree-sitter (auto-detected). Falls back to grep-based search without it.

### jam — AI Brainstorming

Dynamic focus groups with 4-6 AI personas. Technical, user, business, and process perspectives debate your question. v3.4 adds a structured consensus protocol with dissent tracking.

| Command | What It Does |
|---------|-------------|
| `jam:brainstorm` | Full multi-perspective session |
| `jam:quick` | Lightweight exploration (fewer personas) |
| `jam:council` | Multi-model evaluation using external LLM CLIs |
| `jam:perspectives` | Get multiple perspectives on a decision |
| `jam:thinking` | View individual persona perspectives |
| `jam:transcript` | View full conversation transcript |
| `jam:persona` | View a specific persona's contributions |
| `jam:revisit` | Revisit a past brainstorm decision |
| `jam:help` | Show available jam commands |

**Agents** (2): council, facilitator

**v3.4**: `consensus.py` implements a structured 3-stage consensus protocol: (1) proposals — each persona submits independent positions, (2) cross-review — personas critique each other's proposals with confidence scoring, (3) synthesis — areas of agreement are merged, dissenting views are tracked explicitly with reasoning rather than silently dropped. The result includes a confidence score and a dissent register so you can see where genuine disagreement exists.

### kanban — Task Management

Persistent task board that survives sessions. Auto-syncs with Claude's native task tools via hooks.

| Command | What It Does |
|---------|-------------|
| `kanban:board-status` | View current board state |
| `kanban:new-task` | Create a task |
| `kanban:initiative` | Manage project initiatives |
| `kanban:comment` | Add comments to tasks |
| `kanban:name-session` | Name the current session |
| `kanban:start-api` | Check storage health |
| `kanban:help` | Show available kanban commands |

---

## Specialist Disciplines

Eight specialist domains, each with focused agents that crew routes to automatically based on detected signals.

### engineering — Software Engineering

Senior engineer, solution architect, debugger, technical writer, frontend/backend specialists. Handles implementation, architecture, code quality, and code transformations.

| Command | What It Does |
|---------|-------------|
| `engineering:review` | Multi-pass code review |
| `engineering:arch` | Architecture analysis and recommendations |
| `engineering:debug` | Systematic debugging with root cause analysis |
| `engineering:docs` | Generate or improve documentation |
| `engineering:plan` | Review changes against codebase and plan |
| `engineering:rename` | Rename a field/symbol across all usages |
| `engineering:add-field` | Add a field to an entity and propagate |
| `engineering:remove` | Remove a field and all its usages |
| `engineering:apply` | Apply patches from a saved JSON file |
| `engineering:patch-plan` | Show what a change would affect without patching |
| `engineering:new-generator` | Create a new language generator for wicked-patch |
| `engineering:help` | Show available engineering commands |

**Agents** (9): senior-engineer, solution-architect, system-designer, data-architect, debugger, technical-writer, frontend-engineer, backend-engineer, api-documentarian

### product — Product Management & Design

Requirements, UX, customer voice, business strategy, accessibility, visual design review. The largest specialist domain with 16 focused agents.

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
| `product:ux` | UX flow analysis |
| `product:screenshot` | Screenshot-based UI review |
| `product:a11y` | WCAG accessibility audit |
| `product:help` | Show available product commands |

**Agents** (16): product-manager, requirements-analyst, ux-designer, customer-advocate, user-researcher, competitive-analyst, value-analyst, market-analyst, feedback-analyst, business-strategist, alignment-lead, a11y-expert, ui-reviewer, mockup-generator, visual-reviewer, ux-analyst

### platform — DevSecOps

SRE, security engineer, compliance officer, incident responder, infrastructure engineer, release engineer, and auditor. Covers security, infrastructure, compliance, observability, and GitHub operations.

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
| `platform:plugin-debug` | View/set log verbosity |
| `platform:plugin-health` | Run health probes against installed plugins |
| `platform:plugin-traces` | Query hook execution traces |
| `platform:assert` | Run contract assertions against subprocess outputs |
| `platform:help` | Show available platform commands |

**Agents** (9): security-engineer, sre, compliance-officer, incident-responder, infrastructure-engineer, devops-engineer, release-engineer, auditor, privacy-expert

### qe — Quality Engineering

Test strategist, automation engineer, risk assessor, TDD coach, and a full acceptance test pipeline (write, execute, review).

| Command | What It Does |
|---------|-------------|
| `qe:qe` | Full quality engineering review |
| `qe:scenarios` | Generate test scenarios from requirements |
| `qe:acceptance` | Evidence-gated acceptance testing (write, execute, review) |
| `qe:automate` | Generate test code from scenarios |
| `qe:qe-plan` | Comprehensive test plan generation |
| `qe:qe-review` | Review test quality and coverage |
| `qe:run` | Execute an E2E test scenario |
| `qe:list` | List available scenarios with tool status |
| `qe:check` | Validate scenario file format |
| `qe:setup` | Install required CLI tools |
| `qe:report` | File issues from test failures |
| `qe:help` | Show available qe commands |

**Agents** (13): test-strategist, test-automation-engineer, risk-assessor, tdd-coach, acceptance-test-writer, acceptance-test-executor, acceptance-test-reviewer, testability-reviewer, continuous-quality-monitor, production-quality-engineer, requirements-quality-analyst, code-analyzer, scenario-executor

### data — Data Engineering

Data engineer, ML engineer, analytics architect, data analyst. Handles profiling, pipelines, ML, ontology, and interactive analysis via DuckDB.

| Command | What It Does |
|---------|-------------|
| `data:analyze` | Interactive data analysis on files |
| `data:numbers` | DuckDB SQL on CSV/Excel (10GB+, plain English) |
| `data:data` | Data profiling and schema validation |
| `data:analysis` | Exploratory data analysis |
| `data:pipeline` | Data pipeline design and review |
| `data:ml` | ML model review and training pipeline |
| `data:ontology` | Dataset ontology recommendations |
| `data:help` | Show available data commands |

**Agents** (4): data-analyst, data-engineer, ml-engineer, analytics-architect

### delivery — Delivery Management

Delivery manager, cost analyst, experiment designer, rollout coordinator, forecast specialist, and codebase narrator. The second-largest agent roster at 11 agents.

| Command | What It Does |
|---------|-------------|
| `delivery:report` | Multi-perspective stakeholder reports |
| `delivery:setup` | Configure delivery metrics |
| `delivery:rollout` | Progressive rollout plans with risk management |
| `delivery:experiment` | A/B test design with statistical rigor |
| `delivery:help` | Show available delivery commands |

**Agents** (11): delivery-manager, stakeholder-reporter, rollout-manager, experiment-designer, risk-monitor, progress-tracker, forecast-specialist, finops-analyst, cost-optimizer, onboarding-guide, codebase-narrator

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

**Agents** (5): architect, safety-reviewer, pattern-advisor, performance-analyst, framework-researcher

### persona — On-Demand Personas

Invoke any specialist persona directly without crew or jam. Define custom personas with personality, constraints, memories, and preferences.

| Command | What It Does |
|---------|-------------|
| `persona:as` | Invoke a named persona to perform a task |
| `persona:define` | Create or update a custom persona |
| `persona:list` | List all available personas |
| `persona:submit` | PR a persona to the built-in registry |

**Agents** (1): persona-agent

---

## Cross-Cutting Capabilities

Skills and modules that apply across all domains:

| Capability | What It Does |
|-----------|-------------|
| **deliberate** | Five-lens critical thinking before implementation. Challenges premises, finds root causes, spots adjacent opportunities. |
| **multi-model** | Multi-LLM council reviews using external CLI tools (Codex, Gemini, OpenCode). Invoke via `smaht:collaborate`. |
| **issue-reporting** | Automated GitHub issue detection with duplicate checking, codebase research, and SMART validation. |
| **imagery** | Visual asset lifecycle — review, create, and alter images using AI providers. |
| **cross-phase intelligence** | Traceability links, artifact state tracking, and impact analysis connect all crew phases into a coherent dependency graph. Changes in one phase automatically surface downstream effects. |
| **lifecycle scoring** | Phase-weighted, recency-aware, traceability-boosted ranking for search results. Crew-context searches return results ordered by relevance to the current workflow phase. |
| **knowledge graph** | SQLite-backed entity+relationship graph with BFS traversal. Connects concepts across domains and sessions for deeper structural awareness in context assembly. |
| **phase-aware memory** | Affinity matrix weights memory recall by crew phase. Architecture decisions surface during design, test patterns during test-strategy, deployment notes during build. |
