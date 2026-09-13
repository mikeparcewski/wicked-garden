---
name: wicked-garden-repo-learn
user-invocable: true
description: |
  Learn an unfamiliar repo the way a senior engineer does: follow where the code
  actually churns, find what that churn touches that the rest of the system leans
  on, read the load-bearing code for real, then write down BOTH what you learned
  (memories) and what should hold (policies) — as inert estate proposals a human
  reviews, never as asserted fact.

  Four BOUNDED phases: (1) SAMPLED git-churn → ranked active areas (explicit
  top-N cap + a sampling rule for large histories — never streams every commit);
  (2) hotspots + blast-radius via wicked-garden-search, cross-referenced with
  churn to isolate load-bearing volatile code; (3) READ the intersection through
  the estate graph (FetchContent / RetrieveEntity / TraverseGraph) for genuine
  technical understanding; (4) DERIVE memories AND policies and submit them via
  the estate `proposal.submit` tool (inert queue, safe under --readonly).

  Use when: "learn this repo", "onboard me to this codebase", "study the active
  areas", "what should I know before working here", "derive memories / policies
  from this repo", "capture what matters about this codebase". Durable
  orientation + capture — for a read-only narrative with no capture, use
  wicked-garden-search `narrate` instead.
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# wicked-garden-repo-learn — churn-led repo learning that captures back

A repo teaches you where to look if you follow two independent signals at once:
**temporal** (where the code churns) and **structural** (what the rest of the system
depends on). This skill walks the intersection, reads it for real, and **captures the
learning back** as estate proposals — memories (what is true) and policies (what should
hold). Garden ORCHESTRATES; estate GROUNDS (graph + read) and RECEIVES (the proposal
queue); a human APPROVES — every capture is an inert proposal the studio Memories /
Policies surfaces review, never an asserted fact.

**Why churn is a separate step:** estate's `RankHotspots` is *structural* PageRank, not
temporal — it never sees git history. Churn is the gap this skill fills, with a
**bounded, sampled** git-log method; the two signals meet in § Cross-reference.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## The four phases

| # | Phase | Produces | Where |
|---|-------|----------|-------|
| 1 | **churn** | ranked active paths/areas over a window, top-N capped | [refs/churn-sampling.md](refs/churn-sampling.md) |
| 2 | **hotspots** | most-central symbols + blast-radius of the churn set | `wicked-garden-search` (reused — do NOT reimplement) |
| 3 | **read** | real understanding of the load-bearing, volatile code | § Read the intersection |
| 4 | **capture** | memories AND policies as inert `proposal.submit` entries | [refs/capture-proposals.md](refs/capture-proposals.md) |

Run them in order — each phase narrows the next. A partial run still helps (churn alone
orients; without capture it is a briefing), but the contract is **captured proposals**, not prose.

## Phase 1 — churn (the bounded, sampled step)

Rank the paths that changed most over a window. The method is fully specified in
[refs/churn-sampling.md](refs/churn-sampling.md); the non-negotiables:

- **Size the window first** (`git rev-list --count`) — full-scan vs sample by commit count.
- **Explicit top-N cap** (default **40** paths) — always `head -N`; the raw `--name-only`
  stream stays inside the shell pipe (sort / uniq), never in your context.
- **Sampling rule for large histories** — above the commit cap (default **2000**) switch to
  a recency-capped or even-stride sample; never `git log` the full history unbounded (worker
  output is capped ~25K chars — a full-history dump starves the phases that matter).
- **Roll up to directories** for wide monorepos; **filter generated/vendored noise**
  (lockfiles, `dist/`, `target/`, `node_modules/`).

Output of phase 1: a ranked list of ≤N `count  path` (or `count  dir/`) rows.

## Phase 2 — hotspots + blast-radius (reuse wicked-garden-search)

Do NOT reimplement centrality. Use the **wicked-garden-search** skill:

