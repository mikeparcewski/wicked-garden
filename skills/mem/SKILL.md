---
name: wicked-garden-mem
description: |
  Cross-session memory + knowledge over wicked-estate.
  One skill, routed actions: store (a durable decision/pattern/gotcha),
  recall (the current project's memories; all scopes on opt-in), answer (cited
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
  base"; "capture what we learned" / session teardown. wicked-estate is the
  engine; this skill is the agent surface.
metadata:
  role: router
  phases: "*"
  archetypes: "*"
---

# wicked-garden:mem — memory + knowledge over wicked-estate

The engine is wicked-estate (its `memory.*` / `knowledge.*` tools, reached through the
read-only estate shim the backend script spawns — the one way on every seat); the seam
is one deterministic backend script. Per estate's DEC-R doctrine, the agent
reasons (what to store, how to chunk, what an answer means) and the engine
ranks/persists — the backend only moves JSON. Every action degrades
gracefully: when estate is unreachable the backend returns
`{"ok": false, "reason": ...}` instead of crashing.

```bash
wicked-garden run \
  scripts/mem/estate_memory.py <action> '<json-args>'
```

Long content: pass `-` as json-args and pipe the JSON via stdin.

**Every call from a seat carries `--readonly`** — a governed run's unit, a chat turn, any session
where you are the agent (when in doubt, `--readonly`):
```bash
wicked-garden run scripts/mem/estate_memory.py <action> '<json-args>' --readonly
```
A human operator at a terminal may omit it to `store` / `ingest` / `forget`. The backend forwards
`--readonly` to the estate shim (`scripts/_estate_client.py`), which spawns the estate binary
read-only with the store pinned from
the environment (`WICKED_ESTATE_DB` / `WICKED_HOME` / `WICKED_MEMORY_DB`) or `--db <path>`; an
unpinned store is refused (`ok: false`), and `store` / `capture-batch` / `ingest` / `write` /
`forget` are refused by the read-only engine — capture learnings as proposals instead (the
`wicked-garden-repo-learn` skill's capture contract). `recall` / `review` / `sources` / `health`
work unchanged. Spell `--readonly` exactly (`--read-only` is a usage error). This is the one way
to the stores on every seat and in every session kind: no estate tool is registered on a seat,
nothing to connect, nothing to fall back to.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Routing

| Action | Use for | How |
|--------|---------|-----|
| `store` | persist one learning (decision, pattern, gotcha, discovery) | § Store |
| `recall` | find memories ("what do we know about X") | § Recall |
| `answer` | grounded, cited answer from the stores | the `wicked-garden-search` skill's `refs/answer.md` |
| `review` | browse what's stored (counts by kind/tier, scope digest) | § Review / Maintain |
| `forget` | erase a scope subtree (kind-guarded) | § Forget |
| `maintain` | reflect + coverage pulse (consolidation runs in-store) | § Review / Maintain |
| `ingest` | file/dir → knowledge chunks (pdf/docx/pptx/xlsx/images via vision) | dispatch **wicked-garden-mem-ingest** |
| `capture` | end-of-session sweep → memories | dispatch **wicked-garden-mem-capture** |

Scope conventions, kind/tier vocabulary, and the brain-migration layout:
[refs/scopes.md](refs/scopes.md).

A chat seat asked by wicked-crew to label the operator's decisions reads
[refs/decision-report.md](refs/decision-report.md) and ends its reply with that block.

## Store

1. Apply the durability test: *would this help a fresh session, on a
   different task, three months from now?* Store a rule, why it holds, and
   when it applies, in 1–3 self-contained sentences. Never store progress or
   status, versions, SHAs, PR/run ids, PIDs, "today", or what the repo,
   CHANGELOG or tracker already records. The backend refuses the mechanical
   cases with `not a durable learning`; treat that as "don't store", not as
   an error to work around.
2. Pick `kind` (+ tier defaults): `fact` → semantic (decisions, gotchas,
   stable facts) · `skill` → procedural (patterns, conventions, how-tos) ·
   `entity` → semantic (a person/system profile). Add `about` tags for
   recall hooks.
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

By default recall searches the current project (`project:<cwd-basename>`)
and its ancestors, so root-scoped memories stay visible and other projects'
memories do not leak in. Pass `"scope"` to recall another project the same
way. Searching everything, brain-migrated leaves
(`brain:<project>/doc:<id>`) included, is an explicit opt-in:
`"scope_prefix": ""` (or `"scope_prefix": "project:<name>"` for one subtree). Items return content, scope, tier,
and score; present the top hits and cite `memory_id`/scope when the user
needs provenance. For a synthesized, citation-bearing answer use the
`answer` action instead.

**Steering doctrine** (the governance rules, 7 steering types) lives in the
knowledge store under `wiki:` scopes (a historical prefix — e.g.
`wiki:architecture`: planes, storage doctrine, event grammar, ADR
rationale): recall it with `knowledge.recall` /
`{"scope_prefix": "wiki:"}` via `answer`, and recall the *enforceable* rules
behind it with the estate `rules.recall` tool through the read-only shim —
`wicked-garden run scripts/_estate_client.py --readonly call '{"tool":"rules.recall","arguments":{…}}'` — (faceted, severity-ordered,
each hit citing its source doc). Managing steering (import / chat / edit /
retire) is operator work — see `crates/wicked-governance/STEERING.md`
in wicked-core.

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

No hook extracts memories from the transcript. The Stop hook used to
pattern-match "decided to…" / "going to…" and filled the store with
narration, so it was removed: a learning is stored because someone chose to
store it.
