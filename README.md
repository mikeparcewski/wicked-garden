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

Claude scores the work on 9 factors, detects the project archetype, assembles the right specialists by reading their frontmatter, and runs gated phases — clarify, design, (challenge), build, test, review, operate. No skipped steps. No hallucinated shortcuts. Every decision is remembered for the next project.

```bash
claude plugins add mikeparcewski/wicked-garden
```

## What's new in v6

v6 leans hard on Claude Code's native surface — it doesn't replace Claude's primitives, it orchestrates them.

- **Facilitator replaces the rule engine.** A `propose-process` skill scores 9 factors, detects 1 of 7 project archetypes, and picks specialists + phases per project instead of matching keyword patterns.
- **75 specialists routed by frontmatter.** Subagents are discovered at runtime from `agents/**/*.md` — add a markdown file with a `subagent_type` front-matter line and the facilitator can route to it next session. No static maps.
- **Native tasks carry causality.** `TaskCreate` / `TaskUpdate` metadata (`chain_id`, `event_type`, `source_agent`, `phase`, `archetype`) is validated by a PreToolUse hook and consumed by a SubagentStart hook that injects per-role procedure bundles.
- **Convergence lifecycle.** Every build/test artifact moves through Designed → Built → Wired → Tested → Integrated → Verified. The `convergence-verify` gate blocks review approval until each artifact reaches at least Integrated.
- **Contrarian agent + challenge gate** auto-insert at complexity ≥ 4 to steelman the alternative path.
- **Phase-boundary QE evaluator** replaces `test-strategist` at the testability and evidence-quality gates, reading archetype to pick per-type test + evidence expectations.
- **Semantic reviewer** extracts numbered AC / FR / REQ items from clarify artifacts and emits a Gap Report (aligned / divergent / missing) at review — tests passing isn't the same as spec intent being met.
- **Ops bundle.** HMAC-signed dispatch log with orphan detection, pre-flip monitoring with a StrictMode latch, yolo guardrails that gate full-rigor grants behind justification + sentinel, and gate-result security hardening.
- **Process memory + kaizen.** Operate-phase retros auto-populate a facilitator-context digest so future projects inherit learned trade-offs.
- **Skills are Skill()-invokable.** Heavy skills (propose-process, workflow, acceptance-testing, unified-search, adopt-legacy) were flattened so Claude can call them directly.

## Requirements

