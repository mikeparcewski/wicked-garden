# Wicked Garden

**AI-Native SDLC — the complete software development lifecycle as a Claude Code plugin.**

142 commands. 86 specialist agents. 75 skills. 8 specialist disciplines. 51 specialist personas. One unified workflow engine that figures out who to call and when — based on what your project actually needs. No sidecar. No server. Just local files and smart routing.

```bash
claude plugins add mikeparcewski/wicked-garden
```

## What It Actually Does

Here's a real session. One command kicks off a complete delivery:

```bash
/wicked-garden:crew:start "Migrate auth from sessions to JWT across 3 services"
```

Behind the scenes, a signal analysis engine scores your project across impact, reversibility, and novelty. It detects `security`, `architecture`, and `performance` signals. Based on those signals, it assembles a phase plan and routes to the right specialists — automatically:

```
  Smart Decisioning → complexity 7/7, 4 signals detected
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  CLARIFY ──► jam brainstorms 5 approaches                   │
  │              mem recalls "we chose stateless in Q3"          │
  │              product validates requirements                  │
  │                                                              │
  │  DESIGN ───► engineering:arch designs the migration          │
  │              search finds all session.get() calls            │
  │              agentic reviews agent boundaries                │
  │                                                              │
  │  TEST ─────► qe generates scenarios before code              │
  │              shift-left: tests exist before implementation   │
  │                                                              │
  │  BUILD ────► engineering implements with tracking            │
  │              platform checks OWASP, secrets, CVEs            │
  │              kanban tracks every task                        │
  │                                                              │
  │  REVIEW ───► multi-perspective: code + security + product    │
  │              mem stores learnings for next time              │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

A simple config change? Complexity 1, two phases, done in minutes. A cross-cutting migration? Full pipeline, every specialist engaged.

**The system adapts to the work. You don't configure it.**

## Signal-Driven Architecture

Most tools make you pick what to run. Wicked Garden listens to what you're building and figures it out.

Every project description gets analyzed for **signals** — security, performance, data, UX, architecture, compliance, and more. Those signals drive three decisions:

1. **Which phases to include** — a UI tweak skips the security phase; a payment integration includes it automatically
2. **Which specialists to engage** — security signals bring in platform specialists; data signals bring in data engineers
3. **How rigorous to be** — complexity scoring determines whether you get a quick pass or a full gate with evidence

```
"Add a tooltip to the settings page"
  → complexity 1 → auto-finish: quick plan applied, no prompts needed

"Add OAuth2 with PKCE to mobile and web clients"
  → complexity 6 → all phases, 5 specialists → thorough delivery

"Migrate 2M rows from Mongo to Postgres with zero downtime"
  → complexity 7 → full pipeline + data specialist + platform SRE
