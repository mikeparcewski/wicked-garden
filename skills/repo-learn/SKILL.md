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
**temporal** (where the code churns) and **structural** (what the rest of the
system depends on). This skill walks the intersection, reads it for real, and
**captures the learning back** as estate proposals — memories (what is true) and
policies (what should hold). Garden ORCHESTRATES; estate GROUNDS (graph + read)
and RECEIVES (the proposal queue); a human APPROVES. Nothing here asserts a fact
into the record — every capture is an inert proposal the studio Memories /
Policies surfaces review.

**Why churn is a separate step:** estate's `RankHotspots` is *structural*
PageRank, not temporal — it never sees git history. Churn is the gap this skill
fills, with a **bounded, sampled** git-log method (never one that streams every
commit). The two signals are complementary, not redundant; § Cross-reference is
where the value is.

## The four phases

| # | Phase | Produces | Where |
|---|-------|----------|-------|
| 1 | **churn** | ranked active paths/areas over a window, top-N capped | [refs/churn-sampling.md](refs/churn-sampling.md) |
| 2 | **hotspots** | most-central symbols + blast-radius of the churn set | `wicked-garden-search` (reused — do NOT reimplement) |
| 3 | **read** | real understanding of the load-bearing, volatile code | § Read the intersection |
| 4 | **capture** | memories AND policies as inert `proposal.submit` entries | [refs/capture-proposals.md](refs/capture-proposals.md) |

Run them in order — each phase narrows the next. A partial run is still useful
(churn alone orients; churn+hotspots+read without capture is a briefing), but the
skill's contract is that **understanding ends in captured proposals**, not prose.

## Phase 1 — churn (the bounded, sampled step)

Rank the paths that changed most over a window. The method is fully specified in
[refs/churn-sampling.md](refs/churn-sampling.md); the non-negotiables:

- **Size the window first** (`git rev-list --count`) — choose full-scan vs sample
  by commit count, never by hoping.
- **Explicit top-N cap** (default **40** paths) — the final list is always
  `head -N`; the raw `--name-only` stream stays inside the shell pipe (sort /
  uniq), never in your context.
- **Sampling rule for large histories** — above the commit cap (default
  **2000**), switch to a recency-capped or even-stride sample; never `git log`
  the full history unbounded. Worker output is capped ~25K chars — a full-history
  churn dump both blows that and starves the phases that matter.
- **Roll up to directories** for wide monorepos; **filter generated/vendored
  noise** (lockfiles, `dist/`, `target/`, `node_modules/`).

Output of phase 1: a ranked list of ≤N `count  path` (or `count  dir/`) rows.

## Phase 2 — hotspots + blast-radius (reuse wicked-garden-search)

Do NOT reimplement centrality. Use the **wicked-garden-search** skill:

- `hotspots` — most-central symbols by PageRank (`RankHotspots`). Read its
  [refs/hotspots.md](../search/refs/hotspots.md); pass `--limit` near your top-N.
- `blast-radius <path>` — for each top churn path, the dependents estate sees
  (including injected bus/dispatch/capability/archetype edges grep can't). This
  is what tells you a churny file is load-bearing vs peripheral.

Freshness is a precondition: run the search skill's `index` action first
(`wicked-estate index <path>`) and heed any `STALENESS` marker.

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
listing — via the estate MCP (all read-only):

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

Turn understanding into two kinds of durable, reviewable record via the estate
MCP **`proposal.submit`** tool (inert queue; a PERMITTED safe write even under
`--readonly`). Full contract, payloads, facets, and derivation heuristics:
[refs/capture-proposals.md](refs/capture-proposals.md). The essentials:

- **Memory** — what is *true* about this repo. `kind_type: "memory"`,
  `payload: {"content": "<1–3 sentences>", "tier": "semantic"|"procedural"}`,
  `facets: {"repo": "<name>", "project": "<name>"}`.
- **Policy** — what *should hold*. `kind_type: "policy:<type>"` where `<type>` ∈
  architecture · development · security · testing · operations · compliance ·
  design-ux; `payload: {"rule": "<imperative>", "severity":
  "info"|"warn"|"error"|"critical"}`, `facets: {"repo": "<name>", "project":
  "<name>", "language": "<lang>"}`.
- **Never pass `provenance`** — the server stamps it from `WICKED_RUN_*`. Passing
  it is at best ignored; treat provenance as not yours to set.
- Derive **both** per target where the 2×2 warrants it: the memory records the
  *is*, the policy records the *ought*. A stable high-centrality invariant is a
  policy; a "this is how X actually wires up" discovery is a memory.

## Degrade + honesty

- **Estate unreachable** (index/MCP down): phase 1 still runs (pure git); for
  phases 2–3 fall back per the search skill's ladder (CLI → Grep, flagging that
  injected edges are MISSING). Say so — don't present a grep approximation as the
  graph answer.
- **`proposal.submit` fails (a JSON-RPC error, e.g. -32602 / -32603)**: do NOT silently drop the learning.
  Emit the derived memories and policies as a structured block in your report so
  a human (or a later run) can submit them, and name the degrade.
- Capture is a **proposal**, not an assertion — report it as "proposed N
  memories, M policies (pending review)", never "recorded".

## Depth

- [refs/churn-sampling.md](refs/churn-sampling.md) — the bounded/sampled git-log
  method: window sizing, the sample rule, the top-N cap, directory rollup, noise
  filters, and the cross-platform counting fallback.
- [refs/capture-proposals.md](refs/capture-proposals.md) — the `proposal.submit`
  contract for memories and policies, the derivation heuristics (2×2 → what to
  propose), worked examples, and the idempotency/dedup discipline.
