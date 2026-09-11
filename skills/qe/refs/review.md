---
phase_relevance: ["review"]
archetype_relevance: ["review", "build"]
---

<!-- Action ref of the `wicked-garden-qe` router (Phase 6b port of
     the retired wicked-testing plugin's `review` orchestrator). Loaded on demand <!-- historical -->
     via Read() from the router's `review` action — not a skill. -->


# qe review — full playbook

Reviewing is its own discipline. This skill is the place where verdicts are
rendered — not inside the executor, not as a side effect of running.

## Usage

```
wicked-garden-qe review [run-id | path] [--spec <path>] [--focus <area>]
```

Arguments map onto the dispatch table below:

- `run-id` — review a specific recorded run: `wicked-garden-qe-acceptance-test-reviewer` over
  the run's evidence manifest
- `path` — review a source tree or test directory
- `--spec <path>` — supplies the acceptance criteria / spec document
- `--focus semantic` — spec-to-code alignment: `wicked-garden-qe-semantic-reviewer` Gap Report
- `--focus quality` — test quality audit: `wicked-garden-qe-code-analyzer` + the
  test-code-quality Tier-2 specialist
- `--focus testability` — code testability review: `wicked-garden-qe-code-analyzer` static
  review

## When to use

- A run just finished and needs an independent verdict
- Post-implementation: does the code actually match the spec?
- The test suite itself needs a quality pass
- A code review needs a testability-focused perspective

## How it dispatches

| Input                                                      | Dispatch                                     |
|------------------------------------------------------------|----------------------------------------------|
| A run's evidence manifest                                  | `wicked-garden-qe-acceptance-test-reviewer`    |
| Spec + implementation (post-code divergence)               | `wicked-garden-qe-semantic-reviewer`           |
| Test suite path                                            | `wicked-garden-qe-code-analyzer` + Tier-2      |
| A PLAN + the produced tests it claims (the `author` output) | `wicked-garden-qe-test-code-quality-auditor` — § Reviewing produced tests |
| Production metrics, post-deploy                            | `wicked-garden-qe-production-quality-engineer` |

### Dispatch block (executable)

Every id in the tables above is a forked worker skill (`context: fork`) —
invoke it with the Skill tool so it runs in an isolated context. For the
reviewer this is isolation-critical: the forked context is what guarantees
it never sees the executor's history.

Dispatch uses the Skill tool on Claude Code (a fresh forked context). On any other harness, open the named skill's `SKILL.md` from your skills catalog and carry out its instructions inline with the given args, then continue here.

```
Skill(
  skill="wicked-garden-qe-acceptance-test-reviewer",
  args="""Review the evidence manifest at the path below and render an
independent verdict.

## Evidence Directory
.wicked-qe/evidence/{RUN_ID}/

## Scenario Path
{path — read it yourself}

## Instructions
1. Read the scenario file.
2. Read the test plan from the evidence dir.
3. Read evidence files in the evidence dir (step-N.json, artifacts, optional
   context.md). Do NOT use any other context — you never saw the execution.
4. For each assertion, evaluate evidence → verdict (PASS / FAIL / INCONCLUSIVE).
5. If context.md is present, treat it as pre-vetted cold knowledge. If it
   contains a prior verdict, run_id, historical counts, or executor
   reasoning, flag as CONTEXT_CONTAMINATION and return INCONCLUSIVE.

Return the verdict, reasoning per assertion, and next actions.
DO NOT reference executor conversation context beyond the files above."""
)
```

For a spec-vs-code divergence review, swap the `skill` id to
`wicked-garden-qe-semantic-reviewer` and pass the spec path + implementation
path. For a standalone test-suite quality review (no run, just the source),
dispatch `wicked-garden-qe-code-analyzer` + the relevant Tier-2 specialist from the table below.

## Independence

Reviewers work from evidence and spec, not from the executor's story.
`wicked-garden-qe-acceptance-test-reviewer` is isolated (Read-only tools, `context: fork`
forked invocation, scrubbed `context.md` via `{WT_LIB}/context-md-validator.mjs`)
to keep its verdict honest. Do not pre-narrate what it should find.

## Reviewing produced tests (the `author` output: a PLAN + test files)

When the input is a PLAN with an execution table plus the test files it claims
— the `review` phase of a governed test-authoring run, or any "are these new
tests any good" — the reviewer re-derives every claim; it never takes the
author's word. Written after the wave-6 acceptance review (R4-r2 / F-7R2-015),
where seven default-allow gates passed a Playwright suite nobody had run.
Dispatch `wicked-garden-qe-test-code-quality-auditor` with the block below;
where the harness is runnable it re-runs the produced files itself.

1. **Every `covered` claim is opened at its `file:line`.** Confirm the test
   exists, that its assertion is the behaviour the row names, and that the
   count of `it` / `test` / `def test_` blocks matches the PLAN's numbers (new
   vs pre-existing reported separately). A `covered` row without a citation,
   or whose citation does not hold, is reclassified `unverified` and is a
   finding; a padded total is a finding.
