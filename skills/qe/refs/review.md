---
phase_relevance: ["review"]
archetype_relevance: ["review", "build"]
---

<!-- Action ref of the `wicked-garden-qe` router (Phase 6b port of
     wicked-testing's `review` orchestrator). Loaded on demand
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
| Production metrics, post-deploy                            | `wicked-garden-qe-production-quality-engineer` |

### Dispatch block (executable)

Every id in the tables above is a forked worker skill (`context: fork`) —
invoke it with the Skill tool so it runs in an isolated context. For the
reviewer this is isolation-critical: the forked context is what guarantees
it never sees the executor's history.

```
Skill(
  skill="wicked-garden-qe-acceptance-test-reviewer",
  args="""Review the evidence manifest at the path below and render an
independent verdict.

## Evidence Directory
.wicked-testing/evidence/{RUN_ID}/

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
- `FAIL` — assertion unsatisfied, evidence contradicts, or spec-code divergence
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

- `docs/INTEGRATION.md` (wicked-testing npm package)
- `docs/EVIDENCE.md` (wicked-testing npm package)
- `../../qe-acceptance-test-reviewer/SKILL.md`, `../../qe-semantic-reviewer/SKILL.md`,
  `../../qe-code-analyzer/SKILL.md`, `../../qe-production-quality-engineer/SKILL.md`

## Helper resolution (`{WT_LIB}`)

`{WT_LIB}` is the wicked-testing npm package's `lib/` directory — the helper
modules stay in that package until the 6c extraction. Resolve it (cross-platform):

```bash
WT_LIB="$(npm root -g 2>/dev/null)/wicked-testing/lib"
[ -d "$WT_LIB" ] || WT_LIB="$(npm root 2>/dev/null)/wicked-testing/lib"
```
