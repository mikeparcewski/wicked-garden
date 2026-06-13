# incident — live-fire response to production failure

Mitigate first, RCA second, follow-up third. The cost band is variable —
a quick rollback may take 5 minutes; a complex multi-service incident
may consume a day. The phase order is **non-negotiable**: do not
investigate before mitigating unless investigation IS the mitigation.

## Phase shape

| Phase        | Goal                                                |
|--------------|-----------------------------------------------------|
| triage       | Classify severity + scope. Page who needs paging.   |
| investigate  | Find proximate cause. Just enough to mitigate.      |
| mitigate     | Stop the bleeding. Rollback / feature flag / scaling / circuit break. |
| resolve      | Permanent fix. May be the same as mitigate, may not. |
| followup     | RCA writeup, action items, tests/alerting that would have caught this. |

## Produces

- **Mitigation**: the action that stopped the impact (rollback hash,
  feature flag toggle, scaling change, etc.).
- **RCA**: root cause analysis writeup at `docs/postmortems/INC-{N}.md`.
- **Followup list**: action items with owners. Each gets a github issue
  or tracked task.

The mitigate gate **re-derives** these via `wicked-loom` (`scripts/qe/vault_gate.py` shells `wicked-loom gate`, which shells `wicked-vault cross-check`): the evidence is re-hashed and its verifier
re-run, never trusting a cached "mitigated". The honesty move here is the
mitigation pin — a claimed mitigation that doesn't actually make the
symptom check pass must REJECT. wicked-loom (the gate engine) and wicked-vault (the evidence backend) are **required** peers (installed by `/wicked-garden:setup`); if loom is unresolvable — or the vault behind it absent — the gate **fails closed** (`gate: "unavailable"`, `satisfied: false`) rather than
self-asserting a PASS. `--no-require` opts a throwaway/low-rigor run back
to the doctrine-light claim-only path.

## HITL

`hard:mitigate` — mitigate is a hard gate. Don't move past it without
confirming the bleeding stopped. Don't skip to followup before resolve.

## How to run

### triage

1. Classify severity: SEV-1 (revenue/data impact), SEV-2 (degraded
   primary path), SEV-3 (degraded secondary path).
2. Page the right people. SEV-1 is a phone call, not a slack message.
3. Open an incident channel + tracking ticket. The ticket is the
   single source of truth for the timeline.
4. If a vault is resolvable
   (`scripts/qe/vault_gate.py resolve` → `available: true`), declare the
   re-derivable contract so the mitigate gate has a bar to check against:
   `wicked-vault init` (once per repo) then
   `wicked-vault declare-contract --scope <scope> --phase incident --spec contract.json`.
   `required_evidence` pins `mitigation` to a deterministic re-run of the
   symptom check (`exit_code_eq:0`), and `rca` / `followup-list` to
   presence/structure `regex_match` (required RCA sections present;
   followup list non-empty). Skip silently if no vault.

### investigate

1. Look at dashboards FIRST — `wicked-garden:platform:health` /
   `:traces` / `:incident`. Hypothesize from data, not memory.
2. Run `wicked-garden:platform:incident` for triage workflows.
3. **Time-box investigation to 15 minutes during SEV-1.** If you don't
   have a mitigation hypothesis in 15 min, escalate; don't keep
   investigating.
4. Capture the **symptom check** — the command that reproduces the break
   (it fails now). This becomes the deterministic verifier the mitigate
   gate re-runs: a real mitigation makes this same command pass.

### mitigate

1. Pick the cheapest reversible action that stops the impact:
   - Rollback to last-known-good (cheapest).
   - Feature flag off (cheap if instrumented).
   - Scale up (when capacity is the issue).
   - Circuit break a downstream (when a dependency is the issue).
2. **Confirm the bleeding stopped.** Watch the same dashboards that
   surfaced the incident. Don't declare mitigated based on logs alone.
