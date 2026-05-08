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
3. Deploy. Watch for at least 1 hour OR 1000 requests, whichever is
   longer.
4. Compare to baseline. If clean: pass to ramp. If degraded:
   **rollback immediately**. Don't tune in production.

### ramp

1. Step the ramp at 10% → 25% → 50%. Don't skip steps.
2. At each step, the SLO criteria from canary still apply. New metrics
   may surface as load scales (saturation, queue depth, lock contention).
3. Each step gets at least 30 minutes of soak before stepping up.
4. Use `wicked-garden:delivery:rollout` for the canonical playbook.

### full

1. Step from 50% → 100%. The same SLO criteria apply.
2. Tag the release. Publish a one-line "shipped X" note for visibility.

### soak

1. Watch for 24–72h depending on the change's criticality.
2. The long tail surfaces issues canary missed: data drift, slow leaks,
   off-hours load patterns, third-party rate limits.
3. Soak ends when there's no anomaly outside the baseline noise band.

## When to stop

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
