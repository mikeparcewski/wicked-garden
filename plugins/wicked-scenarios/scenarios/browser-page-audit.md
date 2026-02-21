---
name: browser-page-audit
description: Verify page loads correctly and passes basic interaction checks
category: browser
tools:
  required: [playwright]
  optional: [agent-browser]
difficulty: intermediate
timeout: 60
---

# Browser Page Audit

Verifies that a web page loads successfully, renders expected content, and responds to basic interactions.

## Setup

```bash
# Check required tools
if ! command -v npx &>/dev/null; then
  echo "SKIP: npx not available (needed for playwright)"
  exit 0
fi
# Ensure Playwright browsers are installed
npx playwright install chromium 2>/dev/null || true
mkdir -p "${TMPDIR:-/tmp}/wicked-scenario-pw"
```

## Steps

### Step 1: Page load and title check (playwright)

```bash
if ! npx playwright --version &>/dev/null; then
  echo "SKIP: playwright not installed. Run /wicked-scenarios:setup to install."
  exit 0
fi
cat > "${TMPDIR:-/tmp}/wicked-scenario-pw"/title.spec.ts << 'PW_EOF'
import { test, expect } from '@playwright/test';
test('page loads with correct title', async ({ page }) => {
  await page.goto('https://example.com');
  await expect(page).toHaveTitle(/Example Domain/);
});
PW_EOF
npx playwright test "${TMPDIR:-/tmp}/wicked-scenario-pw"/title.spec.ts --reporter=line
```

**Expect**: Exit code 0, page loads with expected title

### Step 2: Content verification (playwright)

```bash
if ! npx playwright --version &>/dev/null; then
  echo "SKIP: playwright not installed. Run /wicked-scenarios:setup to install."
  exit 0
fi
cat > "${TMPDIR:-/tmp}/wicked-scenario-pw"/content.spec.ts << 'PW_EOF'
import { test, expect } from '@playwright/test';
test('page has expected content', async ({ page }) => {
  await page.goto('https://example.com');
  await expect(page.locator('h1')).toHaveText('Example Domain');
  await expect(page.locator('p').first()).toContainText('for use in illustrative examples in documents');
});
PW_EOF
npx playwright test "${TMPDIR:-/tmp}/wicked-scenario-pw"/content.spec.ts --reporter=line
```

**Expect**: Exit code 0, page content matches expectations

### Step 3: Snapshot with agent-browser (agent-browser)

```bash
if ! command -v agent-browser &>/dev/null; then
  echo "SKIP: agent-browser not installed. Run /wicked-scenarios:setup to install."
  exit 0
fi
agent-browser open https://example.com --headless && agent-browser snapshot
```

**Expect**: Exit code 0, page snapshot captured

## Cleanup

```bash
rm -rf "${TMPDIR:-/tmp}/wicked-scenario-pw"
```