3. Record the mitigation as re-derivable evidence (vault present;
   **wicked-vault ≥ 0.4.0**):
   `wicked-vault record --scope <scope> --phase incident --claim mitigation
   --kind mitigation-check --source "<the symptom-check command>"
   --criteria "symptom check passes post-mitigation"
   --verifier exit_code_eq:0 --actor "${WICKED_VAULT_ACTOR:-garden-prove}"
   --run`. The **`--actor`** is mandatory because `mitigate` is a hard
   gate: vault ≥ 0.4.0 refuses an `attest` over evidence recorded under a
   weak/ambient identity, so without an explicit actor the independent
   attestation fails closed and the gate can never PASS. The `--run`
   captures the symptom check's real exit code now and the gate re-runs it
   later — a mitigation you can't re-derive is not evidence. No vault →
   fall back to `evidence_tracker.py claim`.
4. Update the incident channel: "MITIGATED via {action} at {time}".

### resolve

1. The permanent fix may be the same as the mitigation (rollback that
   stays rolled back) or different (rollback unblocks impact, then
   forward-fix the bug).
2. Test the fix in staging when possible. Cowboying a fix into prod
   during an incident is how you get a second incident.
3. Land the fix; close the incident channel.

### followup

1. Write the RCA within 48h. Use the standard postmortem template.
2. Use `wicked-garden:incident-to-scenario-synthesizer` to convert the
   incident into a regression scenario that would catch the same break.
3. Track action items in github. Don't bury them in a Slack thread.
4. Record the docs evidence (vault present; **wicked-vault ≥ 0.4.0**):
   `wicked-vault record --scope <scope> --phase incident --claim rca
   --kind doc --artifact docs/postmortems/INC-{N}.md
   --criteria "required RCA sections present"
   --verifier "regex_match:## Root Cause"
   --actor "${WICKED_VAULT_ACTOR:-garden-prove}"` and
   `wicked-vault record --scope <scope> --phase incident
   --claim followup-list --kind doc --artifact <followup-list>
   --criteria "followup list non-empty"
   --verifier "regex_match:- \[" --actor "${WICKED_VAULT_ACTOR:-garden-prove}"`.
   The **`--actor`** keeps this incident's evidence attestable by an
   independent reviewer under vault ≥ 0.4.0. No vault →
   `evidence_tracker.py claim`.

## When to stop

`mitigate` is a **hard gate** — confirm the bleeding stopped before
moving past it, and don't self-grade the mitigation. Check the gate WITH
judgment:
`scripts/qe/prove.py <claim> --by "<command>" --scope <scope> --phase incident --with-attestations` (frictionless, single claim — re-derive, don't assert) — or the full multi-claim contract via `scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase incident --with-attestations` **`--with-attestations`** keeps this gate `UNATTESTED`/`REJECT` until an INDEPENDENT evaluator (not the doer) runs `wicked-vault attest <artifact-id> --opinion pass` — find it via `wicked-vault list --scope <scope> --phase incident`. The doer's own evidence cannot satisfy a hard gate.
(exit 0 = satisfied). This re-runs the symptom check (the mitigation pin)
and requires an **independent attestation** — an evaluator who is *not*
the responder confirms the mitigation holds and the RCA is adequate,
recorded via `wicked-vault:analyze-evidence`. It fails closed on a
self-grade. A REJECT means the symptom check still fails or the
attestation is missing/negative — fix the work, not the claim. An
`unavailable` verdict means the required vault isn't installed — run
`/wicked-garden:setup`.

Incident is done when the gate is satisfied and the followup list is
owned and tracked. Hand off to `build` (forward-fix work), `migrate`
(when the fix is a shape change), or `review` (when the followup includes
auditing prevention).

## Anti-patterns

- **Don't investigate before you mitigate.** SEV-1 with users impacted
  is not the time for root-cause analysis.
- **Don't skip the RCA.** "We know what happened" is what every team
  says before the same incident recurs.
- **Don't blame.** Blameless postmortems aren't soft — they produce
  better followups.
