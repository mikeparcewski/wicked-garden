---
name: mockup
description: "Generate ASCII wireframes, HTML/CSS mockups, and component specs for UI layout exploration and developer handoff. Use when: sketching a layout, quick UI design, wireframing a page, prototyping a component, creating a mockup without Figma, or producing a developer handoff spec. Not for production design work — use Figma for that."
---

# Mockup Skill

Generate wireframes and mockups at multiple fidelity levels — from quick ASCII sketches to
HTML/CSS previews ready for developer handoff.

## Quick Start

```
# Quick ideation
"Sketch a login page layout in ASCII"

# Stakeholder review
"Create an HTML mockup of the dashboard with sidebar navigation"

# Dev handoff
"Write a component spec for the pricing card"
```

## Output Format Selection

| Format | Fidelity | Best For |
|--------|---------|----------|
| ASCII wireframe | Low | Quick ideation, flow discussion |
| Markdown spec | Medium | Annotated layouts, component inventory |
| HTML/CSS preview | High | Stakeholder review, dev handoff |
| Component spec | Medium-High | Design system documentation |

## ASCII Wireframes

Fast, text-based layout sketches for early ideation:

```
┌─────────────────────────────────────────┐
│  [Logo]          [Nav Item] [Nav Item]  │
│─────────────────────────────────────────│
│                                         │
│  ┌──────────────┐  ┌──────────────┐    │
│  │   [Image]    │  │   [Image]    │    │
│  │  Card Title  │  │  Card Title  │    │
│  │  [Button]    │  │  [Button]    │    │
│  └──────────────┘  └──────────────┘    │
│                                         │
│  ─────── Section Heading ───────────   │
│  ████████████████████ [CTA Button]     │
└─────────────────────────────────────────┘
```

Conventions: `[...]` = interactive element, `{...}` = input field, `████` = image placeholder.

## HTML/CSS Preview

For higher-fidelity mockups, generate minimal HTML with embedded CSS using design tokens:

```html
<style>
  :root {
    --color-primary: #3b82f6;
    --color-surface: #f9fafb;
    --space-4: 1rem;
    --radius: 0.5rem;
  }
</style>
```

Match the project's existing design tokens if available (check `styles/tokens.css` or equivalent).

## Wireframe from Description

When given a description, follow this sequence:

1. **Identify layout pattern** — single column, two-column, grid, sidebar+main
2. **List components** — header, nav, cards, forms, tables, modals
3. **Arrange hierarchy** — most important content first (F-pattern or Z-pattern)
4. **Add interactions** — buttons, links, inputs, toggles
5. **Annotate** — notes on behavior, states, responsive changes

## Output Checklist

Before delivering any mockup, verify:

- [ ] All states shown (default, hover, error, empty, loading)
- [ ] Mobile and desktop layouts included
- [ ] Spacing annotated with token names (not pixel values)
- [ ] Interactive elements clearly marked
- [ ] Accessibility notes included (roles, focus, labels)
- [ ] Open questions flagged for stakeholder input

## Reference

For detailed templates and handoff formats:
- [Component Specs](refs/component-specs.md) — full component spec template, state tables, responsive behavior
- [Handoff Notes](refs/handoff-notes.md) — developer handoff template, asset checklist, animation specs

## Integration

- **ux-review skill** — pair mockups with the UX flow they support
- **screenshot skill** — compare mockup against built implementation
- **visual-review skill** — mockups set the standard for visual review
- **engineering/frontend skill** — coordinate component implementation
