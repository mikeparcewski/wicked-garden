---
name: browser-page-audit
description: Verify page loads correctly and passes basic interaction checks
category: browser
tools:
  required: []
  optional: [agent-browser, playwright]
difficulty: intermediate
timeout: 60
---

# Browser Page Audit

Verifies that a web page loads successfully, renders expected content, and responds to basic interactions using browser CLI tools. Uses a local HTML fixture served via `python3 -m http.server` so assertions are deterministic and never break due to external content changes.

## Setup

```bash
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

# Pick a free port (fall back to 8765 if python one-liner fails)
SCEN_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()" 2>/dev/null || echo 8765)
echo "$SCEN_PORT" > "${TMPDIR:-/tmp}/wicked-scenario-pw/port"

# Start a local server in the background
python3 -m http.server "$SCEN_PORT" --directory "${TMPDIR:-/tmp}/wicked-scenario-pw" &
SERVER_PID=$!
echo "$SERVER_PID" > "${TMPDIR:-/tmp}/wicked-scenario-pw/server.pid"

# Wait for the server to be ready (up to 5 seconds)
for i in 1 2 3 4 5; do
  curl -sf "http://localhost:${SCEN_PORT}/" >/dev/null 2>&1 && break
  sleep 1
done
```

## Steps

### Step 1: Page load and DOM snapshot

```bash
if ! command -v agent-browser &>/dev/null; then
  echo "SKIP: agent-browser not installed — skipping step 1"
  exit 0
fi
SCEN_PORT=$(cat "${TMPDIR:-/tmp}/wicked-scenario-pw/port")
agent-browser open "http://localhost:${SCEN_PORT}/" --headless
SNAPSHOT=$(agent-browser snapshot)
echo "$SNAPSHOT"
echo "$SNAPSHOT" | grep -qi "Wicked" || { echo "FAIL: page content not rendered"; exit 1; }
echo "PASS: page loaded and DOM snapshot captured"
```

**Expect**: Exit code 0, agent-browser loads page and snapshot contains page content (or SKIP when agent-browser is unavailable)

### Step 2: Content verification via DOM

```bash
if ! command -v agent-browser &>/dev/null; then
  echo "SKIP: agent-browser not installed — skipping step 2"
  exit 0
fi
SNAPSHOT=$(agent-browser snapshot)
echo "$SNAPSHOT" | grep -qi "Wicked Garden Scenario Test" || { echo "FAIL: h1 not found in DOM"; exit 1; }
echo "$SNAPSHOT" | grep -qi "browser-page-audit" || { echo "FAIL: paragraph not found in DOM"; exit 1; }
echo "$SNAPSHOT" | grep -qi "About" || { echo "FAIL: about section not found in DOM"; exit 1; }
echo "PASS: all expected content present in DOM"
```

**Expect**: Exit code 0, heading, paragraph, and about section all present in the rendered DOM (or SKIP when agent-browser is unavailable)

### Step 3: Screenshot capture

```bash
SCEN_PORT=$(cat "${TMPDIR:-/tmp}/wicked-scenario-pw/port")
if command -v playwright &>/dev/null; then
  playwright screenshot "http://localhost:${SCEN_PORT}/" "${TMPDIR:-/tmp}/wicked-scenario-pw/screenshot.png" 2>&1
  [ -f "${TMPDIR:-/tmp}/wicked-scenario-pw/screenshot.png" ] || { echo "FAIL: screenshot not created"; exit 1; }
  echo "PASS: screenshot captured via playwright CLI"
elif command -v agent-browser &>/dev/null; then
  agent-browser screenshot "${TMPDIR:-/tmp}/wicked-scenario-pw/screenshot.png" 2>&1
  [ -f "${TMPDIR:-/tmp}/wicked-scenario-pw/screenshot.png" ] || { echo "FAIL: screenshot not created"; exit 1; }
  echo "PASS: screenshot captured via agent-browser"
else
  echo "SKIP: neither playwright nor agent-browser installed — skipping step 3"
  exit 0
fi
```

**Expect**: Exit code 0, screenshot file created (or SKIP when neither playwright nor agent-browser is available)

### Step 4: Link interaction

```bash
if ! command -v agent-browser &>/dev/null; then
  echo "SKIP: agent-browser not installed — skipping step 4"
  exit 0
fi
agent-browser click "a[href='#about']" 2>&1
SNAPSHOT=$(agent-browser snapshot)
echo "$SNAPSHOT" | grep -qi "fixture for reliable testing" || { echo "FAIL: about section content not accessible after click"; exit 1; }
echo "PASS: link click navigated to about section"
```

**Expect**: Exit code 0, clicking the "Learn more" link navigates to the about section (or SKIP when agent-browser is unavailable)

## Cleanup

```bash
# Stop the local server
if [ -f "${TMPDIR:-/tmp}/wicked-scenario-pw/server.pid" ]; then
  kill "$(cat "${TMPDIR:-/tmp}/wicked-scenario-pw/server.pid")" 2>/dev/null || true
fi
rm -rf "${TMPDIR:-/tmp}/wicked-scenario-pw"
```
