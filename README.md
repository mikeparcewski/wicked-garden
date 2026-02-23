# Wicked Garden

**The plugin ecosystem that turns Claude Code into a full engineering organization.**

95 commands. 79 specialist agents. 69 skills. 8 specialist disciplines. One unified workflow engine that figures out who to call and when — based on what your project actually needs.

```bash
claude plugins add something-wicked/wicked-startah
```

## What It Actually Does

Here's a real session. One command kicks off a complete delivery:

```bash
/wicked-crew:start "Migrate auth from sessions to JWT across 3 services"
```

Behind the scenes, a signal analysis engine scores your project across impact, reversibility, and novelty. It detects `security`, `architecture`, and `performance` signals. Based on those signals, it assembles a phase plan and routes to the right specialists — automatically:

```
  Smart Decisioning → complexity 7/7, 4 signals detected
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  CLARIFY ──► wicked-jam brainstorms 5 approaches            │
  │              wicked-mem recalls "we chose stateless in Q3"   │
  │              wicked-product validates requirements           │
  │                                                              │
  │  DESIGN ───► wicked-engineering:arch designs the migration   │
  │              wicked-search finds all session.get() calls     │
  │              wicked-agentic reviews agent boundaries         │
  │                                                              │
  │  TEST ─────► wicked-qe generates scenarios before code       │
  │              shift-left: tests exist before implementation   │
  │                                                              │
  │  BUILD ────► wicked-engineering implements with tracking     │
  │              wicked-platform checks OWASP, secrets, CVEs     │
  │              wicked-kanban tracks every task                 │
  │                                                              │
  │  REVIEW ───► multi-perspective: code + security + product    │
  │              wicked-mem stores learnings for next time       │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

A simple config change? Complexity 1, two phases, done in minutes. A cross-cutting migration? Full pipeline, every specialist engaged.

**The system adapts to the work. You don't configure it.**

## Signal-Driven Architecture

Most tools make you pick what to run. Wicked Garden listens to what you're building and figures it out.

Every project description gets analyzed for **signals** — security, performance, data, UX, architecture, compliance, and more. Those signals drive three decisions:

1. **Which phases to include** — a UI tweak skips the security phase; a payment integration includes it automatically
2. **Which specialists to engage** — security signals bring in wicked-platform; data signals bring in wicked-data
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

## The Plugin Ecosystem

### Workflow & Intelligence

| Plugin | What It Does |
|--------|-------------|
| **[wicked-crew](plugins/wicked-crew)** | Signal-driven workflow engine. Analyzes your project, selects phases, routes to specialists. The orchestrator. |
| **[wicked-smaht](plugins/wicked-smaht)** | Context assembly brain. Intercepts every prompt, detects intent, injects relevant context from all installed plugins. You never call it — it just makes everything smarter. |
| **[wicked-mem](plugins/wicked-mem)** | Cross-session memory with typed categories and auto-decay. Decisions, patterns, and preferences persist across sessions and surface when relevant. |
| **[wicked-search](plugins/wicked-search)** | Structural code intelligence across 73 languages. Symbol graphs, data lineage tracing, blast radius analysis, architecture detection from infra files. Not grep — understanding. |
| **[wicked-jam](plugins/wicked-jam)** | AI brainstorming with dynamic focus groups. 4-6 personas debate your question from technical, user, business, and process angles in 60 seconds. |
| **[wicked-kanban](plugins/wicked-kanban)** | Persistent task board that survives sessions. Auto-syncs with Claude's task tools via hooks — you use TaskCreate, kanban captures it. |

### Specialist Disciplines

Eight plugins, each bringing domain expertise that crew routes to automatically:

| Discipline | Plugin | Key Capabilities |
|-----------|--------|-----------------|
| **Engineering** | [wicked-engineering](plugins/wicked-engineering) | Senior engineer, solution architect, debugger, frontend/backend specialists. Multi-pass code review in one command. |
| **Product** | [wicked-product](plugins/wicked-product) | Product manager, UX designer, requirements analyst, customer advocate. Full voice-of-customer pipeline: listen, analyze, synthesize. |
| **Platform** | [wicked-platform](plugins/wicked-platform) | SRE, security engineer, compliance officer, incident responder. OWASP scanning, SOC2/HIPAA/GDPR checks, GitHub Actions generation. |
| **Quality** | [wicked-qe](plugins/wicked-qe) | Test strategist, automation engineer, risk assessor. Shift-left: generates test scenarios from requirements before code exists. |
| **Data** | [wicked-data](plugins/wicked-data) | Data engineer, ML engineer, analytics architect. DuckDB-powered SQL on 10GB+ CSV/Excel — plain English to results, zero setup. |
| **Delivery** | [wicked-delivery](plugins/wicked-delivery) | Delivery manager, cost analyst, rollout coordinator. Sprint health, A/B test design with statistical rigor, progressive rollout plans. |
| **Agentic** | [wicked-agentic](plugins/wicked-agentic) | Architecture reviewer, safety auditor, framework researcher. Detects 12+ agent frameworks, scores topologies, generates remediation roadmaps. |
| **Brainstorming** | [wicked-jam](plugins/wicked-jam) | Focus group facilitator with dynamic persona assembly. Brings diverse perspectives to ambiguous problems during clarify/design phases. |

### Infrastructure & Tools

| Plugin | What It Does |
|--------|-------------|
| **[wicked-startah](plugins/wicked-startah)** | Starter kit. One install gets Context7 docs, multi-AI conversations (Gemini, Codex), browser automation, runtime execution. |
| **[wicked-workbench](plugins/wicked-workbench)** | Web dashboard with data gateway. Browse plugin data via REST API, generate custom dashboards from plain English. |
| **[wicked-scenarios](plugins/wicked-scenarios)** | E2E testing via markdown scenarios. Human-readable specs that orchestrate curl, Playwright, k6, Trivy, Semgrep, pa11y — no framework lock-in. |
| **[wicked-patch](plugins/wicked-patch)** | Cross-language change propagation. Add a field to a Java entity, auto-patch the SQL migration, DAO, JSP, API, and UI. |

## Use Any Plugin Standalone

Every plugin works independently. The ecosystem is additive, not required.

```bash
/wicked-engineering:review                    # senior code review, right now
/wicked-search:lineage LoginForm --to-db      # trace a field to its database column
/wicked-jam:jam "Redis vs Postgres for sessions?"  # 5 personas, 60 seconds
/wicked-platform:security                     # OWASP scan your codebase
/wicked-data:numbers sales.csv "top 10 customers by revenue"  # SQL on CSV, instant
/wicked-mem:recall "auth decisions"           # what did we decide 30 sessions ago?
/wicked-qe:scenarios "user checkout flow"     # test scenarios before writing code
/wicked-agentic:review ./my-agent-project     # review your AI agent architecture
```

## Built to Be Extended

Wicked Garden is a marketplace, not a monolith. The plugin contract is simple:

```
plugins/wicked-yourplugin/
├── .claude-plugin/
│   ├── plugin.json          # name, version, description
│   └── specialist.json      # (optional) role-based routing contract
├── commands/                # slash commands (markdown + YAML frontmatter)
├── agents/                  # specialist subagents
├── skills/                  # progressive-disclosure expertise modules
├── hooks/                   # event-driven automation
└── scenarios/               # acceptance test scenarios
```

**Want Jira instead of kanban?** Build `wicked-jira` with the same task-tracking interface. Crew routes to it the same way.

**Need Datadog instead of generic observability?** Build `wicked-datadog` as a platform specialist. It enhances the build and review phases automatically via `specialist.json`.

**Have a custom compliance framework?** Build `wicked-compliance-myorg` with your controls. The signal engine picks it up when compliance signals are detected.

The specialist discovery protocol means crew finds your plugin at runtime. No hardcoded references. Install it, and the ecosystem adapts:

```jsonc
// specialist.json — declare what phases you enhance
{
  "role": "project-management",
  "enhances": ["build", "review"],
  "personas": [
    { "name": "Jira Engineer", "focus": "Sprint planning, backlog management" }
  ]
}
```

Three integration patterns, no imports:
1. **Script discovery + subprocess** — infrastructure code calls other plugins' scripts
2. **Hook events** — plugins subscribe to lifecycle events (`crew:phase:started:success`)
3. **Task tool dispatch** — commands invoke agents from other plugins via Claude's tool system

## How Signal Routing Works

```
  Your description
       │
       ▼
  ┌─────────────────────────┐
  │   Smart Decisioning     │
  │                         │
  │  Detect signals:        │     Signals map to specialists:
  │  security ──────────────┼──►  wicked-platform, wicked-qe
  │  architecture ──────────┼──►  wicked-engineering, wicked-agentic
  │  data ──────────────────┼──►  wicked-data
  │  ux ────────────────────┼──►  wicked-product
  │  performance ───────────┼──►  wicked-engineering, wicked-platform
  │  compliance ────────────┼──►  wicked-platform
  │  ambiguity ─────────────┼──►  wicked-jam
  │                         │
  │  Score complexity (0-7) │     Complexity drives phase selection:
  │  0-2: quick pass        │     clarify → build → review
  │  3-4: standard          │     + design, test-strategy
  │  5-7: full pipeline     │     + ideate, test, all specialists
  └─────────────────────────┘
