# Ops Lens

Additional questions for the five lenses when the work involves infrastructure,
deployments, incidents, reliability, or operational concerns.

## Lens 1 Additions: Is This Real?

- Is this an actual outage/degradation, or a monitoring false positive?
- Is this a one-time event or a recurring pattern?
- Is the alert threshold wrong rather than the system behavior?
- Is this impacting users, or just triggering internal noise?

## Lens 2 Additions: What's Actually Going On?

- Is this a capacity issue, a config issue, or a code issue?
- Is the root cause in our system or in a dependency?
- Is the failure domain isolated, or can it cascade?
- Did a recent deployment, config change, or scaling event trigger this?

## Lens 3 Additions: What Else Can We Fix?

- Are other services vulnerable to the same failure mode?
- Is there missing observability that made diagnosis slow?
- Are runbooks stale or missing for this scenario?
- Can we add circuit breakers, retries, or fallbacks for similar failures?

## Lens 4 Additions: Should We Rethink?

- Should this be a managed service instead of self-hosted?
- Would a different deployment strategy (canary, blue-green) prevent blast radius?
- Should we rearchitect for graceful degradation instead of hard failure?
- Would chaos engineering have caught this before production?

## Lens 5 Additions: Better Way?

- Can we auto-remediate instead of alerting a human?
- Can we solve this with resource limits/quotas instead of code?
- Can we add a health check that catches this before users do?
- Can we shift this left — catch it in CI instead of production?
