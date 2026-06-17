---
name: large-scale-migration
description: How to execute a LARGE MECHANICAL change across any codebase with LEVERAGE instead of an agent-grind or hand-edits — a cross-cutting migration, refactor, rename, dialect/framework/DB port, library adoption, or bulk transform. The map→transform→gate pattern: a deterministic transform driven by a source-of-truth map, proven by a differential-equivalence gate. Use when the work is "migrate all X to Y", "rename Z everywhere", "port to a new DB/dialect/framework", "adopt a library across N files", "refactor this pattern in M places", or any change touching dozens-to-thousands of sites. Language/DB/framework-agnostic — the thinking, not a specific tool.
---

# Large-scale mechanical change — leverage, not grind

A change touching dozens-to-thousands of sites is NOT N problems. It is a small number of repeated PATTERNS. Reaching for "fan out 1000 agents to edit each site", "hand-edit every file", or "sed the repo" is the paper bag. Reduce the work to **MAP → TRANSFORM → GATE** instead.

## The core pattern

1. **MAP** — the source of truth that already exists or can be **deterministically extracted**: an inventory of the affected sites, an ownership/registry table, a call graph, a schema. Build it with an **AST tool** (ts-morph, libcst, jscodeshift, tree-sitter, Roslyn…) or **semgrep** — never a regex string-grep (quote/escaping/comment blind spots), and never "an agent grepped and *thinks* it found them all." An exhaustive, reproducible map is the foundation; an approximate one ships a partial migration.
2. **TRANSFORM** — a **deterministic** operation over the map: a **codemod** (AST rewrite), **codegen** (emit from the map), or **regenerate** (edit a single source-of-truth + re-run a generator that produces the derived artifacts). NOT per-site LLM editing. The transform should **preserve semantics by construction** — rewrite the call *shape* while keeping the literal; move a block intact; change the *binding* not the *logic* — so correctness is structural, not hoped-for.
3. **GATE** — a **verifiable equivalence/green check**: **differential execution** (run old vs new on identical seeded inputs, assert identical outputs), the full test suite, or a lint count driven to 0. The change is trusted because it is **proven equivalent**, not because someone reviewed N diffs.

The bulk goes through the transform. The transform **self-flags** what it can't handle (the exceptions). Humans/agents touch **only the residue** — never the bulk.

## The TRANSFORM techniques menu (ranked: deterministic → AI)

The TRANSFORM step is not one tool — it is a ranked ladder. **Prefer the lowest-numbered technique that fully covers the task.** Determinism is cheaper to trust than generation: a recipe or codemod preserves semantics by construction and is re-runnable; an AI wave must be eval-gated every time. Mixing rungs 80/20 across one migration is fine (most go through rung 1–2, the awkward residue through 4–5). **Never reach for rung 4/5 for what a rung-1 recipe already does** — that trades a proven transform for a hoped-for one. **Record which rung you chose** per wave, so "should I use AI here?" is a defensible, auditable decision, not an implicit one.

| # | Technique | Use when |
|---|-----------|----------|
| 1 | **Recipe** (e.g. OpenRewrite, ts-morph preset, framework upgrade-assistant) | A well-known, parameterized transform already exists for this exact change (version bump, API rename, framework migration). Highest leverage, lowest risk — adopt it. |
| 2 | **AST codemod** (jscodeshift, libcst, tree-sitter, Roslyn, ts-morph) | No off-the-shelf recipe, but the change is a structural rewrite expressible as a tree operation (rewrite the call *shape*, move a block intact, change a binding). Deterministic, semantics-preserving by construction. |
| 3 | **Pattern-replace / codegen / regenerate** | The change is driven by a source-of-truth map — emit the derived artifacts from the map, or edit the single source + re-run a generator. (Structured replace only; **never** raw `sed`/regex on code — string blind spots break semantics silently.) |
| 4 | **AI-assisted wave (eval-gated)** | The transform needs judgment a tree op can't encode (idiomatic re-expression, semantic translation across a paradigm gap) but is still bulk-shaped. Run it in waves, each **gated by the differential-equivalence check** — never ship an AI wave on a build-green alone. |
| 5 | **Manual + AI pair** | Genuinely non-portable / one-off residue the transform self-flagged (cross-cutting joins, sync/async boundaries, non-portable platform features). Judgment-only, case-by-case — the *smallest* slice, never the bulk. |