```

At checkpoints (clarify, design, build), the system re-analyzes. If design reveals security concerns that weren't in the original description, the security specialist gets pulled in mid-flight.

## Principles

1. **Signal over ceremony** — The work tells the system what it needs. You don't configure pipelines.
2. **Perspectives over ego** — 8 specialist disciplines catch what one voice misses.
3. **Memory over amnesia** — Decisions persist. Context builds over time. Session 47 knows what session 1 decided.
4. **Graceful degradation** — Every plugin works alone. Missing a specialist? Fallback agents cover the gap.
5. **Prompts over code** — Plugin logic lives in markdown and config, not Python engines. Extensible by anyone who can write instructions.

## Installation

```bash
# Recommended: full starter kit with MCP servers and multi-AI support
claude plugins add something-wicked/wicked-startah

# Or build your own stack
claude plugins add something-wicked/wicked-crew          # workflow engine
claude plugins add something-wicked/wicked-engineering    # code review + architecture
claude plugins add something-wicked/wicked-mem            # persistent memory
claude plugins add something-wicked/wicked-search         # structural code intelligence
claude plugins add something-wicked/wicked-qe             # quality engineering
```

## Contributing

Build a plugin. The ecosystem is designed for it.

```bash
# Scaffold a new plugin
/wg-scaffold plugin wicked-yourplugin "What it does"

# Check marketplace readiness
/wg-check plugins/wicked-yourplugin --full

# Release it
/wg-release plugins/wicked-yourplugin --bump minor
```

See [.claude/CLAUDE.md](.claude/CLAUDE.md) for the full development guide.

## License

MIT
