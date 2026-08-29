# Scenario Format — qe v1

> Ported from the retired wicked-testing package's SCENARIO-FORMAT.md (Phase 6c). <!-- historical -->

qe scenarios are self-contained markdown files that both humans and AI agents can execute and review. Each scenario is a complete specification: what to test, how to test it, and what success looks like.

## Format Overview

Every scenario is a `.md` file with YAML frontmatter followed by a markdown body.

```yaml
---
name: scenario-name          # Required. Unique identifier (slug format)
description: |               # Required. What this scenario tests
  One or more lines describing the scenario's purpose.
version: "1.0"               # Required. Scenario format version
category: api                # Required. api|browser|perf|infra|security|a11y|cli|equivalence
tags: [smoke, auth]          # Optional. List of tags for filtering
tools:
  required: [curl]           # Required CLIs — scenario SKIPs if missing
  optional: [hurl]           # Optional CLIs — used if available, ignored if not
timeout: 120                 # Optional. Max seconds per step (default: 120)
assertions:                  # Required. High-level acceptance criteria
  - id: A1
    description: Response status is 200
  - id: A2
    description: Response body contains expected fields
  - id: A3                   # Optional equivalence assertion (baseline-match)
    description: Output matches the captured baseline
    baseline: tests/baselines/cart.json   # Optional. Path to the captured baseline artifact
    method: golden-master                 # Optional. golden-master|contract|reconciliation|perceptual
    tolerance: 0                          # Optional. Allowed diff count (default 0)
---
```

## Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique slug identifier (lowercase, hyphens OK) |
| `description` | Yes | Human-readable description of what is tested |
| `version` | Yes | Scenario format version (`"1.0"` for v1) |
| `category` | Yes | Test category — determines default tool priority |
| `tags` | No | Array of string tags for filtering |
| `tools.required` | No | CLIs that must be present — steps using them SKIP if absent |
| `tools.optional` | No | CLIs used if present; degraded gracefully if absent |
| `timeout` | No | Per-step timeout in seconds (default: 120) |
| `assertions` | Yes | Array of high-level acceptance criteria (id + description) |
| `assertions[].baseline` | No | Path to a captured baseline artifact — makes the assertion an equivalence (baseline-match) check |
| `assertions[].method` | No | Equivalence method when `baseline` is set: `golden-master`, `contract`, `reconciliation`, or `perceptual` (default `golden-master`) |
| `assertions[].tolerance` | No | Allowed diff count for an equivalence assertion (default `0` — exact match) |

## Category Values

| Category | Primary Tools | What to Test |
|----------|--------------|-------------|
| `api` | curl, hurl | HTTP endpoints, response validation, contracts |
| `browser` | playwright, cypress | Page load, interactions, content |
| `perf` | k6, hey | Load testing, response time thresholds |
| `infra` | trivy | Container scanning, IaC security |
| `security` | semgrep | SAST, code security patterns |
| `a11y` | pa11y | WCAG compliance, accessibility violations |
| `cli` | bash | CLI command behavior, exit codes |
| `equivalence` | diff, jq, pixelmatch | Baseline-match: output reproduces a captured baseline within tolerance (golden-master / contract / reconciliation / perceptual) |

## Body Format

The body is structured markdown with optional `## Setup`, required `## Steps`, and optional `## Cleanup` sections.

### Setup (Optional)

```markdown
## Setup

```bash
# Commands to run before the test steps
# Exit code is non-fatal — warn on failure but continue
# Use a portable tmp dir: TMPDIR (Unix), TEMP (Windows Git Bash), fallback /tmp.
export TEST_ENV=integration
WT_TMP="${TMPDIR:-${TEMP:-/tmp}}"
mkdir -p "${WT_TMP}/test-artifacts"
```
```

### Steps (Required)

Each step is a level-3 heading with the format `### Step N: {description} ({cli-name})`:

```markdown
## Steps

### Step 1: Check API health (curl)

```bash
curl -sf https://example.com/api/health
```

**Expect**: Exit code 0, JSON response with `status: "ok"`

### Step 2: Verify response body (curl)

```bash
curl -sf https://example.com/api/health | grep '"status":"ok"'
```

**Expect**: Exit code 0, "status":"ok" found in body
```

#### Step Rules

1. **Exit code = pass/fail** — exit 0 is PASS, non-zero is FAIL
2. **One CLI per step** — identify it in the step header parenthetical `(curl)`
3. **Fenced code blocks** — use appropriate language hint (`bash`, `javascript`)
4. **`**Expect**:` annotation** — required, explains what success looks like

### Cleanup (Optional)

```markdown
## Cleanup

```bash
# Always runs after steps, even on failure (like a finally block).
# Use the same portable tmp resolution as Setup.
WT_TMP="${TMPDIR:-${TEMP:-/tmp}}"
rm -rf "${WT_TMP}/test-artifacts"
```
```

