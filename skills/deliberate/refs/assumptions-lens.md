# Assumptions Lens

Additional questions for the five lenses that surface hidden assumptions and
fragile dependencies. Maps what we're taking for granted and what breaks if we're wrong.

## Lens 1 Additions: Is This Real?

- What assumption makes us believe this is a problem? Is that assumption verified?
- Are we assuming user behavior that we haven't observed?
- Are we assuming a dependency will remain stable (API, library, service)?
- Are we assuming this environment/context will stay the same?

## Lens 2 Additions: What's Actually Going On?

- What are the implicit assumptions in the current design that led to this issue?
- Is the problem caused by an assumption that was once true but no longer is?
- Are we assuming cause and effect, or just correlation?
- What would we discover if we questioned the constraint we think is fixed?

## Lens 3 Additions: What Else Can We Fix?

- Are there other parts of the system built on the same fragile assumption?
- Can we make assumptions explicit — document them so they're auditable?
- Can we add assertions or contracts that fail loudly when assumptions break?
- Are there undocumented dependencies between components?

## Lens 4 Additions: Should We Rethink?

- Would designing for the assumption being WRONG be more resilient?
- Can we eliminate the assumption entirely instead of coding around it?
- Should we build an abstraction layer so changing this assumption later is cheap?
- Would a different architecture have fewer hidden assumptions?

## Lens 5 Additions: Better Way?

- Can we validate the key assumption before building? (prototype, data check, user test)
- Can we design for graceful degradation when assumptions fail?
- Can we add monitoring that alerts us when an assumption is violated?
- Can we make the dependency explicit and versioned instead of implicit?
