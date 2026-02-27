---
description: UX and design quality review - flows, UI, accessibility, research
argument-hint: "<target> [--focus flows|ui|a11y|research|all] [--quick]"
---

# /wicked-garden:product:ux-review

Comprehensive UX and design quality review covering user flows, visual consistency, accessibility, and user research.

## Usage

```bash
# Auto-detect what to review
/wicked-garden:product:ux-review src/components/Dashboard

# Focus on specific area
/wicked-garden:product:ux-review src/components/Form --focus flows
/wicked-garden:product:ux-review src/components/Form --focus ui
/wicked-garden:product:ux-review src/components/Form --focus a11y
/wicked-garden:product:ux-review outcome.md --focus research

# Comprehensive review
/wicked-garden:product:ux-review src/app --focus all

# Quick triage (faster, less thorough)
/wicked-garden:product:ux-review src/components --quick
```

## Focus Areas

| Focus | Expert | What It Reviews |
|-------|--------|-----------------|
| `flows` | UX Designer | User journeys, interaction patterns, IA |
| `ui` | UI Reviewer | Visual consistency, design system, components |
| `a11y` | A11y Expert | WCAG compliance, keyboard, screen readers |
| `research` | User Researcher | Personas, needs, journey mapping |
| `all` | All experts | Comprehensive review |

## Instructions

### 1. Determine Focus

Parse the `--focus` flag. If not specified, auto-detect from target:
- `.tsx`, `.jsx`, `.vue` files → `flows` + `ui` + `a11y`
- `.css`, `.scss` files → `ui`
- `.md` with requirements → `research`
- Directory → `all`

### 2. Read Target Content

Read files or documents to review. For code, understand:
- Component structure
- User-facing elements
- Interaction handlers
- Accessibility attributes

### 3. Dispatch to Appropriate Expert(s)

Based on the focus area, dispatch to one or more experts in parallel. If `--focus all`, dispatch to all four experts.

**For flows focus**:
```
Task(
  subagent_type="wicked-garden:product/ux-designer",
  prompt="""Review user experience for the following code/document:

{code or document content}

## Evaluation Checklist

1. User flow clarity and logic
2. Error state handling
3. Edge cases (empty, loading, error)
4. Interaction patterns
5. Information architecture

## Return Format

Provide:
- Score (1-5)
- Strengths (what works well)
- Issues (with severity, file:line, impact, recommendation)
"""
)
```

**For ui focus**:
```
Task(
  subagent_type="wicked-garden:product/ui-reviewer",
  prompt="""Review visual design for the following code/document:

{code or document content}

## Evaluation Checklist

1. Design system adherence
2. Color/typography consistency
3. Spacing and layout
4. Component patterns
5. Responsive behavior
6. Visual states (hover, focus, active)

## Return Format

Provide:
- Score (1-5)
- Strengths (what works well)
- Issues (with severity, recommendation)
"""
)
```

**For a11y focus**:
```
Task(
  subagent_type="wicked-garden:product/a11y-expert",
  prompt="""Audit accessibility for the following code/document:

{code or document content}

## Evaluation Checklist

1. WCAG 2.1 Level AA compliance
2. Semantic HTML usage
3. ARIA patterns
4. Keyboard navigation
5. Screen reader support
6. Color contrast
7. Focus management

## Return Format

Provide:
- Score (1-5)
- WCAG Level achieved
- Compliance checklist (Perceivable, Operable, Understandable, Robust)
- Issues (with WCAG criterion, impact, fix recommendation)
"""
)
```

**For research focus**:
```
Task(
  subagent_type="wicked-garden:product/user-researcher",
  prompt="""Analyze user needs for the following requirements/design docs:

{requirements or design docs}

## Evaluation Checklist

1. User personas defined?
2. User needs validated?
3. Journey mapping complete?
4. Jobs to be done identified?
5. Problem-solution fit?

## Return Format

Provide:
- Score (1-5)
- Personas status (defined, missing, incomplete)
- Journeys status (mapped, partial, missing)
- Validation status (validated, assumed, unknown)
- Gaps (missing research elements)
"""
)
```

