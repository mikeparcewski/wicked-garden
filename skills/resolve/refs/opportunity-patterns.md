# Opportunity Patterns

Common patterns where a single issue reveals broader improvement opportunities.
These are domain-agnostic — they apply to code, content, design, and systems alike.

## Pattern: Shotgun Surgery

**Signal**: A single change requires edits in many places.
**Opportunity**: Extract the scattered concern into a shared abstraction.
**Examples**:
- Code: Date formatting fix needed in 12 controllers → extract DateFormatter
- Content: Brand voice update required across 30 pages → extract style tokens
- Design: Color change needed in 15 components → extract design tokens

## Pattern: Silent Failure

**Signal**: Problem caused by something failing silently — no error, no log, no feedback.
**Opportunity**: Audit the area for other silent failures. Add observability.
**Examples**:
- Code: Exception swallowed, returns None → add structured error types
- Content: Broken link returns 200 with wrong page → add link validation
- Design: Form submits but nothing happens → add feedback states

## Pattern: Duplication

**Signal**: Fix needs to be applied in multiple places with similar logic.
**Opportunity**: Consolidate into a single source of truth.
**Examples**:
- Code: Validation logic copy-pasted across endpoints → extract Validator
- Content: Same instructions written differently in 3 guides → single source
- Design: Same component built differently in 4 views → shared component

## Pattern: Missing Abstraction

**Signal**: Multiple consumers implement the same multi-step process inline.
**Opportunity**: Name the process and give it a proper interface.
**Examples**:
- Code: Three services each query→transform→save → extract Pipeline
- Content: Writers each invent their own tutorial structure → extract template
- Design: Each page builds its own nav → extract navigation pattern

## Pattern: Leaky Boundary

**Signal**: Consumers need internal knowledge to use something correctly.
**Opportunity**: Redesign the interface to hide the complexity.
**Examples**:
- Code: Must call init() before use() → use context manager
- Content: Reader must know jargon to understand docs → add glossary/simplify
- Design: User must know hidden gesture to access feature → improve discoverability

## Pattern: Config Drift

**Signal**: Problem from inconsistent settings across environments or components.
**Opportunity**: Centralize with validation and parity checks.
**Examples**:
- Code: Two services define timeouts independently → shared config
- Content: Style guide says one thing, templates do another → sync
- Design: Mobile and desktop use different spacing scales → unify

## Pattern: Temporal Coupling

**Signal**: Problem caused by doing things in the wrong order.
**Opportunity**: Make invalid sequences impossible.
**Examples**:
- Code: Must call connect() before query() → auto-connect on first query
- Content: Must read Part 1 before Part 2 but nothing says so → add prereqs
- Design: Must complete Step A before Step B but UI allows skipping → enforce flow

## Pattern: Primitive Obsession

**Signal**: Problem from using generic types where domain types would prevent errors.
**Opportunity**: Introduce named types that carry meaning.
**Examples**:
- Code: User ID and session ID both strings, swapped in call → typed IDs
- Content: All metadata stored as free text → structured fields
- Design: All buttons look the same regardless of action → semantic variants

## Pattern: Feature Envy

**Signal**: Something reaches deep into another area's internals to get what it needs.
**Opportunity**: Move the logic to where the data lives, expose a proper interface.
**Examples**:
- Code: Report reads 5 private fields → add summary method on the owner
- Content: FAQ duplicates info from other pages → link instead of copy
- Design: Dashboard rebuilds data viz from raw data → expose chart-ready API

## Evaluation

When reviewing an issue, check which patterns apply:

| Pattern | Present? | Severity (0-3) | Fix Effort | Payoff |
|---------|----------|-----------------|------------|--------|
| Shotgun surgery | | | | |
| Silent failure | | | | |
| Duplication | | | | |
| Missing abstraction | | | | |
| Leaky boundary | | | | |
| Config drift | | | | |
| Temporal coupling | | | | |
| Primitive obsession | | | | |
| Feature envy | | | | |

**Priority**: High severity + low effort + high payoff = do it now alongside the fix.
