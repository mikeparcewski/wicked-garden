# Wicked Garden

**Tell Claude to build a feature. It assembles a crew, runs enforced phases, ships clean code.**

```bash
/wicked-garden:crew:start "add OAuth login with role-based access"
```

Claude analyzes the request, detects security and architecture signals, assembles the right specialists, and runs gated phases — clarify, design, build, test, review. No skipped steps. No hallucinated shortcuts. Every decision is remembered for the next project.

```bash
claude plugins add mikeparcewski/wicked-garden
```

## Start Here

| I want to... | Command | What happens |
|-------------|---------|-------------|
| **Build a feature** | `crew:start "add payment processing"` | Signal analysis, specialist routing, enforced phases. Adapts to complexity. |
| **Review my code** | `engineering:review` | Senior engineer perspective. file:line citations. Actionable. |
| **Brainstorm a decision** | `jam:quick "monorepo or polyrepo?"` | 4 personas debate. Synthesis with confidence levels. |
| **Search the codebase** | `search:code "handlePayment"` | Structural search across 73 languages. Symbols, not strings. |
| **Check security** | `platform:security` | OWASP Top 10 scan with remediation guidance. |
| **Analyze data** | `data:analyze sales.csv` | SQL queries on CSV/Excel via DuckDB. Handles 10GB+ files. |
| **Recall a past decision** | `mem:recall "auth decisions"` | Cross-session memory. Surfaces what you decided and why. |

No setup required. Every command works independently on install.

## Why This Works

Most AI coding sessions start from scratch. Session 47 has no idea what session 1 decided. Claude skips steps, hallucinates shortcuts, and ships without review.

Wicked Garden fixes that with three layers:

1. **Enforced workflow** (`crew`) — Signal analysis detects what your project needs, assembles the right specialists, and runs gated phases. Quality gates actually reject work that doesn't meet the bar.
2. **Cross-session memory** (`mem`) — Decisions, patterns, and gotchas persist and surface automatically. Your second month is better than your first week.
3. **Context assembly** (`smaht`) — Every prompt is enriched with memory, search results, project state, and brainstorm outcomes before Claude responds.

## How It Works

```
You type a prompt
       |
   [smaht assembles context: mem + search + kanban + crew state]
       |
   Claude responds with full project context
       |
   [hooks track decisions, sync tasks, store learnings]
       |
   Next session starts with everything remembered
```

For complex work, `crew:start` orchestrates the full lifecycle:

```
Signal Analysis → Phase Selection → Specialist Routing → Quality Gates → Memory Storage
```

A config change? Complexity 1, two phases, done in minutes.
A cross-cutting migration? Full pipeline, every specialist engaged.
**The system adapts to the work. You don't configure it.**

## 14 Domains

Every domain works independently. Install the plugin, use any command.

### Workflow & Intelligence

| Domain | What It Does | Key Commands |
|--------|-------------|--------------|
| **crew** | Signal-driven workflow engine. Analyzes, selects phases, routes to specialists. | `crew:start`, `crew:execute`, `crew:just-finish` |
| **smaht** | Context assembly. Enriches every prompt with relevant context automatically. | `smaht:onboard`, `smaht:debug` |
| **mem** | Cross-session memory. Decisions persist and surface when relevant. | `mem:store`, `mem:recall`, `mem:review` |
| **search** | Structural code intelligence across 73 languages. | `search:code`, `search:lineage`, `search:blast-radius` |
| **jam** | AI brainstorming with dynamic focus groups. | `jam:brainstorm`, `jam:quick`, `jam:council` |
| **kanban** | Persistent task board. Auto-syncs with Claude's task tools. | `kanban:board-status`, `kanban:new-task` |

### Specialist Disciplines

| Discipline | What It Brings |
|-----------|---------------|
| **Engineering** | Code review, architecture, debugging, frontend/backend specialists, code transformations |
| **Product** | Requirements, UX, customer voice, business strategy, accessibility, design review |
| **Platform** | Security (OWASP), compliance (SOC2/HIPAA/GDPR), SRE, incident response, plugin diagnostics |
| **Quality** | Test strategy, automation, TDD, acceptance testing, E2E scenarios with evidence gates |
| **Data** | DuckDB SQL on CSV/Excel (10GB+), pipelines, ML, analytics architecture |
| **Delivery** | Sprint health, A/B tests, progressive rollouts, cost optimization |
| **Agentic** | Agent architecture review, safety audits, framework analysis |
| **Persona** | On-demand specialist perspectives with rich characteristics |

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

1. **Memory over amnesia** — Decisions persist. Session 47 knows what session 1 decided.
2. **Signal over ceremony** — The work tells the system what it needs. You don't configure pipelines.
3. **Perspectives over ego** — 8 specialist domains catch what one voice misses.
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

## Migration from v1.x

v2.0 is backward compatible — all commands work identically. Three changes to be aware of:

1. **Model tiers**: 4 utility agents now use haiku (cheaper, faster). 5 high-stakes agents now use opus (deeper reasoning). If you pin models, review the [changelog](CHANGELOG.md).
2. **Tool restrictions**: All 80 agents now have `allowed-tools` in their frontmatter. Agents can only use the tools listed. This is a security improvement — no behavioral change for normal usage.
3. **Skill invocation control**: 6 infrastructure skills are hidden from the `/` menu (`user-invocable: false`). 3 skills are user-only (`disable-model-invocation: true`).

To stay on v1.x: `claude plugins add mikeparcewski/wicked-garden@v1.49.3`

## License

MIT
