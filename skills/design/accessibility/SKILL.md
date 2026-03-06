---
name: accessibility
description: |
  Accessibility-focused design review and audit. WCAG compliance checking,
  keyboard navigation, screen reader compatibility, color contrast, semantic structure.

  Use when: "accessibility", "a11y", "WCAG", "screen reader", "keyboard navigation",
  "color contrast", "aria", "semantic HTML", "accessible design"
---

# Accessibility Skill

Systematic accessibility review covering WCAG 2.1 Level AA compliance, keyboard
navigation, screen reader support, and inclusive design patterns.

## WCAG 2.1 Principles (POUR)

| Principle | Core Requirement |
|-----------|-----------------|
| **Perceivable** | Content available to all senses — not just visual |
| **Operable** | All functions available via keyboard; no traps |
| **Understandable** | Content and UI are clear and predictable |
| **Robust** | Works with current and future assistive tech |

## Audit Checklist

### Perceivable

- [ ] Images have descriptive `alt` text (decorative: `alt=""`)
- [ ] Videos have captions; audio has transcripts
- [ ] Color is not the only way to convey information
- [ ] Text contrast ratio ≥ 4.5:1 (normal), ≥ 3:1 (large text 18pt+)
- [ ] UI component contrast ≥ 3:1 against adjacent colors
- [ ] Text can be resized to 200% without content loss
- [ ] No content conveyed by shape, size, or visual location alone

### Operable

- [ ] All interactive elements reachable via Tab key
- [ ] Tab order follows visual/logical reading order
- [ ] No keyboard traps (modal dialogs provide ESC exit)
- [ ] Skip navigation link at page top
- [ ] No content that flashes >3 times/second
- [ ] Visible focus indicator on all interactive elements
- [ ] Sufficient time on time-limited interactions

### Understandable

- [ ] `lang` attribute on `<html>` element
- [ ] Error messages identify field and explain fix
- [ ] Labels describe purpose, not just appearance
- [ ] Instructions before form fields (not only placeholder)
- [ ] Consistent navigation across pages
- [ ] Autocomplete attributes on personal data fields

### Robust

- [ ] Valid HTML (no duplicate IDs, properly nested)
- [ ] ARIA only where native semantics insufficient
- [ ] ARIA roles, states, properties correctly used
- [ ] Status messages use `role="status"` or `aria-live`
- [ ] Custom widgets follow ARIA authoring practices

## Color Contrast Reference

| Text Type | Minimum Ratio | Preferred |
|-----------|--------------|-----------|
| Normal text (<18pt) | 4.5:1 | 7:1 |
| Large text (≥18pt or ≥14pt bold) | 3:1 | 4.5:1 |
| UI components, icons | 3:1 | 4.5:1 |
| Decorative elements | No requirement | — |

Quick contrast check: https://webaim.org/resources/contrastchecker/

## ARIA Patterns

### When to Use ARIA

```html
<!-- DO: native semantics first -->
<button>Submit</button>  <!-- not <div role="button"> -->
<nav>...</nav>           <!-- not <div role="navigation"> -->

<!-- DO: ARIA for custom widgets -->
<div role="combobox" aria-expanded="false" aria-haspopup="listbox">
<div role="listbox" aria-label="Options">

<!-- DO: live regions for dynamic content -->
<div aria-live="polite" aria-atomic="true">{status message}</div>
```

### Common ARIA Mistakes

```html
<!-- BAD: redundant role -->
<button role="button">...

<!-- BAD: aria-label on non-interactive element -->
<p aria-label="description">...

<!-- BAD: missing aria-required pairing -->
<input required>  <!-- also add aria-required="true" for older AT -->
```

## Common Issues and Fixes

| Issue | Fix |
|-------|-----|
| Missing alt on image | Add `alt="descriptive text"` or `alt=""` for decorative |
| Low contrast text | Darken text color or lighten background |
| Click handler on `<div>` | Use `<button>` or add `role`, `tabindex`, `onKeyDown` |
| No visible focus | Add `:focus-visible` styles, remove `outline: none` |
| Form with no labels | Add `<label for="">` or `aria-label` |
| Icon-only button | Add `aria-label="Action name"` to button |
| Modal without focus trap | Trap focus inside modal; restore on close |
| Dynamic content not announced | Add `aria-live="polite"` to container |

## Output Format

```markdown
## Accessibility Audit: {target}

**WCAG Level**: {Partial A | A | Partial AA | AA | AAA}
**Score**: {1–5}

### Compliance Summary

| Principle | Status | Issues |
|-----------|--------|--------|
| Perceivable | ✓/⚠/✗ | {count} |
| Operable | ✓/⚠/✗ | {count} |
| Understandable | ✓/⚠/✗ | {count} |
| Robust | ✓/⚠/✗ | {count} |

### Issues

#### Critical (blocks access)
- **WCAG {criterion}**: {issue}
  - Location: {file:line}
  - Impact: {who is blocked}
  - Fix: {code change}

#### Major (significant barrier)
- **WCAG {criterion}**: {issue}
  - Fix: {recommendation}

#### Minor (enhancement)
- {issue and recommendation}

### Passed Checks
- {what is already accessible}
```

## Integration

- **visual-review skill**: Color contrast overlaps with visual consistency
- **screenshot skill**: Capture focus states, contrast visually
- **product/ux-review**: `--focus a11y` invokes this skill's criteria
- **wicked-kanban**: Log issues as tasks for remediation tracking
