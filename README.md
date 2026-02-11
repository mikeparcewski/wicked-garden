# Wicked Garden

**Turn Claude Code into a full engineering team.** Memory that persists across sessions. Code review from senior engineers, architects, and security specialists. Brainstorming with AI focus groups. Guided workflows that clarify before they code. Search that understands your entire codebase. 18 plugins, each useful alone — transformative together.

```bash
# One command to get started
claude plugins add something-wicked/wicked-startah
```

```bash
/wicked-crew:start "Add user authentication with OAuth2"
#  Clarifies requirements → brainstorms approaches → finds existing patterns →
#  builds with tracking → reviews for quality + security → remembers what it learned

/wicked-jam:jam "Redis vs Postgres for session storage?"
#  5 AI personas debate your question from different angles

/wicked-engineering:review
#  Senior engineer + architect + security review in one pass

/wicked-mem:store --type decision "Chose JWT — stateless, no session DB needed"
#  Surfaces automatically 47 sessions from now when someone asks about auth
```

## Why This Exists

Claude Code is powerful but stateless. It forgets past decisions, skips requirements, and reviews its own code. Wicked Garden fixes that:

| Problem | Without | With Wicked Garden |
|---------|---------|-------------------|
| Amnesia | Every session starts from zero | Decisions, patterns, and preferences persist |
| Solo perspective | One voice, one blind spot | Engineering, product, security, data specialists |
| Cowboy coding | Jumps straight to implementation | Clarify → design → build → review |
| Lost context | "What did we decide about auth?" | Auto-surfaces relevant memories |
| No quality gates | Hope for the best | Shift-left QE with embedded gates |

## The Plugins

**Workflow & Memory**

| Plugin | What It Does | Why It's Different |
|--------|-------------|-------------------|
| [wicked-crew](plugins/wicked-crew) | Dynamic multi-phase workflows with risk-aware scoring | Scores changes on 3 dimensions (impact, reversibility, novelty) — a hooks.json change gets treated as behavior-defining code, not "just config". Adapts phases and specialists based on actual risk |
| [wicked-mem](plugins/wicked-mem) | Cross-session memory with typed categories and auto-decay | Only injects context when your question signals need — no context bloat, just relevant recall |
| [wicked-kanban](plugins/wicked-kanban) | Persistent task board with sprint grouping and git commit linking | Built-in tasks reset every session — kanban remembers everything via PostToolUse auto-sync |
| [wicked-jam](plugins/wicked-jam) | AI brainstorming with dynamic focus groups | 4-6 personas that build on each other's ideas — diverse trade-offs in 60 seconds, not a single voice |

**Specialists** — like having senior ICs on call

| Plugin | Roles | Why It's Different |
|--------|-------|-------------------|
| [wicked-engineering](plugins/wicked-engineering) | Senior engineers, architects, debuggers, frontend/backend, tech writers | 10 specialist agents with coordinated multi-pass review — architecture + code quality + security in one command |
| [wicked-product](plugins/wicked-product) | Product managers, UX designers, requirements analysts, customer advocates | Full customer voice pipeline: listen → analyze → synthesize, plus a11y audits and acceptance criteria |
| [wicked-platform](plugins/wicked-platform) | SREs, security engineers, compliance officers, incident responders | Auto-discovers your observability stack (Sentry, Jaeger, Prometheus) via MCP — live metrics, not just static analysis |
| [wicked-delivery](plugins/wicked-delivery) | Delivery managers, cost analysts, onboarding guides, rollout coordinators | Sprint health in seconds + personalized developer onboarding + A/B test design with statistical rigor |
| [wicked-data](plugins/wicked-data) | Data engineers, ML engineers, analytics architects | DuckDB-powered SQL on 10GB+ CSV/Excel with zero database setup — plain English to results |
| [wicked-qe](plugins/wicked-qe) | QE strategists, test automation, shift-left quality | Generates test scenarios from requirements before code exists + hooks that track file changes as you write |
| [wicked-agentic](plugins/wicked-agentic) | Agentic architecture review, pattern detection, trust & safety | Detects 12 frameworks, scores agent topologies, generates remediation roadmaps for AI systems |

