# Domains

Wicked Garden is organized into 15 domains. Each domain brings its own commands, agents, skills, and scenarios. Every domain works independently — the ecosystem is additive, not required.

## Workflow & Intelligence

### crew — Workflow Engine

The orchestrator. Analyzes your project description, detects signals, scores complexity, selects phases, and routes to specialists automatically.

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

**When to use**: Any task that benefits from structured delivery — features, migrations, refactors, bug investigations. Crew auto-detects complexity: simple tasks finish in minutes, complex ones get the full pipeline.

### smaht — Context Assembly

The brain. Intercepts every prompt and injects relevant context from all domains. You rarely call it directly — it works automatically.

| Command | What It Does |
|---------|-------------|
| `smaht:onboard` | Guided codebase walkthrough |
| `smaht:context` | Build structured context for subagents |
| `smaht:debug` | Show what context was assembled |
| `smaht:learn` | Learn a library via ContextSeven docs |
| `smaht:libs` | List cached library cheatsheets |

**Behind the scenes**: Every prompt goes through a three-tier routing system:
- **HOT** (<100ms): Continuation responses get session state only
- **FAST** (<1s): Short prompts with clear intent get 2-5 relevant adapters
- **SLOW** (2-5s): Complex or ambiguous prompts get all 6 adapters + history

### mem — Cross-Session Memory

Decisions, patterns, and preferences persist across sessions. Memories auto-decay based on age and importance.

| Command | What It Does |
|---------|-------------|
| `mem:store` | Save a decision, pattern, or preference |
| `mem:recall` | Search memories by query |
| `mem:review` | Browse and manage memories |
| `mem:stats` | Show memory statistics |
| `mem:forget` | Archive or delete a memory |

**Example**: Store "Chose Postgres for transactions" in session 1. In session 47, ask about database decisions and it surfaces automatically.

### search — Code Intelligence

Structural understanding of your codebase across 73 languages via tree-sitter. Not text search — symbol-level intelligence.

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

**Requires**: tree-sitter (auto-detected). Falls back to grep-based search without it.

### jam — AI Brainstorming

Dynamic focus groups with 4-6 AI personas. Technical, user, business, and process perspectives debate your question.

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

---

## Specialist Disciplines

Nine specialist domains, each with focused agents that crew routes to automatically based on detected signals.

### engineering — Software Engineering

Senior engineer, solution architect, debugger, technical writer, frontend/backend specialists.

| Command | What It Does |
|---------|-------------|
| `engineering:review` | Multi-pass code review |
| `engineering:arch` | Architecture analysis and recommendations |
| `engineering:debug` | Systematic debugging with root cause analysis |
| `engineering:docs` | Generate or improve documentation |
| `engineering:plan` | Review changes against codebase and plan |

**Agents**: senior-engineer, solution-architect, system-designer, data-architect, debugger, technical-writer, frontend-engineer, backend-engineer, api-documentarian

### product — Product Management & Design

Requirements, UX, customer voice, business strategy, accessibility, visual design review.

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

**Agents**: product-manager, requirements-analyst, ux-designer, customer-advocate, user-researcher, competitive-analyst, value-analyst, market-analyst, feedback-analyst, business-strategist, alignment-lead, a11y-expert, ui-reviewer, mockup-generator, visual-reviewer, ux-analyst

### platform — DevSecOps

SRE, security engineer, compliance officer, incident responder, infrastructure engineer.

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

**Agents**: security-engineer, sre, compliance-officer, incident-responder, infrastructure-engineer, devops-engineer, release-engineer, auditor, privacy-expert

### qe — Quality Engineering

Test strategist, automation engineer, risk assessor, TDD coach, acceptance test pipeline.

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

**Agents**: test-strategist, test-automation-engineer, risk-assessor, tdd-coach, acceptance-test-writer, acceptance-test-executor, acceptance-test-reviewer, testability-reviewer, continuous-quality-monitor, production-quality-engineer, requirements-quality-analyst, code-analyzer, scenario-executor

### data — Data Engineering

Data engineer, ML engineer, analytics architect, data analyst.

| Command | What It Does |
|---------|-------------|
| `data:analyze` | Interactive data analysis on files |
| `data:numbers` | DuckDB SQL on CSV/Excel (10GB+, plain English) |
| `data:data` | Data profiling and schema validation |
| `data:analysis` | Exploratory data analysis |
| `data:pipeline` | Data pipeline design and review |
| `data:ml` | ML model review and training pipeline |
| `data:ontology` | Dataset ontology recommendations |

**Agents**: data-analyst, data-engineer, ml-engineer, analytics-architect

### delivery — Delivery Management

Delivery manager, cost analyst, experiment designer, rollout coordinator, forecast specialist.

| Command | What It Does |
|---------|-------------|
| `delivery:report` | Multi-perspective stakeholder reports |
| `delivery:setup` | Configure delivery metrics |
| `delivery:rollout` | Progressive rollout plans with risk management |
| `delivery:experiment` | A/B test design with statistical rigor |

**Agents**: delivery-manager, stakeholder-reporter, rollout-manager, experiment-designer, risk-monitor, progress-tracker, forecast-specialist, finops-analyst, cost-optimizer, onboarding-guide, codebase-narrator

### agentic — Agentic Architecture

Architecture reviewer, safety auditor, pattern advisor, framework researcher.

| Command | What It Does |
|---------|-------------|
| `agentic:review` | Full agentic codebase review |
| `agentic:design` | Interactive architecture design guide |
| `agentic:audit` | Trust and safety audit |
| `agentic:ask` | Ask about agentic patterns and frameworks |
| `agentic:frameworks` | Research and compare frameworks |

**Agents**: architect, safety-reviewer, pattern-advisor, performance-analyst, framework-researcher

### jam — Brainstorming (Specialist Role)

Dynamic persona assembly for clarify and design phases. Brings diverse perspectives to ambiguous problems.

---

## Infrastructure & Tools

### patch — Cross-Language Changes

Add, rename, or remove fields and propagate changes across the full stack.

| Command | What It Does |
|---------|-------------|
| `patch:add-field` | Add a field and propagate to all layers |
| `patch:rename` | Rename a symbol across all usages |
| `patch:remove` | Remove a field and all usages |
| `patch:plan` | Preview what would be affected |
| `patch:apply` | Apply patches from a saved file |
| `patch:new-generator` | Create a new language generator |

### observability — Plugin Health

Three-layer observability for the plugin itself, plus engineer toolchain discovery.

| Command | What It Does |
|---------|-------------|
| `observability:health` | Run health probes against all plugins |
| `observability:traces` | Query hook execution traces |
| `observability:logs` | View operational logs |
| `observability:assert` | Run contract assertions |
| `observability:toolchain` | Discover monitoring CLIs |
| `observability:debug` | Set log verbosity |

---

## Cross-Cutting Capabilities

Skills that apply across all domains:

| Skill | What It Does |
|-------|-------------|
| **deliberate** | Five-lens critical thinking before implementation. Challenges premises, finds root causes, spots adjacent opportunities. |
| **multi-model** | Multi-LLM council reviews using external CLI tools (Codex, Gemini, OpenCode). |
| **issue-reporting** | Automated GitHub issue detection with duplicate checking, codebase research, and SMART validation. |
| **imagery** | Visual asset lifecycle — review, create, and alter images using AI providers. |
