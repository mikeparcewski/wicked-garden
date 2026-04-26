# CLI Detection

How to discover CLI tools available in the user's PATH, decide which to use, and store preferences.

## Detection Method

Use `command -v` for POSIX-portable detection — works on macOS, Linux, and WSL without relying on `which` (which may not be installed or may behave differently).

```bash
# Check if a single tool is available
command -v playwright && echo "found" || echo "not found"

# Check multiple tools, pick first available
for tool in playwright puppeteer-cli cypress selenium-webdriver; do
  if command -v "$tool" > /dev/null 2>&1; then
    echo "Using: $tool"
    break
  fi
done
```

**Why `command -v` over `which`**:
- POSIX standard — defined by POSIX.1-2008
- Works in all POSIX shells (bash, zsh, sh, dash)
- Returns exit code 0 on found, non-zero on not found
- No additional dependencies

## CLI Categories

Seven categories with specific tools to check:

### AI CLIs

Tools for interacting with AI models and coding assistants from the terminal.

| Tool | Command | Description |
|------|---------|-------------|
| claude | `claude` | Anthropic Claude CLI |
| codex | `codex` | OpenAI Codex CLI |
| gemini | `gemini` | Google Gemini CLI |
| opencode | `opencode` | OpenCode AI CLI |
| pi | `pi` | Inflection Pi CLI |

```bash
# Detect available AI CLI
for tool in claude codex gemini opencode pi; do
  command -v "$tool" > /dev/null 2>&1 && echo "$tool" && break
done
```

---

### Browser Automation CLIs

Tools for headless browser automation, testing, and scraping.

| Tool | Command | Description |
|------|---------|-------------|
| playwright | `playwright` or `npx playwright` | Microsoft Playwright |
| puppeteer | `puppeteer` or `npx puppeteer` | Google Puppeteer |
| cypress | `cypress` or `npx cypress` | Cypress test runner |
| selenium-webdriver | `selenium` or via pip/npm | Selenium WebDriver |
| chrome-devtools-protocol | via `node` + CDP | Chrome DevTools Protocol |

```bash
# Priority order: playwright > puppeteer > cypress > selenium-webdriver
for tool in playwright puppeteer cypress selenium-webdriver; do
  if command -v "$tool" > /dev/null 2>&1 || command -v "npx" > /dev/null 2>&1; then
    if npx "$tool" --version > /dev/null 2>&1; then
      echo "Using: $tool"
      break
    fi
  fi
done
```

---

### Cloud CLIs

Tools for interacting with cloud providers and hosting platforms.

| Tool | Command | Description |
|------|---------|-------------|
| aws | `aws` | Amazon Web Services CLI |
| gcloud | `gcloud` | Google Cloud SDK |
| az | `az` | Azure CLI |
| heroku | `heroku` | Heroku CLI |
| vercel | `vercel` | Vercel CLI |
| fly | `fly` | Fly.io CLI |

```bash
# Detect available cloud CLI
for tool in aws gcloud az heroku vercel fly; do
  command -v "$tool" > /dev/null 2>&1 && echo "$tool" && break
done
```

---

### Observability CLIs

Tools for monitoring, tracing, and metrics collection.

| Tool | Command | Description |
|------|---------|-------------|
| datadog-agent | `datadog-agent` | Datadog Agent |
| newrelic | `newrelic` | New Relic CLI |
| dynatrace | `dynatrace` | Dynatrace CLI |

```bash
for tool in datadog-agent newrelic dynatrace; do
  command -v "$tool" > /dev/null 2>&1 && echo "$tool" && break
done
```

---

### Data CLIs

Tools for querying databases and data stores.

| Tool | Command | Description |
|------|---------|-------------|
| duckdb | `duckdb` | DuckDB CLI |
| psql | `psql` | PostgreSQL CLI |
| mysql | `mysql` | MySQL CLI |
| mongosh | `mongosh` | MongoDB Shell |
| redis-cli | `redis-cli` | Redis CLI |

```bash
for tool in duckdb psql mysql mongosh redis-cli; do
  command -v "$tool" > /dev/null 2>&1 && echo "$tool" && break
done
```

---

