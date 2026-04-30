# Mockup Templates

Copy-paste templates for the three mockup output formats. The SKILL.md selection table tells you when to use each.

## HTML/CSS Preview

Minimal HTML with embedded CSS using design tokens. Match the project's existing tokens if available (check `styles/tokens.css` or equivalent).

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

## Component Spec (Markdown)

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

## Handoff Notes

When handing off a mockup to developers:

```markdown
## Handoff Notes for {component}

**Design tokens to use**: See `styles/tokens.css`
**Closest existing component**: {component name in codebase}
**New patterns required**: {list any novel patterns}
**Assets needed**: {icons, images, fonts}
**Animation**: {transition type, duration}
```
