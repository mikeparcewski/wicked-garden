# Frontend Review Checklists

## Component Quality Checklist
- [ ] Single responsibility
- [ ] Clear prop interface
- [ ] Proper TypeScript/PropTypes
- [ ] Reusable and composable
- [ ] Handles edge cases

## React Best Practices Checklist
- [ ] Hook dependencies correct
- [ ] Effects have cleanup
- [ ] No unnecessary re-renders
- [ ] Keys used correctly in lists
- [ ] No mutating state directly

## Styling Checklist
- [ ] Responsive design
- [ ] Accessibility (contrast, sizing)
- [ ] Consistent with design system
- [ ] Performant animations

## Accessibility Checklist
- [ ] Semantic HTML
- [ ] Keyboard navigation
- [ ] Screen reader friendly
- [ ] ARIA where needed
- [ ] Focus indicators visible

## Common Anti-Patterns

### React Anti-Patterns
- Missing hook dependencies (stale closures)
- Using index as key in dynamic lists
- Not cleaning up effects (memory leaks)
- Inline function creation in render
- Direct state mutation

### CSS Anti-Patterns
- Fixed pixel widths for layouts
- Excessive !important
- Non-semantic class names
- Animations not GPU-accelerated

### Accessibility Anti-Patterns
- Using div instead of button
- Missing alt text on images
- Poor color contrast
- No keyboard navigation
- Missing focus indicators

### Performance Anti-Patterns
- Large bundles without code splitting
- Not using lazy loading
- Unnecessary re-renders
- Unoptimized images
- No debouncing on input handlers

## Output Template

```markdown
## Frontend Review: {Component/Feature}

### Component Design
{Assessment of structure and patterns}

### React Implementation
{Hook usage, state management, performance}

### Styling
{CSS quality, responsiveness}

### Accessibility
{A11y compliance and recommendations}

### Issues
| Severity | Issue | Location | Fix |
|----------|-------|----------|-----|
| {Level} | {Problem} | {File:line} | {Solution} |

### Recommendations
1. {Priority item}
2. {Secondary item}
```

## Tools

- React DevTools for profiling
- Browser DevTools for CSS/performance
- Lighthouse for a11y and performance
- React Testing Library for testing
- axe DevTools for accessibility
