# Component Spec Template

Use this template when producing developer handoff documentation for individual components.

## Template

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

## Example: Pricing Card

```markdown
## Component: PricingCard

### Anatomy
- **Container**: bg-surface, border-1 border-gray-200, rounded-lg, p-6
- **Header**: text-lg font-semibold text-gray-900
- **Price**: text-3xl font-bold text-primary
- **Features**: text-sm text-gray-600, list-disc
- **Action**: Button variant=primary size=lg full-width

### States
| State | Visual Change |
|-------|--------------|
| Default | Border gray-200, shadow-sm |
| Hover | Shadow-md, border-primary/30 |
| Featured | Border-primary, shadow-lg, "Popular" badge |
| Disabled | opacity-50, button disabled |

### Spacing
- Internal padding: space-6
- Gap between sections: space-4
- External margin: handled by grid parent

### Responsive Behavior
- Mobile (<768px): full width, stacked vertically
- Tablet (768–1024px): 2-column grid
- Desktop (>1024px): 3-column grid, featured card slightly larger

### Accessibility Notes
- Role: article with aria-label="{plan name} pricing plan"
- Focus: Tab to CTA button, Enter to select
- Labels: Price announced as "{amount} per {period}"
```
