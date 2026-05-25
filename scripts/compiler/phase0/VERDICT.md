# Phase-0 Verdict — compiler falsification probe

**Result: PASS (4/4).** The compiler thesis cleared its Phase-0 bar.
Prototype under `scripts/compiler/phase0/` — committed as provenance, not
production code. The production emit stage is `scripts/compiler/compile.py`,
which reuses this prototype's `detect.py` and `emit.py`.

## What was tested

Can ONE repo-agnostic detector infer a repo's `test_command` + evidence
conventions, and can ONE emitter produce a working repo-native
claim→evidence lint, **without per-repo hand-correction**, across
structurally different repos? Falsifier: if it needs hand-correction per
repo, the "compiler" is really templating-with-manual-wiring.

## Targets (real repos)

| Repo | Ecosystem | Detected `test_command` | Conf | Notes |
|---|---|---|---|---|
| command_iq | node pnpm **monorepo** | `pnpm test` (→ turbo wrapper) | 0.9 | real `claims:` frontmatter + real evidence dir both detected |
| wicked-bus | node single-package | `npm test` (→ `vitest run`) | 0.9 | `coverage/` evidence dir detected |
| Enterprise-AISDLC | python | `python3 -m pytest` | 0.55 | **ambiguity flagged**: Makefile `test:` AND pytest both present |
| memos | **go** (foreign, no package.json) | `go test ./...` | 0.9 | clean foreign-ecosystem detection |

## Findings

1. **Detection generalized, unaided** — all 4 ecosystems, including the
   foreign no-`package.json` Go path. The ambiguous python case was
   *flagged* (conf 0.55), not silently guessed. This was the risky core.
2. **The emitter is genuinely generic** — the first emit had a UNIFORM
   bug (mixed `N passed | M failed` evidence slipped through a
   "tests pass" claim — the §7 "5848 pass / 4 fail → build green"
   failure mode). ONE central fix in `emit.py` flipped all 4 repos.
   A per-repo-rigged emitter could not be fixed by a single central edit.
3. **The emitted lint runs with zero wicked-garden runtime** — plain
   stdlib python; catches missing-evidence AND contradictory-evidence
   claims; embeds the repo's own re-verification command.

## Honest caveats (what Phase-0 did NOT prove)

- **Claims surface is the real next problem.** Only command_iq had a
  structured `claims:` convention to detect. The other 3 fell back to
  `commit-msg` (a stub). The lint LOGIC was proven via staged fixtures,
  but in practice 3/4 repos have no claims doc to check. → Phase-2 emit
  must *install* the claim+evidence convention where absent, not just
  detect it. The compiler establishes conventions in greenfield repos.
- **Honest-control real-runs were mostly synthetic** (vitest invocation
  issues; go toolchain timed out). Only python got a REAL run. The
  fabrication-catch gate held regardless, but "detected command actually
  executes & passes" is only truly proven for 1/4.
- **risk_surfaces detection was not exercised** by the lint (that's the
  validator-pair trigger — Phase 3).
- n=4, narrow sample.

## Decision

Plan gate (`>=2/3 → compiler is real → proceed`) is met decisively.
**Proceed to Phase 2 (compiler emit stage) + Phase 1 (verb re-index +
re-runner) in parallel.** The sharpened Phase-2 scope: the emit stage
must scaffold the claims+evidence convention, since most repos lack one.
