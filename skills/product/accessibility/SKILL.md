---
name: accessibility
description: |
  Accessibility audit, compliance evaluation, and implementation guidance — WCAG 2.1 AA,
  keyboard navigation, screen readers, ARIA patterns, and color contrast.

  Use when: "accessibility audit", "a11y compliance", "WCAG evaluation",
  "audit for accessibility", "remediation plan", "compliance report",
  "make this accessible", "keyboard navigation", "screen reader support",
  "color contrast", "ARIA patterns", "semantic HTML", "accessible component"
---

# Accessibility Skill

WCAG 2.1 Level AA compliance auditing and inclusive design guidance.

## Core Principle

**Accessibility is not optional.** It's legal compliance, user respect, and better code.

## WCAG 2.1 Four Principles: POUR

### 1. Perceivable
Information must be presentable to users in ways they can perceive.
- Text alternatives for images
- Color contrast 4.5:1 (normal), 3:1 (large)
- No info by color alone

### 2. Operable
Interface components must be operable.
- All functionality via keyboard
- No keyboard traps
- Visible focus indicators

### 3. Understandable
Information and operation must be understandable.
- Form labels associated
- Error messages clear
- Consistent navigation

### 4. Robust
Content must work with assistive technologies.
- Valid HTML (no duplicate IDs)
- Proper ARIA usage
- Status messages announced

**Full WCAG checklists**: See [refs/wcag-checklist.md](refs/wcag-checklist.md)

## Quick Audit Process

### 1. Automated Scan
Use the Read tool on a screenshot file, or capture via browser automation if available (e.g., Playwright, Puppeteer, or an MCP browser tool). For automated WCAG scanning, use axe DevTools, Lighthouse, WAVE, or pa11y.

### 2. Keyboard Test (5 minutes)
- Tab through entire page
- Can reach all interactive elements?
- Focus always visible?
- Tab order logical?
- Can escape modals/menus?

**Full keyboard testing guide**: See [refs/keyboard-testing-basics.md](refs/keyboard-testing-basics.md) and [refs/keyboard-testing-patterns.md](refs/keyboard-testing-patterns.md)

### 3. Screen Reader Spot Check
- Turn on VoiceOver (Mac) or NVDA (Windows)
- Are images described?
- Are buttons/links clear?
- Are form labels read?

**Full screen reader guide**: See [refs/screen-reader-testing-commands.md](refs/screen-reader-testing-commands.md) and [refs/screen-reader-testing-advanced.md](refs/screen-reader-testing-advanced.md)

### 4. Code Review
```bash
# Find potential issues
wicked-garden:search "<div.*onclick" --type html  # Non-semantic buttons
wicked-garden:search "<img(?!.*alt)" --type html  # Missing alt
wicked-garden:search "aria-" --type html          # ARIA usage
```

## Common Quick Fixes

```html
<!-- ✗ Missing alt -->
<img src="profile.jpg">
<!-- ✓ Fixed -->
<img src="profile.jpg" alt="Profile of Jane Doe">

<!-- ✗ Non-semantic button -->
<div onclick="submit()">Submit</div>
<!-- ✓ Fixed -->
<button onclick="submit()">Submit</button>

<!-- ✗ Form without label -->
<input type="text" placeholder="Email">
<!-- ✓ Fixed -->
<label for="email">Email</label>
<input type="text" id="email">

<!-- ✗ Low contrast -->
<p style="color: #999; background: #fff;">Text</p>  /* 2.5:1 */
<!-- ✓ Fixed -->
<p style="color: #666; background: #fff;">Text</p>  /* 4.7:1 */
```

**More examples**: See [refs/common-violations-html-css.md](refs/common-violations-html-css.md) and [refs/common-violations-interactive.md](refs/common-violations-interactive.md)

## Output Format

```markdown
## A11y Audit

**WCAG**: {✓ Pass | ⚠ Issues | ✗ Fail}
- Perceivable: {✓⚠✗}
- Operable: {✓⚠✗}
- Understandable: {✓⚠✗}
- Robust: {✓⚠✗}

### Critical (Level A)
- Issue: {description}
  - WCAG: {criterion}
  - Fix: {specific code}

### Major (Level AA)
- Issue: {description}
  - WCAG: {criterion}
  - Fix: {recommendation}

### Recommendations
1. {Priority fixes}
```

**Full report template**: See [refs/audit-report-findings.md](refs/audit-report-findings.md) and [refs/audit-report-results.md](refs/audit-report-results.md)

## Integration

**Tools:**
```bash
# Color contrast check
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/product/contrast-check.py" "#666" "#fff"

# Track issues
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" create-task \
  "A11y" "A11y: {issue}" "todo" --priority P0 --tags "accessibility,wcag"
```

**Collaboration:**
- UX Designer: Ensure accessible patterns in flows
- UI Reviewer: Validate contrast and focus states
- QE: Include keyboard/screen reader testing

## External Integration Discovery

Accessibility auditing can leverage available integrations by capability:

| Capability | Discovery Patterns | Provides |
|------------|-------------------|----------|
| **A11y testing** | `axe`, `a11y`, `accessibility` | Automated WCAG scanning |
| **Browser testing** | `playwright`, `puppeteer` | Screenshots, DOM snapshots |
| **Performance** | `lighthouse` | Combined a11y + performance audit |

Discover available integrations via capability detection. Fall back to local contrast-check.py when none available.

## Resources

- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
- **ARIA Patterns**: https://www.w3.org/WAI/ARIA/apg/
- **WebAIM**: https://webaim.org/articles/
- **Inclusive Components**: https://inclusive-components.design/

**Detailed guides in refs/:**
- [wcag-checklist.md](refs/wcag-checklist.md) - Complete WCAG checklists
- [keyboard-testing-basics.md](refs/keyboard-testing-basics.md) - Keyboard testing checklist and core tests
- [keyboard-testing-patterns.md](refs/keyboard-testing-patterns.md) - Common violations, fixes, and tools
- [screen-reader-testing-commands.md](refs/screen-reader-testing-commands.md) - Screen reader commands and setup
- [screen-reader-testing-advanced.md](refs/screen-reader-testing-advanced.md) - Advanced screen reader tests and workflow
- [aria-patterns-basics.md](refs/aria-patterns-basics.md) - ARIA basics and simple widgets
- [aria-patterns-interactive.md](refs/aria-patterns-interactive.md) - Tabs, modals, dropdown menus
- [aria-patterns-dynamic.md](refs/aria-patterns-dynamic.md) - Combobox, alerts, live regions, best practices
- [common-violations-html-css.md](refs/common-violations-html-css.md) - HTML and CSS violation fixes
- [common-violations-interactive.md](refs/common-violations-interactive.md) - Interactive component violation fixes
- [audit-report-findings.md](refs/audit-report-findings.md) - Audit findings template
- [audit-report-results.md](refs/audit-report-results.md) - Audit results and recommendations

## When to Audit

- Before major releases
- New UI components
- Form implementations
- Modal/dialog work
- Post-build phase (crew integration)
- User-facing features

## Legal Context

**Why it matters:** ADA compliance (US), Section 508 (government), EAA (Europe), 15-20% of users need accessibility, SEO impact (screen readers = search bots)