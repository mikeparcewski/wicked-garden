# Complexity: Keep It Simple

Writing complexity is cognitive load on the reader. Every unnecessary word, section, or concept is debt they pay to understand you.

## Two Types of Complexity

### Essential Complexity

Complexity that exists in the subject matter itself. Can't be removed without losing meaning.

- Technical concepts that require precision
- Nuanced decisions with real tradeoffs
- Regulatory or legal requirements
- Domain-specific terminology

**Don't fight essential complexity.** Explain it clearly, but don't pretend it's simple.

### Accidental Complexity

Complexity introduced by the writer, not required by the subject.

- Jargon when plain language works
- Hedging when you're actually certain
- Sections that repeat other sections
- Structure that doesn't match content

**Accidental complexity is your target.** Remove it ruthlessly.

---

## KISS: Keep It Stupidly Simple

The simplest explanation that's still accurate is usually best.

### Detection Questions

- Could a smart person outside your team understand this?
- Are you explaining the concept or showing off knowledge?
- Would removing this sentence change the meaning?

### Application

```
// BAD: Unnecessarily complex
The implementation leverages a distributed event-driven
architecture paradigm to facilitate loosely-coupled
inter-service communication patterns.

// GOOD: Same meaning, less load
Services communicate through events, so they don't
depend on each other directly.
```

```
// BAD: Over-explained
It's important to note that users will need to
authenticate before accessing the dashboard. This
authentication step ensures that only authorized
users can view sensitive data. Without authentication,
unauthorized access could occur.

// GOOD: Trust the reader
Users must authenticate before accessing the dashboard.
```

---

## YAGNI: You Aren't Gonna Need It

Don't write content for hypothetical readers or future scenarios.

### Symptoms of YAGNI Violations

- "For completeness, we should mention..."
- "Some readers might want to know..."
- "In case anyone asks about..."
- Appendices no one requested

### Application

```
// BAD: Anticipating questions no one asked
## Authentication Methods
We use JWT tokens. For historical context, we
previously used session cookies from 2018-2022,
which had several limitations including...

[3 paragraphs of history]

## Migration Path from Sessions
If any services still use sessions...

[Section for a situation that doesn't exist]

// GOOD: What's needed now
## Authentication
We use JWT tokens. See [auth docs] for implementation.
```

**Rule:** Write for the actual audience with actual questions. Add content when someone asks, not before.

---

## DRY: Don't Repeat Yourself

Say it once, say it well, reference it thereafter.

### The Rule of Three

Don't extract or consolidate until you've seen the same content three times. Premature consolidation creates worse problems than repetition.

```
// Repetition 1: Leave it
// Repetition 2: Note it, leave it
// Repetition 3: Now consolidate
```

### Good Repetition vs. Bad Repetition

**Good (structural repetition):**
- Consistent headings across similar docs
- Same format for all work items
- Repeated structure readers expect

**Bad (content duplication):**
- Same paragraph in multiple places
- Restating what a linked doc already says
- "As mentioned above" (just don't mention it twice)

### Consolidation Patterns

```
// BAD: Duplicate content
## Overview
The system handles 10k requests per second...

## Performance
The system handles 10k requests per second...

// GOOD: Single source
## Overview
The system handles 10k requests per second.
See Performance for details.

// ALSO GOOD: Just don't repeat
## Performance
The system handles 10k requests per second...

[Remove from Overview entirely]
```

---

## Separation of Concerns

Different purposes should be different sections or documents.

### Single Responsibility for Sections

Each section should have one job:
- Explain a concept, OR
- Provide instructions, OR
- Present evidence, OR
- Document a decision

```
// BAD: Mixed concerns
## API Authentication
Authentication uses JWT tokens (Bearer scheme).
To authenticate, include the header "Authorization:
Bearer <token>". We chose JWT over sessions because
of scalability requirements documented in ADR-042.
Tokens expire after 1 hour. To refresh, call POST
/auth/refresh. The security team reviewed this in Q2.

// GOOD: Separated concerns
## API Authentication
Authenticate using JWT Bearer tokens in the
Authorization header. Tokens expire after 1 hour.

See:
- [How to authenticate](/docs/auth-howto) - step by step
- [ADR-042](/decisions/adr-042) - why we chose JWT
```

---

## Cognitive Load Management

### Limit Concepts per Section

**7±2 Rule:** Readers hold about 5-9 items in working memory.

- Max 7 bullets in a list
- Max 5-7 concepts before a break
- Max 3 levels of nesting

### Front-Load Familiar Concepts

Start with what readers know, bridge to what's new.

```
// BAD: New concept without anchor
The flurble processor handles all greebling operations
using a distributed mesh topology.

// GOOD: Anchor to known concept
Like a load balancer distributes traffic, the flurble
processor distributes greebling operations across nodes.
```

### Use Progressive Disclosure

Don't explain everything upfront. Provide depth when readers need it.

```
Layer 1: What it does (everyone reads)
Layer 2: How to use it (most readers)
Layer 3: How it works (some readers)
Layer 4: Implementation details (few readers)
```

---

## Simplification Techniques

### Remove Weasel Words

| Weasel | Problem | Fix |
|--------|---------|-----|
| "Basically" | Implies complexity you're hiding | Just explain simply |
| "Simply" | Often precedes something not simple | Remove and check |
| "Obviously" | If obvious, why say it? | Remove |
| "Clearly" | Same | Remove |
| "In order to" | Wordy | "To" |
| "Utilize" | Fancy "use" | "Use" |

### Remove Meta-Commentary

```
// BAD: Talking about what you're about to say
In this section, we will discuss the authentication
approach. First, we'll cover the basics, then we'll
dive into implementation details.

// GOOD: Just say it
Authentication uses JWT tokens...
```

### Remove Obvious Transitions

```
// BAD: Over-connected
First, we need to authenticate. Next, we fetch the
data. Then, we process it. Finally, we return results.

// GOOD: Let structure carry order
1. Authenticate
2. Fetch data
3. Process
4. Return results
```

---

## Quick Reference

| Principle | Question to Ask |
|-----------|-----------------|
| KISS | Can I say this simpler without losing meaning? |
| YAGNI | Does anyone actually need this? |
| DRY | Have I said this elsewhere? |
| Separation | Is this section doing one job? |
| Cognitive load | How many new concepts at once? |
