# Capture — knowledge, memories AND policies as estate proposals

The learning phase ends by writing back records through the estate
**`proposal.submit`** tool (reached through the estate shim): **knowledge** (how the
code works, read from it), **memories** (what you witnessed or were told) and
**policies** (what *should hold* in it). Both land in
estate's **inert proposal queue** — a type-generic write surface that is a PERMITTED safe
write **even under `--readonly`**, because a proposal is never recalled or applied until
an operator approves it. The shim's `wicked-estate-mcp --readonly` opens the operator
GLOBAL store and permits `proposal.submit`, so proposals surface in the studio Memories /
Policies review UI. This is *propose, not assert* — you never inject a fact into
the record; a human promotes it.

## The `proposal.submit` contract (wire shape)

`proposal.submit` takes exactly three caller-supplied fields:

| Field | Type | Rule |
|-------|------|------|
| `kind_type` | string | `"knowledge"`, `"memory"` OR `"policy:<type>"`; must match `^[a-z][a-z0-9_-]*(:[a-z][a-z0-9_-]*)?$` |
| `payload`   | JSON **object** | required; a present non-object is rejected `-32602` (never silently defaulted) |
| `facets`    | JSON object of `axis:value` strings | each axis is a lowercase token `^[a-z][a-z0-9_-]*$`, each value non-empty; `project` is **required** (the shim refuses a proposal without it) |

**`provenance` is NOT a caller field.** The server stamps it from its own launch
env (`WICKED_RUN_ID` / `WICKED_RUN_UNIT` / `WICKED_RUN_AGENT`) — a worker cannot
forge its own attribution, and passing `provenance` in args is not honored. Do not
construct it.

On success the tool returns `{"id": "<proposal-id>"}`. A malformed `kind_type`,
`facets`, or a non-object `payload` fails loud with `-32602` — fix and resubmit,
never swallow.

### Submitting through the shim (every governed run — the only path; any session without a registered MCP)

The estate shim reaches `proposal.submit` without an MCP server being registered
with your harness, on every seat CLI:

```bash
wicked-garden run scripts/_estate_client.py --readonly propose '{"kind_type":"knowledge","payload":{"content":"…","class":"concept","source":"<repo>:<path>","source_rev":"<sha>"},"facets":{"repo":"<name>","project":"<name>"}}'
```

`--readonly` is literal (the shim spawns `wicked-estate-mcp --readonly`; `proposal.submit`
is the safe write it still permits). The store is pinned from the worker environment
(`WICKED_ESTATE_DB` / `WICKED_HOME` / `WICKED_MEMORY_DB`) or `--db <path>`; in a run an
unpinned store is refused with `{"ok": false, "reason": …}` — report it, do not guess a
store. The shim answers `{"ok": true, "id": "<proposal-id>"}` or `{"ok": false,
"reason": …, "code": <json-rpc code or null>}`: `-32602` is a *your-args* bug (fix the
shape), `null` means the estate was unreachable (keep the objects — next section). Pass
the JSON as ONE quoted argument, even when it is long: `propose` does not read stdin. A
`provenance` key is dropped.

### When `propose` fails in a governed run — no file fallback

