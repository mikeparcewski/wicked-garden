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
>
> **Vision (v11):** work-shape archetypes, not a fixed pipeline. Each prompt routes to one or more archetypes; each archetype owns its phase shape, produces, and HITL discipline. Steering, not blocking.

---

## The problem

Every Claude Code session starts from scratch. Session 47 has no idea what session 1 decided. The auth token format, the migration that caused the outage, the architectural call you spent two hours debating — all gone. So Claude fills the gap the only way it can: it guesses, skips review steps, and ships things that feel right but aren't grounded in your actual history.

The second problem is shape. Software work is not one shape. A typo fix is not a schema migration. A spec elicitation is not a code review. A production incident is not a roadmap brainstorm. Most workflows force every kind of work through one fixed pipeline (`clarify → design → build → test → review`) and modulate "rigor" with a dial. The dial saves you from the worst ceremony but doesn't change the shape — a typo fix still goes through the same phases as a feature.

The third problem is context. The right specialist for a security decision is different from the right specialist for a data architecture call. Claude doesn't route. It answers from whatever context happens to be in the window.

---

## The fix

Wicked Garden is an AI-native SDLC plugin for Claude Code. v11 reframed the workflow primitive: instead of a fixed pipeline, every prompt classifies into one or more **work-shape archetypes**. Each archetype is a complete unit with its own phase shape, produces, HITL discipline, and cost band.

| Archetype | Phases                                                  | Produces                       | HITL                  | Cost      |
|-----------|---------------------------------------------------------|--------------------------------|-----------------------|-----------|
| triage    | classify                                                | routing decision               | none                  | negligible|
| explore   | frame → diverge → converge                              | option set / hypothesis        | continuous            | low       |
| specify   | elicit → structure → validate                           | SMART acceptance criteria      | discrete:validate     | low       |
| decide    | brief → options → score → record                        | ADR / decision artifact        | discrete:select       | medium    |
| ship      | canary → ramp → full → soak                             | rollout verdict / SLO snapshot | discrete:ramp         | medium    |
| review    | scope → assess → findings → remediate-or-accept         | verdict / remediation list     | hard:final-verdict    | medium    |
| incident  | triage → investigate → mitigate → resolve → followup    | mitigation / RCA / followup    | hard:mitigate         | variable  |
| build     | plan → implement → test → review                        | shipped code / test report     | discrete:review       | high      |
| migrate   | plan → expand → backfill → cutover → contract           | shape change / rollback proof  | hard:cutover          | high      |

Archetypes are NOT mutually exclusive. A schema-changing feature is `build + migrate`. A risky deploy is `ship + review`.

---

## How it works

```
prompt
  ↓
UserPromptSubmit hook → archetypes_v11.detect_archetypes()
  ↓
emits <wg archetype="incident" score="0.90" /> system reminder
  ↓
agent invokes /wicked-garden:archetype:incident OR auto-routes
  ↓
skills/archetype/SKILL.md → loads refs/incident.md (the playbook)
  ↓
agent runs: triage → investigate → mitigate → resolve → followup
  ↓
HITL discipline enforced per the archetype (mitigate is hard:*)
```

Each archetype's playbook documents its phases, what it produces, where the human gates are, and what NOT to do. No universal pipeline. No rigor-tier dial. Each shape is self-contained.

---

## Why it works

**Steering, not blocking.** Each archetype's playbook tells you what *should* happen. Hard gates exist where they matter (mitigate during an incident, cutover during a migration, final-verdict during review). Everything else is a discrete or continuous gate that auto-passes when the produces contract is met — and "met" is *re-derived*, never self-asserted (see below).

**Per-archetype, not per-phase.** A `migrate` doesn't have a `clarify` phase; a `build` doesn't have a `cutover` phase. Phase names mean different things inside different archetypes. We don't try to factor common phases — that's how the v6 universal pipeline emerged, and it forced every kind of work into the same shape.

