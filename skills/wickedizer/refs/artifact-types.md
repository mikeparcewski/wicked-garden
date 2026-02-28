# Artifact Types: Mode-Specific Guidance

Different document types have different constraints. This reference provides specific guidance for each artifact type wickedizer handles.

## Artifact Classification

Before rewriting, classify the artifact. This determines structure, tone, and what counts as "good."

| Type | Primary Goal | Length Constraint |
|------|--------------|-------------------|
| exec-summary | Decision support | 5-12 lines |
| technical-doc | Enable correct implementation | As needed, well-structured |
| prd-requirements | Specify what to build | Clear scope, explicit criteria |
| work-item | Enable task execution | Scannable, all context present |
| slide-bullets | Support verbal presentation | 6x6 optional, clarity mandatory |
| code-comments | Explain non-obvious decisions | Terse, meaningful |
| email-comms | Drive action or share info | Reader's time is precious |

---

## exec-summary

### Purpose
Help executives make decisions quickly. They're reading 20 of these today.

### Structure
```
[One stance sentence - what this is and why it matters]

- What's happening
- Why now / why this matters
- Key risks or tradeoffs
- What we need (decision/approval/resources/timeline)
```

### Rules
- 5-12 lines maximum unless specifically asked for more
- No background section - integrate context into bullets
- Decision or ask must be explicit
- Numbers beat narratives

### Example

**Before (typical AI output):**
> The engineering team has been conducting a comprehensive evaluation of our current authentication infrastructure. After extensive analysis, we've identified several opportunities for improvement that could significantly enhance our security posture while also improving the user experience...

**After:**
> **Auth system migration** needs approval by Friday to hit Q2 security audit.
>
> - Current: session tokens, 3 known vulnerabilities, audit finding
> - Proposed: JWT with refresh rotation, fixes all 3 CVEs
> - Risk: 2-week migration, some legacy clients need updates
> - Ask: Budget approval for $40k contractor support

---

## technical-doc (ADR/RFC/Design Doc)

### Purpose
Enable correct implementation and future understanding. These docs outlive their authors.

### Required Sections
1. **Context** - Why are we here? What problem?
2. **Decision** - What we're doing (clear, unambiguous)
3. **Options Considered** - 2-3 alternatives with brief tradeoffs
4. **Tradeoffs** - What we're giving up, what we're gaining
5. **Rollout / Risks** - How we ship, what could go wrong

### Rules
- Preserve rigor - don't simplify technical content
- "Comprehensive" claims need coverage proof
- Diagrams referenced should exist or be noted as needed
- Future reader is the audience, not current team

### Anti-patterns
- Decisions buried in prose
- Options considered that are obviously bad (straw men)
- Missing rollback plan
- "We decided X" without the why

---

## prd-requirements

### Purpose
Specify what to build so engineering can estimate and execute.

### Key Elements
- Problem statement (what pain, for whom)
- Success criteria (measurable)
- Scope (what's in, what's explicitly out)
- Acceptance criteria per feature
- Dependencies and constraints

### Language Precision
| Keyword | Meaning |
|---------|---------|
| MUST | Non-negotiable requirement |
| MUST NOT | Prohibited |
| SHOULD | Expected unless justified exception |
| MAY | Optional, nice to have |

### Rules
- Avoid marketing tone - this is a spec, not a pitch
- Acceptance criteria must be testable
- "User can..." not "Users will be empowered to..."
- Scope boundaries explicit

---

## work-item (Epic/Story/Task/Bug)

Applies to: Jira, Linear, GitHub Issues, Azure DevOps, Shortcut, Asana, or any work tracking system.

### Purpose
Enable someone to pick this up and execute without asking questions.

### Structure
```
[One sentence: what this accomplishes]

**Scope:**
- Include: [explicit list]
- Exclude: [explicit list]

**Acceptance Criteria:**
- [ ] Criterion 1 (testable)
- [ ] Criterion 2 (testable)

**Dependencies:**
- Blocked by: [item] - [brief reason]
- Blocks: [item]
```

### Rules
- Scannable in 10 seconds
- All context in the item (don't rely on memory or tribal knowledge)
- Acceptance criteria are checkboxes, not prose
- Link dependencies, don't just name them

### Anti-patterns
- "As a user, I want..." when it doesn't help
- AC that require interpretation
- Missing scope boundaries
- Dependencies named but not linked

---

## slide-bullets

### Purpose
Support a presenter. Slides are not documents.

### Rules
- One idea per bullet
- 6x6 is guideline, not law
- Sentence fragments preferred over full sentences
- No sub-sub-bullets

### Structure
- Lead with the point
- Evidence or example
- Implication if not obvious

### Anti-patterns
- Bullets that are paragraphs
- Reading the slide verbatim
- Decorative bullets (just filling space)
- Nested lists 3 levels deep

---

## code-comments

### Purpose
Explain what isn't obvious from reading the code.

### What to Comment
- **Why** decisions were made
- Non-obvious constraints or tradeoffs
- Workarounds with context (link to issue if applicable)
- Performance implications that aren't visible
- Security considerations

### What NOT to Comment
- What the code does (code should be readable)
- Restating the function name
- Changelog in comments (use git)
- Commented-out code (delete it)

### Examples

**Bad:**
```typescript
// Increment counter
counter++;
```

**Good:**
```typescript
// Retry limit set to 3 based on p99 latency analysis - higher causes timeout cascade
const MAX_RETRIES = 3;
```

---

## email-comms

### Purpose
Get a response, share information, or document a decision.

### Structure
- **Subject line:** Action + Topic + Deadline (if applicable)
- **First line:** Why you're writing
- **Body:** What they need to know
- **Close:** What you need from them (explicit ask)

### Rules
- Respect inbox triage - get to point fast
- Bold or bullet the ask
- One email = one topic (usually)
- Reply threads: quote only relevant context

### Anti-patterns
- Burying the ask in paragraph 4
- "I hope this email finds you well"
- "Please advise" (advise on what?)
- CC everyone, ask no one

---

## Mixed Artifacts

When a document spans types (e.g., PRD with exec summary), apply each section's rules to the relevant parts. The exec summary follows exec-summary rules even when embedded in a larger doc.
