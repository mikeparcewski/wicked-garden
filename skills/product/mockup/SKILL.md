---
name: mockup
description: |
  Digital mockup and wireframe generation. Outputs ASCII wireframes for quick
  ideation, HTML/CSS previews for interactive review, or component specs for
  developer handoff.

  Use when: "mockup", "wireframe", "prototype", "lo-fi design", "component spec",
  "design sketch", "UI layout", "layout draft", "design handoff"
portability: portable
---

# Mockup Skill

Generate wireframes and mockup designs in multiple fidelity levels — from quick
ASCII sketches to HTML/CSS previews ready for developer handoff.

## Output Format Selection

| Format | Fidelity | Best For |
|--------|---------|----------|
| ASCII wireframe | Low | Quick ideation, flow discussion |
| Markdown spec | Medium | Annotated layouts, component inventory |
| HTML/CSS preview | High | Stakeholder review, dev handoff |
| Component spec | Medium-High | Design system documentation |

## ASCII Wireframes

Fast, text-based layout sketches. Use for early ideation and flow discussion.

```
┌─────────────────────────────────────────┐
│  [Logo]          [Nav Item] [Nav Item]  │
│─────────────────────────────────────────│
│                                         │
│  ┌──────────────┐  ┌──────────────┐    │
│  │              │  │              │    │
│  │   [Image]    │  │   [Image]    │    │
│  │              │  │              │    │
│  │  Card Title  │  │  Card Title  │    │
│  │  Description │  │  Description │    │
│  │  [Button]    │  │  [Button]    │    │
│  └──────────────┘  └──────────────┘    │
│                                         │
│  ─────── Section Heading ───────────   │
│                                         │
│  ████████████████████ [CTA Button]     │
└─────────────────────────────────────────┘
```

### ASCII Symbol Guide

```
┌─┬─┐  Box borders
│ │ │  Vertical dividers
└─┴─┘  Box bottoms
[...]   Button or interactive element
{...}   Input field
████   Image placeholder
~~~~   Text content placeholder
────   Horizontal rule / divider
```

## HTML/CSS Preview

For higher-fidelity mockups, generate minimal HTML with inline or embedded CSS:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mockup: {component name}</title>
<style>
  /* Design tokens */
  :root {
    --color-primary: #3b82f6;
    --color-surface: #f9fafb;
    --space-4: 1rem;
    --space-6: 1.5rem;
    --text-sm: 0.875rem;
    --text-base: 1rem;
    --text-lg: 1.125rem;
    --radius: 0.5rem;
  }
  /* Component styles */
  .card {
    background: var(--color-surface);
    border-radius: var(--radius);
    padding: var(--space-6);
  }
</style>
</head>
<body>
  <!-- mockup content -->
</body>
</html>
```

## Component Specs (Markdown)

For developer handoff without visual preview:

```markdown
## Component: {Name}

### Anatomy
- **Container**: {background, border, border-radius, padding}
- **Header**: {font-size, font-weight, color}
- **Body**: {font-size, line-height, color}
- **Action**: {button variant, size}

### States
| State | Visual Change |
|-------|--------------|
| Default | {description} |
| Hover | {description} |
| Active | {description} |
| Disabled | {opacity: 0.5, cursor: not-allowed} |

### Spacing
- Internal padding: {token}
- Gap between elements: {token}
- External margin: {token or "handled by parent"}

### Responsive Behavior
- Mobile (<768px): {layout change}
- Tablet (768–1024px): {layout change}
- Desktop (>1024px): {base layout}

### Accessibility Notes
- Role: {semantic element or ARIA role}
- Focus: {keyboard interaction}
- Labels: {aria-label or visible label}
```

## Wireframe from Description

When given a description, generate a wireframe in this sequence:

1. **Identify layout pattern**: Single column, two-column, grid, sidebar+main
2. **List components**: Header, nav, cards, forms, tables, modals
3. **Arrange hierarchy**: Most important content first (F-pattern or Z-pattern)
4. **Add interactions**: Buttons, links, inputs, toggles
5. **Annotate**: Notes on behavior, states, responsive changes

## Integration with Frontend Design

When handing off to developers:

```markdown
## Handoff Notes for {component}

**Design tokens to use**: See `styles/tokens.css`
**Closest existing component**: {component name in codebase}
**New patterns required**: {list any novel patterns}
**Assets needed**: {icons, images, fonts}
**Animation**: {transition type, duration}
```

## Output Checklist

Before delivering a mockup:

- [ ] All states shown (default, hover, error, empty, loading)
- [ ] Mobile and desktop layouts included
- [ ] Spacing annotated with token names (not pixel values)
- [ ] Interactive elements clearly marked
- [ ] Accessibility notes included
- [ ] Open questions flagged for stakeholder input

## Integration

- **ux-flow skill**: Pair mockups with the flow they support
- **screenshot skill**: Compare mockup against built implementation
- **visual-review skill**: Mockups set the standard for visual review
- **engineering/frontend-design skill**: Coordinate component implementation
