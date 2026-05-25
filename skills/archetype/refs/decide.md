# decide — pick between options with an ADR

When 2+ paths are viable AND the choice is load-bearing (changing it later
is expensive). Produces an ADR-shaped artifact that records the chosen
path and the reasons.

## Phase shape

| Phase   | Goal                                                       |
|---------|------------------------------------------------------------|
| brief   | One-paragraph framing: the problem, the stakes, the constraints. |
| options | 2–4 named alternatives, each with a one-paragraph description. |
| score   | Qualitative scoring on the dimensions that matter for this decision. |
| record  | Write the ADR. Pick a path. Note the trade-offs you accepted. |

## Produces

- An **ADR** (Architecture Decision Record) at `docs/decisions/{N}-{slug}.md`
  or `docs/adr/{N}-{slug}.md`, following whatever ADR convention the repo
  uses. New repos: use the standard ADR template.
- A **decision artifact**: which option was picked, and the explicit
  trade-offs accepted by picking it.

The select gate **re-derives** these via `wicked-vault`
(`scripts/qe/vault_gate.py`): the ADR's bytes are re-hashed and its
structure verifier re-run, never trusting a cached "ADR written". The
check is **deterministic document-structure** — it proves the ADR
contains the required sections, not that the call was wise. wicked-vault
is a **required** peer (installed by `/wicked-garden:setup`); if it is
genuinely absent the gate **fails closed** (`gate: "unavailable"`,
`satisfied: false`) rather than self-asserting a PASS. `--no-require`
opts a throwaway/low-rigor decision back to the doctrine-light
claim-only path. (A judgment tier — `wicked-vault analyze-evidence` —
exists for "was this the right call" sign-off; it's optional here and
not part of this discrete gate.)

## HITL

`discrete:select-gate` — the user (or a council) picks. Don't auto-select.

## How to run

### brief

1. Restate the problem in one paragraph. What changes if we pick wrong?
2. Name the constraints: budget, time, team capability, blast radius,
   reversibility.
3. If reversibility is HIGH and blast radius is LOW, **stop and ask**
   whether this even needs an ADR. Cheap-to-reverse decisions don't
   benefit from this archetype's overhead.
4. If a vault is resolvable
   (`scripts/qe/vault_gate.py resolve` → `available: true`), declare the
   re-derivable contract so the select gate has a bar to check against:
   `wicked-vault init` (once per repo) then
   `wicked-vault declare-contract --scope <scope> --phase decide --spec contract.json`.
   `required_evidence` pins `adr` (kind `adr-doc`) to a `regex_match`
   verifier proving the ADR carries every required section — Status,
   Context, Decision, Consequences — and pins `decision-artifact` to a
   presence/structure check (`regex_match`, or `commit_exists` once the
   ADR is committed). Skip silently if no vault.

### options

1. Generate 2–4 distinct options. Don't pad — false alternatives weaken
   the decision.
2. For each option:
   - One-paragraph description.
   - Cost: time + complexity + ongoing maintenance.
   - Reversibility: how hard is undoing this in 6 months?
   - Failure mode: what's the worst plausible outcome?

### score

1. Pick 3–5 dimensions that actually matter for this decision (not a
   generic checklist). Examples: latency, operational complexity,
   contract stability, team familiarity, vendor lock-in.
2. Score each option qualitatively (LOW/MEDIUM/HIGH) on each dimension.
3. The score is a *thinking aid*, not a winner-picker. The user picks.

### record

1. Use `wicked-garden:jam:council` for a multi-model second opinion when
   the stakes warrant it.
2. Write the ADR. Sections: context, options considered, decision,
   consequences, trade-offs accepted.
3. Commit the ADR with the implementing change, not separately. The ADR
   is the explanation for the diff.
4. Record the ADR as re-derivable evidence (vault present):
   `wicked-vault record --scope <scope> --phase decide --claim adr
   --kind adr-doc --source "<path to the ADR>"
   --criteria "ADR has Status / Context / Decision / Consequences"
   --verifier 'regex_match:(?ims)^#+\s*(status|context|decision|consequences)\b'
   --run`, then record `decision-artifact` against the committed ADR
   (`--verifier commit_exists:<sha>` once committed, else a `regex_match`
   on the decision line). The `--run` hashes the file's bytes now and the
   gate re-derives the structure later — a claim you can't re-derive is
   not evidence. No vault → fall back to `evidence_tracker.py claim`.

## When to stop

Decide is done when the produces-gate is satisfied AND the chosen option
is named. Check the gate — don't self-assert it:
`scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase decide`
(exit 0 = satisfied). This is a re-derived PASS over the declared
contract — the ADR was re-hashed and its structure verifier re-run. A
REJECT means the recorded ADR doesn't clear its contract (a missing
section, an uncommitted artifact) — fix the document, not the claim. An
`unavailable` verdict means the required vault isn't installed — run
`/wicked-garden:setup`. Then hand off to `build` (implement the chosen
path), `migrate` (when the choice is a shape change), or `ship` (when the
choice is a rollout strategy).

## Anti-patterns

- **Don't run decide for cheap-reversible choices.** A feature flag that
  defaults to off does not need an ADR. The overhead exceeds the benefit.
- **Don't pad to 4 options.** Three honest options beats four with one
  filler.
- **Don't quantify when you don't have data.** Qualitative scoring is
  fine; spurious numbers are worse than honest LOW/MEDIUM/HIGH.
