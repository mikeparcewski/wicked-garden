---
description: Validate scenario file format and structure
---

# /wicked-garden:scenarios-check

Validate scenario file format and structure.

## Usage

```
/wicked-garden:scenarios-check <scenario-file>
/wicked-garden:scenarios-check scenarios/    # Check all scenarios in directory
```

## Instructions

### 1. Read Scenario File(s)

If argument is a directory, glob for `*.md` files. Otherwise read the single file.

### 2. Validate YAML Frontmatter

Required fields:
- `name` (string, kebab-case)
- `description` (string, non-empty)
- `category` (string, one of: api, browser, perf, infra, security, a11y)
- `tools` (object with `required` array)
- `difficulty` (string, one of: basic, intermediate, advanced)

Optional fields:
- `tools.optional` (array)
- `env` (array of strings)
- `timeout` (integer, positive)

### 3. Validate Tools

Check that all tools listed in `tools.required` and `tools.optional` are recognized MVP tools:
- curl, hurl, playwright, agent-browser, k6, hey, trivy, semgrep, pa11y

Warn (not error) for unrecognized tools — they may be post-MVP additions.

### 4. Validate Step Structure

Check the markdown body for:
- At least one `### Step N:` section
- Each step has at least one fenced code block
- Step headers include CLI name in parentheses: `### Step N: description (cli-name)`
- Code fence language hints are present (bash, hurl, javascript, etc.)

### 5. Validate Headless Flags

If category is `browser` or `a11y`, check that code blocks include headless flags:
- playwright: `--headed=false` or headless is default
- agent-browser: `--headless`
- pa11y: headless by default (no flag needed)

Warn if browser steps don't include explicit headless configuration.

### 6. Report Results

```markdown
## Validation: {filename}

**Status**: {VALID|WARNINGS|ERRORS}

### Errors
- {Line N}: {error description}

### Warnings
- {Line N}: {warning description}

### Summary
- Frontmatter: ✅ Valid
- Tools: ✅ All recognized
- Steps: ✅ {count} steps with code blocks
- Headless: ⚠️ Browser step missing headless flag
```
