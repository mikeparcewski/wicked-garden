```
           _      _            _                           _            
 __      _(_) ___| | _____  __| |       __ _  __ _ _ __ __| | ___ _ __  
 \ \ /\ / / |/ __| |/ / _ \/ _` |_____ / _` |/ _` | '__/ _` |/ _ \ '_ \ 
  \ V  V /| | (__|   <  __/ (_| |_____| (_| | (_| | | | (_| |  __/ | | |
   \_/\_/ |_|\___|_|\_\___|\__,_|      \__, |\__,_|_|  \__,_|\___|_| |_|
                                       |___/                             
```

# Wicked Garden

> **Identity at a glance:** see [`ETHOS.md`](ETHOS.md) — what we believe, what we refuse, what we optimize for.

---

## The problem

Every Claude Code session starts from scratch. Session 47 has no idea what session 1 decided. The auth token format, the migration that caused the outage, the architectural call you spent two hours debating — all gone. So Claude fills the gap the only way it can: it guesses, skips review steps, and ships things that feel right but aren't grounded in your actual history.

The second problem is gates. Every team has review steps they believe in. Claude has no enforcement mechanism. Under deadline pressure, review becomes suggestion. Suggestion becomes optional. Optional becomes skipped. The gate existed on paper; the work shipped without it.

The third problem is context. On any real project, the right specialist for a security decision is different from the right specialist for a data architecture call. Claude doesn't route. It answers from whatever context happens to be in the window.

---

## The fix

Wicked Garden is an AI-native SDLC plugin for Claude Code. The trust mechanism is threefold: **the bus is the source of truth** (every gate verdict, every dispatch, every artifact write is a signed event on the bus before it hits disk), **the brain carries knowledge across sessions** (decisions, gotchas, and patterns persist and surface when relevant), and **quality gates reject work that doesn't meet the bar** (REJECT blocks advancement; CONDITIONAL blocks until a conditions manifest is cleared; no advisory checklists).

---

## What a Monday morning looks like

It is 9:00 AM. You left a feature half-finished on Friday. You open Claude Code and type:

```bash
/wicked-garden:crew:start "finish the checkout flow — payment processing and tax calculation"
```

**9:00:01** — The `smaht` context assembler fires before Claude sees your message. It queries `wicked-brain` for every decision tagged to your checkout domain: the Stripe idempotency key pattern you established six weeks ago, the tax library evaluation that concluded `tax-rates` was too slow for realtime calls, the open requirement `REQ-CHECKOUT-14` about VAT handling for EU customers. All of it lands in the prompt context before you finish reading the first response.

**9:00:15** — The facilitator reads your request against nine factors: reversibility (moderate — payment state is hard to undo), blast radius (high — touches order service, tax service, webhook queue), compliance scope (yes — PCI DSS surface), novelty (low — established pattern in this codebase), and five more. It detects the `code-repo` archetype. Rigor tier: **full**. Phase chain: clarify → design → challenge → build → test → review → operate.

**9:01** — The clarify phase begins. The facilitator dispatches the requirements analyst (`wicked-garden:product:elicit`). It surfaces `REQ-CHECKOUT-14` from the brain, notices it has no acceptance criterion for the VAT case, and asks you directly. You answer. The requirement gets a criteria block. The analyst writes the clarify artifact with `REQ-CHECKOUT-17` added for the EU edge case you just described. A `wicked.crew.phase_started` event lands on the bus.

**9:08** — Clarify gates. The semantic reviewer (`wicked-testing:semantic-reviewer`, dispatched via the wicked-testing peer plugin) extracts every `AC-*` and `REQ-*` item from the clarify artifact and emits a gap report. Two items have no design pointer. The gate issues `CONDITIONAL`. A `conditions-manifest.json` is written to `phases/clarify/`. The `wicked.gate.decided` event is on the bus before the file hits disk, signed by the HMAC dispatch log.

**9:12** — You resolve the two conditions. The `wicked-garden:crew:resolve` command marks them cleared. The manifest is updated. Another bus event. The clarify gate flips to `APPROVE`.

**9:13** — Design phase. The solution architect (`wicked-garden:engineering:arch`) reads the clarify artifact and the brain's architectural history. It flags that the tax call pattern you proposed would add ~200ms to checkout latency under the p99 numbers from last month's load test (stored in the brain as a memory from that session). It proposes caching. You agree. Design artifact written. Bus event. Gate dispatched.

**9:25** — Challenge phase fires automatically because complexity ≥ 4. The contrarian agent (`wicked-garden:crew:contrarian`) runs a structured steelman of the alternative: call the tax service synchronously and cache client-side. It finds two real objections to the caching approach — cache invalidation on tax rule changes, and stale rates for high-frequency users. You read the report. You add a cache TTL and a webhook listener for tax rule updates. Challenge gate: `APPROVE`.

**9:40** — Build begins. The implementer has the full chain of requirements, design decisions, architectural calls, and challenge objections in context. It codes against your actual codebase structure (indexed by `wicked-garden:search:blast-radius` at session start). The `coding-task` event type on the build task triggers the SubagentStart hook to inject R1–R6 bulletproof standards: no dead code, no bare panics, no magic values, no swallowed errors.

**10:15** — Test gate. `wicked-testing` dispatches the test designer. Test artifacts are written. The convergence tracker (`scripts/crew/convergence.py`) logs every artifact through its state machine: Designed → Built → Wired → Tested → Integrated. The review gate will not advance until every artifact reaches at least `Integrated`.

**10:45** — Review gate. Multi-reviewer panel: senior engineer, security engineer (OWASP Top 10 against your payment path), the wicked-testing reviewer. BLEND aggregation: `0.4 × min + 0.6 × avg`. All three approve. Gate: `APPROVE`. The `wicked.gate.decided` event lands on the bus. `phases/review/gate-result.json` is materialized by the projector from that event — not written directly.

**10:46** — Session ends. The Stop hook triggers memory consolidation. The Stripe idempotency pattern, the tax caching decision, the EU VAT requirement addition — all captured as durable memories in `wicked-brain`. Next session will know what this one decided.

You shipped a feature that touched PCI scope, EU tax law, and payment state — with enforced gates, cross-session context, and an audit trail that can reconstruct every decision from the event log alone.

---

## Why it works

**Gates are enforced by the bus, not by Claude's willpower.** Every gate verdict writes `phases/{phase}/gate-result.json` AFTER a `wicked.gate.decided` event lands on the bus. The PreToolUse lint (`hooks/scripts/pre_tool.py`) detects writes to gate-critical files that lack a paired bus event in the last N seconds and denies or warns — configurable via `WG_BUS_EMIT_LINT`. An HMAC-signed dispatch log (`phases/{phase}/dispatch-log.jsonl`) records every specialist dispatch; a gate result without a matching dispatch entry downgrades to `CONDITIONAL`. You cannot accidentally approve without a record.

**Context survives session boundaries because the brain indexes everything.** `wicked-brain` maintains an FTS5 index of decisions, architectural patterns, gotchas, wiki articles, and memories. The `smaht` context assembler queries it on every prompt using intent-aware adapter fan-out (DEBUGGING, IMPLEMENTATION, PLANNING, RESEARCH each pull from different adapter subsets). A decision from session 1 surfaces in session 47 because it was stored with confidence, decay rules, and domain tags — not buried in a chat transcript.

**Specialist routing is structural, not keyword-based.** 63 specialist agents live in `agents/**/*.md`. The facilitator discovers them at runtime by reading frontmatter — no static map, no registration ceremony. A security decision routes to the security engineer because the facilitator read its frontmatter description and matched it against the nine-factor rubric output. Add a new agent with a `subagent_type` line and it becomes eligible next session.

**Rigor adapts to the project, not the other way around.** A typo fix and a schema migration are not the same project. The facilitator scores nine factors and detects one of seven archetypes (`schema-migration`, `multi-repo`, `testing-only`, `config-infra`, `skill-agent-authoring`, `docs-only`, `code-repo`). Rigor tier (minimal/standard/full) flows from the scoring. A config change gets two phases and advisory gates. A migration gets a full pipeline with multi-reviewer panels and archetype-aware evidence demands. You do not configure this — it reads the work.

---

## Bus-as-truth architecture

Sites 1–5 of the bus cutover (#746) have shipped (PRs #751, #758, #773, #777, #781–#785). The architecture is now live.

**The invariant**: every write to a gate-critical artifact is preceded by a bus event. The on-disk file is a projection of the event log, not the primary store.

```
Gate verdict computed
        |
   [wicked.gate.decided → wicked-bus]
        |
   [daemon/projector.py handler]
        |
   phases/{phase}/gate-result.json  ← materialized projection
```

The same pattern applies to all five cutover sites:

| Artifact | Bus event | Feature flag |
|----------|-----------|--------------|
| `phases/{phase}/dispatch-log.jsonl` | `wicked.dispatch.log_entry_appended` | `WG_BUS_AS_TRUTH_DISPATCH_LOG` |
| `phases/{phase}/consensus-report.json` | `wicked.consensus.report_created` | `WG_BUS_AS_TRUTH_CONSENSUS_REPORT` |
| `phases/{phase}/reviewer-report.md` | `wicked.consensus.gate_completed` | `WG_BUS_AS_TRUTH_REVIEWER_REPORT` |
| `phases/{phase}/gate-result.json` | `wicked.gate.decided` | `WG_BUS_AS_TRUTH_GATE_RESULT` |
| `phases/{phase}/conditions-manifest.json` | `wicked.gate.decided` (CONDITIONAL) | `WG_BUS_AS_TRUTH_CONDITIONS_MANIFEST` |

Every flag defaults **on** after Sites 1–5 shipped — bus-as-truth is the default. Operators opt out per-site by setting `WG_BUS_AS_TRUTH_<TOKEN>=off` (literal `on`/`off` only, case/whitespace normalized — see PR #777). Each flag is independent; you can revert one site without touching the others, and `git revert` on the cutover PR is the always-available emergency lever.

**The audit trail has teeth** because: the event log is append-only; the dispatch log is HMAC-signed; the content sanitizer (`gate_ingest_audit.py`) runs a codepoint allow-list and injection-pattern check on every gate-result ingestion; orphan detection rejects gate results without a matching dispatch entry. The security floor (AC-9 §5.4) applies to projected files the same as it applied to directly-written files.

---

## Trust the disk vs trust the bus

You can verify bus-as-truth behavior at any time:

```bash
# Check reconciler: projection-stale, event-without-projection, projection-without-event
/wicked-garden:crew:reconcile --all --json

# Check drift class counts (post-cutover schema)
# "projection-stale" = projector is lagging
# "event-without-projection" = handler missing or failed
# "projection-without-event" = direct write bypassed the bus (lint should have caught this)
```

Zero drift on all three classes means the projector is current, every event has a materialized file, and no file appeared without an event.

**Opt-out any site**: set `WG_BUS_AS_TRUTH_<SITE>=off` to revert that site to direct-write behavior. The lint (`WG_BUS_EMIT_LINT=warn|strict|off`) is independent — you can keep drift detection active while a site is in direct-write mode.

**Content-hash idempotency**: the projector handler for each site computes the same output deterministically from the event payload. Re-projecting from a clean `event_log` after deleting all disk files produces byte-for-byte identical artifacts. This is the load-bearing assertion from issue #732: the project state is fully recoverable from the bus alone.

---

## Subtraction is how it stays lean

| Version | What got deleted | Why | Net lines |
|---------|-----------------|-----|-----------|
| [**v4.6**](https://github.com/mikeparcewski/wicked-garden/releases/tag/wicked-garden-v4.6.0) | mem commands collapsed into thin passthroughs to wicked-brain skills | parallel memory store was creating sync bugs | **–25,491** |
| [**v6.1**](https://github.com/mikeparcewski/wicked-garden/releases/tag/wicked-garden-v6.1.0) | v5 rule engine + HOT/FAST/SLOW orchestrator | keyword routing was getting gamed; replaced by 9-factor rubric | partial |
| [**v7.0**](https://github.com/mikeparcewski/wicked-garden/releases/tag/wicked-garden-v7.0.0) | All QE extracted to wicked-testing peer plugin | QE was conflated with workflow; extraction lets each evolve independently | breaking |
| [**v7.1**](https://github.com/mikeparcewski/wicked-garden/releases/tag/wicked-garden-v7.1.0) | `agents/qe/` (11), `skills/qe/` (19), `commands/qe/` (12) | followed through on v7.0 contract | **–6,336** |
| [**v8.0**](https://github.com/mikeparcewski/wicked-garden/releases/tag/wicked-garden-v8.0.0) | `wicked-garden:mem:*` slash commands | shim layer was no longer load-bearing | – |
| [**v8.4**](https://github.com/mikeparcewski/wicked-garden/releases/tag/wicked-garden-v8.4.0) | jam SKILL.md 191→42 (78%); propose-process SKILL.md 600→160 (~73%) | skill files were burning context; agents now own the rubric | – |

The honest pattern is add-then-slim, not pure subtraction. v8.0 also added ~30k lines for the daemon (task projection, hook subscribers, typed state machine). The plugin adds foundational capability when genuinely needed, then aggressively slims the layers above once they prove unnecessary.

**Note on QE deletion (v7.0/v7.1)**: the test gate did not go away — it stays in the phase manager. Only the specialist agents moved to wicked-testing. The framework still enforces test evidence at gate boundaries; it dispatches the work to a peer plugin.

---

## What's in the box

**13 domains**, 63 specialist agents, 76 skills, 12 lifecycle hooks.

Workflow and intelligence: `crew` (facilitator, gates, convergence), `smaht` (context assembly, intent routing), `mem` (memory tiers), `search` (blast radius, lineage, hotspots), `jam` (brainstorming, multi-model council).

Specialist disciplines: `engineering` (10 agents), `product` (11), `platform` (11), `qe` via wicked-testing (11), `data` (4), `delivery` (7), `agentic` (5), `persona` (1).

Agents are discovered at runtime by reading `agents/**/*.md` frontmatter. Add a markdown file with a `subagent_type` line and it becomes eligible next session. No registration ceremony.

---

## What's the relationship with wicked-testing?

wicked-garden orchestrates the full SDLC — crew workflow, phase management, gate enforcement, memory, and context assembly. wicked-testing is a separate peer plugin that owns all QE behavior: test planning, authoring, execution, and review. The two communicate through a stable public contract (`wicked-testing:*` subagent names, bus events, and an evidence manifest schema). wicked-garden's crew gate dispatches QE agents by their `wicked-testing:*` subagent names and subscribes to `wicked.verdict.recorded` for results.

See the [wicked-garden integration guide](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/WICKED-GARDEN.md) for the full contract.

---

## Principles

1. **Memory over amnesia** — Decisions persist. Session 47 knows what session 1 decided.
2. **Factors over signals** — The facilitator reads 9 factors and archetype, not keyword patterns.
3. **Perspectives over ego** — Multiple specialist domains catch what one voice misses.
4. **Enforcement over suggestion** — Gates reject work that doesn't meet the bar.
5. **Graceful degradation** — No external tools? Local JSON. Missing a specialist? Fallback agents.
6. **Prompts over code** — Logic lives in markdown and config. Extensible by anyone.

---

## Requirements

- **Python 3.9+** — required for hook scripts and storage layer
- **Node.js 18+** — required for wicked-testing
- **[wicked-testing](https://github.com/mikeparcewski/wicked-testing) `^0.2`** — required peer plugin; QE behavior lives here in v7.0+

wicked-garden runs standalone with local JSON storage and grep fallback when optional companions are absent. For the full SDLC install [wicked-brain](https://github.com/mikeparcewski/wicked-brain) (memory + search index).

### Version pinning

`plugin.json:wicked_testing_version` pins a caret-range (`^0.2.0` for v7.1.x). Patch releases are backward-compatible bug fixes. Minor releases may add new Tier-1 agents (additive only). A wicked-testing major bump requires a coordinated wicked-garden major release. See [INTEGRATION.md §8](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/INTEGRATION.md#8-version--compatibility).

---

## Install

```bash
claude plugins add mikeparcewski/wicked-garden
npx wicked-testing install
```

Then start a project:

```bash
/wicked-garden:crew:start "add OAuth login with role-based access"
```

Use `/wicked-garden:crew:guide` once a project is active — it ranks "what to do next" against the current phase and detected archetype. With no active project, `/wicked-garden:help` lists every command.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, first session, common workflows, troubleshooting |
| [Domains](docs/domains.md) | All 13 domains with full command tables |
| [Crew Workflow](docs/crew-workflow.md) | Facilitator rubric, archetype detection, gates, convergence |
| [Architecture](docs/architecture.md) | Storage, native task metadata, gate policy, context assembly |
| [Advanced Usage](docs/advanced.md) | Multi-model, yolo mode, customization, development commands |
| [Cross-Phase Intelligence](docs/cross-phase-intelligence.md) | Traceability, artifact states, verification, convergence |
| [Migration v7.0](docs/MIGRATION-v7.md) | Upgrading from v6.x, grace-period timeline, rollback |

---

## Changelog

**v9.x (bus-cutover)** — Sites 1–5 of bus-as-truth cutover shipped (#751, #758, #773, #777, #781–#785). Bus events are now the source of truth for gate-critical artifacts; on-disk files are projections materialized by `daemon/projector.py`. Drift detector (`crew:reconcile`) measures projection-stale, event-without-projection, and projection-without-event. All five `WG_BUS_AS_TRUTH_*` flags default **on**; operators opt out per-site by setting the flag to `off`, with `git revert` on the cutover PR as the emergency lever.

**v8.4** — jam SKILL.md 191→42 (78%); propose-process SKILL.md 600→160 (~73%). Skill files were burning context; agents now own the rubric.

**v8.0** — `wicked-garden:mem:*` slash commands removed; shim layer was no longer load-bearing. wicked-brain is the direct interface for memory persistence.

**v7.1** — `agents/qe/` (11 agents), `skills/qe/` (19), `commands/qe/` (12) deleted (–6,336 lines). Followed through on v7.0 extraction contract.

**v7.0** — All QE extracted to wicked-testing peer plugin. Test gate stays in phase manager; specialists moved to the peer plugin.

**v6.3** — Phase-boundary QE evaluator + archetype detection (7 archetypes, DOMINANCE_RATIO=4). Per-archetype score-band tables in gate-adjudicator.

**v6.2** — HMAC-signed dispatch log with orphan detection, BLEND multi-reviewer aggregation (0.4×min + 0.6×avg), blind reviewer context stripping, partial-panel pending invariant, yolo full-rigor guardrails, gate-result security hardening.

**v6.1** — Mode-3 formal crew execution, convergence lifecycle, contrarian agent + challenge gate, semantic reviewer, cross-session quality telemetry.

**v6.0** — Facilitator replaces rule engine. 9-factor rubric, dynamic specialist routing via agent frontmatter, phase selection from `phases.json`, `gate-policy.json`.

---

## License

MIT