### CI/CD CLIs

Tools for interacting with version control and CI/CD platforms.

| Tool | Command | Description |
|------|---------|-------------|
| gh | `gh` | GitHub CLI |
| glab | `glab` | GitLab CLI |
| circleci | `circleci` | CircleCI CLI |

```bash
for tool in gh glab circleci; do
  command -v "$tool" > /dev/null 2>&1 && echo "$tool" && break
done
```

---

### Package Managers

Tools for managing project dependencies.

| Tool | Command | Description |
|------|---------|-------------|
| npm | `npm` | Node Package Manager |
| pip | `pip` or `pip3` | Python Package Installer |
| cargo | `cargo` | Rust Package Manager |
| go | `go` | Go toolchain |
| uv | `uv` | Python package manager (fast) |
| bun | `bun` | Bun JavaScript runtime + package manager |

```bash
for tool in bun uv npm pip3 pip cargo go; do
  command -v "$tool" > /dev/null 2>&1 && echo "$tool" && break
done
```

---

## Auto-Decide vs Ask Policy

Not all tool selection decisions have the same impact. Use this policy to determine when to decide silently, decide and inform, or ask the user.

### Low Stakes — Auto-Decide Silently

Decisions that are reversible and have no significant downstream impact.

**Examples**:
- Which package manager to use for a local install (npm vs pip vs uv)
- Which database CLI for a read-only query (psql vs mysql)
- Which AI CLI for a one-off summarization

**Behavior**: Pick the first available tool in priority order. Do not mention the choice unless the user asks.

```markdown
[Auto-decided: using uv for package install — first available package manager]
```

---

### Medium Stakes — Auto-Decide but Inform

Decisions that affect visible outputs or workflow configuration.

**Examples**:
- Which issue tracker MCP to use (linear vs jira)
- Which browser automation tool (playwright vs puppeteer)
- Which CI/CD CLI to use for a pipeline trigger

**Behavior**: Pick the first available tool in priority order. Briefly note the choice to the user in a single parenthetical or line.

```markdown
Using Playwright for browser automation (detected in PATH; preferred over Puppeteer and Cypress).
```

---

### High Stakes — Always Ask User

Decisions that affect production systems, cost money, or are difficult to reverse.

**Examples**:
- Which cloud provider for a deployment (aws vs gcloud vs az)
- Which observability platform for metric ingestion
- Which database for persistent data storage

**Behavior**: List available options with one-line descriptions. Wait for user confirmation before proceeding.

```markdown
Multiple cloud CLIs detected. Which should I use for this deployment?

1. aws — Amazon Web Services (IAM configured)
2. gcloud — Google Cloud SDK (project: my-project)
3. fly — Fly.io (authenticated)

Please choose (number or name):
```

---

## Storing Preferences in wicked-brain

After the first tool selection decision, store the preference so future decisions are consistent.

### Store Pattern

```
Skill(skill="wicked-brain:memory", args="store \"cli-preference:{category}: {chosen-tool} (project: {project-path})\" --type preference")
```

**Examples**:

```
cli-preference:browser → playwright
cli-preference:cloud → aws
cli-preference:package-manager → uv
cli-preference:database → psql
```

### Recall Pattern

Before detecting CLIs for a category, check if a preference already exists:

```
Skill(skill="wicked-brain:memory", args="recall \"cli-preference:{category}\" --filter_type preference")
```

If a stored preference exists and the tool is still available (`command -v` check), use it without re-running discovery.

---

## Usage Pattern for Other Domains

Other domains and skills call integration-discovery for CLI selection rather than implementing ad-hoc detection themselves.

**Detection snippet** (copy into any skill or command):

```bash
# Pick first available browser automation CLI
for tool in playwright puppeteer cypress selenium-webdriver; do
  command -v "$tool" > /dev/null 2>&1 && BROWSER_CLI="$tool" && break
done
# If not found, recommend: npm i -D playwright && npx playwright install
```

**Output format** — include in your response when a CLI selection is made:

```
CLI Detection: playwright found (medium stake — informing user of choice)
Recommendation: npx playwright test
Install fallback: npm i -D playwright && npx playwright install
```

