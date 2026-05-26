```
           _      _            _                           _            
 __      _(_) ___| | _____  __| |       __ _  __ _ _ __ __| | ___ _ __  
 \ \ /\ / / |/ __| |/ / _ \/ _` |_____ / _` |/ _` | '__/ _` |/ _ \ '_ \ 
  \ V  V /| | (__|   <  __/ (_| |_____| (_| | (_| | | | (_| |  __/ | | |
   \_/\_/ |_|\___|_|\_\___|\__,_|      \__, |\__,_|_|  \__,_|\___|_| |_|
                                       |___/                             
```

# Wicked Garden

**An evidence-driven SDLC for Claude Code: it detects the shape of work, applies the rigor that shape needs, verifies "done" through independent re-derived evidence, and preserves decisions, evidence, and learning across sessions. Done is not claimed; done is re-derived.**

> **Identity at a glance:** see [`ETHOS.md`](ETHOS.md) — what we believe, what we refuse, what we optimize for.
>
> **Vision (v11):** work-shape archetypes, not a fixed pipeline. Each prompt routes to one or more archetypes; each archetype owns its phase shape, produces, and human-in-the-loop (HITL) discipline. Steering, not blocking.

---

## Why you'd want it

AI coding assistants confidently announce "tests pass" and "done" — sometimes when neither is true — and the reasoning behind last week's decisions is gone by next session. Wicked Garden doesn't take "done" on faith. Every gate **re-derives** the evidence (re-runs the test command, re-checks the artifact) instead of trusting the claim, and the gates that matter are signed off by an **independent** reviewer — not the agent that did the work. Decisions, evidence, and audit persist across sessions, so session 47 knows what session 1 decided.

You get verdicts you can trust, not green checkmarks you can't. *Done is not claimed; done is re-derived.*

---

## How it works (four beats)

**1 · Detect the shape.** A `UserPromptSubmit` hook classifies your prompt into one or more of nine **work-shape archetypes** — a typo is `triage`, a feature is `build`, a schema change is `build + migrate`. There's no universal pipeline; each shape runs its own phases. (Why archetypes and not one pipeline? → [`docs/v11/archetypes.md`](docs/v11/archetypes.md).)

| Archetype | Phases | Produces | HITL |
|---|---|---|---|
| triage | classify | routing decision | none |
| explore | frame → diverge → converge | option set / hypothesis | continuous |
| specify | elicit → structure → validate | SMART acceptance criteria | discrete:validate |
| decide | brief → options → score → record | ADR / decision artifact | discrete:select |
| ship | canary → ramp → full → soak | rollout verdict / SLO snapshot | discrete:ramp |
| review | scope → assess → findings → remediate-or-accept | verdict / remediation list | hard:final-verdict |
| incident | triage → investigate → mitigate → resolve → followup | mitigation / RCA / followup | hard:mitigate |
| build | plan → implement → test → review | shipped code / test report | discrete:review |
| migrate | plan → expand → backfill → cutover → contract | shape change / rollback proof | hard:cutover |

**2 · Run the archetype.** Each has its own phases, produces contract, and human-in-the-loop (HITL) gates — light for a fix, hard for a migration cutover. Archetypes compose: a schema-changing feature is `build + migrate`; a risky deploy is `ship + review`.

**3 · Gate on re-derived evidence.** At each gate, [wicked-vault](https://www.npmjs.com/package/wicked-vault) re-hashes the evidence and re-runs its verifier — a false "tests pass" is **REJECTED**, a missing backend **fails closed** (never a vacuous pass). Hard gates also require an *independent* attestation: the evaluator is not the agent that did the work.

**4 · Carry it forward.** Decisions, evidence, and audit persist on disk via the four required peers — testing · vault · brain · bus — so the next session resumes with the chain intact.

`/wicked-garden:compile` can stamp that same evidence gate into *any* repo; the emitted gate runs with **no wicked-garden installed**.

---

## What's in the box

- **9 work-shape archetypes** with playbooks, slash commands, and a detector.
- **Vault-backed gates** — every gating archetype re-derives its produces through [wicked-vault](https://www.npmjs.com/package/wicked-vault) (required), fail-closed. "Done" can't be asserted into truth.
- **The compiler** (`/wicked-garden:compile`) — detect a repo's test/lint/build commands and emit a self-contained, vault-backed build gate into `<repo>/.wicked/`. It runs with **no wicked-garden runtime present** (resolves the vault via `npx`), and can install the triggers that fire it (pre-push hook / GitHub Actions).
- **A work-mode status line** — `scripts/statusline.py` renders the live archetype · intent · phase · gate verdict (`🌱 wg │ build·migrate │ intent: feature │ phase: implement │ ⚖ PASS`) at the bottom of the screen, so the detected shape and the gate's honest verdict are always visible. Opt-in via `settings.json` (see [getting-started](docs/getting-started.md#show-the-active-mode-status-line)).
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

Required peers — `/wicked-garden:setup` verifies all four and blocks without them (required at install, resilient to a transient runtime outage):
```bash
npx wicked-testing install     # evidence-gated acceptance testing (≥ 0.3)
npx wicked-vault-install       # the honest-evidence backend gates re-derive against (≥ 0.3)
/plugin install wicked-brain   # cross-session memory + cited search
/plugin install wicked-bus     # event audit substrate
```

See [`docs/required-peers.md`](docs/required-peers.md) for why each is load-bearing.

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
- **Required peers (all four):** `wicked-testing` (≥ 0.3), `wicked-vault` (≥ 0.3, the backend gates re-derive against), `wicked-brain` (cross-session memory + search), `wicked-bus` (audit substrate). `/wicked-garden:setup` verifies all four and blocks without them — required at install, resilient at runtime. See [`docs/required-peers.md`](docs/required-peers.md).

---

## License

MIT. See [LICENSE](LICENSE).