## Complete Examples

### Example 1: API Scenario

```yaml
---
name: health-check-positive
description: |
  Verify the API health endpoint returns 200 with correct JSON body.
  Positive case: valid request → expected response.
version: "1.0"
category: api
tags: [smoke, api, health]
tools:
  required: [curl]
  optional: []
timeout: 30
assertions:
  - id: A1
    description: HTTP status 200
  - id: A2
    description: Body contains status ok
---

## Steps

### Step 1: HTTP GET returns 200 (curl)

```bash
curl -sf -o /dev/null -w "%{http_code}" https://api.example.com/health | grep -q "^200$"
```

**Expect**: Exit code 0, HTTP 200 returned

### Step 2: Body contains status ok (curl)

```bash
curl -sf https://api.example.com/health | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ok', 'status not ok'; print('PASS')"
```

**Expect**: Exit code 0, "PASS" printed
```

### Example 2: Browser Scenario

```yaml
---
name: login-flow-positive
description: |
  Verify the user login flow works end-to-end in a headless browser.
  Positive case: valid credentials → authenticated dashboard.
version: "1.0"
category: browser
tags: [auth, browser, smoke]
tools:
  required: [playwright]
  optional: []
timeout: 60
assertions:
  - id: A1
    description: Login page loads without JS errors
  - id: A2
    description: Valid credentials grant access to dashboard
---

## Steps

### Step 1: Login page loads without errors (playwright)

```bash
npx playwright test --grep "login page" --reporter=line
```

**Expect**: Exit code 0, no JS errors, page loads successfully

### Step 2: Valid credentials authenticate user (playwright)

```bash
npx playwright test --grep "login flow" --reporter=line
```

**Expect**: Exit code 0, user is redirected to dashboard

## Cleanup

```bash
npx playwright test --reporter=list 2>/dev/null || true
```
```

### Example 3: CLI Scenario

```yaml
---
name: wt-insight-returns-json
description: |
  Verify that wicked-garden-qe insight --json returns valid JSON with expected fields.
  Self-test scenario: the qe domain validates itself.
version: "1.0"
category: cli
tags: [self-test, insight, json]
tools:
  required: [node]
  optional: [sqlite3]
timeout: 30
assertions:
  - id: A1
    description: Stats command exits 0
  - id: A2
    description: Output is valid JSON
  - id: A3
    description: JSON contains ok=true and data.counts
---

## Steps

### Step 1: DomainStore stats() returns valid structure (node)

```bash
node -e "
import('wicked-ledger').then(({ DomainStore }) => {
  const store = new DomainStore('.wicked-qe');
  const stats = store.stats();
  const output = JSON.stringify({ok: true, data: stats});
  console.log(output);
  if (!stats.counts) { process.exit(1); }
  store.close();
}).catch(e => { console.error(e.message); process.exit(1); });
"
```

**Expect**: Exit code 0, valid JSON with `counts` object containing table names

### Step 2: Schema version is at least 1 (node)

```bash
node -e "
import('wicked-ledger').then(({ DomainStore }) => {
  const store = new DomainStore('.wicked-qe');
  const version = store.schemaVersion();
  console.log('Schema version:', version);
  if (!(version >= 1)) { console.error('FAIL: expected version >= 1, got', version); process.exit(1); }
  store.close();
}).catch(e => { console.error(e.message); process.exit(1); });
"
```

**Expect**: Exit code 0, "Schema version:" line with a value >= 1 (currently 2)
```

## Validation Rules

A valid scenario file MUST:

1. Have valid YAML frontmatter parseable without errors
2. Include all required frontmatter fields (`name`, `description`, `version`, `category`, `assertions`)
3. Have at least one `### Step N:` section in the body
4. Each step must have at least one fenced code block
5. `name` must be a slug (lowercase, hyphens, no spaces)
6. `category` must be one of the documented values
7. `version` must be a quoted string (e.g. `"1.0"`)

## Naming Conventions

| Convention | Example |
|-----------|---------|
| Positive scenarios | `{feature}-positive.md` |
| Negative scenarios | `{feature}-negative.md` |
| Self-test scenarios | `{component}-self-test.md` |
| Performance scenarios | `{feature}-perf.md` |
| Security scenarios | `{feature}-security.md` |

## Integration with the qe domain

Scenarios are:
- **Executed** by the `wicked-garden-qe` skill's `execute` action → evidence JSON written to `.wicked-qe/evidence/<run-id>/`
- **Accepted** by the `wicked-garden-qe` skill's `accept` action → 3-agent pipeline produces verdicts
- **Registered** in DomainStore via the `wicked-garden-qe` skill's `author` action
- **Queryable** via `wicked-garden-qe insight "what scenarios exist for project X?"`
