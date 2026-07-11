# build — plan / implement / test / review

The most common archetype. Implement and ship a feature or fix. **Test
rigor scales with complexity, blast_radius, and novelty** — a one-line
typo fix and a new auth path are both `build` archetype, but the test
phase looks different.

## Phase shape

| Phase     | Goal                                                |
|-----------|-----------------------------------------------------|
| plan      | Name the diff in 2–3 sentences. Pick the test rigor. |
| implement | Write the change. Stay in the diff; resist drift.   |
| test      | Verify the diff does what plan said. Rigor scales.  |
| review    | Hand off to the `review` archetype if needed.       |

## Produces

- **Shipped code**: a commit (or PR) with the diff.
- **Test report**: at minimum, evidence that the change was exercised.
  At higher rigor: unit tests, integration tests, acceptance evidence.

The review gate **re-derives** these via `wicked-loom` (`scripts/qe/vault_gate.py` shells `wicked-loom gate`, which shells `wicked-vault cross-check`): the evidence is re-hashed and its verifier
re-run, never trusting a cached "done". wicked-loom (the gate engine) and wicked-vault (the evidence backend) are **required** peers (installed by `/wicked-garden-core setup`); if loom is unresolvable — or the vault behind it absent — the gate **fails closed** (`gate: "unavailable"`, `satisfied: false`) rather
than self-asserting a PASS. `--no-require` opts a throwaway/low-rigor run
back to the doctrine-light claim-only path.

## HITL

`discrete:review-gate` — review is the discrete gate. Approve happens
through PR review, council, or the `review` archetype if rigor warrants.

## Ground in the repo's method first

Before you plan, check for **wicked-understanding** repo playbooks (the opt-in
"how to work in THIS repo" layer). If its skills are present — `add-feature` /
`fix-bug` / `scaffold` / `write-tests`, or the routing block in
`AGENTS.md` / `CLAUDE.md` — **load the one matching this task and follow its
repo-specific method**: the file that owns this kind of change, the wiring step
("register it here or it won't boot"), the real test command, the gotcha. That
turns the plan phase from "discover how this repo works" into "follow the known
method." Absent? Discover it the usual way — and consider
`npx skills add mikeparcewski/wicked-understanding --all` so next time it's known.

## How to run

### plan

1. Initialise the evidence tracker for this archetype run:
   `scripts/qe/evidence_tracker.py init <project_dir> --archetype build`.
   Pre-populates `shipped-code` and `test-report` as pending.
   Then, if a vault is resolvable
   (`scripts/qe/vault_gate.py resolve` → `available: true`), declare the
   re-derivable contract for this phase so the review gate has a bar to
   check against:
   `wicked-vault init` (once per repo) then
   `wicked-vault declare-contract --scope <scope> --phase build --spec contract.json`
   — `required_evidence` should pin `tests-pass` to a deterministic
   verifier (e.g. `exit_code_eq:0`). Skip silently if no vault.
2. If picking up open conditions from a prior `review` archetype, read
   `scripts/qe/conditions_manifest.py status <project_dir>` and pin
   each one to a build task so they don't get lost.
3. Name the diff in 2–3 sentences. What changes? What stays the same?
   What's the smallest possible scope?
2. Pick the test rigor based on signals (factor scoring from the
   propose-process rubric is a fine input):

   | Signal pattern                                  | Test rigor             |
   |-------------------------------------------------|------------------------|
   | reversibility HIGH + blast_radius LOW + novelty LOW | one targeted test  |
   | medium on any of the above                      | unit tests + 1–2 integration |
   | high on any of the above                        | unit + integration + acceptance |
   | compliance scope OR auth changes                | full + security audit  |

3. If the diff is simple-edit-class (typo, comment, format), build
   shouldn't have been the archetype — drop back to `triage` and
   suppress.

### implement

1. Write the change. Stay tight to the plan.
2. Use `wicked-garden:engineering:apply` for patch-style edits when the
   change is well-scoped.
3. **Don't refactor adjacent code unless plan said so.** Drift is the
   #1 source of inflated build cycles.

### test

1. The rigor picked in plan governs which tests get written.
2. Use `wicked-testing:authoring` to generate tests when the rigor is
   medium or high.
3. **Tests must actually fail when the code is wrong.** The
   test-code-quality-auditor exists for a reason — assertion-free
   tests are worse than no tests.
4. Record the test run as re-derivable evidence (vault present):
   `wicked-vault record --scope <scope> --phase build --claim tests-pass
   --kind test-run --source "<the test command>" --criteria "<the bar>"
   --verifier exit_code_eq:0 --run`. The `--run` captures the command's
   real exit code now and the gate re-runs it later — a claim you can't
   re-derive is not evidence. No vault → fall back to
   `evidence_tracker.py claim`.

### review

1. Open the PR. Use the appropriate review skill:
   - Low rigor: `pr-review-toolkit:code-reviewer` only.
   - Medium: code-reviewer + relevant specialist (security / data /
     etc.).
   - High: full `review` archetype (this skill family).
2. Address findings. Keep the response narrow — review feedback is for
   THIS diff, not for opening adjacent issues.

## When to stop

Build is done when the produces-gate is satisfied AND the PR is merged.
Check the gate — don't self-assert it.

**Frictionless (recommended for a single decisive claim):** skip the
init/declare/record/gate ritual and re-derive in one call —
`scripts/qe/prove.py tests-pass --by "<your test command>" --scope <scope> --phase build`
(exit 0 = re-derived PASS; exit 1 = REJECT; exit 3 = backend down / fail-closed).
Run it before you tell anyone the build is done.

**Full contract (multi-claim):** declare a contract then
`scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase build`
(exit 0 = satisfied). Either way it is a re-derived PASS over the declared
contract. A REJECT means the recorded evidence does not clear its
contract — fix the work, not the claim. An `unavailable` verdict means
the required vault isn't installed — run `/wicked-garden-core setup`. If the
change is high-blast-radius, hand off to `ship`.

## Anti-patterns

- **Don't refactor in build.** A bug fix doesn't need surrounding
  cleanup. The CLAUDE.md "no premature abstraction" rule applies.
- **Don't write tests before the code compiles.** TDD is fine; testing
  uncompilable code is not.
- **Don't merge with red CI.** The "I'll fix it in a follow-up"
  mentality is how main goes red and stays red.
- **Don't test-stamp with rigor that doesn't match the change.**
  Adding 200 LOC of integration scaffolding for a typo fix is its own
  anti-pattern.
