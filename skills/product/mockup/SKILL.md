---
name: mockup
description: |
  Use when you need a quick ASCII wireframe or HTML mockup in-chat without Figma overhead.
  NOT for production design work — use the figma plugin for that.
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

For higher-fidelity mockups, generate minimal HTML with embedded CSS using design tokens. Match the project's existing tokens if available (check `styles/tokens.css` or equivalent).

Full template: `refs/templates.md` § HTML/CSS Preview.

## Component Specs (Markdown)

For developer handoff without visual preview, use the spec template. Sections: Anatomy, States table, Spacing tokens, Responsive Behavior, Accessibility Notes.

Full template: `refs/templates.md` § Component Spec (Markdown).

## Wireframe from Description

When given a description, generate a wireframe in this sequence:

1. **Identify layout pattern**: Single column, two-column, grid, sidebar+main
2. **List components**: Header, nav, cards, forms, tables, modals
3. **Arrange hierarchy**: Most important content first (F-pattern or Z-pattern)
4. **Add interactions**: Buttons, links, inputs, toggles
5. **Annotate**: Notes on behavior, states, responsive changes

## Integration with Frontend Design

When handing off to developers, attach handoff notes covering: design tokens to use, closest existing component, new patterns required, assets needed, animation specs.

Template: `refs/templates.md` § Handoff Notes.

## Output Checklist

Before delivering a mockup:

- [ ] All states shown (default, hover, error, empty, loading)
- [ ] Mobile and desktop layouts included
- [ ] Spacing annotated with token names (not pixel values)
- [ ] Interactive elements clearly marked
- [ ] Accessibility notes included
- [ ] Open questions flagged for stakeholder input

## Integration

- **ux-review skill**: Pair mockups with the UX flow they support
- **screenshot skill**: Compare mockup against built implementation
- **visual-review skill**: Mockups set the standard for visual review
- **engineering/frontend-design skill**: Coordinate component implementation
