---
name: a11y-wcag-check
description: WCAG 2.1 Level AA accessibility compliance check
category: a11y
tools:
  required: [pa11y]
difficulty: basic
timeout: 60
---

# Accessibility WCAG Check

Runs a WCAG 2.1 Level AA accessibility audit against a web page. Identifies accessibility issues including missing alt text, poor contrast, missing form labels, and keyboard navigation problems.

## Setup

```bash
export PAGE_URL="${PAGE_URL:-https://example.com}"
```

## Steps

### Step 1: WCAG 2.1 AA audit (pa11y)

```bash
pa11y --standard WCAG2AA --reporter json "${PAGE_URL}" > "${TMPDIR:-/tmp}/pa11y-results.json" 2>&1
```

**Expect**: Exit code 0 if no accessibility issues, exit code 2 if issues found

### Step 2: Summarize findings (pa11y)

```bash
pa11y --standard WCAG2AA "${PAGE_URL}" 2>&1 | head -20
```

**Expect**: Human-readable summary of accessibility issues (if any)

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/pa11y-results.json"
```
