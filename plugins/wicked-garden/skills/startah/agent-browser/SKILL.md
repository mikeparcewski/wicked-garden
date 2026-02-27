---
name: agent-browser
description: |
  Browser automation via agent-browser CLI. Screenshots, scraping, accessibility audits,
  form automation, and live viewport streaming.

  Use when:
  - Taking screenshots or extracting page content
  - Automating web forms and UI interactions
  - Accessibility audits
  - Web scraping for AI agents
  - Testing web applications
---

# Agent Browser

Use the `agent-browser` CLI for headless browser automation.

## Prerequisites

```bash
# Check if installed
which agent-browser

# Install via npm
npm install -g agent-browser

# Or use npx (no install)
npx agent-browser --help
```

## Core Commands

```bash
# Open a URL
agent-browser open https://example.com

# Take screenshot
agent-browser screenshot --output screenshot.png

# Get page snapshot (accessibility tree + content)
agent-browser snapshot

# Click element
agent-browser click "button.submit"

# Fill form field
agent-browser fill "input[name=email]" "user@example.com"

# Extract text content
agent-browser text "main"

# Get page HTML
agent-browser html
```

## Common Workflows

### Screenshot a Page

```bash
agent-browser open https://example.com
agent-browser screenshot --output page.png
```

### Fill and Submit Form

```bash
agent-browser open https://example.com/login
agent-browser fill "#email" "user@example.com"
agent-browser fill "#password" "secret"
agent-browser click "button[type=submit]"
agent-browser wait 2000
agent-browser screenshot --output result.png
```

### Extract Page Content

```bash
agent-browser open https://example.com
agent-browser snapshot  # Returns accessibility tree + text
```

### Accessibility Audit

```bash
agent-browser open https://example.com
agent-browser a11y  # Returns accessibility violations
```

## Live Preview

Stream the browser viewport via WebSocket:

```bash
agent-browser open https://example.com --stream
# Opens ws://localhost:9222 for live viewport
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `open URL` | Navigate to URL |
| `screenshot` | Capture viewport |
| `snapshot` | Get accessibility tree + content |
| `click SELECTOR` | Click element |
| `fill SELECTOR VALUE` | Fill input field |
| `text SELECTOR` | Extract text content |
| `html` | Get page HTML |
| `a11y` | Accessibility audit |
| `wait MS` | Wait for milliseconds |

For full reference: https://github.com/vercel-labs/agent-browser
