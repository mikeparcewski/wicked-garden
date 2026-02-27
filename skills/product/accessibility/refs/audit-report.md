# Accessibility Audit Report Template

Comprehensive template for documenting accessibility audits.

## Executive Summary

**Project**: [Project name]
**Audit Date**: [YYYY-MM-DD]
**Auditor**: [Name/Team]
**WCAG Target**: [Level AA | Level AAA]
**Pages Tested**: [List or count]

### Overall Result

**Compliance Status**: [✓ Compliant | ⚠ Partial Compliance | ✗ Non-Compliant]

**WCAG 2.1 Principles:**
- Perceivable: [✓ | ⚠ | ✗]
- Operable: [✓ | ⚠ | ✗]
- Understandable: [✓ | ⚠ | ✗]
- Robust: [✓ | ⚠ | ✗]

### Summary Metrics

| Severity | Count | % Fixed |
|----------|-------|---------|
| Critical (Level A) | X | 0% |
| Major (Level AA) | X | 0% |
| Minor (AAA/Best Practice) | X | 0% |
| **Total** | **X** | **0%** |

### Key Findings

**Top 3 Issues:**
1. [Most impactful issue]
2. [Second most impactful]
3. [Third most impactful]

**Positive Observations:**
- [Good practice found]
- [Another good practice]

---

## Methodology

### Testing Approach

**Automated Tools:**
- axe DevTools [version]
- Lighthouse [version]
- WAVE
- Pa11y

**Manual Testing:**
- Keyboard navigation (Chrome, Safari)
- Screen readers:
  - VoiceOver + Safari (macOS)
  - NVDA + Firefox (Windows)
- Color contrast analyzer
- Code review

**User Flows Tested:**
1. [Primary user flow]
2. [Secondary flow]
3. [Form submission flow]

**Browsers Tested:**
- Chrome [version]
- Firefox [version]
- Safari [version]
- Edge [version]

**Devices:**
- Desktop (1920x1080)
- Tablet (iPad)
- Mobile (iPhone)

---

## Detailed Findings

### Critical Issues (Level A)

Blocking issues that prevent access for users with disabilities.

#### 1. [Issue Title]

**WCAG Criterion**: [e.g., 1.1.1 Non-text Content (Level A)]

**Impact**: [High | Medium | Low]
**Affected Users**: [Screen reader users | Keyboard users | Low vision users | etc.]
**Frequency**: [How often this occurs - e.g., "All pages" | "Form pages only"]

