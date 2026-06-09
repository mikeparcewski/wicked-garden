# ship — progressive rollout with widening blast radius

For changes that are already built and tested but need controlled exposure
to production. Each phase widens blast radius; gates are explicit ramps.

## Phase shape

| Phase  | Goal                                                       |
|--------|------------------------------------------------------------|
| canary | Expose to a small slice (1–5% traffic, internal only, single region). |
| ramp   | Widen progressively (10% → 25% → 50%) with monitoring at each step. |
| full   | 100% exposure. Production traffic on the new path.         |
| soak   | Keep the new path running unchanged for 24–72h. Watch the long tail. |

## Produces

- **Rollout verdict**: APPROVE / ROLLBACK / HOLD at each gate.
- **SLO snapshot**: error rate, latency, saturation at each phase
  boundary, compared to the pre-rollout baseline.

The ramp gate **re-derives** these via `wicked-loom` (`scripts/qe/vault_gate.py` shells `wicked-loom gate`, which shells `wicked-vault cross-check`): the SLO snapshot's verifier is re-run and
the rollout-verdict command's exit code re-checked, never trusting a
cached "looked clean". Because live observation verifiers
(`http_status_eq`, `pr_check_status`) aren't implemented yet, **capture
the SLO metrics to a snapshot file** and verify with `jq_pred` over that
captured JSON — deterministic and re-derivable, not a one-shot live
probe. wicked-loom (the gate engine) and wicked-vault (the evidence backend) are **required** peers (installed by `/wicked-garden:setup`); if loom is unresolvable — or the vault behind it absent — the gate **fails closed** (`gate: "unavailable"`, `satisfied: false`) rather than
self-asserting an APPROVE. `--no-require` opts a throwaway/low-rigor
rollout back to the doctrine-light claim-only path.

## HITL

`discrete:ramp-gates` — each phase boundary is a discrete gate. Auto-pass
is allowed when SLO criteria are clean and prior phases passed; auto-fail
(rollback) is allowed when SLO criteria breach. **Manual override is
always available.** Don't bypass the gate; widen the criteria.

## How to run

### canary

1. Define the slice: which traffic, what %, what region.
2. Define the SLO criteria: error rate threshold, latency p95/p99
   threshold, saturation threshold. Pull baseline from the last 7d.
3. If a vault is resolvable
   (`scripts/qe/vault_gate.py resolve` → `available: true`), declare the
   re-derivable contract for this rollout so every ramp gate has a bar to
   check against: `wicked-vault init` (once per repo) then
   `wicked-vault declare-contract --scope <scope> --phase ship --spec
   contract.json`. `required_evidence` pins `slo-snapshot` (kind
   `metrics-snapshot`) to a `jq_pred` verifier over a captured metrics
   JSON file (e.g. `.error_rate <= 0.01 and .p95_ms < 250`) and
   `rollout-verdict` to `exit_code_eq:0` on the canary/ramp check command.
   Skip silently if no vault.
4. Deploy. Watch for at least 1 hour OR 1000 requests, whichever is
   longer.
5. Compare to baseline. If clean: pass to ramp. If degraded:
   **rollback immediately**. Don't tune in production.

### ramp

1. Step the ramp at 10% → 25% → 50%. Don't skip steps.
2. At each step, the SLO criteria from canary still apply. New metrics
   may surface as load scales (saturation, queue depth, lock contention).
3. Each step gets at least 30 minutes of soak before stepping up.
4. At each step, **capture fresh SLO metrics to a snapshot file** (don't
   probe live), then record both produces as re-derivable evidence
   (vault present):
   `wicked-vault record --scope <scope> --phase ship --claim slo-snapshot
   --kind metrics-snapshot --artifact <metrics.json> --criteria "<the
   SLO bar>" --verifier 'jq_pred:.error_rate <= 0.01 and .p95_ms < 250'`
   and `wicked-vault record --scope <scope> --phase ship --claim
   rollout-verdict --kind check --source "<the canary/ramp check
   command>" --criteria "verdict is APPROVE" --verifier exit_code_eq:0
   --run`. The `jq_pred` re-runs against the captured snapshot and
   `--run` re-checks the verdict command's real exit code — a claim you
   can't re-derive is not evidence. Each ramp step supersedes the prior
   snapshot, so the cross-check runs against fresh captured evidence at
   every step. No vault → fall back to `evidence_tracker.py claim`.
5. The `ship` archetype owns the canonical rollout playbook.

### full

1. Step from 50% → 100%. The same SLO criteria apply.
2. Tag the release. Publish a one-line "shipped X" note for visibility.

### soak

1. Watch for 24–72h depending on the change's criticality.
2. The long tail surfaces issues canary missed: data drift, slow leaks,
   off-hours load patterns, third-party rate limits.
3. Soak ends when there's no anomaly outside the baseline noise band.

## When to stop

Each ramp step advances only when the produces-gate is satisfied — check
it, don't self-assert it:
`scripts/qe/prove.py <claim> --by "<command>" --scope <scope> --phase ship` (frictionless, single claim — re-derive, don't assert) — or the full multi-claim contract via `scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase ship`
(exit 0 = satisfied). This is a re-derived APPROVE over the declared
contract, re-run at **every** ramp step against the fresh captured
snapshot. A REJECT means the recorded SLO snapshot doesn't clear its
budget — **rollback**, don't widen. An `unavailable` verdict means the
required vault isn't installed — run `/wicked-garden:setup`.

Ship is done when soak is clean. Hand off to `review` for a post-rollout
audit when the change was high-blast-radius, or close out otherwise.

## Anti-patterns

- **Don't skip ramp.** 0% → 100% is not a rollout; it's a deploy.
- **Don't auto-pass under degraded SLOs.** "It's only slightly worse"
  has rolled out exactly the kind of regression rollouts are meant to
  catch.
- **Don't ship and walk.** Soak is part of ship. A rollout that ends at
  full is incomplete.
- **Don't treat ramp as a build phase.** No code changes during ramp.
  Tuning happens in a follow-up build → ship cycle.
