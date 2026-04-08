```
           _      _            _                           _            
 __      _(_) ___| | _____  __| |       __ _  __ _ _ __ __| | ___ _ __  
 \ \ /\ / / |/ __| |/ / _ \/ _` |_____ / _` |/ _` | '__/ _` |/ _ \ '_ \ 
  \ V  V /| | (__|   <  __/ (_| |_____| (_| | (_| | | | (_| |  __/ | | |
   \_/\_/ |_|\___|_|\_\___|\__,_|      \__, |\__,_|_|  \__,_|\___|_| |_|
                                       |___/                             
```

# Wicked Garden

**Tell Claude to build a feature. It assembles a crew, runs enforced phases, ships clean code.**

```bash
/wicked-garden:crew:start "add OAuth login with role-based access"
```

Claude analyzes the request, detects security and architecture signals, assembles the right specialists, and runs gated phases — clarify, design, build, test, review, operate. No skipped steps. No hallucinated shortcuts. Every decision is remembered for the next project.

```bash
claude plugins add mikeparcewski/wicked-garden
```

## What You Do

Commands you run when you need them. No setup required.

| I want to... | Command |
|-------------|---------|
| **Build a feature end-to-end** | `crew:start "add payment processing"` — assembles specialists, runs enforced phases, adapts to complexity |
| **Teach Claude my codebase** | `smaht:onboard` — indexes structure, traces flows, maps architecture. Claude remembers it across sessions. |
| **Review code with domain expertise** | `engineering:review` — security checks OWASP Top 10, architecture detects scope creep, QE catches test manipulation |
| **Test before I code** | `qe:scenarios "checkout flow"` — generates happy paths, edge cases, error conditions, maps to CLI tools |
| **Brainstorm with real perspectives** | `jam:council "monorepo or polyrepo?"` — pipes the question to every LLM CLI on your machine (Codex, Gemini, Copilot), synthesizes agreements and dissent |
| **Find what breaks if I change this** | `search:blast-radius "handlePayment"` — dependency analysis across your codebase, not string matching |
| **Design an A/B test** | `delivery:experiment` — hypothesis, sample size calculation, instrumentation plan, decision criteria |
| **Collect audit evidence** | `platform:audit` — per-control evidence collection (SOC2, HIPAA, GDPR) with PASS/PARTIAL/FAIL and auditor notes |

## What the Plugin Does Automatically

These run in the background via lifecycle hooks. You don't invoke them — they make everything above smarter.

| What happens | How it works |
|-------------|-------------|
| **Every prompt gets project context** | `smaht` assembles brain knowledge, memory, project state, and event history before Claude responds — 4-tier routing (hot/fast/slow/synthesize) keeps it fast for simple prompts and thorough for complex ones |
| **Decisions persist across sessions** | `mem` stores what you decided and surfaces it when relevant — search "auth" and find the JWT decision from three months ago via auto-generated synonym tags |
| **Working memory consolidates over time** | Session noise drops away, important patterns get promoted to durable knowledge. 3 tiers: working (transient) → episodic (sprint-level) → semantic (permanent) |
| **Tasks sync to a kanban board** | Claude's task tools auto-sync to the kanban via hooks — no manual tracking |
| **Complexity shapes the workflow** | 7-dimension scoring (impact, reversibility, novelty, test complexity, documentation, coordination, operational) — a config change gets 2 phases, a migration gets 7 |
| **Quality gates enforce standards** | Gates actually reject work. High-complexity gates require multi-perspective consensus from specialist proposers. Bad coverage blocks advancement. |
| **Traceability links deliverables across phases** | Requirements → designs → code → tests → evidence → gate approvals. After deploy, incidents link back to the requirements that caused them. |
| **Session teardown captures learnings** | Stop hook prompts memory storage, consolidates working memories, and persists session metadata for next time |

## Why This Works

Most AI coding sessions start from scratch. Session 47 has no idea what session 1 decided. Claude skips steps, hallucinates shortcuts, and ships without review.

Wicked Garden fixes that with three layers:

1. **Enforced workflow** (`crew`) — Signal analysis detects what your project needs, scores complexity across 7 dimensions, assembles the right specialists, and runs gated phases. Quality gates reject work that doesn't meet the bar. Consensus review at complexity 5+ brings multiple specialist perspectives before advancement.
2. **Cross-session memory** (`mem`) — Decisions, patterns, and gotchas persist and surface automatically. Auto-generated search tags mean "auth" finds the "JWT session token" decision. Working memories consolidate into durable knowledge over time.
3. **Context assembly** (`smaht`) — Every prompt is enriched with brain knowledge, memory, project state, and event history. Four-tier routing (hot/fast/slow/synthesize) keeps simple prompts fast and complex ones thorough. wicked-brain is an optional but strongly recommended companion plugin that serves as the primary knowledge layer.

## How It Works

```
You type a prompt
       |
   [smaht assembles context: brain + mem + events + domain state]
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
| **crew** | Signal-driven workflow engine with 8 phases, consensus gates, and operate-phase feedback loops | `crew:start`, `crew:execute`, `crew:just-finish`, `crew:retro` |
| **smaht** | Automatic context assembly on every prompt. 4-tier routing (hot/fast/slow/synthesize) keeps simple prompts fast and complex ones thorough. wicked-brain is the primary knowledge source. | `smaht:onboard`, `smaht:collaborate`, `smaht:briefing` |
| **mem** | 3-tier persistent memory (working → episodic → semantic) with auto-consolidation and tag-based search | `mem:store`, `mem:recall`, `mem:consolidate` |
| **search** | Structural code intelligence — symbols, blast radius, data lineage, service maps | `search:code`, `search:lineage`, `search:blast-radius`, `search:service-map` |
| **jam** | AI brainstorming with dynamic focus groups and multi-model council sessions | `jam:brainstorm`, `jam:quick`, `jam:council` |
| **kanban** | Persistent task board. Auto-syncs with Claude's task tools via hooks. | `kanban:board-status`, `kanban:new-task`, `kanban:initiative` |

### Specialist Disciplines

| Discipline | What It Brings |
|-----------|---------------|
| **Engineering** | Code review with scope creep detection, architecture analysis, systematic debugging, implementation planning with parallel risk assessment |
| **Product** | Requirements elicitation, stakeholder alignment (maps power/interest), multi-dimensional strategy (ROI + market + competitive), UX flows, WCAG accessibility audits, wireframes |
| **Platform** | Security review (OWASP), compliance evidence collection (SOC2/HIPAA/GDPR/PCI per control), incident triage with deployment correlation, infrastructure review |
| **Quality** | Test scenarios mapped to CLI tools, test code generation matching project conventions, acceptance testing with evidence gates, agent manipulation detection in tests |
| **Data** | DuckDB SQL on CSV/Excel (10GB+), pipeline review (silent data loss, idempotency), ML review (data leakage, production readiness), analytics architecture |
| **Delivery** | A/B test design with sample size calculation, progressive rollouts with automatic rollback triggers, multi-perspective stakeholder reports, cost optimization |
| **Agentic** | Agent architecture design, 5-layer validation, safety audit (guardrails, prompt injection, PII), framework comparison |
| **Persona** | On-demand specialist invocation with rich characteristics — custom personas with personality, constraints, and memories |

## Integration

| Integration | With It | Without It |
|------------|---------|------------|
| **External MCP tools** | kanban syncs to Jira/Linear, mem to Notion — auto-discovered at runtime | Local JSON files — same API |
| **GitHub CLI (`gh`)** | Auto-file issues, PR creation, releases | Manual issue/PR workflow |
| **Tree-sitter** | 73-language structural code search, lineage | Grep-based text search |
| **DuckDB** | SQL on 10GB+ CSV/Excel files | Basic file reading |
| **External LLM CLIs** | Multi-model council reviews (Codex, Gemini, Copilot) with independent perspectives | Claude-only specialist agents |

The plugin works fully standalone. Each integration adds capability but nothing breaks without it.

## What You Can't Do With Just a CLAUDE.md

| Capability | CLAUDE.md | Wicked Garden |
|-----------|-----------|---------------|
| Persistent cross-session memory | No — each session starts fresh | Yes — decisions surface automatically when relevant |
| Automatic context assembly | No — must manually recap | Yes — smaht injects memory + search + project state every turn |
| Enforced quality gates | No — suggestions, often skipped | Yes — hooks deny advancement when evidence is missing |
| Runtime integration discovery | No — hardcoded tool references | Yes — auto-detect MCP servers, CLI tools, external LLMs |
| Multi-model perspectives | No — Claude only | Yes — council pipes to Codex, Gemini, Copilot |
| Signal-driven complexity scoring | No — fixed workflow | Yes — 7-dimension analysis adapts phases to the work |
| Session teardown with learning capture | No — session just ends | Yes — stop hook prompts memory storage, consolidates knowledge |
| Cross-phase traceability | No — deliverables are disconnected | Yes — requirements → designs → code → tests → evidence → incidents |

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
| [Cross-Phase Intelligence](docs/cross-phase-intelligence.md) | Traceability links, artifact states, verification protocol, knowledge graph |

## Changelog

**v4.0** — wicked-brain as unified knowledge layer: brain adapter replaces search as the primary context source, FTS5 index queried on every prompt. smaht v2 pipeline: 4-tier routing (hot/fast/slow/synthesize), intent-based adapter fan-out, budget enforcer, history condenser. Agentic synthesis skill for complex/risky prompts. Automatic brain lifecycle — setup pipeline, incremental reindex, bootstrap directives.

**v3.6** — Consensus-backed gate decisions for high-complexity work (multi-perspective specialist review), Operate phase closing the SDLC feedback loop (incidents, feedback, retro), 3-tier memory with auto-consolidation (working → episodic → semantic), auto-generated search tags for better keyword recall.

**v3.5** — Comprehensive documentation update across all domains.

**v3.4** — Cross-phase intelligence: traceability links, artifact state machine, verification protocol, knowledge graph, council consensus with dissent tracking. 10 E2E scenarios.

**v3.3** — Manifest modernization, 4 new lifecycle hook events, agent budgets for all 80 agents.

**v3.0-3.2** — Unified event log, session briefing, domain consolidation from 5 plugins into 1.

## License

MIT
