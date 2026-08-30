---
name: wicked-garden-mem
user-invocable: true
description: |
  Cross-session memory + knowledge over wicked-estate (FOLD-1, Phase 5-S7).
  One skill, routed actions: store (capture a decision/pattern/gotcha as a
  memory), recall (query memories across every scope), answer (cited
  synthesis from the knowledge + memory stores), review (browse coverage by
  kind/tier), forget (kind-guarded erase of a scope subtree), maintain
  (reflect + coverage pulse; estate consolidates in-store), ingest (file or
  directory → knowledge chunks, binary docs via LLM vision), and capture
  (session-teardown sweep of decisions/patterns/gotchas).

  Use when: "remember this" / "store this decision" / "note this gotcha";
  "recall what we decided" / "what do I know about X"; "answer from the
  knowledge base" / "ask the record"; "review my memories" / "what have I
  stored"; "forget this" / "erase that scope"; "consolidate memories";
  "ingest this file/pdf/directory" / "add this document to the knowledge
  base"; "capture what we learned" / session teardown. Replaces the retired
  brain product's memory/review/forget/ingest/session-teardown skill cluster —
  wicked-estate is the engine, this is the agent surface.
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# wicked-garden:mem — memory + knowledge over wicked-estate

The engine is wicked-estate (`memory.*` / `knowledge.*` MCP tools); the seam
is one deterministic backend script. Per estate's DEC-R doctrine, the agent
reasons (what to store, how to chunk, what an answer means) and the engine
ranks/persists — the backend only moves JSON. Every action degrades
gracefully: when estate is unreachable the backend returns
`{"ok": false, "reason": ...}` instead of crashing.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/mem/estate_memory.py" <action> '<json-args>'
```

Long content: pass `-` as json-args and pipe the JSON via stdin.

## Routing

| Action | Use for | How |
|--------|---------|-----|
| `store` | persist one learning (decision, pattern, gotcha, discovery) | § Store |
| `recall` | find memories ("what do we know about X") | § Recall |
| `answer` | grounded, cited answer from the stores | [../search/refs/answer.md](../search/refs/answer.md) |
| `review` | browse what's stored (counts by kind/tier, scope digest) | § Review / Maintain |
| `forget` | erase a scope subtree (kind-guarded) | § Forget |
| `maintain` | reflect + coverage pulse (consolidation runs in-store) | § Review / Maintain |
| `ingest` | file/dir → knowledge chunks (pdf/docx/pptx/xlsx/images via vision) | dispatch **wicked-garden-mem-ingest** |
| `capture` | end-of-session sweep → memories | dispatch **wicked-garden-mem-capture** |

Scope conventions, kind/tier vocabulary, and the brain-migration layout:
[refs/scopes.md](refs/scopes.md).

## Store

1. Distill the learning into 1–3 self-contained sentences (the *why* and
   *what*, not the *how*). Skip trivia — store only what a future session
   needs.
2. Pick `kind` (+ tier defaults): `fact` → semantic (decisions, gotchas,
   stable facts) · `skill` → procedural (patterns, conventions, how-tos) ·
   `episode` → episodic (events: "X happened when Y") · `entity` → semantic
   (a person/system profile) · `working` → working (session scratch). Add
   `about` tags for recall hooks.
3. Run the backend:
   ```bash
   ... estate_memory.py store '{"content":"<distilled>","kind":"fact","about":["tag1","tag2"]}'
   ```
   Scope defaults to `project:<cwd-basename>`; pass `"scope"` to override
   (see refs/scopes.md).
4. Confirm the returned `memory_id`; on `ok: false` report the degrade — do
   not silently drop the learning.

## Recall

```bash
... estate_memory.py recall '{"query":"<topic>"}'
```

Default `scope_prefix: ""` searches the ENTIRE subtree — including
brain-migrated leaves (`brain:<project>/doc:<id>`). Narrow with
`"scope_prefix": "project:<name>"`, or pass `"scope"` instead for estate's
ancestor-visible inheritance semantics. Items return content, scope, tier,
and score; present the top hits and cite `memory_id`/scope when the user
needs provenance. For a synthesized, citation-bearing answer use the
`answer` action instead.

**Architecture-wiki doctrine** lives in the knowledge store under `wiki:`
scopes (e.g. `wiki:architecture` — planes, storage doctrine, event grammar,
ADR rationale): recall it with `knowledge.recall` /
`{"scope_prefix": "wiki:"}` via `answer`, and recall the *enforceable* rules
behind it with the estate MCP `rules.recall` tool (faceted, severity-ordered,
each hit citing its source doc). Authoring/seeding/retiring the wiki is
operator work — see wicked-core's `crates/wicked-governance/WIKI.md`.

## Review / Maintain

```bash
... estate_memory.py review '{}'                       # counts by kind/tier
... estate_memory.py review '{"scope":"project:x"}'    # + distilled digest
... estate_memory.py maintain '{}'                     # reflect + coverage
```

Estate owns the memory lifecycle in-store (decay, promotion, merge — the
consolidate engine); `maintain` is the user-facing pulse, not a batch job to
schedule. Report `total`, the kind/tier distribution, and any distilled
facts from `reflect`.

## Forget

```bash
... estate_memory.py forget '{"scope_prefix":"brain:old-project"}'
```

Erase is subtree-wide and permanent, so the backend enforces a kind-guard:
the prefix must contain a `kind:id` segment. Erasing everything requires an
explicit `{"scope_prefix": "", "confirm_erase_all": true}` — confirm with
the user before ever doing that. Report `deleted_count`.

## Ingest — files and directories into the knowledge store

Dispatch the **wicked-garden-mem-ingest** fork worker with the source path
(and optional scope/title). It detects text vs binary, chunks text
deterministically, extracts pdf/docx/pptx/xlsx/images via LLM vision, writes
through estate `knowledge.ingest` (every chunk carries `source` provenance),
and verifies with a seeded recall. Estate's embedded method card
(`skill://knowledge-ingest/SKILL.md`) is the chunking doctrine.

## Capture — session teardown

Dispatch the **wicked-garden-mem-capture** fork worker at session end ("
capture what we learned", before /clear or exit). It sweeps the conversation
for decisions, patterns, gotchas, discoveries, and preferences, classifies
each onto the estate kind/tier vocabulary, and batch-writes them via
`capture-batch`. Report what it stored.

**Auto-memorize (ambient path)**: independent of this action, the Stop hook
emits `wicked.garden.fact.extracted` events for decisions/discoveries it
spots and drains them into estate via `scripts/mem/auto_memorize.py`
(durable wicked-bus cursor, content-hash dedup, native DLQ — inspect with
`... auto_memorize.py status '{}'` or `wicked-bus dlq list`).
