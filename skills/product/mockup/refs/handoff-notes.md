# Developer Handoff Notes

Use this template when handing off mockups to developers for implementation.

## Handoff Template

```markdown
## Handoff Notes for {component}

**Design tokens to use**: See `styles/tokens.css`
**Closest existing component**: {component name in codebase}
**New patterns required**: {list any novel patterns}
**Assets needed**: {icons, images, fonts}
**Animation**: {transition type, duration}
```

## Full HTML/CSS Preview Template

When generating high-fidelity mockups, use this structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mockup: {component name}</title>
<style>
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
  body { font-family: system-ui, sans-serif; margin: 0; padding: var(--space-6); }
  .card {
    background: var(--color-surface);
    border-radius: var(--radius);
    padding: var(--space-6);
  }
</style>
</head>
<body>
  <!-- mockup content here -->
</body>
</html>
```

## ASCII Symbol Reference

| Symbol | Meaning |
|--------|---------|
| `┌─┬─┐ │ └─┴─┘` | Box borders and dividers |
| `[...]` | Button or interactive element |
| `{...}` | Input field |
| `████` | Image placeholder |
| `~~~~` | Text content placeholder |
| `────` | Horizontal rule / divider |
