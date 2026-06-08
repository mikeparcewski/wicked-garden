# North-Star Spec — `wicked-loom`: extracting the orchestration runtime

- **Date:** 2026-06-08
- **Status:** Design (approved shape; pending written-spec review → implementation plan)
- **Author:** brainstormed with Mike Parcewski
- **Topic:** Reshape wicked-garden from a heavy library into a thin orchestrator by extracting its runtime/wiring into a new standalone peer, `wicked-loom`.
- **Related:** ETHOS.md, docs/required-peers.md, issues #887 #843 #878 #842

---

## 1. Context & motivation

`wicked-garden` is published at **v12.2.0** on a marketplace with real users. It has grown heavy: **~127k lines** across **71 skills · 93 commands · 55 agents · 131 Python scripts**. A large share of that weight is not domain expertise or archetype intelligence — it is *runtime plumbing*: peer detection/install/resolution, bus wiring, gate execution, and phase-loop mechanics. That plumbing was even formalized once as a `daemon/` (typed bus subscribers + projector + council, #592/#624) and then **deliberately deleted in v11** (commit `d205fc3`, "daemon cleanup") for being too heavy in-tree. The plumbing keeps wanting to exist, and keeps not belonging in garden.

Meanwhile the `wicked-*` ecosystem already decomposes cleanly by concern, each concern a standalone primitive:

| Primitive | Concern |
|---|---|
| `wicked-bus` | messaging substrate (how components talk) |
| `wicked-brain` | memory / knowledge |
| `wicked-vault` | evidence / verification (re-derive, never trust a claim) |
| `wicked-testing` | QE execution (plan → run → judge) |
| `wicked-understanding` | per-repo knowledge + **verifier spec** |

`wicked-garden` uniquely owns three things none of the primitives provide: the **archetype engine** (classify work-shape, steer phases), the **domain catalog** (skills + agents), and the **compiler** (stamp a self-contained gate into any repo). Everything else garden does today is runtime that *should be a primitive too* — and isn't. That missing primitive is `wicked-loom`.

**Thesis:** garden should *drive* a runtime, not *be* one. Extract the runtime into `wicked-loom`; garden becomes "archetype engine + domain catalog + compiler, running on loom."

---

## 2. Decisions (locked)

These were settled during brainstorming and are the spine of this spec.

| # | Decision | Rationale |
|---|---|---|
| D1 | **North star = Level 1.** Garden keeps the archetype engine, domain catalog, and compiler. Extract concerns *gate/phase + autonomy substrate* and *peer-wiring/adapters* into one standalone. | L1 is destination *and* first increment — biggest clarity win, smallest blast radius, and it names the missing component precisely. L2 (unbundle the domain catalog) and L3 (gut the archetype engine) are explicitly **out of scope** — L3 would erase garden's identity. |
| D2 | **One new primitive, not two.** `wicked-loom`, containing a `compose` module and a `conduct` module. | Honors the "a missing component" (singular) framing and YAGNI — do not spec a separate `compose` primitive until a *second* consumer needs it. |
| D3 | **Hybrid autonomy, synchronous-core-first.** The in-session synchronous runtime is the L1 deliverable. Headless/daemon is **spec'd now, built later**, with the park-at-hard-gate contract baked into the interface from day one. | The deleted daemon shows headless was too heavy as a default; garden's HITL discipline (hard gates require a human) collides with unattended autonomy unless bounded. Baking the contract in now prevents a later repaint. |
| D4 | **Hybrid wiring.** Bus-as-spine for coordination/audit/knowledge/parks (async); direct synchronous resolution for re-derivation gates. **An event never satisfies a gate.** | Vault re-derivation must be blocking + in-line — a gate cannot return "pass" off a stale event. The bus carries everything that *isn't* a gate verdict. |
| D5 | **Language-neutral standalone, Python impl, CLI + (deferred) daemon surface, consumed by garden via subprocess.** | Reuses nearly all existing Python code (daemon, `qe/`, resolvers) while making loom a true sibling primitive any stack can shell to — identical to how garden already consumes `npx wicked-vault`. Keeps garden's plugin packaging decoupled from loom's Python env. |
| D6 | **Name: `wicked-loom`.** | A loom is the frame that wires threads together into cloth — the literal metaphor for "only wiring them together." |

---

## 3. Target architecture

```
                       ┌───────────────────────────────────────────┐
 prompt ─────────────► │            wicked-garden (plugin)          │
                       │  • archetype engine (classify + steer)     │   KEEPS
                       │  • domain catalog (71 skills / 55 agents)  │
                       │  • compiler (emit stamped gate into repos) │
                       │  compiles archetype → FLOW DEFINITION;     │
                       │  shells to loom for compose / gate / flow  │
                       └───────────────┬───────────────────────────┘
                          subprocess (CLI, sync)  +  bus events (async)
                                       ▼
                       ┌───────────────────────────────────────────┐
                       │        wicked-loom  (NEW standalone)       │   TAKES
                       │  COMPOSE: declare → install → version →    │
                       │           resolve (the WICKED_*_BIN ladder)│
                       │  CONDUCT: run any FLOW DEFINITION —        │
                       │           phase-loop · gate exec · park-   │
                       │           at-hard-gate · bus-consumer+proj │
                       └──┬──────────┬──────────┬──────────┬─────────┘
            direct/sync ──┘          │          │          └── bus/async
                       ▼             ▼          ▼             ▼
                  wicked-vault  wicked-testing  wicked-brain  wicked-bus
                  (re-derive)   (QE exec)       (knowledge)   (spine)
                              (+ wicked-understanding — verifier spec, optional/fail-soft)
```

### 3.1 The load-bearing abstraction: loom is archetype-agnostic

Garden does **not** hand loom an archetype name. Garden's archetype engine compiles a catalog entry into a generic, declarative **flow definition**:

```jsonc
// flow definition — garden produces it, loom executes it
{
  "flow_id": "…",
  "phases": [
    { "name": "plan",      "gate": null,                       "produces": [...] },
    { "name": "implement", "gate": null,                       "produces": [...] },
    { "name": "test",      "gate": "produces:test-report",     "hitl": "discrete:review" },
    { "name": "review",    "gate": "produces:verdict",         "hitl": "hard:final-verdict" }
  ],
  "peers_required": ["vault", "testing"],
  "verifier_spec_ref": "…optional wicked-understanding verify.json…"
}
```

Loom knows nothing about "build" vs "migrate" vs "incident." It runs *any* flow definition: advance phase → if the phase has a gate, execute it (sync vault re-derive) → if the gate is `hard:*`, park and emit `needs-human` → else continue. This is the seam that makes loom a genuine reusable primitive (any agent system can author flow definitions) rather than "garden's engine in a sidecar repo." Garden remains the archetype-to-flow compiler; loom is the generic flow runtime.

### 3.2 Responsibility split

| Concern | Owner | Notes |
|---|---|---|
| Archetype catalog, detector, steering hook, playbooks | **garden** | `archetypes_v11.py`, `prompt_submit.py`, `commands/archetype/`, `skills/archetype/refs/`, `archetypes.json` |
| Domain catalog (skills/agents) | **garden** | unchanged |
| Compiler (stamped-gate emitter) | **garden** | stays; see §7 synergy |
| Archetype → flow-definition compilation | **garden** | new thin layer; the handoff contract to loom |
| Peer install + version-check + resolution (compose) | **loom** | cross-cutting; not archetype-specific |
| Gate execution (vault re-derive) | **loom** | the honest-evidence engine |
| Flow/phase mechanics + state + park-at-gate | **loom** | generic flow runtime |
| Bus consumer + projector (headless) | **loom** | resurrected daemon, deferred-on by default |

---

## 4. `wicked-loom` component spec

One standalone, two modules, three surfaces.

### 4.1 COMPOSE module
Owns the peer lifecycle. Salvaged from garden's `bootstrap.py` (peer portion), `_integration_resolver.py`, `_capability_resolver.py`, `_capability_registry.py`, and `required-peers` logic.

- **Declare** — a peer manifest (peer name, npm package, pinned `^x.y`, resolution env var, optional/required).
- **Install** — orchestrate installs across mechanisms. **All four current peers are on npm**, so install runs headless via `npm`/`npx` (`npx wicked-testing install`, `npx wicked-vault-install`, `npm i wicked-brain@0.14`, `npm i wicked-bus@2`). The Claude Code `/plugin install` path is UX sugar, *not* the only route — loom never depends on a live CC session to install.
- **Version-check** — verify resolved versions satisfy the pins; report drift.
- **Resolve** — own the runtime resolution ladder (`WICKED_<PEER>_BIN` → config → `PATH` → `node_modules/.bin` → `npx`), including the `WICKED_VAULT_BIN=""` kill-switch.

### 4.2 CONDUCT module
Runs flow definitions. Salvaged from `qe/vault_gate.py`, `crew/phase_manager.py`, and the deleted `daemon/`.

- **Run a flow** — advance through declared phases; persist phase state.
- **Execute a gate** — *synchronous, in-line* vault re-derivation: re-hash recorded evidence + re-run the verifier via `cross-check`. Missing vault → `gate: "unavailable"`, **fail-closed**, never a vacuous pass. Hard gates additionally require an independent attestation (`--with-attestations`). If a `verifier_spec_ref` is present, read it to know *what* to re-derive; if absent/stale, fall back to generic detection (fail-soft on the *spec*, never on the *gate*).
- **Park at hard gate** — on `hard:mitigate / cutover / final-verdict`, stop the flow and emit `loom:flow:needs-human`; do not self-approve. (Contract present from day one even though headless execution is deferred.)
- **Project** — materialize flow/phase/evidence state from bus events to disk (headless, deferred).

### 4.3 Surfaces
1. **CLI** (the L1 deliverable; garden shells to it):
   - `loom compose install [--peer X] [--check]` · `loom resolve <peer>` · `loom doctor`
   - `loom gate <produces> [--verifier-spec path] [--with-attestations]`
   - `loom flow run <flow-def.json>` · `loom flow status <flow-id>` · `loom flow resume <flow-id>`
2. **Bus-consumer / daemon** (deferred per D3): headless mode that reacts to bus events, runs soft-gated flows unattended, parks at hard gates.
3. **Event contract** (stable, on `wicked-bus`): `loom:flow:started|phase-advanced|gate-passed|gate-failed|needs-human|completed`, `loom:compose:installed|drift-detected`.

---

## 5. Wiring contract & invariants

- **I1 — Gates are synchronous and direct.** `loom gate` re-derives every call. **An event never satisfies a gate.**
- **I2 — Fail-closed.** Missing vault → `unavailable`, never pass. A claimed-but-false "tests pass" is rejected.
- **I3 — Fail-soft on the verifier spec only.** Absent/stale `wicked-understanding` verifier spec → generic detection, never a blocked or vacuous gate.
- **I4 — Bus is the spine for everything that is not a gate verdict:** phase transitions, evidence-recorded notices, brain knowledge writes, audit, and `needs-human` parks.
- **I5 — Autonomy never overrides a hard gate.** Headless flows park + emit at `hard:*`.
- **I6 — Loom is archetype-agnostic.** It executes flow definitions; it does not know archetype names.

---

## 6. Extraction inventory (file-level, grounded)

`→ loom` = moves; `STAY` = remains in garden; `PARTIAL` = split.

> **OUTCOME (shipped 2026-06-08 — supersedes the forward-looking `→ loom` dispositions below).** What *actually* moved to loom: **resolve** (peer resolution) and **gate** (`vault_gate.cross_check`) — both fully cut over **and contracted** (in-process deleted; loom is the sole path, fail-closed). **flow** landed as a loom-*authoritative* hard-gate park decision with an in-process fail-closed floor — the `phase_manager` state machine was **not** moved (incompatible execution models: garden advances one phase agent-in-loop; loom runs a whole flow-def). Everything else listed `→ loom` below **STAYS in garden permanently** — re-decided, *not* future loom work: `_integration_resolver` / `_capability_resolver` / `_capability_registry` (agent/domain MCP-tool discovery — a different concern from wicked-peer orchestration), `bootstrap` (session assembly; loom peer-detection already shimmed), `_bus`/`_event_*` (not migrated), `phase_manager` storage (rejected). The loom migration is **complete**; nothing further is owed. Shipped: garden **v12.3.0** (resolve/gate) + **v12.4.0** (flow); loom **v0.2.x**.

| File | Lines | Disposition |
|---|---:|---|
| `hooks/scripts/bootstrap.py` | 1711 | **PARTIAL** — peer detect/install/resolve → loom compose; session-bootstrap (state init, archetype priming, brain orientation) STAYS |
| `scripts/_integration_resolver.py` | 321 | → loom (compose) |
| `scripts/_capability_resolver.py` | 322 | → loom (compose) |
| `scripts/_capability_registry.py` | 226 | → loom (compose) |
| `scripts/qe/vault_gate.py` | 348 | → loom (conduct/gate) |
| `scripts/crew/phase_manager.py` | 614 | → loom (conduct/state) |
| `scripts/_bus.py` | 973 | **PARTIAL** — consumer/projector role → loom; thin fire-and-forget emit (`_bus_emit.py`, 43) STAYS so any garden component can emit |
| `scripts/_event_store.py` / `_event_log_reader.py` / `_event_schema.py` | 397 / 154 / 305 | → loom (conduct/projector) — confirm during expand phase |
| `scripts/_wicked_testing_probe.py` / `_wicked_testing_tier1.py` | 277 / 88 | → loom (compose/resolution) |
| `scripts/_brain_port.py` | 65 | → loom (compose/resolution) |
| `scripts/crew/archetypes_v11.py` | 348 | **STAY** — archetype engine (garden identity) |
| `hooks/scripts/prompt_submit.py` | 1126 | **STAY** — classification entry (archetype engine) |
| `scripts/crew/scope_delta.py` | 264 | **STAY** — HITL scope heuristic feeds flow-definition compilation |
| `scripts/compiler/**` | 2312 | **STAY** — see §7 synergy |

Exact partial boundaries (esp. `bootstrap.py`, `_bus.py`, the `_event_*` trio) are confirmed empirically during the **expand** phase, not asserted here.

---

## 7. Migration plan — strangler (expand → cutover → contract)

Garden is published with users; this is a migration, not a rewrite. Each step is independently verifiable via vault.

1. **Expand.** Stand up the `wicked-loom` repo. *Copy* (don't move) compose + conduct code; ship the CLI; publish to npm with a `^0.1` pin. Garden is byte-for-byte unchanged and keeps working. Loom is usable standalone by other consumers immediately.
2. **Cutover (strangler).** Garden's `scripts/` shims start shelling to `loom` instead of running in-process, **one surface at a time**: `resolve` → `gate` → `flow`. Each cutover ships behind the existing fail-soft posture (if loom unresolvable, the old in-process path or graceful degradation still applies during transition). Add `wicked-loom` as a **5th peer** in `docs/required-peers.md` (required at install, resilient at runtime — same stance as the other four). Introduce the archetype → flow-definition compiler in garden.
3. **Contract.** Delete the now-dead in-garden runtime code (the `→ loom` rows above). Re-measure garden's footprint; slim whatever genuinely remains (this absorbs #843).

**Backward compat:** during expand+cutover, no user-visible behavior change. The contract phase is a major version bump for garden (v13) with a migration note: "wicked-loom is now a required peer; `/wicked-garden:setup` installs it."

---

## 8. The four open issues, re-triaged against the north star

| Issue | Disposition |
|---|---|
| **#887** consume wicked-understanding | **Absorbed into loom.** Understanding's `verify.json` is the `verifier_spec_ref` that `loom gate` reads to know *what* to re-derive. Optional/fail-soft peer (I3), exactly as the author proposed. Resolve by speccing it into loom, not as a standalone garden change. Open sub-item: confirm the `verify.json` schema loom's gate consumes (tracked in §9). |
| **#843** slim `commands/*` | **Largely dissolved** by the contract phase — much weight is runtime plumbing that leaves. Re-measure after contract; slim the genuine remainder. |
| **#878** cwd-leak PreToolUse hook | **Tactical, do now.** Independent of the rethink — worktree-safety bug. Not blocked by loom. |
| **#842** SessionEnd dogfood (v9.2.15) | **Stale** (we're at v12.2). Verify-or-close; do not carry v9 dogfooding forward. |

---

## 9. Open questions / deferred

- **D-headless:** the daemon/bus-consumer execution mode is spec'd (§4.2/§4.3) but **not built** in L1. The contract (park-at-hard-gate, event names) is fixed now to avoid a repaint.
- **Compiler↔loom synergy:** `loom gate` and the compiler's stamped gate are the same logic at different lifetimes (live runtime vs. stamped file). L1 leaves the compiler as-is (self-contained, resolves vault directly via npx). A later increment *may* have the compiler emit a thin shim over loom — flagged, not scoped.
- **compose-as-its-own-primitive:** deferred per D2 (YAGNI). Revisit only if a non-garden consumer needs the composer.
- **`verify.json` schema:** the structured sidecar wicked-understanding would emit (issue #887, rec #2) needs its shape confirmed against what `loom gate` consumes. Coordinate cross-repo before building.
- **CLI verb naming:** `compose`/`gate`/`flow` are provisional.

---

## 10. Error handling & testing posture

- **Error handling:** all peer interaction is fail-soft *except gates* (fail-closed, I2). Loom unresolvable → garden degrades gracefully during transition; a gate with no vault returns `unavailable`. The `WICKED_VAULT_BIN=""` kill-switch and the loom resolution ladder are preserved verbatim.
- **Testing:** loom ships with its own suite (compose resolution ladder, gate fail-closed behavior, flow phase advance + park-at-hard-gate). Garden adds **contract tests** asserting each cutover shim produces identical results to the in-process path it replaces (the strangler's safety net). The emitted-compiler-gate AST test (stdlib-only, imports nothing from the garden) is unaffected.

---

## 11. Success criteria for L1

1. `wicked-loom` exists as a standalone npm-published primitive with a working CLI, usable by a non-garden consumer.
2. Garden shells to loom for `resolve`, `gate`, and `flow`; the in-process runtime code is deleted.
3. No regression: every archetype's gate behavior is identical pre/post cutover (proven by contract tests + vault re-derivation, not asserted).
4. Garden's footprint drops measurably (target: the `→ loom` rows above leave; #843 re-measured).
5. The honest-evidence invariants (§5) hold unchanged — done is still re-derived, never claimed.
6. Loom is archetype-agnostic: it runs a hand-authored flow definition with zero garden knowledge.
