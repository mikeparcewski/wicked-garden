# Wicked Garden

**AI-Native SDLC — the complete software development lifecycle as a Claude Code plugin.**

142 commands. 80 specialist agents. 79 skills. 8 specialist disciplines. One unified workflow engine that figures out who to call and when — based on what your project actually needs. No sidecar. No server. Just local files and smart routing.

**v2.6** — On-demand personas with rich characteristics (personality, constraints, memories, preferences). Crew quality gates that actually reject work. Script-to-skill conversion eliminates Python dependency for reasoning. [Changelog](CHANGELOG.md) | [Migration from v1.x](#migration-from-v1x)

```bash
claude plugins add mikeparcewski/wicked-garden
```

## What It Actually Does

One command kicks off a complete delivery:

```bash
/wicked-garden:crew:start "Migrate auth from sessions to JWT across 3 services"
```

A signal analysis engine scores your project across impact, reversibility, and novelty. It detects `security`, `architecture`, and `performance` signals. Based on those signals, it assembles a phase plan and routes to the right specialists — automatically:

```
  Smart Decisioning -> complexity 7/7, 4 signals detected
  +--------------------------------------------------------------+
  |                                                              |
  |  CLARIFY --> jam brainstorms 5 approaches                   |
  |              mem recalls "we chose stateless in Q3"          |
  |              product validates requirements                  |
  |                                                              |
  |  DESIGN ---> engineering:arch designs the migration          |
  |              search finds all session.get() calls            |
  |              agentic reviews agent boundaries                |
  |                                                              |
  |  TEST -----> qe generates scenarios before code              |
  |              shift-left: tests exist before implementation   |
  |                                                              |
  |  BUILD ----> engineering implements with tracking            |
  |              platform checks OWASP, secrets, CVEs            |
  |              kanban tracks every task                        |
  |                                                              |
  |  REVIEW ---> multi-perspective: code + security + product    |
  |              mem stores learnings for next time              |
  |                                                              |
  +--------------------------------------------------------------+
```

A simple config change? Complexity 1, two phases, done in minutes. A cross-cutting migration? Full pipeline, every specialist engaged.

**The system adapts to the work. You don't configure it.**

## Quick Start

```bash
# Install
claude plugins add mikeparcewski/wicked-garden

# Use any domain immediately — no setup required:
/wicked-garden:crew:start "Add user authentication"     # full workflow
/wicked-garden:engineering:review                         # code review
/wicked-garden:search:code "handleAuth"                   # find symbols
/wicked-garden:jam:quick "Redis vs Postgres?"             # brainstorm
/wicked-garden:platform:security                          # OWASP scan
/wicked-garden:data:analyze sales.csv "top 10 by revenue" # SQL on CSV
/wicked-garden:qe:scenarios "checkout flow"               # test scenarios
/wicked-garden:mem:recall "auth decisions"                # cross-session memory
```

## Domains

14 domains, each with its own commands, agents, skills, and scenarios. Every domain works independently.

### Start Here

Three paths, pick the one that fits:
- **Build software**: `/wicked-garden:crew:start "your project description"` — orchestrates the full lifecycle
- **Brainstorm ideas**: `/wicked-garden:jam:brainstorm "your question"` — multi-perspective debate
- **Understand code**: `/wicked-garden:search:code "symbolName"` — structural search across 73 languages

### Workflow & Intelligence

| Domain | What It Does | Key Commands |
|--------|-------------|--------------|
| **crew** | Signal-driven workflow engine. Analyzes, selects phases, routes to specialists. | `crew:start`, `crew:execute`, `crew:just-finish` |
| **smaht** | Context assembly brain. Enriches every prompt with relevant context automatically. | `smaht:onboard`, `smaht:debug` |
| **mem** | Cross-session memory. Decisions and patterns persist and surface when relevant. | `mem:store`, `mem:recall`, `mem:review` |
| **search** | Structural code intelligence across 73 languages. Symbols, lineage, blast radius. | `search:code`, `search:lineage`, `search:blast-radius` |
| **jam** | AI brainstorming. 4-6 personas debate from technical, user, and business angles. | `jam:brainstorm`, `jam:quick`, `jam:council` |
| **kanban** | Persistent task board. Auto-syncs with Claude's task tools via hooks. | `kanban:board-status`, `kanban:new-task` |

### Specialist Disciplines

| Discipline | What It Brings |
|-----------|---------------|
| **Engineering** | Code review, architecture, debugging, frontend/backend specialists |
| **Product** | Requirements, UX, customer voice, business strategy, accessibility, design review |
| **Platform** | Security (OWASP), compliance (SOC2/HIPAA/GDPR), SRE, incident response |
| **Quality** | Test strategy, automation, TDD, acceptance testing, E2E scenarios with evidence gates |
| **Data** | DuckDB SQL on CSV/Excel (10GB+), pipelines, ML, analytics architecture |
| **Delivery** | Sprint health, A/B tests, progressive rollouts, cost optimization |
| **Agentic** | Agent architecture review, safety audits, framework analysis |
| **Brainstorming** | Dynamic focus groups for ambiguous problems |
| **Persona** | On-demand personas — invoke any specialist perspective with rich characteristics (personality, constraints, memories, preferences) |

## Integration

| Integration | With It | Without It |
|------------|---------|------------|
| **External MCP tools** | kanban syncs to Jira/Linear, mem to Notion | Local JSON files — same API |
| **GitHub CLI (`gh`)** | Auto-file issues, PR creation, releases | Manual issue/PR workflow |
| **Tree-sitter** | 73-language structural code search, lineage | Grep-based text search |
| **DuckDB** | SQL on 10GB+ CSV/Excel files | Basic file reading |
| **External LLM CLIs** | Multi-model council reviews (Codex, Gemini) | Claude-only specialist agents |

The plugin works fully standalone. Each integration adds capability but nothing breaks without it.

## Principles

1. **Signal over ceremony** — The work tells the system what it needs. You don't configure pipelines.
2. **Perspectives over ego** — 8 specialist domains catch what one voice misses.
3. **Memory over amnesia** — Decisions persist. Session 47 knows what session 1 decided.
4. **Graceful degradation** — No external tools? Local JSON. Missing a specialist? Fallback agents.
5. **Prompts over code** — Logic lives in markdown and config. Extensible by anyone.

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, first session, common workflows |
| [Domains](docs/domains.md) | All 14 domains with full command tables |
| [Crew Workflow](docs/crew-workflow.md) | Signal routing, phases, specialists, checkpoints |
| [Architecture](docs/architecture.md) | Storage, integration discovery, context assembly |
| [Advanced Usage](docs/advanced.md) | Multi-model, customization, development commands |

## Commands

All 142 commands use colon namespacing: `/wicked-garden:{domain}:{command}`

| Domain | Command | What It Does |
|--------|---------|-------------|
| crew | `crew:start` | Start a signal-driven workflow |
| crew | `crew:just-finish` | Maximum autonomy execution |
| engineering | `engineering:review` | Multi-pass code review |
| search | `search:code` | Structural code search |
| search | `search:lineage` | Trace data from UI to database |
| platform | `platform:security` | OWASP vulnerability scan |
| platform | `platform:compliance` | SOC2/HIPAA/GDPR/PCI checks |
| qe | `qe:scenarios` | Generate test scenarios |
| qe | `qe:acceptance` | Evidence-gated acceptance testing |
| data | `data:analyze` | SQL on CSV/Excel via DuckDB |
| jam | `jam:brainstorm` | Multi-persona brainstorming |
| persona | `persona:as` | Invoke any persona on any task |
| persona | `persona:define` | Create custom personas with rich characteristics |
| mem | `mem:store` / `mem:recall` | Cross-session memory |

See `/wicked-garden:help` for the full list, or browse [all domains](docs/domains.md).

## Migration from v1.x

v2.0 is backward compatible — all commands work identically. Three changes to be aware of:

1. **Model tiers**: 4 utility agents now use haiku (cheaper, faster). 5 high-stakes agents now use opus (deeper reasoning). If you pin models, review the [changelog](CHANGELOG.md).
2. **Tool restrictions**: All 80 agents now have `allowed-tools` in their frontmatter. Agents can only use the tools listed. This is a security improvement — no behavioral change for normal usage.
3. **Skill invocation control**: 6 infrastructure skills are hidden from the `/` menu (`user-invocable: false`). 3 skills are user-only (`disable-model-invocation: true`).

To stay on v1.x: `claude plugins add mikeparcewski/wicked-garden@v1.49.3`

## License

MIT