**The brain carries knowledge across sessions.** Decisions, gotchas, and patterns persist via [wicked-brain](https://github.com/mikeparcewski/wicked-brain) and surface when relevant. Wicked Garden's archetype detector + steering directives don't replace context — they sit on top of it.

**The bus carries the audit trail.** Every meaningful event flows through [wicked-bus](https://github.com/mikeparcewski/wicked-bus). The v6–v10 "bus-as-truth" enforcement (signed dispatches, projection resolvers per event type) is gone; the bus is now an audit substrate, not a gate enforcement mechanism. Archetypes own their own discipline.

**Evidence is re-derived, not asserted.** A produces-gate doesn't go green because an agent said "done." It re-derives through [wicked-vault](https://www.npmjs.com/package/wicked-vault) — the evidence is re-hashed and its verifier re-run, never trusting a cached status. A claimed-but-false "tests pass" is **REJECTED**; a missing vault **fails closed** rather than passing on a self-assertion. Hard gates (review, incident, migrate) additionally require an *independent* judgment — the evaluator is not the agent that did the work. This is what makes "auto-passes when the produces contract is met" trustworthy: *met* means re-derived.

---

## What's in the box

- **9 work-shape archetypes** with playbooks, slash commands, and a detector.
- **Vault-backed gates** — every gating archetype re-derives its produces through [wicked-vault](https://www.npmjs.com/package/wicked-vault) (required), fail-closed. "Done" can't be asserted into truth.
- **The compiler** (`/wicked-garden:compile`) — detect a repo's test/lint/build commands and emit a self-contained, vault-backed build gate into `<repo>/.wicked/`. It runs with **no wicked-garden runtime present** (resolves the vault via `npx`), and can install the triggers that fire it (pre-push hook / GitHub Actions).
- **Hooks** for prompt classification, tool tracking, session lifecycle.
- **Domain skills + agents** across engineering, platform, product, data, jam, search, agentic, persona, and delivery — invoked by archetypes when their work needs domain expertise.
- **wicked-brain integration** for persistent memory across sessions.
- **wicked-bus integration** for the audit trail.

---

## Install

```bash
# In Claude Code
/plugin install wicked-garden

# First time setup (verifies the required peers below)
/wicked-garden:setup
```

Required peers (`/wicked-garden:setup` checks these and blocks without them):
```bash
npx wicked-testing install     # evidence-gated acceptance testing (≥ 0.3)
npx wicked-vault-install       # the honest-evidence backend gates re-derive against (≥ 0.3)
```

Recommended companions:
```bash
/plugin install wicked-brain   # session memory + cited search
/plugin install wicked-bus     # event audit substrate
```

---

## Quick start

```bash
# Let the hook auto-route a prompt
"implement caching for the dashboard"
# → emits <wg archetype="build" score="0.55" /> → invokes the build archetype

# Or invoke an archetype directly
/wicked-garden:archetype:incident "checkout 5xx spiking"
/wicked-garden:archetype:migrate  "drop legacy_id column with backfill"
/wicked-garden:archetype:decide   "redis or memcached for sessions"
/wicked-garden:archetype:specify  "write acceptance criteria for the export feature"
```

Each command loads `skills/archetype/refs/{archetype}.md` and runs the per-archetype phase shape.

```bash
# Compile a self-contained, vault-backed gate into ANY repo
# (the emitted gate runs with no wicked-garden runtime present)
/wicked-garden:compile ~/path/to/repo --trigger ci
```

---

## Principles

- **Steering, not blocking.** Tell the agent what should happen; hard gates exist only where they matter.
- **Per-archetype, not per-phase.** Each work shape is self-contained.
- **Slim body contract.** Command and skill bodies stay small; refs/ carry the detail.
- **Partner, not host platform.** Use Claude Code's native primitives (`TaskCreate`, `Task()`, system reminders, skill progressive loading); don't reimplement them.

---

## Documentation

- `docs/v11/archetypes.md` — design notes for the v11 reframe (the why)
- `.claude/CLAUDE.md` — repo-internal guidance for Claude
- `ETHOS.md` — what we believe, refuse, optimize for
- `CHANGELOG.md` — release history (v11+ live; pre-v11 in git tags)

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) ≥ 1.0
- Python 3.9+ (stdlib only for hook scripts)
- Node.js + `npx` — required by `wicked-vault` (the evidence backend) and `wicked-testing`
- **Required peers:** `wicked-testing` (≥ 0.3) and `wicked-vault` (≥ 0.3, the backend gates re-derive against). `/wicked-garden:setup` verifies both and blocks without them.
- Optional: `wicked-brain` (session memory + search), `wicked-bus` (audit trail)

---

## License

MIT. See [LICENSE](LICENSE).