- `hotspots` — most-central symbols by PageRank (`RankHotspots`). Read its
  the `wicked-garden-search` skill's `refs/hotspots.md`; pass `--limit` near your top-N.
- `blast-radius <path>` — for each top churn path, the dependents estate sees
  (including injected bus/dispatch/capability/archetype edges grep can't). This
  is what tells you a churny file is load-bearing vs peripheral.

Freshness is a precondition. In a human session run the search skill's `index`
action first (`wicked-estate index <path>`) and heed any `STALENESS` marker.

**In a governed run never run `wicked-estate index`** or any other write subcommand —
the run hands you an indexed store; read its `STALENESS` marker and report it
(§ In a governed run).

## Cross-reference — the 2×2 that picks read targets

Churn and centrality answer different questions; the intersection ranks targets.

|                       | **High churn** | **Low churn** |
|-----------------------|----------------|---------------|
| **High centrality**   | load-bearing + volatile → **read deeply**; likely yields BOTH a memory (how it works / why it moves) AND a policy (what must hold as it changes) | stable core → **read for invariants**; yields policies (severity `error`/`critical`) more than memories |
| **Low centrality**    | churny periphery (config, fixtures, generated) → **mostly noise**; skip unless it's a hot integration seam | quiet leaf → **skip** |

The prime targets are the top-left cell: paths that appear in BOTH the phase-1
churn list and the phase-2 hotspot/blast-radius set. Read those first.

## Phase 3 — read the intersection

For each cross-referenced target, build **genuine** understanding — not a file
listing — via the estate tools (all read-only; in a governed run through the shim's
`call` action, § In a governed run):

1. `SearchEntity` `{"name": "<symbol-or-path>"}` → resolve to node ids/kinds.
2. `RetrieveEntity` → the symbol's structured record; `FetchContent` → the actual
   source slice (read the code, don't infer from names).
3. `TraverseGraph` (bounded — it carries `max_depth`/`max_nodes`) or `Lineage` →
   how the target connects: what it calls, what calls it, which events/commands
   inject edges into it.
4. Recall what's already known before writing anything new: `wicked-garden-mem`
   `recall` (`scope_prefix: ""`) so you extend the record rather than duplicate it.

Stop when you can state, per target, **what it does, why it changes, what it
depends on, and what would break** — that is the input to phase 4.

## Phase 4 — capture: memories AND policies as proposals

Turn understanding into two kinds of reviewable record via the estate
**`proposal.submit`** tool (inert queue; a PERMITTED safe write even under
`--readonly`) — in a governed run through the shim's `propose` action, AND written to
the unit's deliverable file (§ In a governed run). Full contract, payloads, facets,
and derivation heuristics: [refs/capture-proposals.md](refs/capture-proposals.md). The essentials — use the
enum values EXACTLY as written (an out-of-enum `tier` or `severity` is rejected
when the proposal is approved, so the learning is lost):

- **Memory** — what is *true* about this repo. `kind_type: "memory"`; payload
  `{"content": "<1–3 sentences>", "tier": "<value>"}` where `tier` is EXACTLY one
  of `working` / `episodic` / `semantic` / `procedural` / `archival` — for a repo
  learning use `semantic` (a fact/decision) or `procedural` (a how-to/convention);
  NEVER invent a tier like `durable`. Facets `{"repo": "<name>", "project": "<name>"}`.
- **Policy** — what *should hold*. `kind_type: "policy:<type>"` where `<type>` ∈
  architecture · development · security · testing · operations · compliance ·
  design-ux; payload `{"rule": "<imperative>", "severity": "<value>"}` where
  `severity` is EXACTLY one of `info` / `warn` / `error` / `critical` — the middle
  band is `warn`, NOT `warning`. Facets `{"repo": "<name>", "project": "<name>", "language": "<lang>"}`.
- **Never pass `provenance`** — the server stamps it from `WICKED_RUN_*`. Passing
  it is at best ignored; treat provenance as not yours to set.
- Derive **both** per target where the 2×2 warrants it: the memory records the
  *is*, the policy records the *ought*. A stable high-centrality invariant is a
  policy; a "this is how X actually wires up" discovery is a memory.

## In a governed run

You are in a governed run when you were dispatched as a unit of a wicked-crew run — a phase
directive and/or the `wicked-garden-governed-worker` skill was handed to you; `WICKED_RUN_ID` /
`WICKED_GATE_SCOPE` in your environment confirm it when present, their absence does not refute
it. **When unsure, take this ladder** — the shim in `--readonly` is also correct in a human
session. Follow `wicked-garden-governed-worker` (A2, A5) and ground through the **estate shim
in read-only mode** — it works on every seat CLI and does not depend on an MCP server being
registered (an organization MCP allowlist can drop one silently). The store is pinned from the
worker environment (`WICKED_ESTATE_DB` / `WICKED_HOME` / `WICKED_MEMORY_DB`) or `--db <path>`;
the shim refuses an unpinned store — report that, never guess one.

1. **Grounding ladder** (phases 2–3; stop at the first rung that answers and name it):
   the shim, `--readonly` literal — every estate tool named above is reachable as
   `wicked-garden run scripts/_estate_client.py --readonly call '{"tool":"FetchContent","arguments":{…}}'`;
   then a read-only CLI subcommand (`wicked-estate blast-radius|query|rank|stats|source|semantic|cross-graph`);
   then grep, flagging that injected edges are MISSING. The write CLI is **never** a
   rung: never `wicked-estate index`, `scip`, `tfstate`, `import-telemetry`, `compact`,
   `watch`; never `wicked-estate clusters --annotate`. A denied call is final — take
   the next rung.
2. **Capture** (phase 4) submits each proposal through the shim —
   `wicked-garden run scripts/_estate_client.py --readonly propose '{"kind_type":"memory","payload":{…},"facets":{…}}'`
   (`proposal.submit`; provenance is server-stamped from `WICKED_RUN_*`, never passed) —
   AND writes the exact `{kind_type, payload, facets}` objects, as one JSON array, to the
   **deliverable file the run names** in your problem statement or intake: an absolute
   path inside the unit's declared write root, **never a path inside the repository**
   (governed-worker E1). If the shim path is unavailable that file IS the record —
   wicked-crew lands its proposals — so write it whether or not the submit succeeded.
   If no path was named, emit the array as a fenced `json` block in your output and say so.
3. **Report** the rung that answered each phase and honest counts: derived N /
   submitted M / written-to-file W / failed K (governed-worker A4).

## Degrade + honesty

- **Estate unreachable** (index/MCP down): phase 1 still runs (pure git); for
  phases 2–3 fall back per the search skill's ladder (read-only CLI → grep, flagging
  that injected edges are MISSING). Say so — don't present a grep approximation as the
  graph answer, and **name the rung that answered** (shim / estate tools / CLI / grep).
- **`proposal.submit` fails (a JSON-RPC error, e.g. -32602 / -32603)**: do NOT silently drop the learning.
  Emit the derived memories and policies as a structured block in your report so
  a human (or a later run) can submit them, and name the degrade. In a governed run
  the deliverable file (§ In a governed run) already carries them.
- Capture is a **proposal**, not an assertion — report it as "proposed N
  memories, M policies (pending review)", never "recorded".

## Depth

- [refs/churn-sampling.md](refs/churn-sampling.md) — the bounded/sampled git-log method:
  window sizing, the sample rule, the top-N cap, directory rollup, noise filters, counting fallback.
- [refs/capture-proposals.md](refs/capture-proposals.md) — the `proposal.submit`
  contract for memories and policies, the derivation heuristics (2×2 → what to
  propose), worked examples, the idempotency/dedup discipline, the shim `propose`
  command and the deliverable-file shape for governed runs.