```

Low-complexity work (score 0-2) auto-applies the quick phase plan and chains directly into just-finish mode — no user prompt required. Pass `--no-auto-finish` to override.

Signals are re-evaluated at checkpoints. If the design phase reveals unexpected complexity, new phases get injected mid-flight. The plan adapts.

## Domains

Everything is organized by domain — each domain brings its own commands, agents, skills, and scenarios:

### Workflow & Intelligence

| Domain | What It Does | Key Commands |
|--------|-------------|--------------|
| **crew** | Signal-driven workflow engine. Analyzes your project, selects phases, routes to specialists. The orchestrator. | `crew:start`, `crew:execute`, `crew:just-finish` |
| **smaht** | Context assembly brain. Intercepts every prompt, detects intent, injects relevant context from all domains. You never call it — it just makes everything smarter. | `smaht:debug`, `smaht:onboard` |
| **mem** | Cross-session memory with typed categories and auto-decay. Decisions, patterns, and preferences persist across sessions and surface when relevant. | `mem:store`, `mem:recall`, `mem:review` |
| **search** | Structural code intelligence across 73 languages. Symbol graphs, data lineage tracing, blast radius analysis, architecture detection from infra files. Not grep — understanding. | `search:code`, `search:lineage`, `search:blast-radius` |
| **jam** | AI brainstorming with dynamic focus groups. 4-6 personas debate your question from technical, user, business, and process angles in 60 seconds. | `jam:brainstorm`, `jam:quick`, `jam:council` |
| **kanban** | Persistent task board that survives sessions. Auto-syncs with Claude's task tools via hooks. Scoped boards per domain (crew, jam, issues). | `kanban:board-status`, `kanban:new-task`, `kanban:initiative` |

### Specialist Disciplines

Eight specialist roles plus design, each bringing expertise that crew routes to automatically:

| Discipline | Domain | Key Capabilities |
|-----------|--------|-----------------|
| **Engineering** | engineering | Senior engineer, solution architect, debugger, frontend/backend specialists. Multi-pass code review in one command. |
| **Product** | product | Product manager, UX designer, requirements analyst, customer advocate. Full voice-of-customer pipeline: listen, analyze, synthesize. |
| **Platform** | platform | SRE, security engineer, compliance officer, incident responder. OWASP scanning, SOC2/HIPAA/GDPR checks, GitHub Actions generation. |
| **Quality** | qe | Test strategist, automation engineer, risk assessor, TDD coach, acceptance test pipeline (write → execute → review). Shift-left across the full lifecycle. |
| **Data** | data | Data engineer, ML engineer, analytics architect. DuckDB-powered SQL on 10GB+ CSV/Excel — plain English to results, zero setup. |
| **Delivery** | delivery | Delivery manager, cost analyst, rollout coordinator. Sprint health, A/B test design with statistical rigor, progressive rollout plans. |
| **Agentic** | agentic | Architecture reviewer, safety auditor, framework researcher. Detects 12+ agent frameworks, scores topologies, generates remediation roadmaps. |
| **Design** | design | Visual reviewer, UX analyst, mockup generator. Screenshot-based UI review, wireframe generation, accessibility audits, design system compliance. |
| **Brainstorming** | jam | Focus group facilitator with dynamic persona assembly. Brings diverse perspectives to ambiguous problems during clarify/design phases. |

### Infrastructure & Tools

| Domain | What It Does | Key Commands |
|--------|-------------|--------------|
| **scenarios** | E2E testing via markdown scenarios. Human-readable specs that orchestrate curl, Playwright, k6, Trivy, Semgrep, pa11y — no framework lock-in. | `scenarios:run`, `scenarios:list` |
| **patch** | Cross-language change propagation. Add a field to a Java entity, auto-patch the SQL migration, DAO, JSP, API, and UI. | `patch:add-field`, `patch:apply`, `patch:rename` |
| **observability** | Three-layer plugin observability (hook tracing, contract assertions, health probes) plus engineer toolchain discovery for APM, logging, metrics, and cloud monitoring CLIs. | `observability:health`, `observability:traces`, `observability:toolchain` |

### Cross-Cutting Capabilities

Skills that apply across all domains — no specialist affiliation, just sharper thinking:

| Skill | What It Does |
|-------|-------------|
| **deliberate** | Five-lens critical thinking framework. Challenges the premise, finds the root cause, spots adjacent opportunities, and validates whether the stated ask is the right ask — before any implementation begins. Auto-integrated into crew clarify and design phases. |
| **multi-model** | Multi-LLM council reviews using external CLI tools (Codex, Gemini, OpenCode). Runs independent analysis in parallel and synthesizes perspectives. Falls back to Claude-only specialist subagents when external CLIs are unavailable. |
| **issue-reporting** | Automated GitHub issue detection and filing. Hooks monitor tool failures and task mismatches throughout your session. Manual filing runs duplicate detection, codebase research, memory recall, SMART validation, and an advisory quality gate before opening any issue. |

## Use Any Domain Standalone

Every domain works independently. The ecosystem is additive, not required.

```bash
/wicked-garden:engineering:review                      # senior code review, right now
/wicked-garden:search:lineage LoginForm --to-db        # trace a field to its database column
/wicked-garden:jam:quick "Redis vs Postgres for sessions?" # 5 personas, 60 seconds
/wicked-garden:platform:security                       # OWASP scan your codebase
/wicked-garden:data:analyze sales.csv "top 10 by revenue" # SQL on CSV, instant
/wicked-garden:mem:recall "auth decisions"             # what did we decide 30 sessions ago?
/wicked-garden:qe:scenarios "user checkout flow"       # test scenarios before writing code
/wicked-garden:agentic:review ./my-agent-project       # review your AI agent architecture
```

## Storage & Integration Discovery

Every domain owns its own data. No sidecar process, no external server required.

**How it works**: Each domain writes to local JSON files scoped to your current project. Storage is isolated per working directory — two projects with the same name don't share state. When a domain needs external tools (e.g., kanban looking for Jira, Linear, or Rally), it uses **integration-discovery** to find them automatically.

```
~/.something-wicked/wicked-garden/projects/{project-slug}/{domain}/
```

Global configuration (shared across all projects) lives at `~/.something-wicked/wicked-garden/config.json`.

**Resolution order** when multiple tools are found:
1. Check local settings (`config.json` preferences)
2. Check memory (stored decisions from past sessions)
3. Ask the user once, remember the choice

**If no external tools are found** — or no auth is configured — data stays local and project-scoped. This is the default experience and it just works.

```
  Domain Command
       │
       ▼
  ┌─────────────────────────┐
  │  Integration Discovery   │     Resolution:
  │                          │     1. config.json → "use linear"
  │  Find matching tools ────┼──►  2. memory → "chose jira last time"
  │  Resolve which to use    │     3. ask user → store choice
  │  Fall back to local JSON │     4. no tools? → local JSON ✓
  └─────────────────────────┘
