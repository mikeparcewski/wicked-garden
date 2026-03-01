# Wicked Garden

**AI-Native SDLC — the complete software development lifecycle as a Claude Code plugin.**

116 commands. 78 specialist agents. 70 skills. 8 specialist disciplines. One unified workflow engine that figures out who to call and when — based on what your project actually needs.

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
  → complexity 1 → clarify + build + review → 3 minutes

"Add OAuth2 with PKCE to mobile and web clients"
  → complexity 6 → all phases, 5 specialists → thorough delivery

"Migrate 2M rows from Mongo to Postgres with zero downtime"
  → complexity 7 → full pipeline + data specialist + platform SRE
```

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
| **jam** | AI brainstorming with dynamic focus groups. 4-6 personas debate your question from technical, user, business, and process angles in 60 seconds. | `jam:jam`, `jam:brainstorm`, `jam:council` |
| **kanban** | Persistent task board that survives sessions. Auto-syncs with Claude's task tools via hooks — you use TaskCreate, kanban captures it. | `kanban:board-status`, `kanban:new-task` |

### Specialist Disciplines

Eight domains, each bringing specialist expertise that crew routes to automatically:

| Discipline | Domain | Key Capabilities |
|-----------|--------|-----------------|
| **Engineering** | engineering | Senior engineer, solution architect, debugger, frontend/backend specialists. Multi-pass code review in one command. |
| **Product** | product | Product manager, UX designer, requirements analyst, customer advocate. Full voice-of-customer pipeline: listen, analyze, synthesize. |
| **Platform** | platform | SRE, security engineer, compliance officer, incident responder. OWASP scanning, SOC2/HIPAA/GDPR checks, GitHub Actions generation. |
| **Quality** | qe | Test strategist, automation engineer, risk assessor. Shift-left: generates test scenarios from requirements before code exists. |
| **Data** | data | Data engineer, ML engineer, analytics architect. DuckDB-powered SQL on 10GB+ CSV/Excel — plain English to results, zero setup. |
| **Delivery** | delivery | Delivery manager, cost analyst, rollout coordinator. Sprint health, A/B test design with statistical rigor, progressive rollout plans. |
| **Agentic** | agentic | Architecture reviewer, safety auditor, framework researcher. Detects 12+ agent frameworks, scores topologies, generates remediation roadmaps. |
| **Brainstorming** | jam | Focus group facilitator with dynamic persona assembly. Brings diverse perspectives to ambiguous problems during clarify/design phases. |

### Infrastructure & Tools

| Domain | What It Does | Key Commands |
|--------|-------------|--------------|
| **scenarios** | E2E testing via markdown scenarios. Human-readable specs that orchestrate curl, Playwright, k6, Trivy, Semgrep, pa11y — no framework lock-in. | `scenarios:run`, `scenarios:list` |
| **patch** | Cross-language change propagation. Add a field to a Java entity, auto-patch the SQL migration, DAO, JSP, API, and UI. | `patch:add-field`, `patch:apply`, `patch:rename` |
| **observability** | Three-layer observability: runtime hook tracing, contract assertions, and structural health probes. | `observability:health`, `observability:traces` |

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

## Control Plane

Wicked Garden uses the **wicked-control-plane** as its persistence backend — a Fastify + SQLite service that provides team-shared storage for memories, kanban boards, crew projects, and more.

```bash
# First run triggers interactive setup
# Choose: local (localhost:18889), remote (your server), or offline (local JSON files)
```

**Three modes**:
- **Local**: Run the control plane on your machine. All data in SQLite, instant.
- **Remote**: Point to a team-hosted control plane. Shared state across developers.
- **Offline**: Pure local JSON files. No server needed. Queued writes replay when you reconnect.

The plugin auto-detects connectivity and falls back gracefully. Offline writes are queued in `_queue.jsonl` and replayed on the next healthy connection.

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
2. **Perspectives over ego** — 8 specialist disciplines catch what one voice misses.
3. **Memory over amnesia** — Decisions persist. Context builds over time. Session 47 knows what session 1 decided.
4. **Graceful degradation** — Missing the control plane? Local fallback. Missing a specialist? Fallback agents cover the gap.
5. **Prompts over code** — Logic lives in markdown and config, not Python engines. Extensible by anyone who can write instructions.

## Quick Start

```bash
# Install the plugin
claude plugins add mikeparcewski/wicked-garden

# First session runs interactive setup for control plane connection
# Then start using any domain immediately:

/wicked-garden:crew:start "Add user authentication"   # full workflow
/wicked-garden:engineering:review                       # code review
/wicked-garden:search:code "handleAuth"                 # find symbols
/wicked-garden:jam:quick "Redis vs Postgres?"           # brainstorm
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

See `/wicked-garden:help` for the full command list.

## Integration

| Integration | With It | Without It |
|------------|---------|------------|
| **Control Plane** | Team-shared persistence, cross-session memories, kanban boards | Local JSON files, single-developer mode |
| **wicked-control-plane** | Real-time data sync, offline write queue with replay | Standalone with local storage fallback |
| **GitHub CLI (`gh`)** | Auto-file issues, PR creation, release management | Manual issue/PR creation |
| **Tree-sitter** | 73-language structural code search, symbol graphs, lineage | Grep-based text search fallback |
| **DuckDB** | SQL analytics on 10GB+ CSV/Excel files | Basic file reading only |

The plugin works fully standalone. Each integration adds capability but nothing breaks without it.

## Plugin Structure

```
wicked-garden/
├── .claude-plugin/
│   ├── plugin.json          # name, version, description
│   ├── specialist.json      # 8 specialist roles, 47 personas
│   └── marketplace.json     # marketplace registration
├── phases.json              # 7-phase catalog with gates and checkpoints
├── commands/
│   ├── {domain}/            # domain-scoped slash commands
│   └── *.md                 # root-level commands (setup, help, report-issue)
├── agents/{domain}/         # 78 specialist subagents by domain
├── skills/
│   ├── {domain}/            # domain-scoped skills
│   └── {name}/              # root-level skills (CLI tools, patterns)
├── hooks/
│   ├── hooks.json           # 7 lifecycle hooks
│   └── scripts/             # 6 Python hook scripts (stdlib-only)
├── scripts/{domain}/        # domain APIs and utilities
└── scenarios/{domain}/      # acceptance test scenarios
```

## License

MIT
