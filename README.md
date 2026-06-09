```
           _      _            _                           _            
 __      _(_) ___| | _____  __| |       __ _  __ _ _ __ __| | ___ _ __  
 \ \ /\ / / |/ __| |/ / _ \/ _` |_____ / _` |/ _` | '__/ _` |/ _ \ '_ \ 
  \ V  V /| | (__|   <  __/ (_| |_____| (_| | (_| | | | (_| |  __/ | | |
   \_/\_/ |_|\___|_|\_\___|\__,_|      \__, |\__,_|_|  \__,_|\___|_| |_|
                                       |___/                             
```

# Wicked Garden

**Gap-filling capabilities for modern coding agents. Don't fight the harness — fill its gaps.**

> **Identity at a glance:** see [`ETHOS.md`](ETHOS.md) — what we believe, what we refuse, what we optimize for.

---

## The premise

Coding agents have become **harnesses**. Claude Code, Codex, Cursor, Antigravity, Aider, OpenCode, Gemini CLI, Zed (ACP), Kiro — these aren't autocomplete anymore. They plan. They parallelize and swarm. And each has an *opinionated, prescriptive way it wants to work.*

Most plugins fight that. They re-implement planning, impose their own workflow, and try to make the agent behave the way the plugin wants. You end up wrestling your own tools.

**Wicked Garden does the opposite.** It assumes the harness is good at what it's good at — planning and execution — and fills the gaps the harness *can't* fill on its own. It rides on top of how your agent already works; it doesn't replace it.

---

## The gaps it fills

A great planner-executor still can't do these. Wicked Garden can:

| Gap in the harness | What Wicked Garden adds |
|---|---|
| **It claims "done."** The harness will cheerfully say *"tests pass"* — sometimes when they don't. It has no way to re-derive that and refuse a false claim. | **Proof, not claims.** A gate re-runs the verifier and re-hashes the evidence ([wicked-loom](https://www.npmjs.com/package/wicked-loom) → [wicked-vault](https://www.npmjs.com/package/wicked-vault)). A false "done" is **rejected**; a missing backend **fails closed**. Gates that matter need an *independent* attestation — not the agent that did the work. |
| **It can only see literal references.** Read + grep miss relationships wired by a *string through a registry* — an event producer→consumer, a command→agent dispatch, an agent→capability. | **Relationships grep can't see.** `search:blast-radius` / `search:lineage` run on a real code graph ([codegraph](https://github.com/colbymchenry/codegraph)) **plus injected edges** the static graph and grep both miss. |
| **Refactors are best-effort sweeps.** | **Deterministic multi-file refactor.** wicked-patch plans a rename/field-change as an operation over the symbol graph, not a hopeful find-replace. |
| **It forgets when the session ends.** | **Memory across sessions.** [wicked-brain](https://www.npmjs.com/package/wicked-brain) keeps decisions, patterns, and gotchas — session 47 knows what session 1 decided. |
| **A second opinion is the same model arguing with itself.** | **A real external opinion.** `jam:council` runs a genuine multi-model panel (Gemini / Codex / …) for hard calls. |
| **Domain expertise is re-derived from scratch each time.** | **Expertise on demand, portable.** Hard-won rubrics — WCAG, CWE, SOC2, coding standards — load only when needed and travel to any repo as skill-refs. |
| **The agent grades its own homework.** | **Evidence-gated testing.** [wicked-testing](https://www.npmjs.com/package/wicked-testing) separates the author, the executor, and the reviewer, so a verdict isn't self-graded. |

The throughline: *done is re-derived, not asserted.* You get verdicts you can trust on the first read, not green checkmarks you can't.

---

## What it is *not*

- **Not a workflow it imposes.** Your harness still plans and executes. Wicked Garden reads the *shape* of the work to apply the right gate and the right rigor — then gets out of the way.
- **Not a re-implementation** of the planning and swarm your harness already does well.
- **Not Claude-only at the core.** It ships as a Claude Code plugin, but the engine is CLI/npm peers (testing · vault · brain · bus · loom) and the gate **compiles into any repo and runs with no wicked-garden installed** (`/wicked-garden:compile`). The model is *stand on the harness, fill its gaps, hand off* — never *absorb.*

### How it stays out of the way: work-shape, not pipeline

There is **no universal pipeline** to follow. A `UserPromptSubmit` hook reads the *shape* of each prompt — a typo is `triage` (no ceremony), a feature is `build`, a schema change is `build + migrate` — and that shape decides only one thing: **how much rigor, and which gap-fillers, this work needs.** A typo gets nothing; a migration cutover gets a hard, independently-attested gate with a rollback proof. Steering, not blocking — the harness drives.

<details><summary>The nine work-shapes (rigor follows shape)</summary>

| Shape | Produces | Gate |
|---|---|---|
| triage | routing decision | none |
| explore | option set / hypothesis | continuous HITL |
| specify | SMART acceptance criteria | discrete |
| decide | ADR / decision artifact | discrete |
| build | shipped code / test report | discrete review |
| review | verdict / remediation list | **hard:final-verdict** |
| ship | rollout verdict / SLO snapshot | discrete |
| incident | mitigation / RCA / followup | **hard:mitigate** |
| migrate | shape change / rollback proof | **hard:cutover** |

Why work-shapes and not one pipeline → [`docs/v11/archetypes.md`](docs/v11/archetypes.md).
</details>

---

## Install

```bash
# In Claude Code
/plugin install wicked-garden
/wicked-garden:setup            # verifies the required peers below
```

The honest-evidence model needs five CLI/npm peers — `/wicked-garden:setup` verifies all five and blocks without them (required at install, resilient to a transient runtime outage):

```bash
npx wicked-testing install     # evidence-gated acceptance testing (≥ 0.3)
npx wicked-vault-install       # the honest-evidence backend gates re-derive against (≥ 0.3)
/plugin install wicked-brain   # cross-session memory + cited search
/plugin install wicked-bus     # event audit substrate
npm i -g wicked-loom           # the gate engine — re-derives produces via the vault (or via npx)
```

Optional, enables the code graph: `npx @colbymchenry/codegraph` (Node ≥ 22.5) powers `search:blast-radius` / `lineage` / `hotspots` and wicked-patch. See [`docs/required-peers.md`](docs/required-peers.md).

---

## Quick start

```bash
# Just work — the hook reads the shape and applies the right rigor underneath
"implement caching for the dashboard"          # → build
/wicked-garden:archetype:migrate "drop legacy_id column with backfill"   # hard cutover gate

# Fill a specific gap, directly
/wicked-garden:prove                            # re-derive "done" from evidence (fail-closed)
/wicked-garden:search:blast-radius emit_event   # impact incl. injected edges grep can't see
/wicked-garden:engineering:rename oldField newField   # deterministic multi-file refactor
/wicked-garden:jam:council "redis or memcached for sessions"   # real multi-model panel

# Stamp the evidence gate into ANY repo — runs with no wicked-garden installed
/wicked-garden:compile ~/path/to/repo --trigger ci
```

---

## Principles

- **Don't fight the harness.** Fill the gaps it can't fill; never re-implement what it already does well.
- **Done is re-derived, not asserted.** Every gate recomputes the evidence; hard gates are signed by an independent reviewer.
- **Steering, not blocking.** Rigor follows the shape of the work, applied only where it matters.
- **Enforcement that travels.** The gate compiles into any repo and runs without wicked-garden present.
- **Native primitives over bespoke abstractions.** Extend the harness's `TaskCreate`/`Task()`/skills/hooks — don't replace them.

---

## Documentation

- [`ETHOS.md`](ETHOS.md) — what we believe, refuse, optimize for
- [`docs/getting-started.md`](docs/getting-started.md) — first hour
- [`docs/domains.md`](docs/domains.md) — the skill + agent families
- [`docs/required-peers.md`](docs/required-peers.md) · [`docs/compiler.md`](docs/compiler.md) — the five peers, and the compiler
- [`docs/v11/archetypes.md`](docs/v11/archetypes.md) — why work-shapes, not a pipeline

---

## Requirements

- A coding-agent harness — [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) ≥ 1.0 for the plugin surface; the peers + compiled gate are harness-agnostic CLIs.
- Python 3.9+ (stdlib only for hooks) · Node.js + `npx` (for the peers and the optional code graph).
- **Five required peers:** `wicked-testing` · `wicked-vault` · `wicked-brain` · `wicked-bus` · `wicked-loom`. `/wicked-garden:setup` verifies all five — required at install, resilient at runtime.

## License

MIT. See [LICENSE](LICENSE).
