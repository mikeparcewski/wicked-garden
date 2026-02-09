# Scenario Format Specification

## YAML Frontmatter (Required)

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| name | string | yes | kebab-case | Unique scenario identifier |
| description | string | yes | - | One-line description of what this tests |
| category | string | yes | api, browser, perf, infra, security, a11y | Testing category |
| tools.required | array | yes | MVP tool names | CLIs that must be available |
| tools.optional | array | no | MVP tool names | CLIs used if available |
| difficulty | string | yes | basic, intermediate, advanced | Complexity level |
| timeout | integer | no | positive int (default 120) | Max execution seconds |
| env | array | no | VAR_NAME or VAR_NAME? | Required env vars (? suffix = optional) |

## Markdown Body Structure

```markdown
# {Title}

{Description paragraph}

## Setup

\`\`\`bash
{setup commands}
\`\`\`

## Steps

### Step 1: {description} ({cli-name})

\`\`\`{language}
{cli commands}
\`\`\`

**Expect**: {natural language description of success}

### Step 2: ...

## Cleanup

\`\`\`bash
{cleanup commands}
\`\`\`
```

## Validation Rules

1. Frontmatter must contain all required fields
2. Category must be one of the 6 valid values
3. Tools must reference recognized CLI names
4. Each step must have a fenced code block
5. Step headers should include CLI name in parentheses
6. Browser/a11y steps must include headless flags
7. Env vars ending with `?` are optional and silently skipped if missing

## Result Semantics

| Overall Status | Condition | Exit Code |
|---------------|-----------|-----------|
| PASS | All steps pass | 0 |
| FAIL | Any step fails (non-zero exit) | 1 |
| PARTIAL | No fails, but some skipped | 2 |