### 4. Present Review

```markdown
## UX Review: {target}

### Summary
**Focus**: {focus areas reviewed}
**Overall**: {Good|Needs Work|Critical Issues}

### Review by Area

#### User Flows {if reviewed}
**Score**: {1-5}

**Strengths**:
- {positive finding}

**Issues**:
- **{severity}**: {issue} in `{file}:{line}`
  - Impact: {user impact}
  - Recommendation: {fix}

#### Visual Design {if reviewed}
**Score**: {1-5}

**Strengths**:
- {positive finding}

**Issues**:
- **{severity}**: {issue}
  - Recommendation: {fix}

#### Accessibility {if reviewed}
**Score**: {1-5}
**WCAG Level**: {A|AA|AAA}

**Compliance**:
- [ ] Perceivable
- [ ] Operable
- [ ] Understandable
- [ ] Robust

**Issues**:
- **{WCAG criterion}**: {violation}
  - Impact: {who affected}
  - Fix: {recommendation}

#### User Research {if reviewed}
**Score**: {1-5}

**Personas**: {defined|missing|incomplete}
**Journeys**: {mapped|partial|missing}
**Validation**: {validated|assumed|unknown}

**Gaps**:
- {missing research element}

### Priority Actions

#### Critical
1. {must fix before release}

#### High
1. {should fix soon}

#### Medium
1. {improvement opportunity}

### Kanban Tasks Created
- {task ID}: {issue summary}
```

## Quick Mode

With `--quick` flag:
- Scan for obvious issues only
- Skip deep analysis
- Focus on critical/high severity
- Return in <30 seconds

```markdown
## Quick UX Scan: {target}

### Critical Issues
- {issue 1}
- {issue 2}

### Warnings
- {warning 1}

### Recommendation
Run full review with `/wicked-garden:product:ux-review {target} --focus all` for complete analysis.
```

## Integration

- **wicked-kanban**: Track issues as tasks
- **wicked-mem**: Recall design system patterns
- **wicked-crew**: Auto-suggest during build/review phases
- **wicked-engineering**: Coordinate with code review

## Example

```
User: /wicked-garden:product:ux-review src/components/LoginForm.tsx --focus a11y

Claude: I'll perform an accessibility audit of the LoginForm component.

[Reads LoginForm.tsx]
[Dispatches to a11y-expert agent]
[Agent audits against WCAG 2.1 AA]

## UX Review: LoginForm.tsx

### Summary
**Focus**: Accessibility (WCAG 2.1 Level AA)
**Overall**: Needs Work (3 issues found)

### Accessibility Review
**Score**: 3/5
**WCAG Level**: Partial AA

**Compliance**:
- [x] Perceivable
- [ ] Operable (2 issues)
- [x] Understandable
- [ ] Robust (1 issue)

### Issues

#### Critical
1. **WCAG 2.1.1 Keyboard**: Submit button not keyboard accessible
   - Impact: Keyboard users cannot submit form
   - Fix: Add `tabIndex={0}` and `onKeyDown` handler

#### High
2. **WCAG 1.4.3 Contrast**: Error message text fails contrast
   - Current: 3.2:1 (red on white)
   - Required: 4.5:1
   - Fix: Use `#c41e3a` instead of `#ff6666`

#### Medium
3. **WCAG 4.1.2 Name, Role, Value**: Password field missing label
   - Impact: Screen readers announce "edit text" only
   - Fix: Add `<label htmlFor="password">` or `aria-label`

### Priority Actions

#### Critical
1. Fix keyboard accessibility on submit button

#### High
1. Increase error message contrast ratio

### Kanban Tasks Created
- task-a11y-001: Fix LoginForm keyboard accessibility
- task-a11y-002: Fix LoginForm contrast issues
```

## Phase Integration

| Phase | Suggested Review | Auto-Trigger |
|-------|------------------|--------------|
| Clarify | `--focus research` | When requirements unclear |
| Design | `--focus flows` | When design docs ready |
| Build | `--focus a11y` + `--focus ui` | When components created |
| Review | `--focus all` | Before release |
