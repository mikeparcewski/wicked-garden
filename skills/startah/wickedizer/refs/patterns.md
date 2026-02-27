# Patterns: Reusable Writing Structures

Patterns are proven structures for common writing situations. Don't reinvent—adapt.

## Opening Patterns

### The Direct Lead

State your point in the first sentence.

```
[What this is] + [Why it matters]

// Example
JWT authentication replaces sessions across all APIs,
reducing latency by 40%.
```

**Use for:** Technical docs, work items, status updates—anything where readers want the point fast.

### The Context-Point Lead

Brief context, then the point.

```
[One sentence of context]. [Point].

// Example
After three months of evaluation, we recommend Postgres
over MongoDB for the new order service.
```

**Use for:** Decisions, recommendations, proposals where minimal context helps.

### The Problem Lead

Open with the pain, then the solution.

```
[Problem]. [Solution].

// Example
Deploy failures increased 40% last quarter. This RFC
proposes automated rollback triggers.
```

**Use for:** Proposals, RFCs, business cases—when you need buy-in.

---

## Argument Patterns

### What-So What-Now What

```
WHAT: [State the fact or situation]
SO WHAT: [Explain why it matters]
NOW WHAT: [State the action or decision]

// Example
WHAT: Customer churn increased from 5% to 8% this quarter.
SO WHAT: At this rate, we lose $2M ARR by year end.
NOW WHAT: Propose immediate investment in retention features.
```

### Problem-Cause-Solution

```
PROBLEM: [What's broken]
CAUSE: [Why it's broken]
SOLUTION: [How to fix it]

// Example
PROBLEM: API response times exceed SLA (>500ms).
CAUSE: N+1 queries in the order aggregation endpoint.
SOLUTION: Implement batch loading, projected 80% improvement.
```

### Option-Criteria-Recommendation

```
OPTIONS: [2-3 viable approaches]
CRITERIA: [How we evaluate]
RECOMMENDATION: [Which option and why]

// Example
OPTIONS:
- A: Build in-house (4 months, full control)
- B: Buy vendor X ($50k/yr, 2-week setup)
- C: Open source Y (free, 1 month integration)

CRITERIA: Time to market, long-term cost, flexibility

RECOMMENDATION: Option B. We ship in 2 weeks, cost is
acceptable, and we can migrate later if needed.
```

---

## Section Patterns

### The Setup-Payoff

Establish context, then deliver the insight.

```
SETUP: [Background the reader needs]
PAYOFF: [The insight or conclusion]

// Example
SETUP: The cache layer was designed for 1K rps.
We now serve 10K rps at peak.
PAYOFF: Cache misses cause 60% of our latency spikes.
```

### The Comparison

Side-by-side evaluation.

```
| Aspect | Option A | Option B |
|--------|----------|----------|
| Cost | $X | $Y |
| Time | X weeks | Y weeks |
| Risk | Low | Medium |

VERDICT: [Which wins and why]
```

### The Sequence

Ordered steps or timeline.

```
1. [First step] — [brief note if needed]
2. [Second step]
3. [Third step]
...

// Example
1. Merge feature branch — requires 2 approvals
2. Deploy to staging — automated
3. QA validation — 24 hour window
4. Production deploy — requires release train
```

---

## Whole-Document Patterns

### The One-Pager

For decisions that need quick alignment.

```
## [Decision Title]

**TL;DR:** [One sentence summary]

**Context:** [2-3 sentences of background]

**Proposal:** [What we should do]

**Alternatives Considered:**
- [Alt 1]: [Why not]
- [Alt 2]: [Why not]

**Risks:** [What could go wrong]

**Ask:** [What you need - approval/feedback/resources]
```

### The Technical RFC

For engineering decisions that need review.

```
## [RFC Title]

**Status:** Draft | Review | Approved | Superseded

**Author(s):** [Names]

**Reviewers:** [Names]

### Context
[Why are we here? What problem?]

### Decision
[What we're doing, unambiguously]

### Alternatives Considered
[2-3 options with tradeoffs]

### Consequences
[What changes as a result]

### Migration/Rollout
[How we get from here to there]
```

### The Incident Report

For post-mortems and incident documentation.

```
## [Incident Title] — [Date]

**Severity:** P1/P2/P3
**Duration:** [Start] to [End]
**Impact:** [What was affected, how many users]

### Timeline
- [HH:MM] [Event]
- [HH:MM] [Event]
...

### Root Cause
[What actually caused this]

### Resolution
[How we fixed it]

### Action Items
- [ ] [Action] — Owner: [Name] — Due: [Date]
...

### Lessons Learned
[What we'll do differently]
```

### The Work Item

For tickets in any tracking system.

```
## [Title: Action + Object]

[One sentence: what this accomplishes]

**Scope:**
- Include: [explicit]
- Exclude: [explicit]

**Acceptance Criteria:**
- [ ] [Testable criterion]
- [ ] [Testable criterion]

**Context/Links:**
- Related: [links]
- Blocked by: [ticket]
```

---

## Anti-Patterns

### The Throat-Clear

```
// BAD: Warm-up before content
Before we dive into the details, it's worth taking
a moment to establish some context about why this
matters and how we arrived at this point...

// GOOD: Just start
The auth system needs replacement by Q2.
```

### The False Balance

```
// BAD: Equal weight to unequal options
Option A has some advantages. However, Option B
also has some advantages. Both have tradeoffs.

// GOOD: Make a call
Option A wins on cost and time. Option B's flexibility
advantage doesn't justify the 3x cost.
```

### The Buried Lede

```
// BAD: Point at the end
We analyzed Q3 data, consulted stakeholders,
reviewed industry trends, and considered three
approaches. After careful deliberation, we
recommend migrating to the new platform.

// GOOD: Point at the start
We recommend migrating to the new platform.
Q3 data, stakeholder input, and industry trends
all support this decision.
```

### The Infinite Scroll

```
// BAD: Everything in one section
[Page after page with no structure]

// GOOD: Chunked with clear navigation
## Summary (read this first)
## Details (if you need them)
## Appendix (reference only)
```

---

## Pattern Selection Guide

| Situation | Pattern |
|-----------|---------|
| Quick decision needed | One-pager |
| Technical decision for review | RFC |
| Something broke | Incident report |
| Assigning work | Work item |
| Persuading stakeholders | Problem-Cause-Solution |
| Comparing options | Option-Criteria-Recommendation |
| Explaining a change | What-So What-Now What |
| Status update | Direct lead + bullets |
