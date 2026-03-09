---
name: deliberate
description: |
  Critical thinking framework applied before doing work. Challenges assumptions,
  reframes problems, identifies hidden opportunities, and validates whether the stated
  ask is the right ask. A way of approaching work, not a specialist discipline.

  Use when: "rethink this approach", "is this the right problem", "challenge assumptions",
  "reframe the problem", "before implementation", "issue triage", "deliberate on this",
  "should we even do this", "root cause analysis", "5 whys"
---

# Deliberate

A structured way of thinking about work **before doing it**. Applied to any request —
bugs, features, enhancements, content, design, infrastructure — to ensure we're solving
the right problem the right way.

## When to Use

- Before accepting any work request at face value
- During crew **clarify** and **design** phases (auto-integrated)
- When triaging issues, tickets, or ad-hoc asks
- Any time the gut response is "just do it" — pause and deliberate first

## The Five Lenses

### 1. Is This Real?

Challenge the premise before solving it.

- Is the reported problem actually a problem, or is it working as intended?
- Is this a symptom or the root cause? Would fixing it just move the pain?
- What's the evidence? Observed behavior, user feedback, or speculation?
- What's the cost of doing nothing? Sometimes inaction is the right action.

### 2. What's Actually Going On?

If the problem is real, dig to the root.

- Trace the issue to its origin — don't stop at the first explanation
- Is this a design flaw wearing a different mask?
- Map the blast radius: what else shares the same root cause?
- Is the framing itself wrong? (e.g., "the button is broken" vs "the flow is confusing")

### 3. What Else Can We Fix While We're Here?

Every change is a window into the surrounding code/content/system.

- Are there adjacent areas suffering from the same weakness?
- Can we generalize instead of point-fixing?
- Is there duplication that should be consolidated?
- Would a structural change prevent entire categories of similar asks?

See [refs/opportunity-patterns.md](refs/opportunity-patterns.md) for common patterns.

### 4. Should We Rethink the Design?

Step back further. Is the current approach the right one?

- Would a different structure make this problem disappear entirely?
- Are we patching around a leaky abstraction or flawed model?
- Is the boundary in the wrong place?
- What would we build if starting fresh with today's knowledge?

See [refs/rethink-framework.md](refs/rethink-framework.md) for evaluation.

### 5. Is There a Better Way?

Before committing to the obvious solution, explore alternatives.

- Can we solve this by **removing** instead of adding?
- Can we solve this with configuration instead of code?
- Is there a simpler approach that covers 90% of cases?
- What are we trading off with each option?

## Output: Deliberation Brief

```markdown
## Deliberation Brief: {title}

### Assessment
**Validity**: Real problem / Symptom / Not a problem / Wrong framing
**Root cause**: {actual cause, not what was reported}
**Blast radius**: {what else is affected by the same root cause}

### Opportunities
**Cleanup**: {what can be improved alongside}
**Generalization**: {can we abstract or consolidate?}
**Rethink**: {should we redesign the approach?}

### Recommendation
**Strategy**: Fix / Redesign / Generalize / Defer / Close
**Rationale**: {why this approach over alternatives}
**Scope**: Expand / Contract / Same — {what changed from original ask}

### Guidance
{specific direction for whoever does the work}
```

## Domain-Specific Depth

The five lenses are universal. The refs provide depth for specific contexts:

- [refs/opportunity-patterns.md](refs/opportunity-patterns.md) — Structural patterns that signal cleanup opportunities
- [refs/rethink-framework.md](refs/rethink-framework.md) — When and how to propose a redesign
- [refs/code-lens.md](refs/code-lens.md) — Code-specific patterns (error handling, abstractions, tech debt)
- [refs/content-lens.md](refs/content-lens.md) — Content/docs patterns (messaging, structure, audience)
- [refs/design-lens.md](refs/design-lens.md) — Design patterns (UX flows, information architecture)
- [refs/architecture-lens.md](refs/architecture-lens.md) — System patterns (boundaries, dependencies, scaling)
- [refs/data-lens.md](refs/data-lens.md) — Data patterns (pipelines, schemas, quality, contracts)
- [refs/ops-lens.md](refs/ops-lens.md) — Ops patterns (incidents, reliability, deployment, observability)
- [refs/security-lens.md](refs/security-lens.md) — Security patterns (auth, vulnerabilities, threat models, compliance)
- [refs/product-lens.md](refs/product-lens.md) — Product patterns (user needs, prioritization, value, strategy)
- [refs/testing-lens.md](refs/testing-lens.md) — Testing patterns (test strategy, flakiness, coverage, test design)
- [refs/timing-lens.md](refs/timing-lens.md) — Timing patterns (urgency, sequencing, premature optimization)
- [refs/assumptions-lens.md](refs/assumptions-lens.md) — Assumption patterns (hidden dependencies, fragile premises)

## Integration

- **Crew workflow**: Auto-invoked during clarify and design phases
- **Standalone**: `/wicked-garden:deliberate {description or GH#}`
- **Batch**: Process multiple issues together to find shared root causes
