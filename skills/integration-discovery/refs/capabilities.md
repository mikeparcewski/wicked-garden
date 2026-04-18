# Capability Definitions

Detailed patterns for discovering integrations by capability category.

## Project Management

**Purpose**: Task tracking, sprints, boards, issue management

**Discovery patterns** (check server names/descriptions for):
- `issue`, `task`, `ticket`, `bug`
- `project`, `board`, `sprint`, `backlog`
- `jira`, `linear`, `asana`, `github`, `gitlab`
- `trello`, `monday`, `clickup`, `notion`

**Common operations**:
- Create/update issues
- Query project status
- Link code to issues
- Track progress

**Fallback**: Use native TaskCreate/TaskUpdate for local task management

---

## Analytics & Metrics

**Purpose**: User behavior, product metrics, event tracking

**Discovery patterns**:
- `analytics`, `metrics`, `events`, `tracking`
- `posthog`, `mixpanel`, `amplitude`, `segment`
- `google-analytics`, `plausible`, `matomo`

**Common operations**:
- Query user behavior
- Analyze funnels
- Track feature usage
- Generate reports

**Fallback**: Use data for local data analysis

---

## Error Tracking & Monitoring

**Purpose**: Exception tracking, crash reports, APM

**Discovery patterns**:
- `error`, `exception`, `crash`, `sentry`
- `monitoring`, `observability`, `apm`
- `rollbar`, `bugsnag`, `datadog`, `newrelic`

**Common operations**:
- Query recent errors
- Analyze error trends
- Link errors to code
- Track release health

**Fallback**: Search logs via wicked-garden:search

---

## Design Systems

**Purpose**: Design tokens, components, visual assets

**Discovery patterns**:
- `design`, `figma`, `sketch`, `adobe`
- `component`, `storybook`, `chromatic`
- `token`, `theme`, `style`

**Common operations**:
- Export design tokens
- Query component specs
- Sync design decisions
- Access visual assets

**Fallback**: Manual design system documentation

---

## Data Warehouses

**Purpose**: Large-scale data queries, BI, transformations

**Discovery patterns**:
- `warehouse`, `lakehouse`, `dbt`
- `snowflake`, `databricks`, `bigquery`, `redshift`
- `sql`, `query`, `etl`

**Common operations**:
- Execute SQL queries
- Access data models
- Query lineage
- Generate reports

**Fallback**: Use data for local file analysis

---

## Documentation & Knowledge

**Purpose**: Wikis, docs, knowledge bases

**Discovery patterns**:
- `wiki`, `docs`, `documentation`
- `confluence`, `notion`, `coda`
- `knowledge`, `kb`

**Common operations**:
- Search documentation
- Create/update pages
- Link code to docs
- Export content

**Fallback**: Use wicked-garden:search for local doc search

---

## Communication

**Purpose**: Team chat, notifications, collaboration

**Discovery patterns**:
- `chat`, `message`, `slack`, `teams`
- `discord`, `mattermost`, `rocket`
- `notification`, `alert`

**Common operations**:
- Send notifications
- Query conversations
- Create channels
- Share updates

**Fallback**: Manual communication

---

## CI/CD & DevOps

**Purpose**: Pipelines, deployments, infrastructure

**Discovery patterns**:
- `pipeline`, `ci`, `cd`, `deploy`
- `github-actions`, `gitlab-ci`, `jenkins`
- `terraform`, `kubernetes`, `docker`

**Common operations**:
- Trigger builds
- Check pipeline status
- Deploy applications
- Manage infrastructure

**Fallback**: Use platform CLI skills

---

## Security & Compliance

**Purpose**: Vulnerability scanning, secrets, compliance

**Discovery patterns**:
- `security`, `vulnerability`, `scan`
- `snyk`, `trivy`, `vault`, `secrets`
- `compliance`, `audit`, `sast`, `sca`

**Common operations**:
- Run security scans
- Manage secrets
- Check compliance
- Generate SBOMs

**Fallback**: Use platform local checks

---

## Feature Flags

**Purpose**: Feature toggles, experiments, gradual rollouts

**Discovery patterns**:
- `feature`, `flag`, `toggle`
- `launchdarkly`, `unleash`, `split`
- `experiment`, `ab-test`, `rollout`

**Common operations**:
- Check flag status
- Create experiments
- Query rollout progress
- Manage targeting

**Fallback**: Config-based flags in code

---

## Customer Feedback

**Purpose**: Support tickets, surveys, user feedback

**Discovery patterns**:
- `support`, `ticket`, `zendesk`
- `intercom`, `freshdesk`, `helpscout`
- `survey`, `feedback`, `nps`

**Common operations**:
- Query support tickets
- Analyze feedback trends
- Link bugs to reports
- Track satisfaction

**Fallback**: Manual feedback review

---

## CLI Detection

**Purpose**: Discover installed CLI tools in the system PATH

**Detection method**: `command -v {tool}` (POSIX-portable, works on macOS, Linux, WSL)

**CLI categories**:
- AI CLIs: claude, codex, copilot, gemini, opencode, pi
- Browser: playwright, puppeteer, cypress, chrome-devtools-protocol
- Cloud: aws, gcloud, az, heroku, vercel, fly
- Observability: datadog-agent, newrelic, dynatrace
- Data: duckdb, psql, mysql, mongosh, redis-cli
- CI/CD: gh, glab, circleci
- Package managers: npm, pip, cargo, go, uv, bun

**Decision policy**:
- Low stakes (e.g., package manager): auto-decide silently
- Medium stakes (e.g., browser tool): auto-decide, inform user
- High stakes (e.g., cloud provider): always ask user

**Fallback**: Recommend installation of the preferred tool for the category

See [cli-detection.md](cli-detection.md) for full detection patterns and decision policy.

---

## Discovery Implementation

```python
# Pseudo-code for capability discovery

def discover_capability(capability_name):
    """Discover integrations matching a capability."""
    patterns = CAPABILITY_PATTERNS[capability_name]

    # Get available MCP servers
    servers = list_mcp_resources()

    # Match by patterns
    matches = []
    for server in servers:
        for pattern in patterns:
            if pattern in server.name.lower() or pattern in server.description.lower():
                matches.append(server)
                break

    return matches or None
```

## Usage in Skills

```markdown
## Integration Discovery

This skill can leverage external integrations:

| Capability | Purpose | Discovery |
|------------|---------|-----------|
| project-management | Link work to issues | Check for jira, linear, github |
| analytics | User behavior data | Check for posthog, mixpanel |

Run `ListMcpResourcesTool` and match against capability patterns.
If no match found, use standalone mode with local alternatives.
```
