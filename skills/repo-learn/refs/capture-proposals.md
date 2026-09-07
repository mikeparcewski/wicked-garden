# Capture — memories AND policies as estate proposals

The learning phase ends by writing back **two kinds** of record through the estate
MCP **`proposal.submit`** tool: **memories** (what is *true* about this repo) and
**policies** (what *should hold* in it). Both land in estate's **inert proposal
queue** — a type-generic write surface that is a PERMITTED safe write **even under
`--readonly`**, because a proposal is never recalled or applied until an operator
approves it. A governed worker's estate MCP already opens the operator GLOBAL
store and permits `proposal.submit`, so proposals surface in the studio Memories /
Policies review UI. This is *propose, not assert* — you never inject a fact into
the record; a human promotes it.

## The `proposal.submit` contract (wire shape)

`proposal.submit` takes exactly three caller-supplied fields:

| Field | Type | Rule |
|-------|------|------|
| `kind_type` | string | `"memory"` OR `"policy:<type>"`; must match `^[a-z][a-z0-9_-]*(:[a-z][a-z0-9_-]*)?$` |
| `payload`   | JSON **object** | required; a present non-object is rejected `-32602` (never silently defaulted) |
| `facets`    | JSON object of `axis:value` strings | optional; each axis is a lowercase token `^[a-z][a-z0-9_-]*$`, each value non-empty |

**`provenance` is NOT a caller field.** The server stamps it from its own launch
env (`WICKED_RUN_ID` / `WICKED_RUN_UNIT` / `WICKED_RUN_AGENT`) — a worker cannot
forge its own attribution, and passing `provenance` in args is not honored. Do not
construct it.

On success the tool returns `{"id": "<proposal-id>"}`. A malformed `kind_type`,
`facets`, or a non-object `payload` fails loud with `-32602` — fix and resubmit,
never swallow.

### `<type>` for policies (the seven steering types)

`policy:` must be suffixed with exactly one: `architecture` · `development` ·
`security` · `testing` · `operations` · `compliance` · `design-ux`. These are the
estate/steering types — pick the one the rule governs, not a freeform tag.

## Memory payload + facets

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
- `tier` — `"semantic"` for stable facts/decisions/gotchas ("X is wired via the
  bus, not a direct call"); `"procedural"` for a repeatable how-to/convention
  ("to add a language, drop a row in languages.toml + a .scm file — no core
  change").
- `facets` — `repo:` and `project:` locate the memory so faceted recall admits it
  for the right work. Use the repo's directory/remote name and the umbrella
  project (here, `wicked`).

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
| **high churn + high centrality** | load-bearing and moving | **BOTH**: a memory (how it works / why it churns / what it wires) + a policy (the invariant that must survive the churn — often `error`) |
| **low churn + high centrality** | stable core / invariant | mostly **policy** (`error`/`critical`) capturing the invariant; add a memory only if the *why* is non-obvious |
| **high churn + low centrality** | churny periphery | usually **neither**; a memory only if it's a hot integration seam worth flagging (e.g. "config X is edited every release — treat as an interface") |
| **low churn + low centrality** | quiet leaf | **skip** |

The discipline: a memory records the **is** (this is how the system is), a policy
records the **ought** (this is what a change must preserve). A single load-bearing
target frequently yields one of each — the memory so the next reader understands
it, the policy so the next editor doesn't break it. Do not force a proposal from a
cell that says skip; a thin capture pollutes the queue the operator must triage.

## Worked examples

Memory (procedural, from reading a high-churn/high-centrality extractor):

```json
{
  "kind_type": "memory",
  "payload": {
    "content": "Language extractors are data, not code: a new language is a row in wicked-estate-extract/languages.toml plus a <name>.scm query file — zero core change. Per-language match arms in Rust are a rejected pattern.",
    "tier": "procedural"
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
- `-32603` / transport / MCP unreachable: the store or server failed. Do **not**
  drop the learning — collect the derived memories and policies into a structured
  block in your final report (the exact `{kind_type, payload, facets}` objects) so
  a human or a later run can submit them, and name the degrade explicitly.
- Report captures honestly: "**proposed** N memories, M policies (pending
  review)", never "recorded" or "stored" — nothing is in the record until an
  operator approves it.