**Description:**
[Detailed description of the issue and why it's a problem]

**Location:**
```
File: src/components/Header.tsx
Line: 45-52
URL: /dashboard
Element: <img src="logo.png">
```

**Current State:**
```html
<img src="logo.png">
```

**Expected State (WCAG):**
```html
<img src="logo.png" alt="Company Name - Home">
```

**How to Reproduce:**
1. Navigate to /dashboard
2. Turn on screen reader
3. Tab to logo image
4. Image announced as "logo.png" instead of company name

**Recommendation:**
Add descriptive alt text to the logo image. The alt text should identify the company and indicate that it's a link to the homepage.

**Code Fix:**
```html
<a href="/">
  <img src="logo.png" alt="Company Name - Home">
</a>
```

**Resources:**
- [WebAIM: Alternative Text](https://webaim.org/techniques/alttext/)
- [WCAG 1.1.1 Understanding Doc](https://www.w3.org/WAI/WCAG21/Understanding/non-text-content.html)

**Priority**: P0 (Must fix before release)
**Estimated Effort**: 1 hour

---

#### 2. [Next Critical Issue]

[Repeat structure above for each critical issue]

---

### Major Issues (Level AA)

Significant barriers that impact usability for many users.

#### 3. [Issue Title]

**WCAG Criterion**: [e.g., 1.4.3 Contrast (Minimum) (Level AA)]

**Impact**: [High | Medium | Low]
**Affected Users**: [Low vision users | Color blind users | etc.]
**Frequency**: [Throughout site | Specific components]

**Description:**
[Detailed description]

**Location:**
```
File: src/styles/theme.css
Line: 23
Components: Buttons, Links
```

**Current State:**
```css
.button-secondary {
  color: #999999;
  background: #ffffff;
}
```
Contrast ratio: 2.8:1 (Fails - needs 4.5:1)

**Expected State:**
```css
.button-secondary {
  color: #666666;
  background: #ffffff;
}
```
Contrast ratio: 4.7:1 (Passes)

**Recommendation:**
Darken the text color to meet WCAG AA contrast requirements. Test with a contrast checker tool.

**Tool to Verify:**
```bash
python3 scripts/contrast-check.py "#666666" "#ffffff"
# Output: 4.7:1 - PASS (AA)
```

**Priority**: P1 (Fix before public release)
**Estimated Effort**: 2 hours (update theme + test all instances)

---

### Minor Issues (AAA / Best Practices)

Enhancements that improve accessibility beyond minimum compliance.

#### [Issue Number]. [Issue Title]

**WCAG Criterion**: [e.g., 2.4.8 Location (Level AAA)] or [Best Practice]

**Impact**: Low
**Affected Users**: [All users benefit]

**Description:**
[Brief description]

**Recommendation:**
[Quick fix suggestion]

**Priority**: P3 (Nice to have)
**Estimated Effort**: [Time estimate]

---

## Test Results by Page

### Homepage (/)

**Status**: [✓ Pass | ⚠ Issues | ✗ Fail]

**Issues Found**: [Count]
- Critical: [Count]
- Major: [Count]
- Minor: [Count]

**Detailed Issues:**
- Issue #1: [Brief description]
- Issue #3: [Brief description]

**Keyboard Navigation**: [✓ Pass | ✗ Fail]
**Screen Reader**: [✓ Pass | ✗ Fail]
**Color Contrast**: [✓ Pass | ✗ Fail]

---

### Dashboard (/dashboard)

[Repeat structure for each tested page]

---

## Test Results by Component

### Navigation

**Status**: ⚠ Issues

**Issues:**
- Missing skip link (Issue #5)
- Dropdown not keyboard accessible (Issue #7)

**Recommendations:**
1. Add skip navigation link
2. Implement ARIA menu pattern for dropdown

---

### Forms

**Status**: ✗ Fail

**Issues:**
- Missing labels (Issue #2)
- Error messages not associated with fields (Issue #8)
- No error summary

**Recommendations:**
1. Associate all labels with inputs
2. Use aria-describedby for error messages
3. Add error summary with role="alert" at top of form

---

## Automated Scan Results

### axe DevTools Summary

**Violations**: [Count]
**Passes**: [Count]
**Incomplete**: [Count requiring manual review]

**Top Violations:**
1. [Rule name]: [Count] instances
2. [Rule name]: [Count] instances

**Export**: [Link to full axe report JSON]

---

### Lighthouse Accessibility Score

**Score**: [0-100]

**Opportunities:**
- [Lighthouse suggestion 1]
- [Lighthouse suggestion 2]

---

## Screen Reader Testing

### VoiceOver + Safari (macOS)

**Primary Flow**: ✓ Pass
**Issues Encountered:**
- [Issue description]

**Notable Behaviors:**
- [Positive or negative behavior]

---

### NVDA + Firefox (Windows)

**Primary Flow**: ⚠ Issues
**Issues Encountered:**
- [Issue description]

**Notable Behaviors:**
- [Positive or negative behavior]

---

## Keyboard Navigation Testing

**Overall**: [✓ Pass | ⚠ Issues | ✗ Fail]

**Tab Order**: [✓ Logical | ⚠ Some issues | ✗ Broken]
**Focus Indicators**: [✓ Visible | ⚠ Inconsistent | ✗ Missing]
**Keyboard Traps**: [✓ None found | ✗ Found]

**Issues:**
1. [Issue description with location]
2. [Issue description with location]

**Flows Tested:**
- ✓ Navigate homepage
- ✗ Complete checkout (Issue #12 - modal keyboard trap)
- ⚠ Submit contact form (Issue #8 - unclear error handling)

---

## Recommendations

### Immediate Actions (P0)

Must be fixed before launch or next release.

1. **Add alt text to all images**
   - Effort: 2-4 hours
   - Files affected: [List]
   - Assigned to: [Developer]

2. **Fix form label associations**
   - Effort: 3-5 hours
   - Files affected: [List]
   - Assigned to: [Developer]

3. **Fix keyboard trap in modal**
   - Effort: 4-6 hours
   - Files affected: Modal.tsx
   - Assigned to: [Developer]

### High Priority (P1)

Should be fixed within 2-4 weeks.

1. **Improve color contrast**
   - Effort: 2-3 hours
   - Update design tokens
   - Assigned to: [Designer/Developer]

2. **Add ARIA to custom components**
   - Effort: 6-8 hours
   - Components: Dropdown, Tabs, Accordion
   - Assigned to: [Developer]

### Medium Priority (P2)

Fix within 1-2 months.

1. **Add skip navigation link**
2. **Improve heading structure**
3. **Add landmark regions**

### Low Priority (P3)

Nice to have improvements.

1. **Add ARIA live regions for dynamic content**
2. **Improve focus management on route changes**

---

## Design System Recommendations

If fixing individual issues keeps recurring, consider systematic improvements:

1. **Create accessible component library**
   - Build once, use everywhere
   - Include ARIA patterns by default
   - Document keyboard interactions

2. **Establish design tokens for color contrast**
   - Pre-approved color combinations
   - Automated contrast checking in CI

3. **Add accessibility linting**
   - eslint-plugin-jsx-a11y
   - Pre-commit hooks
   - CI pipeline checks

4. **Developer training**
   - WCAG overview
   - Screen reader basics
   - Keyboard navigation patterns

---

## Testing Checklist for Future Releases

Use this checklist for ongoing accessibility testing:

### Automated
```
□ Run axe DevTools on all pages
□ Run Lighthouse audit
□ Check color contrast with automated tool
□ Validate HTML (duplicate IDs, nesting issues)
```

### Manual
```
□ Keyboard navigation test (10 min)
□ Screen reader spot check (15 min)
□ Test primary user flow with eyes closed
□ Review code for semantic HTML
□ Check ARIA usage
```

### Before Release
```
□ All Critical (P0) issues resolved
□ All Major (P1) issues resolved or scheduled
□ Keyboard navigation works for all user flows
□ Screen reader can complete primary actions
□ Color contrast meets WCAG AA
□ Forms are fully accessible
```

---

## Resources

### Tools
- **axe DevTools**: Browser extension
- **Lighthouse**: Built into Chrome DevTools
- **WAVE**: https://wave.webaim.org/
- **Color Contrast Analyzer**: https://www.tpgi.com/color-contrast-checker/

### Guidelines
- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
- **WebAIM**: https://webaim.org/
- **A11Y Project**: https://www.a11yproject.com/

### Training
- **Deque University**: https://dequeuniversity.com/
- **WebAIM Training**: https://webaim.org/training/
- **A11ycasts**: https://www.youtube.com/playlist?list=PLNYkxOF6rcICWx0C9LVWWVqvHlYJyqw7g

---

## Appendix

### A. Full Issue List (CSV)

Export all issues as CSV for tracking:

```
ID,Severity,WCAG,Issue,Location,Status,Assignee,Due Date
1,Critical,1.1.1,Missing alt text,Header.tsx:45,Open,Jane,2026-02-01
2,Critical,1.3.1,Form labels missing,ContactForm.tsx,Open,John,2026-02-01
...
```

### B. Code Snippets

[Include longer code examples if needed]

### C. Screenshots

[Attach screenshots showing issues visually]

### D. Automated Report Files

- axe-results.json
- lighthouse-report.html
- pa11y-output.txt

---

## Sign-off

**Auditor**: [Name]
**Date**: [YYYY-MM-DD]
**Next Audit**: [Recommended date - typically after fixes or quarterly]

**Notes:**
[Any additional context or observations]
