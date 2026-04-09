---
name: agent-browser
description: |
  Browser automation skill with priority-ordered CLI discovery.
  Detects the best available browser automation tool in the system PATH and provides
  usage patterns for Playwright, Puppeteer, Cypress, and Selenium WebDriver.

  Use when:
  - Taking screenshots or extracting page content
  - Automating web forms and UI interactions
  - Accessibility audits
  - Web scraping for AI agents
  - Testing web applications
  - End-to-end test execution
portability: portable
---

# Browser Automation

Detects and uses the best available browser automation CLI in your environment.

## CLI Discovery

Before executing browser automation, detect which tool is available:

```bash
# Priority order: playwright > puppeteer > cypress > selenium-webdriver
for tool in playwright puppeteer cypress selenium-webdriver; do
  if command -v "$tool" > /dev/null 2>&1; then
    echo "Using: $tool"
    break
  fi
  # Check via npx for Node-based tools
  if command -v npx > /dev/null 2>&1; then
    if npx "$tool" --version > /dev/null 2>&1; then
      echo "Using: npx $tool"
      break
    fi
  fi
done
```

**Stake level**: Medium — inform the user which tool was selected.

**If none found**: Recommend Playwright installation (see below).

**Pattern**: This follows the integration-discovery CLI detection pattern.
See [integration-discovery refs/cli-detection.md](../../integration-discovery/refs/cli-detection.md) for the full decision policy.

## Priority Order

| Priority | Tool | Why |
|----------|------|-----|
| 1 | **Playwright** | Best AI-agent support, cross-browser, built-in waiting |
| 2 | **Puppeteer** | Mature API, Chrome-focused, wide adoption |
| 3 | **Cypress** | Test-focused, good DX, component testing |
| 4 | **Selenium WebDriver** | Legacy support, multi-language |

## Installation (None Found)

```bash
# Playwright (recommended)
npm i -D playwright
npx playwright install

# Or with uv (Python)
uv add playwright
python -m playwright install
```

## Quick Command Reference

| Scenario | Playwright | Puppeteer | Cypress |
|----------|------------|-----------|---------|
| Run tests | `npx playwright test` | node script | `npx cypress run` |
| Open UI | `npx playwright test --ui` | - | `npx cypress open` |
| Record test | `npx playwright codegen URL` | - | - |
| Screenshot | `page.screenshot()` | `page.screenshot()` | `cy.screenshot()` |
| Navigate | `page.goto(URL)` | `page.goto(URL)` | `cy.visit(URL)` |
| Click | `page.click(sel)` | `page.click(sel)` | `cy.get(sel).click()` |
| Fill input | `page.fill(sel, val)` | `page.type(sel, val)` | `cy.get(sel).type(val)` |
| Wait | `page.waitForSelector()` | `page.waitForSelector()` | built-in |

## Common Patterns

### Screenshot a Page

```bash
# Playwright
npx playwright screenshot --browser chromium https://example.com out.png
```

### Run Existing Tests

```bash
# Playwright
npx playwright test

# Cypress
npx cypress run

# Puppeteer (node script)
node tests/puppeteer.js
```

### Record a New Test (Playwright only)

```bash
npx playwright codegen https://example.com
# Opens browser + code recorder, paste generated test into your test file
```

### Accessibility Audit

```bash
# Playwright + axe-core
npx playwright test --grep @a11y

# agent-browser CLI (legacy)
agent-browser open https://example.com
agent-browser a11y
```

## Legacy: agent-browser CLI

If `agent-browser` is installed (older projects), it provides a simpler command interface:

```bash
agent-browser open https://example.com
agent-browser screenshot --output page.png
agent-browser snapshot    # accessibility tree + content
agent-browser click "button.submit"
agent-browser fill "input[name=email]" "user@example.com"
agent-browser a11y        # accessibility violations
```

## References

- [Playwright](refs/playwright.md) - Full Playwright usage patterns
- [Puppeteer](refs/puppeteer.md) - Puppeteer API and patterns
- [Cypress](refs/cypress.md) - Cypress test runner guide
- [Selenium](refs/selenium.md) - Selenium WebDriver patterns
