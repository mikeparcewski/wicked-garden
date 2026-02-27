# CLI Reference: MVP Tools

## API Testing

### curl
- **Category**: api
- **Install**: Pre-installed on most systems
- **Structured output**: JSON via `-w` format strings
- **Pass/fail**: `-f` flag returns non-zero on HTTP errors, `--max-time` for timeouts
- **Example**:
  ```bash
  curl -sf --max-time 5 https://api.example.com/health
  ```

### hurl
- **Category**: api
- **Install**: `brew install hurl`
- **Structured output**: JSON (`--json`), JUnit XML (`--report-junit`)
- **Pass/fail**: Non-zero on assertion failure
- **Example**:
  ```hurl
  GET https://api.example.com/health
  HTTP 200
  [Asserts]
  jsonpath "$.status" == "healthy"
  ```

## Browser Testing

### playwright
- **Category**: browser
- **Install**: `npm i -D @playwright/test && npx playwright install`
- **Structured output**: JSON (`--reporter=json`), JUnit XML (`--reporter=junit`)
- **Headless**: Default in CI, use `--headed` to show browser
- **Example**:
  ```bash
  npx playwright test --reporter=json
  ```

### agent-browser
- **Category**: browser
- **Install**: `npm i -g agent-browser`
- **Structured output**: Text (snapshot command)
- **Headless**: `--headless` flag
- **Example**:
  ```bash
  agent-browser open https://example.com --headless && agent-browser snapshot
  ```

## Performance Testing

### k6
- **Category**: perf
- **Install**: `brew install k6`
- **Structured output**: JSON (`--out json=file.json`), CSV
- **Pass/fail**: Non-zero when thresholds breached
- **Example**:
  ```bash
  k6 run --vus 10 --duration 30s script.js
  ```

### hey
- **Category**: perf
- **Install**: `brew install hey`
- **Structured output**: CSV (`-o csv`), text summary
- **Pass/fail**: Zero on completion, non-zero on connection errors
- **Example**:
  ```bash
  hey -n 200 -c 20 https://api.example.com/
  ```

## Infrastructure Testing

### trivy
- **Category**: infra
- **Install**: `brew install trivy`
- **Structured output**: JSON, JUnit XML, SARIF
- **Pass/fail**: `--exit-code 1` returns non-zero when vulns found
- **Example**:
  ```bash
  trivy image --severity HIGH,CRITICAL --exit-code 1 nginx:latest
  ```

## Security Testing

### semgrep
- **Category**: security
- **Install**: `brew install semgrep`
- **Structured output**: JSON (`--json`), SARIF, JUnit XML
- **Pass/fail**: Exit code 1 when findings match
- **Example**:
  ```bash
  semgrep scan --config p/owasp-top-ten --json .
  ```

## Accessibility Testing

### pa11y
- **Category**: a11y
- **Install**: `npm i -g pa11y`
- **Structured output**: JSON (`--reporter json`), JUnit XML
- **Headless**: Headless by default (Puppeteer)
- **Pass/fail**: Exit code 2 when accessibility issues found
- **Example**:
  ```bash
  pa11y --standard WCAG2AA --reporter json https://example.com
  ```
