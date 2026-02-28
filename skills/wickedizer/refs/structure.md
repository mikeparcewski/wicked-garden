# Structure: Document Architecture

How you organize content determines whether readers find what they need. Structure is invisible when done well—readers just "get it."

## The Dependency Rule for Writing

**Information flows from general to specific, from decision to detail.**

```
// BAD: Bottom-up (reader must hold context)
We analyzed 47 metrics across 3 quarters.
The data showed a 23% decline in engagement.
User surveys confirmed the trend.
Therefore, we recommend redesigning the onboarding flow.

// GOOD: Top-down (reader gets point first)
We recommend redesigning the onboarding flow.
Engagement dropped 23% over 3 quarters.
User surveys confirm new users abandon at step 3.
```

**Rule:** If the reader can't state your point after the first paragraph, restructure.

---

## Vertical Organization

### Inverted Pyramid (News Style)

Most important information first, details descend in importance.

```
[Lead: What happened, why it matters]
[Key details: Who, when, how]
[Background: Context, history]
[Additional: Nice-to-know]
```

**Use for:** Exec summaries, announcements, status updates, any doc readers might not finish.

### Problem-Solution-Benefit

```
[Problem: What's broken, what pain exists]
[Solution: What we're doing about it]
[Benefit: What improves, for whom]
```

**Use for:** Proposals, PRDs, business cases, change requests.

### Situation-Complication-Resolution (SCR)

```
[Situation: Current state, shared context]
[Complication: What changed, what's the tension]
[Resolution: What to do about it]
```

**Use for:** Strategy docs, recommendation memos, persuasive writing.

### Chronological

```
[First: What happened first]
[Then: What happened next]
[Now: Current state]
[Next: What happens next]
```

**Use for:** Incident reports, project updates, historical documentation.

---

## Horizontal Layering

### The Three Layers of a Document

```
Layer 1: NAVIGATION (scannable in 10 seconds)
├── Title tells you what this is
├── Headings show structure
├── Bold text marks key points
└── Bullets list scannable items

Layer 2: SUMMARY (readable in 2 minutes)
├── Opening paragraph states the point
├── Section leads summarize each part
└── Conclusion restates decision/action

Layer 3: DETAIL (full read when needed)
├── Supporting evidence
├── Technical specifics
└── Background context
```

**Rule:** A reader at Layer 1 should know if they need Layer 2. A reader at Layer 2 should know if they need Layer 3.

---

## Heading Architecture

### Headings Should Work as an Outline

```
// BAD: Headings that don't standalone
1. Background
2. Analysis
3. Discussion
4. Conclusion

// GOOD: Headings that tell the story
1. Auth system needs replacement by Q2
2. JWT outperforms sessions on all metrics
3. Migration requires 2 sprints + testing
4. Approve budget for contractor support
```

### Heading Levels

| Level | Purpose | Example |
|-------|---------|---------|
| H1 | Document title | One per document |
| H2 | Major sections | 3-7 per document |
| H3 | Subsections | 2-5 per H2 |
| H4+ | Avoid if possible | Indicates need to split |

**Rule:** If you need H4, consider whether that section should be its own document.

---

## Section Boundaries

### When to Create a New Section

- Topic changes completely
- Audience might skip to this part
- Content could be read independently
- Length exceeds comfortable scroll

### When NOT to Create a New Section

- You have only one paragraph to put in it
- The heading restates what the content says
- You're creating symmetry for aesthetics

```
// BAD: Section for one sentence
## Timeline
The project will complete in Q2.

## Budget
The budget is $50,000.

// GOOD: Combined when brief
## Timeline and Budget
The project completes in Q2 with a $50,000 budget.
```

---

## Lists vs. Prose

### Use Lists When

- Items are parallel (same type of thing)
- Order matters (steps, priority)
- Reader needs to scan quickly
- Items will be referenced later ("see item 3")

### Use Prose When

- Ideas need connection and flow
- Nuance matters more than speed
- Narrative builds an argument
- List would have only 2 items

```
// BAD: Prose that should be a list
The system supports three authentication methods.
First, users can log in with email and password.
Second, they can use SSO through Okta.
Third, they can authenticate via API key.

// GOOD: List for parallel items
The system supports three auth methods:
- Email/password
- SSO (Okta)
- API key

// BAD: List that should be prose
- The feature was requested by customers
- It aligns with our Q2 goals
- Engineering confirmed feasibility

// GOOD: Prose for connected argument
Customers requested this feature, it aligns with Q2 goals,
and engineering confirmed it's feasible within the sprint.
```

---

## Document Length

### Right-Sizing by Type

| Type | Target Length | Max Before Split |
|------|---------------|------------------|
| Exec summary | 5-12 lines | 1 page |
| Email | 3-5 paragraphs | 1 scroll |
| PRD | 2-5 pages | 10 pages |
| Technical doc | As needed | When sections exceed 3 pages |
| Work item | Fits in view | When scrolling required |

### Signals You Need to Split

- Table of contents would help
- Readers need different sections for different purposes
- Sections could have different owners
- Updates to one part don't affect others

### Signals to Keep Together

- Context from early sections needed throughout
- Reader must understand A before B makes sense
- Splitting creates duplication

---

## Structural Anti-Patterns

### The Intro-Body-Conclusion Trap

```
// BAD: School essay structure
Introduction: This document will discuss...
Body: [content]
Conclusion: In conclusion, this document discussed...

// GOOD: Get to it
[Point]
[Support]
[Action/Decision]
```

### The Symmetric Sections Trap

Don't force sections to match length or structure. If one section needs 5 paragraphs and another needs 2 sentences, that's fine.

### The Nested List Trap

```
// BAD: Over-nested
- Category A
  - Subcategory A1
    - Item A1a
    - Item A1b
  - Subcategory A2
    - Item A2a

// GOOD: Flatten or use headings
## Category A

**Subcategory A1:** Item A1a, Item A1b

**Subcategory A2:** Item A2a
```

---

## Quick Reference

| Principle | Application |
|-----------|-------------|
| Point first | Lead with the conclusion |
| Scannable layers | Title → Headings → Bold → Body |
| Headings as outline | Should tell story without body |
| Right-size sections | Split when purpose diverges |
| Lists for parallel | Prose for connected |
