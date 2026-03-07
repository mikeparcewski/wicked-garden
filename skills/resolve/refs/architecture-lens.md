# Architecture Lens

Additional questions for the five lenses when the work involves system architecture.

## Lens 1 Additions: Is This Real?

- Is this a scalability problem now, or a theoretical future concern?
- Is this an architecture issue, or an implementation issue within a sound architecture?
- Are we solving for the current scale or a projected scale we may never reach?

## Lens 2 Additions: What's Actually Going On?

- Is the service boundary in the wrong place?
- Is the coupling between components the root cause?
- Is this a data model issue masquerading as an application issue?

## Lens 3 Additions: What Else Can We Fix?

- Are other service boundaries suffering from the same poor decomposition?
- Can we introduce a shared contract that prevents integration drift?
- Are there undocumented architectural decisions (ADRs) that should be captured?

## Lens 4 Additions: Should We Rethink?

- Would merging two services be simpler than fixing their interaction?
- Would an event-driven approach replace fragile synchronous coupling?
- Would a different data ownership model eliminate the coordination problem?

## Lens 5 Additions: Better Way?

- Can we solve this with a configuration change instead of code?
- Can we solve this with a proxy/gateway instead of modifying services?
- Can we defer the architectural change with a well-placed facade?
