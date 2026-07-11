# Peers — two required, three opt-in

Wicked Garden is a **curated toolkit**, and like any toolkit you can use the
parts you want. Only one thing is non-negotiable: the **evidence gate**. A gate
that can't re-derive its own evidence is the single thing the toolkit refuses to
fake — so its two peers are required. Everything else is an **opt-in layer**:
install it for the capability it unlocks, skip it and the rest of the kit still
works.

> **History:** v12 briefly made all five peers required infrastructure. That
> maximized the honesty guarantee and minimized adoption — you couldn't try the
> toolkit without standing up five things first. We walked it back: the gate
> stays required (that's the floor), the other three became opt-in layers.

## Required — the evidence gate (setup blocks without these)

| Peer | What it does | Install |
|------|--------------|---------|
| **wicked-vault** | The honest-evidence backend the gate re-derives against: record → re-hash + re-run the verifier → cross-check. Never trusts a cached status. | `npx wicked-vault-install` (npm; pinned `^0.3.0`). Resolved at runtime via `WICKED_VAULT_BIN` → config → `PATH` → `node_modules` → `npx wicked-vault`. |
| **wicked-loom** | The gate engine garden drives: peer resolution (`loom resolve`), synchronous fail-closed evidence gating (`loom gate`), and the flow runtime (`loom flow run/status/resume`). It is the *sole* re-derivation engine — without it the produces-gate fails closed. | `npx wicked-loom` (npm; pinned `^0.2.0`). Resolved via `WICKED_LOOM_BIN` → config → `PATH` → `node_modules` → `npx wicked-loom`; `WICKED_LOOM_BIN=""` is the kill-switch. |

The core skill's `setup` action (`/wicked-garden-core setup`) **blocks** without
these two — a toolkit whose headline is "done is re-derived, not asserted"
cannot ship the gate as optional.

## Opt-in layers (setup recommends; never blocks)

Add what you want. Each unlocks one capability; the rest of the toolkit (the gate,
the code graph, wicked-patch, the council, the rubric skill-refs) runs without any
of them.

| Layer | What it unlocks | Skip it and… | Install |
|-------|-----------------|--------------|---------|
| **wicked-testing** | Evidence-gated acceptance testing with writer/executor/**independent reviewer** separation — no self-graded "it passed." | the produces-gate still works (via vault+loom); you just don't get the acceptance-testing tool. | `npx wicked-testing install` (npm `^0.3.0`) |
| **wicked-brain** | The memory layer — cross-session recall, cited search, `smaht:briefing`. Carries decisions/gotchas from session 1 to session 47. | structural search (`blast-radius`/`lineage`/`hotspots`, via codegraph) still works; you lose cross-session memory + semantic search. | `/plugin install wicked-brain` (npm `0.14.0`) |
| **wicked-bus** | The audit-trail layer — append-only events recording what happened. | nothing breaks — emission is already fire-and-forget / fail-open; events just aren't recorded. | `/plugin install wicked-bus` (npm `2.0.0`) |
| **wicked-understanding** | The repo-playbooks layer — analyzes the repo at HEAD into task playbooks (`fix-bug`/`add-feature`/`verify`/`write-tests`/`scaffold`) that tell the agent *how to work in this repo*: the file that owns the bug, the wiring step, the test command, the gotcha. Pairs with brain — brain is the *what*, this is the *how* (`repo-analyst --enrich-from-brain` folds in design rationale). | the agent re-derives the method from scratch each task; the rest of the toolkit works. | `npx skills add mikeparcewski/wicked-understanding --all` (skills-standard; multi-CLI, no server, no lock-in) |

The SessionStart bootstrap hook probes for all peers and **warns** (non-blocking)
when one isn't resolvable — informational for the opt-in layers, a real flag for
the gate's two.

## The stance: gate required, layers optional, runtime resilient

- **The gate is the floor.** vault + loom are required because the toolkit's
  central promise — re-derived, fail-closed "done" — is meaningless without them.
  This is the one place we trade adoption for honesty on purpose.
- **The layers are a toolkit, not a checklist.** Testing/brain/bus each add a
  capability; none is a prerequisite for the others. Install the toolkit and reach
  for the layers you need. Breadth is the point of a toolkit — but breadth you can
  *adopt incrementally*, not a five-thing prerequisite wall.
- **Resilient at runtime.** Even the required gate degrades cleanly: a transient
  outage never crashes a session, and the kill-switches (`WICKED_VAULT_BIN=""`,
  `WICKED_LOOM_CUTOVER=off`) disable cleanly and **fail closed** — they never let a
  gate treat missing evidence as a pass. `WICKED_LOOM_CUTOVER=off` is an emergency
  disable (e.g. a wedged `npx`): gating pauses and fails closed until loom is
  restored, rather than thrashing.

The line is simple: **fake-able honesty is worse than no honesty**, so the gate is
required. Everything else earns its place by being useful when you reach for it —
which is exactly what makes it a toolkit and not a monolith.