```

## How Signal Routing Works

```
  Your description
       │
       ▼
  ┌─────────────────────────┐
  │   Smart Decisioning     │
  │                         │
  │  Detect signals:        │     Signals map to specialists:
  │  security ──────────────┼──►  platform, qe
  │  architecture ──────────┼──►  engineering, agentic
  │  data ──────────────────┼──►  data
  │  ux ────────────────────┼──►  product
  │  performance ───────────┼──►  engineering, platform
  │  compliance ────────────┼──►  platform
  │  ambiguity ─────────────┼──►  jam
  │                         │
  │  Score complexity (0-7) │     Complexity drives phase selection:
  │  0-2: quick pass        │     clarify → build → review
  │  3-4: standard          │     + design, test-strategy
  │  5-7: full pipeline     │     + ideate, test, all specialists
  └─────────────────────────┘
```

At checkpoints (clarify, design, build), the system re-analyzes and enforces phase completeness. If complexity >= 2, test-strategy and test phases are injected automatically — you can't skip testing without explicitly documenting why. If design reveals security concerns that weren't in the original description, the security specialist gets pulled in mid-flight.

## Principles

1. **Signal over ceremony** — The work tells the system what it needs. You don't configure pipelines.
2. **Perspectives over ego** — 9 specialist domains catch what one voice misses.
3. **Memory over amnesia** — Decisions persist. Context builds over time. Session 47 knows what session 1 decided.
4. **Graceful degradation** — No external tools? Local JSON. Missing a specialist? Fallback agents cover the gap.
5. **Prompts over code** — Logic lives in markdown and config, not Python engines. Extensible by anyone who can write instructions.

## Quick Start

```bash
# Install the plugin
claude plugins add mikeparcewski/wicked-garden

# Start using any domain immediately — no setup required:

/wicked-garden:crew:start "Add user authentication"   # full workflow
/wicked-garden:engineering:review                       # code review
/wicked-garden:search:code "handleAuth"                 # find symbols
/wicked-garden:jam:quick "Redis vs Postgres?"           # brainstorm
/wicked-garden:design:mockup "settings page"            # wireframe generation
/wicked-garden:qe:acceptance                            # evidence-gated testing
```

## Commands

All commands use colon namespacing: `/wicked-garden:{domain}:{command}`

| Domain | Command | What It Does |
|--------|---------|-------------|
| crew | `crew:start` | Start a signal-driven workflow for any task |
| crew | `crew:just-finish` | Execute remaining work with maximum autonomy |
| engineering | `engineering:review` | Multi-pass code review from senior perspective |
| engineering | `engineering:arch` | Architecture analysis and recommendations |
| search | `search:code` | Structural code search across 73 languages |
| search | `search:lineage` | Trace data from UI to database (or reverse) |
| search | `search:blast-radius` | Analyze dependencies of a symbol |
| platform | `platform:security` | OWASP vulnerability scan |
| platform | `platform:compliance` | SOC2/HIPAA/GDPR/PCI checks |
| qe | `qe:scenarios` | Generate test scenarios from requirements |
| qe | `qe:acceptance` | Evidence-gated acceptance testing |
| data | `data:analyze` | SQL on CSV/Excel via DuckDB |
| jam | `jam:brainstorm` | Multi-persona brainstorming session |
| mem | `mem:store` / `mem:recall` | Cross-session memory persistence |
| kanban | `kanban:board-status` | View persistent task board |
| delivery | `delivery:report` | Multi-perspective delivery reports |
| (root) | `reset` | Selectively clear local state for a fresh start |

See `/wicked-garden:help` for the full command list.

## Integration

| Integration | With It | Without It |
|------------|---------|------------|
| **External MCP tools** | kanban syncs to Jira/Linear, mem stores to Notion, etc. | Local JSON files — same API, same behavior |
| **GitHub CLI (`gh`)** | Auto-file issues, PR creation, release management | Manual issue/PR creation |
| **Tree-sitter** | 73-language structural code search, symbol graphs, lineage | Grep-based text search fallback |
| **DuckDB** | SQL analytics on 10GB+ CSV/Excel files | Basic file reading only |
| **External LLM CLIs** | Multi-model council reviews (Codex, Gemini, OpenCode) | Claude-only review with specialist subagents |

The plugin works fully standalone. Each integration adds capability but nothing breaks without it. Integration discovery finds tools automatically — you don't configure anything.

## Plugin Structure

```
wicked-garden/
├── .claude-plugin/
│   ├── plugin.json          # name, version, description
│   ├── specialist.json      # 8 specialist roles, 51 personas
│   ├── marketplace.json     # marketplace registration
│   └── phases.json          # 7-phase catalog with gates and checkpoints
├── commands/
│   ├── {domain}/            # domain-scoped slash commands
│   └── *.md                 # root-level commands (setup, reset, help, report-issue)
├── agents/{domain}/         # 86 specialist subagents across 9 domains
├── skills/
│   ├── {domain}/SKILL.md    # single-skill domains (flat)
│   └── {domain}/{skill}/    # multi-skill domains (nested)
├── hooks/
│   ├── hooks.json           # 8 lifecycle hook bindings
│   └── scripts/             # 7 Python hook scripts (stdlib-only)
├── scripts/{domain}/        # domain APIs and utilities
└── scenarios/{domain}/      # acceptance test scenarios
```

## License

MIT
