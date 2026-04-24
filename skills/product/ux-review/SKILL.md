---
name: ux-review
description: |
  Use when evaluating UX quality — user flows, information architecture, user research synthesis,
  personas, and usability assessment. Also covers generative UX flow design from requirements.
  NOT for visual design consistency (use visual-review) or accessibility code audits (use product/accessibility).
---

# UX Review Skill

UX and design quality thinking embedded throughout delivery.

## Core Concept

Good UX is how we build trust. Don't wait for polish phase—design with users in mind from the start.

## Four Focus Areas

| Area | Expert | Focus |
|------|--------|-------|
| **User Flows** | UX Designer | Experience design, interactions, IA |
| **Visual Design** | UI Reviewer | Consistency, components, design system |
| **Accessibility** | A11y Expert | WCAG, keyboard, screen readers |
| **User Research** | User Researcher | Needs, personas, journeys |

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:product:ux-review` | Run UX review (auto-detect focus) |
| `/wicked-garden:product:ux-review --focus flows` | User flow analysis |
| `/wicked-garden:product:ux-review --focus ui` | Visual design review |
| `/wicked-garden:product:ux-review --focus a11y` | Accessibility audit |
| `/wicked-garden:product:ux-review --focus research` | User research |
| `/wicked-garden:product:ux-review --focus all` | Comprehensive review |

## Usage

```bash
# Auto-detect what to review
/wicked-garden:product:ux-review src/components/Dashboard

# Focus on accessibility
/wicked-garden:product:ux-review src/components/Form --focus a11y

# User research on requirements
/wicked-garden:product:ux-review outcome.md --focus research

# Comprehensive review
/wicked-garden:product:ux-review src/app --focus all

# Quick triage
/wicked-garden:product:ux-review src/components --quick
```

## Output

Review produces:
- **Issues**: Critical / Major / Minor findings
- **Recommendations**: Specific, actionable improvements
- **Evidence**: Screenshots, code snippets, WCAG citations
- **Tasks**: Issues tracked via native TaskCreate for follow-up

## Review Types

### User Flow Review
- Happy path clarity
- Error handling
- User mental models
- Interaction patterns
- Information architecture

### Visual Design Review
- Color consistency
- Typography scale
- Spacing system
- Component patterns
- Responsive design
- Visual polish

### Accessibility Audit
- WCAG 2.1 Level AA compliance
- Keyboard navigation
- Screen reader support
- Semantic HTML
- ARIA patterns
- Color contrast

### User Research
- User needs discovery
- Persona creation
- Journey mapping
- Problem validation
- Jobs to Be Done

## Integration

Works with:
- **wicked-crew**: Auto-suggested after phases
- **Read tool**: Analyze screenshots directly; capture via browser automation if available
- **Native tasks**: Issue tracking via TaskCreate with `metadata.event_type="task"`
- **wicked-garden:mem**: Design system memory
- **wicked-garden:search**: Pattern discovery

## Phase Integration

| Phase | Suggested Review | Expert |
|-------|------------------|--------|
| Clarify | User research | User Researcher |
| Design | User flows + IA | UX Designer |
| Build | A11y + UI consistency | A11y Expert + UI Reviewer |
| Review | Comprehensive review | All experts |

## Quick Checks

For fast feedback:

```bash
# Quick a11y scan
/wicked-garden:product:ux-review {file} --focus a11y --quick

# Quick UI consistency
/wicked-garden:product:ux-review {file} --focus ui --quick

# Quick flow check
/wicked-garden:product:ux-review {file} --focus flows --quick
```

## Common Findings

**UX**: Unclear flows, missing error states, confusing navigation
**UI**: Color/typography/spacing inconsistencies, missing states
**A11y**: Missing alt text, poor contrast, no keyboard access
**Research**: Assumed needs, missing personas, unmapped journeys

## Output Artifacts

- `ux-review.md` - Findings and recommendations
- `personas/`, `journeys/` - Research artifacts
- `a11y-report.md` - Accessibility results
- Native tasks for tracking (TaskCreate with `metadata.event_type="task"`)

## Best Practices

1. Review early - catch issues in design phase
2. Focus on users - always ask "how does this help?"
3. Be specific - give actionable recommendations
4. Cite standards - reference WCAG, design system
5. Track issues - use native TaskCreate for follow-through

## Getting Started

```bash
# Comprehensive quick review
/wicked-garden:product:ux-review src/ --focus all --quick

# Accessibility deep dive
/wicked-garden:product:ux-review src/components --focus a11y

# User research
/wicked-garden:product:ux-review outcome.md --focus research
```
