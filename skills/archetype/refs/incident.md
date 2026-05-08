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

### investigate

1. Look at dashboards FIRST — `wicked-garden:platform:health` /
   `:traces` / `:incident`. Hypothesize from data, not memory.
2. Run `wicked-garden:platform:incident` for triage workflows.
3. **Time-box investigation to 15 minutes during SEV-1.** If you don't
   have a mitigation hypothesis in 15 min, escalate; don't keep
   investigating.

### mitigate

1. Pick the cheapest reversible action that stops the impact:
   - Rollback to last-known-good (cheapest).
   - Feature flag off (cheap if instrumented).
   - Scale up (when capacity is the issue).
   - Circuit break a downstream (when a dependency is the issue).
2. **Confirm the bleeding stopped.** Watch the same dashboards that
   surfaced the incident. Don't declare mitigated based on logs alone.
3. Update the incident channel: "MITIGATED via {action} at {time}".

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

## When to stop

Incident is done when the followup list is owned and tracked. Hand off
to `build` (forward-fix work), `migrate` (when the fix is a shape
change), or `review` (when the followup includes auditing prevention).

## Anti-patterns

- **Don't investigate before you mitigate.** SEV-1 with users impacted
  is not the time for root-cause analysis.
- **Don't skip the RCA.** "We know what happened" is what every team
  says before the same incident recurs.
- **Don't blame.** Blameless postmortems aren't soft — they produce
  better followups.
