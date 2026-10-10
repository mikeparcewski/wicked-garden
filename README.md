```
           _      _            _                           _            
 __      _(_) ___| | _____  __| |       __ _  __ _ _ __ __| | ___ _ __  
 \ \ /\ / / |/ __| |/ / _ \/ _` |_____ / _` |/ _` | '__/ _` |/ _ \ '_ \ 
  \ V  V /| | (__|   <  __/ (_| |_____| (_| | (_| | | | (_| |  __/ | | |
   \_/\_/ |_|\___|_|\_\___|\__,_|      \__, |\__,_|_|  \__,_|\___|_| |_|
                                       |___/                             
```

# wicked-garden

**Your coding agent already plans and swarms. wicked-garden is the curated toolkit for what it can't do alone.**

> 📖 Docs → [wg.wickedagile.com](https://wg.wickedagile.com). Identity & beliefs → [`ETHOS.md`](ETHOS.md). How it works → [`CLAUDE.md`](.claude/CLAUDE.md).

---

## The premise

Coding agents grew up. Claude Code, Codex, Cursor, Antigravity, Aider, OpenCode, Zed/ACP — they're not autocomplete anymore. They plan. They parallelize. And each has *strong opinions* about how it likes to work.

Most plugins try to boss them around — re-implement planning, impose a workflow, make the agent dance. You end up fighting your own tools.

**wicked-garden refuses to wrestle the harness.** It assumes your agent is good at the things it's good at, and fills the gaps it *can't* fill on its own.

## The gaps it fills

| Your harness… | wicked-garden… |
|---|---|
| says *"tests pass"* (sometimes it's lying) | re-runs the proof. False "done" → **rejected.** Missing backend → **fails closed.** Never a vacuous green. |
| greps and reads — blind to string-wired links | sees the **injected edges** (event→consumer, command→agent, agent→capability) grep never will → `blast-radius`, `lineage` |
| refactors on a hope and a prayer | renames across files as a **graph operation**, not find-replace roulette → wicked-patch |
| forgets everything at `exit` | remembers what session 1 decided when you're in session 47 → the mem domain over wicked-estate |
| re-derives *how to work in this repo* every task — which file owns the bug, the wiring step, the test command | loads the repo's own playbooks (`fix-bug`/`add-feature`/`verify`…), generated from HEAD → wicked-understanding |
| asks *itself* for a second opinion | convenes a **review panel** → the jam skill's `council` action: usable external CLIs (Antigravity / Codex / …) take the seats; with fewer than two it fills them with isolated same-family workers and **labels them as weaker diversity**, and below two isolated seats it reports *no quorum* instead of synthesizing |
| re-derives WCAG/CWE/SOC2 from memory every time | loads the rubric on demand, ships it to any repo |
| grades its own homework | author ≠ executor ≠ reviewer as separate workers → evidence-gated testing (the `qe` domain) |

The throughline: **done is re-derived, not asserted** — wherever the gate actually runs. Which entry paths block and which only advise is spelled out in [What blocks, what advises](#what-blocks-what-advises).

## What it's *not*

- **Not a workflow it forces on you.** Your harness still drives. wicked-garden reads the *shape* of the work, applies the right amount of rigor, and steps back.
- **Not a reinvention** of the planning and swarm your agent already nails.
- **Not Claude-only under the hood.** Ships as a Claude Code plugin, but the engine is CLI/npm peers — and the gate **compiles into any repo and runs with no wicked-garden installed** (`/wicked-garden-prove compile`). Stand on the harness, fill its gaps, hand off. Never absorb.

<details><summary><b>How it stays out of the way: work-shape, not pipeline</b></summary>

No universal pipeline to obey. A hook reads each prompt's *shape* and that decides one thing: **how much rigor this work earns.** A typo (`triage`) gets none; a migration cutover (`migrate`) gets a hard, independently-attested gate with a rollback proof. Ten shapes — `triage · explore · specify · decide · build · review · ship · incident · migrate · modernize` — steering, not blocking. Why shapes and not one pipeline → [`docs/v11/archetypes.md`](docs/v11/archetypes.md).
</details>

---

## Install

```bash
claude plugins marketplace add mikeparcewski/wicked-garden
claude plugins install wicked-garden
```

Or use the family installer — [`npx wicked-installer`](https://www.npmjs.com/package/wicked-installer)
installs/updates the whole wicked-\* family (garden, its peers, and the rest).

> `npx wicked-garden install` makes a bare, **unregistered** copy under `<config-dir>/plugins/wicked-garden`
> (honours `CLAUDE_CONFIG_DIR` / `--claude-home`, `--dry-run`); registration is
> `npx wicked-installer install wicked-garden`. The copy is staged in `plugins/.staging-wicked-garden-<pid>-<hex>`
> and swapped in atomically; a previous copy passes through `plugins/.old-wicked-garden-<pid>-<hex>` and is removed only
> after the installed tree verified (a tree that fails verification is set aside as `plugins/.failed-wicked-garden-<pid>-<hex>`
> and the previous copy is put back). Those transient dirs are **not plugins**; a leftover after an interrupted install is
> safe to delete (`status` lists them).

**Other CLIs (Codex, OpenCode, Pi, Antigravity)** — `npx wicked-installer install-<cli> wicked-garden` copies
the skills only (flat, by name — no `scripts/`, no venv). Every skill's text works there as written: own files are
referenced relative to the skill's directory, other skills by name, and the shared runtime only through the
launcher — `wicked-garden run scripts/<x>.py …`. So for script-backed skills the runtime prerequisite on those
CLIs is `npm i -g wicked-garden` (or `npx wicked-garden`); the launcher resolves the plugin root and the Python
interpreter itself (`wicked-garden doctor` shows what it found) and never writes under the root. Prose-only
skills need nothing. Under wicked-crew the same launcher points at the run's snapshot via `WICKED_GARDEN_ROOT`.

Then, in a Claude Code session:

```bash
/wicked-garden-core setup          # verifies peers; blocks only on the one the gate needs
```

**One required peer, the rest opt-in.** The evidence gate is the floor we won't fake, so it needs one external peer — setup blocks without it:

```bash
npm i -g wicked-vault          # wicked-vault (≥ 0.5.0), the honest-evidence backend the gate re-derives against
```

> The gate/resolve engine (formerly the separate `wicked-loom` package) is now **absorbed in-package** as of v12.27.0 (`scripts/loom/`) — nothing extra to install. The gate re-hashes recorded evidence and re-runs its verifier through that engine; a false "tests pass" is **rejected**, a missing backend **fails closed**.

The rest of the kit is **opt-in layers** — add what you want, skip the rest and the toolkit still works:

```bash
# wicked-estate — the memory/knowledge layer (cross-session recall + cited search, the "what"):
#   install the `wicked-estate` + `wicked-estate-mcp` binaries onto PATH or ~/.local/bin
npm i -g wicked-bus && npx wicked-bus-install   # the audit-trail layer (fire-and-forget; fail-open without it)
```

> Evidence-gated acceptance testing (author ≠ executor ≠ reviewer) needs no extra install — it ships **in-catalog** as the `qe` domain (`wicked-garden-qe`).

Optional, lights up the code graph: **wicked-estate** (single binary; `wicked-estate index <path>` + the estate MCP server) → powers `blast-radius` / `lineage` / `hotspots` / wicked-patch (ADR 0005 — no external codegraph engine, no Node version floor). Details: [`docs/required-peers.md`](docs/required-peers.md).

## Try it

```bash
# Just work — in Claude Code the plugin's hook reads the work's shape and suggests the rigor (advisory)
"implement caching for the dashboard"

# Or reach for a gap-filler on purpose — everything is a skill now
/wicked-garden-prove                              # re-derive "done" from evidence (fail-closed)
/wicked-garden-search blast-radius emit_event     # impact, incl. edges grep can't see
/wicked-garden-engineering-patch rename oldField newField  # deterministic, graph-driven
/wicked-garden-jam council "redis or memcached?"  # a panel; it says which seats were external models

# Stamp the evidence gate into ANY repo (runs with no wicked-garden installed)
/wicked-garden-prove compile ~/path/to/repo --trigger ci
```

---

## What blocks, what advises

"Done is re-derived" is a property of the **gate**, not of every surface the toolkit touches. What a
false "done" runs into depends on the host and the entry path:

| Host · entry path | Blocks | Only advises |
|---|---|---|
| **Any host — the gate, invoked** (`wicked-garden-prove`, an archetype's produces-gate → `scripts/qe/vault_gate.py`) | Re-hashes the recorded evidence and re-runs its verifier through `wicked-vault`: a false claim is **rejected**, an unresolvable backend **fails closed** (`gate: "unavailable"`). Hard gates also need an attestation under an explicit `--actor` that differs from the author's — a local label, not an authenticated identity. The verdict stops whatever acts on it. | With `--no-require`, a backend that cannot run falls back to the claim-only tracker and says so (`claim-only`, not re-derived); a working backend still re-derives. |
| **Claude Code — plugin hooks** (plain conversation, "just work") | `PreToolUse` denies a few specific tool calls: native `EnterPlanMode` (always — planning goes through the archetype playbooks), writes to `MEMORY.md` / the auto-memory dir, build-phase writes on a high-complexity crew project with no challenge artifacts, a `phase_manager.py approve` whose gate preflight fails, a worktree cwd leak, and — only in `strict` mode (default `warn`) — invalid task metadata (`WG_TASK_METADATA`) and orphan state writes (`WG_BUS_EMIT_LINT`). Prompts are held until `/wicked-garden-core setup` completes. | Everything else. The archetype detector **steers** (it does not gate), the Stop-time claim sentinel is a fail-open **nudge** when a "done/passing" claim has no verdict for HEAD, `TaskCompleted` never blocks, and output governance is advisory. A completion claim is **not** blocked unless a gate is run. |
| **Codex · OpenCode · Pi · Antigravity — skills only** (`npx wicked-installer install-<cli> wicked-garden`) | Nothing by itself: no plugin hooks are installed on those hosts. | The skill text tells the agent to run the gate; it blocks only when the agent does run it (and the launcher + `wicked-vault` are present). |
| **Compiled repo gate** (`/wicked-garden-prove compile <repo> --trigger hook,ci`) | `.wicked/gate.py` fails the **git pre-push hook / CI job** it is wired into, with no wicked-garden installed. | Without a trigger it is a script you run by hand. |
| **wicked-crew governed run** | crew's engine decides each gated phase deny-dominates, on the layers that actually ran — deterministic floors, repo checks, policies, a judge. Review moves to a distinct seat when the roster has an eligible one; team runs refuse without one. | An ordinary run on a too-small roster keeps review on the creator seat and labels it "evaluator ≠ creator not held"; a pinned floor with no distinct judge is labelled "floor only"; a phase nothing gated is "approved by default, not verified". |

Garden's own daemon `/council` endpoint is a single-model synthesis (v0.1); the multi-model panel is
the jam skill's `council` action above.

---

## Build on it

The catalog is open: ship your own domain pack — a `wicked-pack.json`
manifest plus `{vendor}-{domain}` router / `{vendor}-{domain}-{role}` fork
workers — and the runtime discovers it without a garden PR: catalog listing,
crew specialist routing, peer-floor probing, same evidence discipline.

```bash
npx wicked-garden pack check ./acme-seo-pack   # the shipped conformance gate
npx wicked-installer pack add acme-seo-pack    # acquire + validate + install + register
npx wicked-garden pack list                    # what the runtime sees
```

Full author guide: [`docs/extending.md`](docs/extending.md).

---

## Principles

- **Don't fight the harness.** Fill the gaps; never re-implement what it already does well.
- **Done is re-derived, not asserted.** Every gate recomputes the evidence; the gates that matter need an attestation recorded under an actor other than the author (a declared label, not an authenticated identity).
- **Steering, not blocking.** Rigor follows the shape of the work, applied only where it earns its keep.
- **Enforcement that travels.** The gate compiles into any repo and runs without wicked-garden present.
- **Borrow the harness's primitives.** Extend `TaskCreate`/`Task()`/skills/hooks — don't rebuild them.

## More

[`ETHOS.md`](ETHOS.md) · [`docs/getting-started.md`](docs/getting-started.md) · [`docs/domains.md`](docs/domains.md) · [`docs/required-peers.md`](docs/required-peers.md) · [`docs/compiler.md`](docs/compiler.md) · [`docs/extending.md`](docs/extending.md)

## Requirements

A coding-agent harness ([Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) ≥ 1.0 for the plugin surface; the peers + compiled gate are harness-agnostic) · Python 3.9+ (stdlib-only hooks) · Node + `npx` · the gate's one required peer (`wicked-vault` ≥ 0.5.0) plus opt-in layers (`wicked-estate` · `wicked-bus`).

## License

MIT. See [LICENSE](LICENSE).
