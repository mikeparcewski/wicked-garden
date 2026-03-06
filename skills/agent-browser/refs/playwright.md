# Playwright

Microsoft Playwright — the recommended browser automation tool for AI agents. Supports Chromium, Firefox, and WebKit with built-in auto-waiting and a rich inspector.

## Installation

```bash
# Node.js (recommended)
npm i -D playwright
npx playwright install           # downloads browser binaries

# Or install specific browsers only
npx playwright install chromium
npx playwright install firefox

# Python
pip install playwright
python -m playwright install

# uv (Python, fast)
uv add playwright
python -m playwright install

# No install (npx)
npx playwright --version
```

**Verify installation**:
```bash
npx playwright --version
# Playwright v1.x.x
```

## Key CLI Commands

```bash
# Run all tests
npx playwright test

# Run specific test file
npx playwright test tests/login.spec.ts

# Run tests matching a grep pattern
npx playwright test --grep "login"

# Run in headed mode (see the browser)
npx playwright test --headed

# Run in a specific browser
npx playwright test --browser chromium
npx playwright test --browser firefox
npx playwright test --browser webkit

# Run tests in parallel (default) or serially
npx playwright test --workers 4
npx playwright test --workers 1

# Open interactive UI mode
npx playwright test --ui

# Show trace viewer for a recorded trace
npx playwright show-trace trace.zip

# Record a new test (code generation)
npx playwright codegen https://example.com

# Take a screenshot from CLI
npx playwright screenshot --browser chromium https://example.com shot.png

# Generate a PDF
npx playwright pdf https://example.com output.pdf
```

## Common Patterns

### Page Navigation

```typescript
import { test, expect } from '@playwright/test';

test('navigate to page', async ({ page }) => {
  // Navigate
  await page.goto('https://example.com');

  // Wait for load state
  await page.waitForLoadState('networkidle');

  // Check URL
  expect(page.url()).toContain('example.com');

  // Navigate back/forward
  await page.goBack();
  await page.goForward();
});
```

### Screenshots

```typescript
test('take screenshots', async ({ page }) => {
  await page.goto('https://example.com');

  // Full page screenshot
  await page.screenshot({ path: 'full.png', fullPage: true });

  // Viewport screenshot
  await page.screenshot({ path: 'viewport.png' });

  // Screenshot of specific element
  const element = page.locator('h1');
  await element.screenshot({ path: 'heading.png' });

  // Screenshot with clip region
  await page.screenshot({
    path: 'clip.png',
    clip: { x: 0, y: 0, width: 800, height: 400 }
  });
});
```

### Form Filling

```typescript
test('fill and submit form', async ({ page }) => {
  await page.goto('https://example.com/login');

  // Fill input fields
  await page.fill('#email', 'user@example.com');
  await page.fill('#password', 'secret123');

  // Or use locators (more robust)
  await page.getByLabel('Email').fill('user@example.com');
  await page.getByLabel('Password').fill('secret123');

  // Click submit
  await page.click('button[type=submit]');
  // Or: await page.getByRole('button', { name: 'Sign in' }).click();

  // Wait for navigation after submit
  await page.waitForURL('**/dashboard');
  await expect(page).toHaveTitle(/Dashboard/);
});
```

### Waiting

```typescript
test('wait for elements and events', async ({ page }) => {
  await page.goto('https://example.com');

  // Wait for selector (auto-waits by default)
  const element = await page.waitForSelector('.loaded');

  // Wait for navigation
  await Promise.all([
    page.waitForNavigation(),
    page.click('a[href="/next"]'),
  ]);

  // Wait for network idle
  await page.waitForLoadState('networkidle');

  // Wait for specific response
  const responsePromise = page.waitForResponse('**/api/data');
  await page.click('#load-data');
  const response = await responsePromise;
  const data = await response.json();

  // Wait for timeout (avoid when possible — prefer event-based)
  await page.waitForTimeout(1000);
});
```

### Content Extraction

```typescript
test('extract page content', async ({ page }) => {
  await page.goto('https://example.com');

  // Get text content
  const heading = await page.textContent('h1');
  const allText = await page.textContent('body');

  // Get inner HTML
  const html = await page.innerHTML('.content');

  // Get attribute value
  const href = await page.getAttribute('a.link', 'href');

  // Evaluate JavaScript in page context
  const title = await page.evaluate(() => document.title);

  // Get all matching elements
  const links = await page.$$eval('a', els => els.map(el => el.href));
});
```

### Accessibility Testing

```typescript
import { test, expect } from '@playwright/test';
import { checkA11y, injectAxe } from 'axe-playwright';

test('accessibility audit', async ({ page }) => {
  await page.goto('https://example.com');

  // Inject axe-core
  await injectAxe(page);

  // Run accessibility check (throws on violations)
  await checkA11y(page, null, {
    detailedReport: true,
    detailedReportOptions: { html: true },
  });
});
```

### Network Interception

```typescript
test('mock API responses', async ({ page }) => {
  // Intercept and mock a route
  await page.route('**/api/users', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 1, name: 'Test User' }]),
    });
  });

  await page.goto('https://example.com');
  // Page will use mocked API response
});
```

## Playwright Configuration

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 2,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'https://example.com',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'mobile', use: { ...devices['iPhone 14'] } },
  ],
});
```

## Debugging

```bash
# Run with inspector (step through test)
npx playwright test --debug

# Run in headed mode
npx playwright test --headed

# Slow down execution
PLAYWRIGHT_SLOWMO=500 npx playwright test

# Capture trace for all tests
npx playwright test --trace on

# View captured trace
npx playwright show-trace test-results/*/trace.zip
```

## AI Agent Usage Tips

- Use `page.getByRole()` and `page.getByLabel()` locators — more stable than CSS selectors
- Prefer `waitForLoadState('networkidle')` for SPAs before extracting content
- Use `page.screenshot({ fullPage: true })` to capture full page for analysis
- `page.accessibility.snapshot()` returns the full accessibility tree as JSON — useful for AI agents reading page structure without rendering
