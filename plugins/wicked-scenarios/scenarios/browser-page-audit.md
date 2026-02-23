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

Verifies that a web page loads successfully, renders expected content, and responds to basic interactions. Uses a local HTML fixture served via `python3 -m http.server` so assertions are deterministic and never break due to external content changes.

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

# Create a local HTML fixture for deterministic testing
cat > "${TMPDIR:-/tmp}/wicked-scenario-pw/index.html" << 'HTML_EOF'
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Wicked Test Page</title></head>
<body>
  <h1>Wicked Garden Scenario Test</h1>
  <p>This page is used for browser-page-audit scenario validation.</p>
  <a href="#about">Learn more</a>
  <section id="about"><h2>About</h2><p>A local fixture for reliable testing.</p></section>
</body>
</html>
HTML_EOF

# Start a local server in the background
python3 -m http.server 8765 --directory "${TMPDIR:-/tmp}/wicked-scenario-pw" &
SERVER_PID=$!
echo "$SERVER_PID" > "${TMPDIR:-/tmp}/wicked-scenario-pw/server.pid"
# Give the server a moment to start
sleep 1
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
  await page.goto('http://localhost:8765/');
  await expect(page).toHaveTitle(/Wicked Test Page/);
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
  await page.goto('http://localhost:8765/');
  await expect(page.locator('h1')).toHaveText('Wicked Garden Scenario Test');
  await expect(page.locator('p').first()).toContainText('browser-page-audit scenario validation');
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
agent-browser open http://localhost:8765/ --headless && agent-browser snapshot
```

**Expect**: Exit code 0, page snapshot captured

## Cleanup

```bash
# Stop the local server
if [ -f "${TMPDIR:-/tmp}/wicked-scenario-pw/server.pid" ]; then
  kill "$(cat "${TMPDIR:-/tmp}/wicked-scenario-pw/server.pid")" 2>/dev/null || true
fi
rm -rf "${TMPDIR:-/tmp}/wicked-scenario-pw"
```