**Search & Intelligence**

| Plugin | What It Does | Why It's Different |
|--------|-------------|-------------------|
| [wicked-search](plugins/wicked-search) | Structural codebase understanding — 73 languages, PDF/Office docs, symbol graph with typed relationships | Trace a form field to its DB column, blast-radius analysis, architecture diagrams from Docker/K8s + code, lineage coverage audits, self-improving 95%+ accuracy |
| [wicked-smaht](plugins/wicked-smaht) | Intercepts every prompt, detects intent, injects context from all installed plugins automatically | 6 adapters (memory, search, tasks, brainstorms, project state, docs), fast/deep path routing, session history condensation, turn-budget warnings — the brain that ties the ecosystem together |

**Infrastructure & Tools**

| Plugin | What It Does | Why It's Different |
|--------|-------------|-------------------|
| [wicked-cache](plugins/wicked-cache) | Shared caching layer with namespace isolation | File-aware invalidation — auto-expires when source files change, makes other plugins instant |
| [wicked-startah](plugins/wicked-startah) | Starter kit with MCP servers and multi-AI conversations | One install gets Context7 docs, Atlassian integration, Gemini/Codex conversations, browser automation |
| [wicked-workbench](plugins/wicked-workbench) | Web dashboard for browsing and executing plugin commands | ACP-powered React UI — browse all installed plugins and generate custom dashboards from plain English |
| [wicked-scenarios](plugins/wicked-scenarios) | E2E testing via markdown scenarios | Human-readable test specs that orchestrate 9 CLIs (curl, playwright, k6, trivy, semgrep, pa11y) — no framework lock-in |
| [wicked-patch](plugins/wicked-patch) | Code generation and change propagation | Add a field to a Java entity → auto-patches SQL migration + DAO + JSP + API + UI across 5 languages |

## How They Work Together

```
  /wicked-crew:start "Migrate auth from sessions to JWT across 3 services"
       │
       │  Smart Decisioning scores: impact=3, reversibility=3, novelty=1
       │  Complexity: 7 → full pipeline, all matched specialists
       │
       ├── CLARIFY ──► wicked-jam brainstorms approaches
       │                    └── wicked-mem recalls past auth decisions
       │
       ├── DESIGN ──► wicked-engineering:arch reviews architecture
       │                    └── wicked-search finds existing auth patterns
       │
       ├── BUILD ───► Implementation with wicked-kanban tracking
       │                    └── wicked-platform checks security
       │
       └── REVIEW ──► wicked-engineering:review (multi-pass)
                           └── wicked-mem stores learnings
```

Or use any plugin standalone — every one works independently:

```bash
/wicked-search:search "error handling"     # just search
/wicked-engineering:review                  # just review
/wicked-product:elicit                      # just gather requirements
/wicked-platform:security                   # just scan for vulnerabilities
```

## Principles

1. **Lightweight over heavyweight** — No ceremonies. Use what helps, skip what doesn't.
2. **Guardrails over gates** — Prevents force pushes and secret commits without blocking flow.
3. **Memory over amnesia** — Learns from past sessions. Builds context over time.
4. **Perspectives over ego** — Multiple specialists catch what one voice misses.
5. **Graceful degradation** — Every plugin works alone. The ecosystem is optional.

## Installation

```bash
# Recommended: starter kit with MCP servers
claude plugins add something-wicked/wicked-startah

# Or pick what you need
claude plugins add something-wicked/wicked-crew
claude plugins add something-wicked/wicked-engineering
claude plugins add something-wicked/wicked-mem
```

## Contributing

1. Fork the repo
2. Create your plugin in `plugins/wicked-yourplugin/`
3. Run `/wg-check plugins/wicked-yourplugin --full` for marketplace readiness
4. Submit a PR

See [.claude/CLAUDE.md](.claude/CLAUDE.md) for development tooling.

## License

MIT