The GATE is the same regardless of rung: differential equivalence (or suite-green / lint-to-0) is what makes the change trustworthy. A higher rung does not lower the bar — it raises it (rungs 4–5 need *more* fixture coverage, not less).

## Before you transform: make the INSTRUMENT trustworthy
You cannot drive a count to 0 if the count is a fiction. Fix the *measurement* FIRST:
- Does the lint/audit/inventory actually see **all** the cases? Prove it: inject a known violation and confirm it's caught. (Real failure mode: a "complete" audit that masked single-quoted strings and silently under-counted by hundreds.)
- Is the **baseline** the right one? Diffing the after-state against a baseline that *already contains part of the change* catches nothing — pin the true before-state.

## Buy / rewrite / build — not "write more code"
Solve for the OUTCOME with maximum leverage, per sub-problem:
- An **OSS component** that meets the requirement beats building it — a query builder, an **in-process embedded engine** for tests (so the test→fix loop needs no infra), a parser/translator. Adopt it; build only the thin seam it doesn't cover.
- A clean **rewrite** of a section (you have the working code as the spec) beats editing it in place across dozens of touch-points.

## The rules (non-negotiable)
- **No grandfathering.** "Done" = the count is 0 **AND** zero exemptions (suppressions / allow-markers / "left raw with a TODO / DEFERRAL"). Fix the code; never exempt it. An exemption is a landmine that *defeats the migration's purpose* — it preserves the exact case the migration exists to remove, and it stays invisible until it breaks.
- **Differential equivalence is the trust — not review.** `old(input) === new(input)` on real seeded data. Strength tracks fixture coverage → seed broadly; an empty fixture passes trivially and lies.
- **Residue is small, self-flagged, judgment-only.** The transform reports what it couldn't do; that list is the only place to reason case-by-case (cross-cutting joins, genuinely non-portable constructs, sync/async boundaries).
- **Prove the runtime — don't trust build-green.** Build/test green ≠ feature works, *especially* for LLM/agent features (the assembled context can drift while stored rows stay byte-identical → degraded reasoning / hallucination that no unit test catches). Prove the running process serves the right build; **grade** functional outputs (content correctness + faithfulness), don't just check a 200-OK.
- **No implicit completeness, and never narrow the DoD to skip work.** Name what is NOT done. If a phase can't reach its green gate, STOP there and name the blocker — do not declare a convenient subset "done."

## Worked example (transferable): a data-access migration → second engine
Goal: move ~1,900 raw `db.prepare(sql)`-style call sites behind one typed port, then run the app on a second DB engine/dialect — without hand-editing 1,900 sites or standing up infra.
- **MAP:** an AST extractor walks the *call expressions* (matching the call node, not string contents → no quote blind spot) → an exhaustive inventory of every query, its tables, and static-vs-dynamic shape.
- **TRANSFORM:** a codemod rewrites the call *shape* (e.g. positional `?` → named params; SQL literal preserved) and injects the port; the sync→async cascade propagates up the call graph; sync-boundaries self-flag for manual handling.
- **GATE:** a differential test runs the OLD query and the NEW port call against the **same seeded in-memory DB** and asserts byte-identical results (rows + affected-rows + resulting state). Per-module then full-suite green is the bar.
- **Second engine:** adopt an **in-process embedded build of the target engine** for tests (no server), translate **only** the non-portable patterns the inventory *proves* exist (dialect translation at the adapter boundary), and route truly-non-portable features (full-text, vector) behind **thin adapter interfaces**. The **cross-engine differential** (same query, both engines, equivalent) is the gate.
- **Same pattern, different map, per phase:** correcting an *ownership/registry map* = edit the single source-of-truth + **regenerate** the derived artifacts (never hand-edit the derivatives). Relocating code by an ownership map = a codemod keyed on that map. Isolating onto separate connections/processes = a **config flip** on a registry the port already abstracts (no code rewrite — that's the payoff of routing everything through the port first).

## Anti-patterns this kills
- "Fan out 1,000 agents to hand-edit each site" — context blow-up, non-deterministic, no equivalence proof.
- "sed / regex replace across the repo" — string blind spots, false positives, breaks semantics silently.
- "Exempt the hard ones / leave a TODO / suppress the lint" — grandfathering, the landmine.
- "Build green + suite green, ship it" — never proved the feature, never proved the runtime.
- "This subset counts as done" — narrowing the DoD to skip work.

## Pair with (if your project has them)
A "prove the feature works, not just build-green" discipline; a "no silent failures" discipline; and a recorded "definition of done" you refuse to narrow.