- **Python 3.9+** — required for hook scripts and storage layer
- **Node.js 18+** — required for wicked-testing
- **[wicked-testing](https://github.com/mikeparcewski/wicked-testing) `^0.2`** — required peer plugin; QE behavior lives here in v7.0+

### Version pinning policy

`plugin.json:wicked_testing_version` pins a caret-range (`^0.2.0` for v7.1.x). Patch releases are backward-compatible bug fixes — always drop-in. Minor releases may add new Tier-1 agents (additive only) — compatible for consumers, no wicked-garden changes needed. A wicked-testing major bump requires wicked-garden to update its pin, coordinated with the next wicked-garden major release. See [INTEGRATION.md §8](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/INTEGRATION.md#8-version--compatibility) for the full policy.

## Quick Start

```bash
claude plugins add mikeparcewski/wicked-garden
npx wicked-testing install
```

Then start a project:

```bash
/wicked-garden:crew:start "add OAuth login with role-based access"
```

The plugin detects your stack, assembles specialists, and runs enforced phases. wicked-testing must be installed for test and review phases to work.

## What's the relationship with wicked-testing?

wicked-garden orchestrates the full SDLC — crew workflow, phase management, gate enforcement, memory, and context assembly. wicked-testing is a separate peer plugin that owns all QE behavior: test planning, authoring, execution, and review. The two communicate through a stable public contract (agent `subagent_type` names, bus events, and an evidence manifest schema). wicked-garden's crew gate dispatches QE agents by their `wicked-testing:*` subagent names and subscribes to `wicked.verdict.recorded` for results. You can use wicked-testing independently on projects that don't use wicked-garden's crew workflow. See the [wicked-garden integration guide](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/WICKED-GARDEN.md) for the full contract.

## What You Do

Commands you run when you need them. No setup required.

| I want to... | Command |
|-------------|---------|
| **Build a feature end-to-end** | `crew:start "add payment processing"` — facilitator scores 9 factors, picks specialists + phases, runs enforced gates |
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
| **Task metadata carries causality** | Native `TaskCreate` / `TaskUpdate` get a structured envelope (`chain_id`, `event_type`, `phase`, `archetype`). A PreToolUse hook validates it; a SubagentStart hook reads it to inject per-role procedures (R1–R6 for coding-tasks, Gate Finding Protocol for gate-findings) |
| **The facilitator picks the plan** | 9-factor rubric scores your request, archetype detection classifies the work (schema-migration, docs-only, code-repo, etc.), rigor tier (minimal/standard/full) adapts gate behavior. A config change gets minimal tier + advisory gates; a migration gets full tier + multi-reviewer panels |
| **Quality gates actually enforce** | APPROVE advances. CONDITIONAL writes a conditions manifest that must be verified. REJECT blocks. BLEND aggregation (0.4×min + 0.6×avg) lets one strong dissent hold up weak work. 3+ gate failures trigger swarm crisis response. |
| **Artifacts converge, not just complete** | Designed → Built → Wired → Tested → Integrated → Verified. Completion ≠ wired into production. `convergence-verify` gate blocks review sign-off until every artifact reaches Integrated; stalls at 3 sessions become findings. |
| **Traceability links deliverables across phases** | Requirements → designs → code → tests → evidence → gate approvals. After deploy, incidents link back to the requirements that caused them. |
| **Session teardown captures learnings** | Stop hook prompts memory storage, consolidates working memories, runs the session-close guard pipeline, and persists session metadata for next time |

## Why This Works

Most AI coding sessions start from scratch. Session 47 has no idea what session 1 decided. Claude skips steps, hallucinates shortcuts, and ships without review.

Wicked Garden fixes that with three layers:

1. **Enforced workflow** (`crew`) — Facilitator rubric scores 9 factors, detects archetype, picks specialists by reading their frontmatter, runs gated phases. Quality gates reject work that doesn't meet the bar. Multi-reviewer BLEND aggregation at full rigor brings several specialist perspectives before advancement.
2. **Cross-session memory** (`mem`) — Decisions, patterns, and gotchas persist and surface automatically. Auto-generated search tags mean "auth" finds the "JWT session token" decision. Working memories consolidate into durable knowledge over time.
3. **Context assembly** (`smaht`) — Every prompt is enriched with brain knowledge, memory, project state, and event history. Four-tier routing keeps simple prompts fast and complex ones thorough. wicked-brain is an optional but strongly recommended companion plugin that serves as the primary knowledge layer.

## How It Works

```
You type a prompt
       |
   [smaht assembles context: brain + domain + events + context7 + tools + delegation]
       |
   Claude responds with full project context
       |
   [PreToolUse validates task metadata; hooks track decisions, store learnings]
       |
   Next session starts with everything remembered
```

For complex work, `crew:start` orchestrates the full lifecycle:

```
Facilitator Rubric -> Archetype Detection -> Phase Plan -> Specialist Routing -> Quality Gates -> Memory Storage
```

A config change? Minimal rigor, two phases, done in minutes.
A schema migration? Full rigor pipeline, archetype-aware evidence demands, multi-reviewer panels.
**The system adapts to the work. You don't configure it.**

## 13 Domains

Every domain works independently. Install the plugin, use any command.

### Workflow & Intelligence

| Domain | What It Does | Key Commands |
|--------|-------------|--------------|
| **crew** | Facilitator-driven workflow engine with 7 archetypes, phase-boundary QE evaluator, convergence lifecycle, challenge gate, yolo guardrails, and multi-reviewer gate enforcement | `crew:start`, `crew:execute`, `crew:convergence`, `crew:swarm`, `crew:retro` |
| **smaht** | Automatic context assembly on every prompt. 4-tier routing (hot/fast/slow/synthesize). Six adapters: domain, brain, events, context7, tools, delegation. | `smaht:onboard`, `smaht:collaborate`, `smaht:briefing` |
| **mem** | 3-tier persistent memory (working → episodic → semantic) with auto-consolidation and tag-based search — **requires [wicked-brain](https://github.com/mikeparcewski/wicked-brain) plugin** | Use `wicked-brain:memory` (store/recall modes) directly |
| **search** | Structural code intelligence — symbols, blast radius, data lineage, service maps | `search:code`, `search:lineage`, `search:blast-radius`, `search:service-map` |
| **jam** | AI brainstorming with dynamic focus groups and multi-model council sessions | `jam:brainstorm`, `jam:quick`, `jam:council` |

Tasks use Claude Code's native `TaskCreate` / `TaskUpdate` directly — no separate task domain. The PreToolUse validator enforces the metadata envelope.

### Specialist Disciplines

| Discipline | What It Brings |
|-----------|---------------|
| **Engineering** (10) | Senior engineer, solution architect, system designer, backend/frontend, debugger, tech writer, API documentarian, DevEx engineer, migration engineer |
| **Product** (11) | Requirements, UX design + analysis, user research + voice, market/value strategy, WCAG a11y, UI review, mockups |
| **Platform** (11) | Security, SRE, compliance, incident response, infrastructure, DevOps, release, audit, privacy, chaos, observability |
| **Quality** (11) | Test strategist, test designer, automation, risk, testability, semantic reviewer, contract testing, requirements quality, code analyzer, continuous + production quality monitors |
| **Data** (4) | Data analyst, engineer, ML engineer, unified OLTP+OLAP data architect |
| **Delivery** (7) | Delivery manager, stakeholder reporter, rollout, experiments, risk, progress, cloud-cost intelligence |
| **Agentic** (5) | Architect, safety, patterns, performance, framework research |
| **Persona** (1) | On-demand specialist invocation with rich characteristics |

Total: **75 specialist agents**, discovered at runtime via `subagent_type` frontmatter.

## Integration

| Integration | With It | Without It |
|------------|---------|------------|
| **External MCP tools** | Integration-discovery routes mem to Notion, delivery to Jira/Linear — auto-discovered at runtime | Local JSON files — same API |
| **GitHub CLI (`gh`)** | Auto-file issues, PR creation, releases | Manual issue/PR workflow |
| **Tree-sitter** | 73-language structural code search, lineage | Grep-based text search |
| **DuckDB** | SQL on 10GB+ CSV/Excel files | Basic file reading |
| **External LLM CLIs** | Multi-model council reviews (Codex, Gemini, OpenCode) with independent perspectives | Claude-only specialist agents |
| **wicked-brain** | FTS5-indexed knowledge layer (wiki articles, chunks, memories) queried on every prompt | Brain adapter returns empty; grep/glob fallback |

The plugin works fully standalone. Each integration adds capability but nothing breaks without it.

## What You Can't Do With Just a CLAUDE.md

| Capability | CLAUDE.md | Wicked Garden |
|-----------|-----------|---------------|
| Persistent cross-session memory | No — each session starts fresh | Yes — decisions surface automatically when relevant |
| Automatic context assembly | No — must manually recap | Yes — smaht injects memory + search + project state every turn |
| Enforced quality gates | No — suggestions, often skipped | Yes — PreToolUse validator + gate-policy denies advancement when evidence is missing |
| Runtime specialist routing | No — fixed roles | Yes — facilitator reads agent frontmatter dynamically; 75 specialists on disk |
| Native task metadata envelope | No | Yes — `chain_id`, `event_type`, `source_agent`, `phase`, `archetype` validated on every TaskCreate |
| Procedure injection per role | No | Yes — SubagentStart hook injects R1–R6 for coding-tasks, Gate Finding Protocol for gate-findings |
| Convergence tracking | No | Yes — Designed → Built → Wired → Tested → Integrated → Verified with stall detection |
| Multi-model perspectives | No — Claude only | Yes — council pipes to Codex, Gemini, OpenCode |
| Archetype-aware evidence | No | Yes — phase-boundary QE evaluator picks per-archetype test + evidence expectations |
| Cross-phase traceability | No | Yes — requirements → designs → code → tests → evidence → incidents |

## Troubleshooting

- **wicked-testing not installed** — test and review phases will fail with "unknown subagent_type: wicked-testing:xxx". Run `npx wicked-testing install`, then confirm with `npx wicked-testing status`. See the [wicked-garden integration guide](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/WICKED-GARDEN.md) for full migration steps.
- **Version mismatch** — wicked-garden `^7.1` requires wicked-testing `^0.2`. The SessionStart hook warns if the installed version falls outside the pinned range in `plugin.json`.
- **Gate returns empty verdicts** — wicked-bus may not be running. wicked-bus is optional but wicked-garden's crew gate subscribes to `wicked.verdict.recorded` to advance phases. Run `npx wicked-bus status`.
- **Node.js not installed** — `npx wicked-testing install` requires Node.js 18 or later. Download and install from [nodejs.org](https://nodejs.org), then re-run the install command.
- **npm/npx auth failure during install** — common causes: corporate npm proxy not configured, VPN blocking the registry, or a stale `~/.npmrc` auth token. Fix: run `npm config get registry` to verify the registry URL, clear the token with `npm logout`, and re-run. If behind a proxy, set `npm config set proxy http://your-proxy` first.
- **Offline install** — for air-gapped or offline environments, follow the offline bundle instructions tracked in [mikeparcewski/wicked-testing#5](https://github.com/mikeparcewski/wicked-testing/issues/5).

## Principles

1. **Memory over amnesia** — Decisions persist. Session 47 knows what session 1 decided.
2. **Factors over signals** — The facilitator reads 9 factors and archetype, not keyword patterns.
3. **Perspectives over ego** — Multiple specialist domains catch what one voice misses.
4. **Enforcement over suggestion** — Gates reject work that doesn't meet the bar.
5. **Graceful degradation** — No external tools? Local JSON. Missing a specialist? Fallback agents.
6. **Prompts over code** — Logic lives in markdown and config. Extensible by anyone.

## Upgrading to v7.0

If you are upgrading from v6.x, see [docs/MIGRATION-v7.md](docs/MIGRATION-v7.md) for the grace-period timeline, rollback path, and troubleshooting steps.

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, first session, common workflows |
| [Domains](docs/domains.md) | All 13 domains with full command tables |
| [Crew Workflow](docs/crew-workflow.md) | Facilitator rubric, archetype detection, gates, convergence |
| [Architecture](docs/architecture.md) | Storage, native task metadata, gate policy, context assembly |
| [Advanced Usage](docs/advanced.md) | Multi-model, yolo mode, customization, development commands |
| [Cross-Phase Intelligence](docs/cross-phase-intelligence.md) | Traceability, artifact states, verification, convergence, knowledge graph |
| [Migration v7.0](docs/MIGRATION-v7.md) | Upgrading from v6.x, grace-period timeline, rollback |

## Changelog

**v6.3** — Phase-boundary QE evaluator + archetype detection (7 archetypes, DOMINANCE_RATIO=4); `subagent_type` frontmatter injected across 75 agents; agent consolidations (jam/facilitator → brainstorm-facilitator, visual-reviewer → ui-reviewer, business-strategist → market-strategist, value-analyst + alignment-lead → value-strategist, feedback-analyst + customer-advocate → user-voice, acceptance-test trio → test-designer, tdd-coach → test-strategist, analytics-architect → data-architect); new `ux-analyst` agent; workflow skill rewritten for v6.

**v6.2** — Ops bundle: HMAC-signed dispatch log with orphan detection and rotation, pre-flip monitoring with StrictMode banner, yolo full-rigor guardrails (justification + sentinel), BLEND multi-reviewer aggregation (0.4×min + 0.6×avg), blind reviewer context stripping, partial-panel pending invariant, re-eval addendum schema 1.1.0, amendments.jsonl, plain-language `crew:explain` skill, gate-result security hardening (schema validator + content sanitizer + audit log).

**v6.1** — Mode-3 formal crew execution with `phase-executor` + gate dispatch, SessionState + build-phase guard hook (R3/R5 AST heuristics), convergence lifecycle with `convergence-verify` gate, contrarian agent + challenge gate (auto-insert at complexity ≥ 4), semantic reviewer for spec-to-code alignment, persistent process memory + kaizen backlog, autonomous session-close guard pipeline, cross-session quality telemetry + drift detection, scored spec quality rubric + clarify-gate enforcement, wicked-bus integration.

**v6.0** — Facilitator (`skills/propose-process/`) replaces the rule engine. 9-factor rubric, dynamic specialist routing via agent frontmatter, phase selection from `phases.json`, rigor tiers (minimal/standard/full). Bidirectional re-evaluation with addendum log. `gate-policy.json` codifies reviewer × rigor × dispatch-mode. Heavy skills flattened to be Skill()-invokable. `adopt-legacy` skill migrates v5 markers idempotently.

**v5.0** — Retired kanban domain. Tasks migrated to Claude Code's native `TaskCreate` / `TaskUpdate` with a structured metadata envelope (`chain_id`, `event_type`, `source_agent`, `phase`) validated by a PreToolUse hook. SubagentStart injects procedure bundles keyed on `event_type`.

**v4.0** — wicked-brain as unified knowledge layer: brain adapter replaces search as the primary context source, FTS5 index queried on every prompt. smaht v2 pipeline: 4-tier routing (hot/fast/slow/synthesize), intent-based adapter fan-out, budget enforcer, history condenser.

**v3.6** — Consensus-backed gate decisions for high-complexity work, operate phase closing the SDLC feedback loop, 3-tier memory with auto-consolidation, auto-generated search tags.

**v3.4** — Cross-phase intelligence: traceability links, artifact state machine, verification protocol, knowledge graph, council consensus with dissent tracking.

**v3.0–3.3** — Unified event log, session briefing, domain consolidation from 5 plugins into 1, lifecycle hook events.

## License

MIT
