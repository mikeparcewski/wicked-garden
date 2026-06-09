# Mockup / Wireframe Rubric

Apply this inline. Produce wireframes, mockups, or component specs at the right
fidelity — quick ASCII for ideation, HTML/CSS for stakeholder review, annotated
spec for developer handoff. (Not production design — that's the figma plugin. For
imagery generation, see the `imagery` skill.)

## Fidelity selection

| Purpose | Fidelity | Format |
|---------|----------|--------|
| Quick ideation | Low | ASCII wireframe |
| Flow discussion | Low | ASCII + annotations |
| Stakeholder review | High | HTML/CSS preview |
| Developer handoff | Medium | Component spec (Markdown) |

Auto-select: `--fidelity low` / bare description -> ascii; `--fidelity high` /
stakeholder context -> html; file-path target -> spec (current + improvements).

## Process

1. Clarify scope (component or page? fidelity?).
2. Check existing — search for similar components to reuse/adapt; recall design tokens.
3. Draft ASCII first (validate layout).
4. Elevate to HTML/CSS or spec if the fidelity requires it.
5. Annotate all states + responsive + a11y.
6. Flag open questions.

## ASCII wireframe

```
┌─────────────────────────────────────────────┐
│ [Logo]              [Nav]  [Nav]  [CTA]      │
├─────────────────────────────────────────────┤
│   Hero Headline                              │
│   [Primary CTA]  [Secondary CTA]             │
├─────────────────────────────────────────────┤
│  ┌────────┐  ┌────────┐  ┌────────┐          │
│  │ Card 1 │  │ Card 2 │  │ Card 3 │          │
│  └────────┘  └────────┘  └────────┘          │
└─────────────────────────────────────────────┘
```

## HTML/CSS preview

Clean minimal HTML, embedded styles, design tokens in `:root` (`--color-primary`,
`--space-4`, `--radius`, `--text-base`), `box-sizing: border-box`, system-ui font.

## Component spec

```markdown
## Component: {Name}
### Anatomy — Container (surface bg, radius, padding), Heading, Body, Action
### States
| State | Change |
|-------|--------|
| Default | base | Hover | elevation/scale | Focus | 2px outline offset |
| Disabled | opacity 0.5, not-allowed | Error | error border + icon |
### Spacing — internal padding {token}, gap {token}
### Responsive — Mobile stack / Tablet 2-col / Desktop 3-col
### Accessibility — semantic element + aria-labelledby; keyboard nav; visible focus; alt text
```

## Output

```markdown
## Mockup: {component or page}
**Fidelity**: {Low|Medium|High}   **Format**: {ASCII|HTML|Spec}

### Wireframe / Preview
{ASCII, HTML block, or spec}

### Annotations — {state/behavior}, {responsive}, {a11y}
### Design Decisions — {decision + rationale}
### Open Questions — {for product/stakeholder}
### Next Steps — [ ] validate flow · [ ] visual-consistency review · [ ] a11y check
```