There is **no deliverable file**: a governed run writes proposals nowhere but through
the shim (nothing into the repository — `wicked-garden-governed-worker` E1 — and nothing
elsewhere; the former deliverable-file fallback was never consumed by wicked-crew and is
gone). If the shim answers `{"ok": false, …}` or the fence denies the call, emit every
proposal you derived as **one fenced `json` block** of exact `{kind_type, payload, facets}`
objects in your output, write `estate: not available (<reason>)`, and continue — that
block is the ONLY record; a human can submit from it. Report the counts:
derived N / submitted M / failed K — and, in a governed run, as the machine-readable last
line `wicked-capture-report {"derived": N, "submitted": M, "failed": K}` (wicked-core#535;
see the SKILL's "In a governed run" step 3). A degrade is `submitted 0 / failed N`, which
the engine's capture-report floor denies into the human gate on purpose.

### `<type>` for policies (the seven steering types)

`policy:` must be suffixed with exactly one: `architecture` · `development` ·
`security` · `testing` · `operations` · `compliance` · `design-ux`. These are the
estate/steering types — pick the one the rule governs, not a freeform tag.

## Knowledge payload (code facts: the usual case)

What you learn by reading code is **acquired**, so it is knowledge, not memory
(DES-memory-vs-knowledge §3).

Submit it through the shim's `propose` like a memory. Estate 0.29.2+ approves a
knowledge proposal into the knowledge store, keeping its `source`, `observed_at` and
`source_rev`. The shim refuses one with no `source` (`-32602`). Never re-file a code fact as a
`memory`. The shape is:

```json
{
  "kind_type": "knowledge",
  "payload": {
    "content": "<1–3 sentences: what the code does and why>",
    "class": "concept",
    "source": "<repo>:<path>",
    "source_rev": "<commit sha you read>"
  },
  "facets": { "repo": "<repo-name>", "project": "<project-name>" }
}
```

`source` + `source_rev` let the record be refreshed or expired when the code
changes. Never propose a graph metric (PageRank rank, churn count, blast-radius
size): `RankHotspots` / `BlastRadius` re-derive them on demand.

## Memory payload + facets (witnessed or told only)

Propose a `memory` only for something you **witnessed** while studying (a
gotcha you hit, with why it bites) or were **told** by the operator. Split a
mixed finding: "we chose fail-closed because of incident X" is memory; "the
implementation fails closed" is knowledge.

```json
{
  "kind_type": "memory",
  "payload": { "content": "<1–3 self-contained sentences>", "tier": "semantic" },
  "facets": { "repo": "<repo-name>", "project": "<project-name>" }
}
```

- `content` — distilled, self-contained: the *why* and *what* a future session
  needs, not a paragraph of *how*. One to three sentences. If it needs the current
  file open to make sense, it isn't distilled yet.
- `tier` — `"semantic"` for a decision or gotcha you witnessed or were told
  ("the bus path was chosen over a direct call because direct calls dropped
  events in incident X"); `"procedural"` for a how-to you were taught. How the
  code is wired ("X is wired via the bus") was read from the code: that is a
  `knowledge` proposal, not a memory.
- `facets` — `repo:` and `project:` locate the memory so faceted recall admits it
  for the right work. Use the repo's directory/remote name and the umbrella
  project (here, `wicked`). **`project:` is required** on every proposal,
  memory or policy: the shim refuses one without it (`-32602`, "proposal
  needs facets.project"), so nothing lands in the queue unscoped. In a run,
  `WICKED_RUN_PROJECT` supplies it.
- `content` must pass the durability test: a rule, why it holds, and when it
  applies, useful to a fresh session on a different task months from now. No
  release-status versions ("shipped 2.4.1"), commit SHAs, PR/run ids or progress
  notes. A version *constraint* ("needs SQLite >= 3.35.0 because …") is fine.

## Policy payload + facets

```json
{
  "kind_type": "policy:architecture",
  "payload": { "rule": "<imperative statement of what must hold>", "severity": "error" },
  "facets": { "repo": "<repo-name>", "project": "<project-name>", "language": "<lang>" }
}
```

- `rule` — an imperative the code should satisfy, phrased so a reviewer can judge
  a diff against it ("Every emitted Edge carries {confidence, provenance,
  resolved_by}"; "No content-hash or line-number node ids"). Not a description —
  a *ought*.
- `severity` — `info` (advisory) · `warn` (should) · `error` (must; a violation
  blocks) · `critical` (must; a violation is a security/data-loss class). Map from
  the 2×2 below and from what the code's own guardrails signal.
- `facets` — policies add `language:` on top of `repo:`/`project:`, so a rule that
  is language-scoped ("Rust: no bare `panic!` in library crates") admits only for
  that language. Omit `language:` for a language-agnostic architectural rule.

## Deriving BOTH — the 2×2 → proposal map

The cross-reference cell (SKILL.md § Cross-reference) tells you *what kind* of
proposal a read target warrants:

| Cell | Signal | Propose |
|------|--------|---------|
| **high churn + high centrality** | load-bearing and moving | **BOTH**: knowledge (how it works / what it wires, read from the code) + a policy (the invariant that must survive the churn — often `error`) |
| **low churn + high centrality** | stable core / invariant | mostly **policy** (`error`/`critical`) capturing the invariant; add knowledge only if the *why* is non-obvious from the code, and a memory only if the operator told you the why |
| **high churn + low centrality** | churny periphery | usually **neither**; knowledge only if it's a hot integration seam worth flagging (e.g. "config X is edited every release — treat as an interface") |
| **low churn + low centrality** | quiet leaf | **skip** |

The discipline: knowledge records the **is** (this is how the system is, read
from the code), a policy records the **ought** (this is what a change must
preserve). A single load-bearing target frequently yields one of each — the
knowledge so the next reader understands it, the policy so the next editor
doesn't break it. A memory is only for what you witnessed or were told.
Do not force a proposal from a cell that says skip; a thin capture pollutes the queue the operator must triage.

## Worked examples

Knowledge (from reading a high-churn/high-centrality extractor):

```json
{
  "kind_type": "knowledge",
  "payload": {
    "content": "Language extractors are data, not code: a new language is a row in wicked-estate-extract/languages.toml plus a <name>.scm query file — zero core change. Per-language match arms in Rust are a rejected pattern.",
    "class": "concept",
    "source": "wicked-estate:crates/wicked-estate-extract/languages.toml",
    "source_rev": "<commit sha you read>"
  },
  "facets": { "repo": "wicked-estate", "project": "wicked" }
}
```

Policy (architecture, from the same subsystem's invariant):

```json
{
  "kind_type": "policy:architecture",
  "payload": {
    "rule": "Every emitted Edge must carry {confidence, provenance, resolved_by}; never present a heuristic edge as a fact.",
    "severity": "error"
  },
  "facets": { "repo": "wicked-estate", "project": "wicked", "language": "rust" }
}
```

Policy (development, language-scoped, from a stable core with a clear guardrail):

```json
{
  "kind_type": "policy:development",
  "payload": {
    "rule": "Rust: no bare panic!/unwrap in library crates; surface a typed error.",
    "severity": "warn"
  },
  "facets": { "repo": "wicked-estate", "project": "wicked", "language": "rust" }
}
```

## Before you submit — recall first, then dedup

1. **Recall the existing record** (`wicked-garden-mem` `recall`, `scope_prefix:
   ""`, and estate `rules.recall` for policies). If the learning already exists,
   do not re-propose it — the queue is a human's triage list, and duplicates cost
   review time. Propose only the *delta*.
2. **One claim per proposal.** A memory that bundles three facts, or a policy that
   bundles three rules, can't be approved/rejected cleanly. Split them.
3. **Ground the claim in what you read.** Every proposal must trace to a target
   you actually opened in phase 3 (`FetchContent`/`RetrieveEntity`), not to a name
   you inferred. An ungrounded proposal is exactly the asserted-not-evidenced
   failure this method exists to avoid.

## Failure handling

- `-32602` (invalid kind_type/facets/payload): a *your-args* bug — fix the shape
  (lowercase kind_type suffix, object payload, valid axis tokens) and resubmit.
- `-32603` / transport / estate unreachable (shim `code: null`): the store or server
  failed. Do **not** drop the learning — collect the derived memories and policies into
  a structured block in your final report (the exact `{kind_type, payload, facets}`
  objects) so a human can submit them, and name the degrade explicitly.
  That block is the only record — a governed run writes no file; say whether the shim
  answered.
- Report captures honestly: "**proposed** N memories, M policies (pending
  review)", never "recorded" or "stored" — nothing is in the record until an
  operator approves it.
- **Always emit the machine-readable report line last** —
  `wicked-capture-report {"derived": N, "submitted": M, "failed": K}` — including on a
  degrade and on a legitimate 0. It is the engine's only evidence that the capture ran
  (wicked-core#535): no line, no pass.
