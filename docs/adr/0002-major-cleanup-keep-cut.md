# ADR 0002 — Major cleanup: collapse rubric-wrappers to skills; keep only what the agent actually uses

- **Status:** Accepted — **fully executed**. All domains collapsed (product #910; engineering #911; platform #912; data+delivery #913; agentic+jam+persona+smaht #914), orphan agents purged via `scripts/ci/find_orphan_agents.py`, and `components.json` re-derived via `scripts/ci/sync_components.py`. End state: 90 commands, 40 agents (from 56), 71 skills.
- **Date:** 2026-06-09

## The test

The customer is the AI coding agent (and, downstream, the human reading its output and *other-repo* agents that load these skills). A feature **earns its current shape only if it does at least one of:**
1. **makes the agent's life easier** (a capability/ergonomic the agent lacks natively), or
2. **greatly reduces tokens** (vs. the agent's native Read/Grep/Bash/subagent path), or
3. **improves the quality of the final output** (catches errors, enforces evidence, adds a perspective the agent can't produce alone).

Most "commands" in the garden are a checklist the agent already applies, wrapped in a `Task(subagent)` hop that costs *more* tokens and latency for the *same* output. The hop fails all three — but **the rubric inside it usually doesn't.** The knowledge is the asset; the dispatch is the tax.

So the default disposition is **COLLAPSE-TO-SKILL, not DELETE.** The rubric/knowledge moves to an on-demand `skills/*/refs/<name>.md` file (progressive disclosure → near-zero idle context cost — it loads only when the command runs), and the command becomes a **slim body that loads the ref and does the work INLINE** (a `Read` of the ref, then apply directly — no `Task`/subagent dispatch).

This is grounded in a full hands-on pass: every domain was invoked and judged against native tools.

## Dispositions

- **COLLAPSE (default)** — rubric → `skills/*/refs/`; command → slim inline body, no dispatch. The functionality survives; only the hop is removed.
- **KEEP DISPATCH** — only where dispatch genuinely earns it: **real parallelism** (3-4 lenses running at once), **context isolation** for a huge payload, a **real external tool**, or an **independent gate** (an evaluator that must not be the agent that did the work).
- **DELETE** — only the truly-dead: already-removed `crew:archive` / `delivery:process-health`, plus `smaht:propose-skills`, the dead half of `smaht:state`, and `persona:submit`. These have no rubric worth rescuing.

## KEEP (earns its place)

| Feature | Why (criterion) |
|---|---|
| `prove` + the produces-gate (vault/loom, outputs + attestation + semantic) | **output** — stops false "done"; no native equivalent |
| `/compile` | **easier** — emits a self-contained gate into any repo |
| code-graph (codegraph + injected-edge extractors) → `search:blast-radius`, `search:lineage` | **output + tokens** — finds injected relationships grep can't; impact in one query vs. reading many files |
| wicked-patch (`rename`/`add-field`/`remove`/`apply`) — once wired to the graph DB | **easier + output** — deterministic multi-file refactor |
| `jam:council` / multi-model | **output** — real external-model perspective the agent can't produce alone |
| `jam:brainstorm` / `revisit` (the wicked-brain decision-memory loop) | **output** — longitudinal decision/outcome memory |
| `smaht:briefing` | **tokens** — one event-store query replaces stitching git+memory+tasks |
| `data:ontology` | **output** — real RDF-vocabulary engine (beats free-recall) |
| `persona:as` (built-in personas) + `persona:list` | **output** — hand-authored constraints/memories measurably steer; cheap discovery |
| `platform:security` (now drives real `gitleaks`/`semgrep`) | **output** — real SAST/secrets, not grep-guessing |
| `platform:toolchain` | **tokens/easier** — fast deterministic CLI inventory |
| wicked-testing integration (`acceptance`/`run`/`plan`/`review`) | **output** — evidence-gated testing backbone |
| archetype **gate** + actionable steering (emits the `prove` one-liner) | **output** — turns the principle into a reflex |
| Core plumbing: `setup`, `where-am-i`, `help`, `intent`, `reset`, `classify`, hooks | load-bearing |

## COLLAPSE (default — fails the hop test, but the rubric is worth keeping)

These are `Task(subagent)` rubric-wrappers: a checklist the agent already applies, behind a hop that costs more tokens for the same result. **The hop goes; the rubric becomes an on-demand `skills/*/refs/<name>.md`; the command runs it inline.** Roughly ~42 commands, plus the agents that exist *only* as their dispatch targets (those go; agents still referenced by a surviving command/skill stay).

| Domain | Collapse | Note |
|---|---|---|
| product | ✅ **EXECUTED — all 12** (`a11y`,`ux`,`ux-review`,`elicit`,`strategy`,`mockup`,`screenshot`,`analyze`,`synthesize`,`listen`,`align`,`acceptance`) | The pattern. Each rubric is now `skills/product/refs/<name>.md`, loaded inline. **Kept dispatch** only for the genuine multi-lens cases: `ux-review --focus all` (4 lenses) and `strategy --focus all` (2 lenses). Removed the dispatch-only agents `ux-analyst`, `user-voice`, `mockup-generator`; kept the rest (still referenced). `acceptance --scenarios` wicked-testing tie-in preserved in the ref. |
| engineering | `debug`, `plan`, `arch`, `review`, `docs` | `debug` duplicates `superpowers:systematic-debugging` (collapse to a pointer); rest collapse with R1–R6 preserved as a ref. |
| platform | `compliance`, `audit`, `incident`, `health`, `traces`, `actions`, `gh`, `infra` | keep `security` + `toolchain`. Collapse the SOC2/HIPAA audit checklist into a ref. |
| data | `analyze`, `data`, `pipeline`, `ml` | keep `ontology`. |
| delivery | `experiment`, `report`, `rollout`, `setup` | document templates → refs; `process-health` already deleted. Domain effectively retired. |
| agentic | `review`, `audit`, `design`, `frameworks` | scripts emit false signals (drop those); collapse the T&S 8-layer rubric into a ref. |
| jam | `quick`, `perspectives` (single-model role-play); `thinking`/`transcript`/`persona` (retrieval utils) | keep `council`/`brainstorm`/`revisit`. |
| persona | `define` | thin (define can't set the rich fields) — collapse. Keep `as`/`list`. |
| smaht | `state` (half-dead — collapse the live half) | keep `briefing`; `events-import` is a one-time util (keep or archive). |

## DELETE (truly-dead — no rubric to rescue)

`crew:archive` + `delivery:process-health` (already removed), `smaht:propose-skills` (weak signal), the dead half of `smaht:state`, `persona:submit` (no-op stub). Nothing of value is lost.

## What we lose

**With collapse, functionality lost ≈ 0.** The rubric, checklist, and capability survive verbatim as a `refs/` file — still discoverable (it's in the skill tree), still loadable on demand, still valid on **other repos and other toolchains** (a ref is portable knowledge; a dispatch hop is not). What's removed is *only the token-burning dispatch hop* — the parent no longer pays subagent spin-up + round-trip for a checklist it can apply itself.

The win is **dual-customer**:
- **the AI agent** — fewer tokens, lower latency, the rubric inlined exactly when it's needed (progressive disclosure keeps idle context near zero);
- **the human** — a smaller, legible surface; the rubric reads as documentation;
- **other-repo agents** — `skills/*/refs/` ships as portable knowledge they can load without the garden's dispatch machinery.

Only the genuinely-dead DELETE rows lose anything, and those had no rubric worth keeping.

## Estimated impact

- Commands: stay numerically similar (collapsed, not deleted) but each is **slim** — the parent-context cost per command drops to a few lines; the rubric body moves to on-demand `refs/`.
- Agents: **down sharply** (~56 → ~20) — the dispatch-only targets go; the rubric-bearing ones survive as refs.
- Net: idle parent-context shrinks (slim bodies); per-invocation tokens drop (no hop); **zero capability lost**. The surface finally matches the "thin, high-value toolkit" the agent actually reaches for.

## Phased execution (each phase = one worktree PR, parallelizable, suite-gated)

0. ✅ Remove dead commands (`crew:archive`, `delivery:process-health`).
1. ✅ **product** domain collapse (#910) — the executed pattern the rest followed.
2. ✅ **engineering** collapse (#911) — arch/debug/docs/plan/review; patch family kept.
3. ✅ **platform** collapse (#912) — 8 wrappers; security/toolchain/assert/plugin-health kept.
4. ✅ **data + delivery** collapse (#913) — keep ontology + setup.
5. ✅ **agentic + jam + persona + smaht** collapse (#914) — keep council/brainstorm/revisit/briefing; delete persona:submit + smaht:propose-skills.
6. ✅ **Agent-orphan purge + registry sync** — `find_orphan_agents.py` did a reachability analysis (roots = commands/skills/scenarios/registries, **not** the generated `components.json`); removed 3 truly-orphaned delivery agents (cloud-cost-intelligence, delivery-manager, progress-tracker) while correctly keeping the 4 that live scenarios still dispatch to. `sync_components.py` re-derived the manifest; `docs/domains.md` updated.

Each phase was reversible (git), suite-gated, and PR'd. Two reusable anti-drift tools fell out of phase 6: `find_orphan_agents.py` (dead-agent detection) and `sync_components.py` (manifest never silently drifts again).
