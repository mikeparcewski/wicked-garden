```
           _      _            _                           _            
 __      _(_) ___| | _____  __| |       __ _  __ _ _ __ __| | ___ _ __  
 \ \ /\ / / |/ __| |/ / _ \/ _` |_____ / _` |/ _` | '__/ _` |/ _ \ '_ \ 
  \ V  V /| | (__|   <  __/ (_| |_____| (_| | (_| | | | (_| |  __/ | | |
   \_/\_/ |_|\___|_|\_\___|\__,_|      \__, |\__,_|_|  \__,_|\___|_| |_|
                                       |___/                             
```

# Wicked Garden

**Your coding agent already plans and swarms. Wicked Garden fills the gaps it can't fill alone — and otherwise gets out of the way.**

> Identity & beliefs → [`ETHOS.md`](ETHOS.md). How it works → [`CLAUDE.md`](.claude/CLAUDE.md).

---

## The premise

Coding agents grew up. Claude Code, Codex, Cursor, Antigravity, Aider, OpenCode, Gemini CLI, Zed/ACP — they're not autocomplete anymore. They plan. They parallelize. And each has *strong opinions* about how it likes to work.

Most plugins try to boss them around — re-implement planning, impose a workflow, make the agent dance. You end up fighting your own tools.

**Wicked Garden refuses to wrestle the harness.** It assumes your agent is good at the things it's good at, and fills the gaps it *can't* fill on its own.

## The gaps it fills

| Your harness… | Wicked Garden… |
|---|---|
| says *"tests pass"* (sometimes it's lying) | re-runs the proof. False "done" → **rejected.** Missing backend → **fails closed.** Never a vacuous green. |
| greps and reads — blind to string-wired links | sees the **injected edges** (event→consumer, command→agent, agent→capability) grep never will → `blast-radius`, `lineage` |
| refactors on a hope and a prayer | renames across files as a **graph operation**, not find-replace roulette → wicked-patch |
| forgets everything at `exit` | remembers what session 1 decided when you're in session 47 → wicked-brain |
| asks *itself* for a second opinion | convenes a **real multi-model panel** (Gemini / Codex / …) → `jam:council` |
| re-derives WCAG/CWE/SOC2 from memory every time | loads the rubric on demand, ships it to any repo |
| grades its own homework | author ≠ executor ≠ reviewer → evidence-gated testing |

The throughline: **done is re-derived, not asserted.** Verdicts you can trust on the first read — not green checkmarks you can't.

## What it's *not*

- **Not a workflow it forces on you.** Your harness still drives. Wicked Garden reads the *shape* of the work, applies the right amount of rigor, and steps back.
- **Not a reinvention** of the planning and swarm your agent already nails.
- **Not Claude-only under the hood.** Ships as a Claude Code plugin, but the engine is CLI/npm peers — and the gate **compiles into any repo and runs with no wicked-garden installed** (`/wicked-garden:compile`). Stand on the harness, fill its gaps, hand off. Never absorb.

<details><summary><b>How it stays out of the way: work-shape, not pipeline</b></summary>

No universal pipeline to obey. A hook reads each prompt's *shape* and that decides one thing: **how much rigor this work earns.** A typo (`triage`) gets none; a migration cutover (`migrate`) gets a hard, independently-attested gate with a rollback proof. Nine shapes — `triage · explore · specify · decide · build · review · ship · incident · migrate` — steering, not blocking. Why shapes and not one pipeline → [`docs/v11/archetypes.md`](docs/v11/archetypes.md).
</details>

---

## Install

```bash
/plugin install wicked-garden      # in Claude Code
/wicked-garden:setup               # verifies the five peers below
```

Honest evidence needs five CLI/npm peers — setup verifies all five and blocks without them (required at install, resilient to a transient runtime blip):

```bash
npx wicked-testing install     # evidence-gated acceptance testing (≥ 0.3)
npx wicked-vault-install       # the honest-evidence backend gates re-derive against (≥ 0.3)
/plugin install wicked-brain   # cross-session memory + cited search
/plugin install wicked-bus     # event audit trail
npm i -g wicked-loom           # the gate engine (re-derives produces via the vault; or via npx)
```

Optional, lights up the code graph: `npx @colbymchenry/codegraph` (Node ≥ 22.5) → powers `blast-radius` / `lineage` / `hotspots` / wicked-patch. Details: [`docs/required-peers.md`](docs/required-peers.md).

## Try it

```bash
# Just work — the hook applies the right rigor underneath, quietly
"implement caching for the dashboard"

# Or reach for a gap-filler on purpose
/wicked-garden:prove                              # re-derive "done" from evidence (fail-closed)
/wicked-garden:search:blast-radius emit_event     # impact, incl. edges grep can't see
/wicked-garden:engineering:rename oldField newField   # deterministic, graph-driven
/wicked-garden:jam:council "redis or memcached?"  # a panel that isn't just you

# Stamp the evidence gate into ANY repo (runs with no wicked-garden installed)
/wicked-garden:compile ~/path/to/repo --trigger ci
```

---

## Principles

- **Don't fight the harness.** Fill the gaps; never re-implement what it already does well.
- **Done is re-derived, not asserted.** Every gate recomputes the evidence; the gates that matter are signed by someone who isn't the author.
- **Steering, not blocking.** Rigor follows the shape of the work, applied only where it earns its keep.
- **Enforcement that travels.** The gate compiles into any repo and runs without wicked-garden present.
- **Borrow the harness's primitives.** Extend `TaskCreate`/`Task()`/skills/hooks — don't rebuild them.

## More

[`ETHOS.md`](ETHOS.md) · [`docs/getting-started.md`](docs/getting-started.md) · [`docs/domains.md`](docs/domains.md) · [`docs/required-peers.md`](docs/required-peers.md) · [`docs/compiler.md`](docs/compiler.md)

## Requirements

A coding-agent harness ([Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) ≥ 1.0 for the plugin surface; the peers + compiled gate are harness-agnostic) · Python 3.9+ (stdlib-only hooks) · Node + `npx` · the five peers (`wicked-testing` · `wicked-vault` · `wicked-brain` · `wicked-bus` · `wicked-loom`).

## License

MIT. See [LICENSE](LICENSE).