2. **Every produced file has an execution record** — file · exact command ·
   result. Re-run at least the produced files when the harness is available
   and compare with the record. A produced file with no record, a record with
   no result, or a `needs-fixture` e2e that was never run against its fixture
   → **the plan FAILS** (`[unexecuted-test]`), whatever else holds. The
   "evidence-gated" label is decided here, not by the author.
3. **Mutate or reason — at least two behaviours.** For ≥ 2 tested behaviours
   either apply a deliberate source mutation (swallow the error, invert the
   guard, drop the branch), re-run the test, confirm it FAILS, and restore the
   source — guarded: `git status --porcelain -- <file>` must be empty before
   you mutate (otherwise copy the file aside and restore from the copy — never
   `git checkout`, which would also discard the author's uncommitted edit), and
   `git diff --quiet -- <file>` afterwards proves the tree is byte-identical;
   or — when you cannot run — write the specific mutation and the assertion
   line that would catch it. A test for which no failing mutation can be named
   is tautological → that row FAILS.
4. **Behaviour vs implementation.** Flag tests that assert internal structure,
   a mock asserting on a mock, a snapshot of a fixture, or that would still
   pass with the implementation deleted.
5. **e2e oracles are checked against the source.** For every selector, test id
   and text an e2e waits on, confirm it is rendered on the route the test
   visits under the fixture the PLAN names (read the component; `grep` the
   `data-testid`). An oracle that can never match is `[scenario-defect]`.
6. **Scope honesty.** The PLAN's `not covered` rows must name what the intent
   asked for and why it is absent; an intent area with no row and no test is
   a finding.
7. **The verdict goes back to the run.** The reviewer never opens, edits or
   merges the PR and never pushes — the run's deliver phase (or the human)
   does; a reviewer that ships is a creator grading itself.

Verdict vocabulary (`MODE=produced-test`): **`PASS`** only when 1–7 hold with
zero findings — every `covered` claim verified at its `path:line`, every
produced test executed and green (your re-run reproduces the record), no
`unverified` or `failing` row; **`CONDITIONAL`** with the fixes listed when only
P1/P2 rows fail (implementation-shaped test, padded total, silent scope gap,
style); **`FAIL`** on any `[unexecuted-test]`, red produced test, tautological
test, unsupported-`covered` claim, or `[scenario-defect]` oracle. Cite
`file:line` for every finding. The auditor's §9 carries the same rule.

Dispatch fallback as in § Dispatch block above: without a Skill tool, open the
named skill's `SKILL.md` and carry the args out inline.

```
Skill(
  skill="wicked-garden-qe-test-code-quality-auditor",
  args="""Review the produced tests named in the PLAN below against the qe
`review` playbook's "Reviewing produced tests" rules. Re-derive every claim.

## Mode
MODE: produced-test — grade per the auditor's §9 produced-test verdict
(`PASS` reachable), not its §5 audit.

## PLAN
{path to the PLAN carrying the execution table}

## Produced files
{paths}

## Instructions
1. Open every `covered` row at its file:line; reclassify unsupported rows
   `unverified`; recount new vs pre-existing tests.
2. Confirm every produced file has an execution record (file · command ·
   result). None — or a `needs-fixture` e2e never run against its fixture —
   is VERDICT=FAIL `[unexecuted-test]`.
3. Re-run the produced files when the harness is available; compare with
   the record.
4. Mutate-or-reason about at least two tested behaviours; name the failing
   mutation and the assertion that catches it; restore any mutated source
   (guarded: clean `git status` on the file first, `git diff --quiet` after).
5. Check every e2e selector / test id / text against the source on the
   visited route under the named fixture.
6. Check the PLAN's `not covered` rows against the intent.
7. Flag implementation-shaped tests: internal structure, a mock asserting on
   a mock, a snapshot of a fixture, or one that would pass with the
   implementation deleted.

Return `VERDICT={PASS|CONDITIONAL|FAIL} MODE=produced-test` — PASS only with
every claim verified at path:line, every produced test executed and green, no
`unverified` — and per-row findings with file:line. Do NOT push, open, edit or
merge a PR — the run's deliver phase delivers."""
)
```

## Tier-2 specialists this skill routes to

For domain-specific reviews, dispatch the specialist. Each returns a verdict
or a list of findings the skill folds into the review output:

| Trigger                                                | Specialist                                  |
|--------------------------------------------------------|---------------------------------------------|
| "Is this test suite effective?" (mutation kill rate)   | `wicked-garden-qe-mutation-test-engineer`     |
| "Did this suite exercise WCAG surfaces?"               | `wicked-garden-qe-a11y-test-engineer`         |
| Translated-copy review (pseudoloc, RTL, pluralization) | `wicked-garden-qe-localization-test-engineer` |
| Observability-assertion review (logs / traces / PII)   | `wicked-garden-qe-observability-test-engineer` |
| Flake detection for a scenario's history               | `wicked-garden-qe-flaky-test-hunter`          |
| Untested-path audit                                    | `wicked-garden-qe-coverage-archaeologist`     |
| "Does this meet contract?" (Pact / OpenAPI)            | `wicked-garden-qe-contract-testing-engineer`  |
| Audit test-suite quality (smells, dead tests)          | `wicked-garden-qe-test-code-quality-auditor`  |
| Audit snapshot hygiene (stale, over-broad, dead)       | `wicked-garden-qe-snapshot-hygiene-auditor`   |
| Release gate — GO / CONDITIONAL / NO-GO                | `wicked-garden-qe-release-readiness-engineer` |
| Compliance evidence review (SOC2 / HIPAA / GDPR)       | `wicked-garden-qe-compliance-test-engineer`   |

## Verdict semantics

- `PASS` — evidence + spec agree, tests exercise what was changed
- `FAIL` — assertion unsatisfied, evidence contradicts, spec-code divergence, or
  a produced test with no execution record (`[unexecuted-test]` — an e2e nobody
  ran is a FAIL, never a PASS on paper)
- `N-A` — reviewable item doesn't apply (must be justified)
- `SKIP` — applicable but deferred (ticket required)
- `CONDITIONAL` — approve with listed fixes before ship
- `INCONCLUSIVE` — evidence missing OR context contaminated

## Output

- Verdict + reason
- Evidence citations (file paths, line numbers, AC IDs)
- Next actions: specific, assignable, bounded

Emits `wicked.test.verdict.created` on the bus when present.

## References

- [refs/integration.md](refs/integration.md)
- [refs/evidence.md](refs/evidence.md)
- `wicked-garden-qe-acceptance-test-reviewer`, `wicked-garden-qe-semantic-reviewer`,
  `wicked-garden-qe-code-analyzer`, `wicked-garden-qe-production-quality-engineer`

## Helper resolution (`{WT_LIB}`)

`{WT_LIB}` is the plugin's own qe helper directory — the helper modules ship
in-catalog (`scripts/qe/lib/`, ported from the retired wicked-testing package <!-- historical -->
in Phase 6c). Resolve it (cross-platform):

```bash
WT_LIB="$(wicked-garden path scripts/qe/lib)"
```
