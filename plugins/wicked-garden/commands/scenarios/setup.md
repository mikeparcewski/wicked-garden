---
description: Install required CLI tools for running E2E test scenarios
---

# /wicked-garden:scenarios-setup

Install required CLI tools for running E2E test scenarios.

## Usage

```
/wicked-garden:scenarios-setup [--category api|browser|perf|infra|security|a11y]
```

## Instructions

### 1. Discover Tool Status

Run CLI discovery to check all tools:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cli_discovery.py"
```

Parse the JSON output. Separate tools into **available** and **missing**.

If all tools are available, report success and exit:

```markdown
All scenario tools are installed. You're ready to run any scenario.
```

### 2. Filter by Category (optional)

If `--category` is specified, filter to only tools used by that category. Category-to-tool mapping:

| Category | Tools |
|----------|-------|
| api | curl, hurl |
| browser | playwright, agent-browser |
| perf | hey, k6 |
| infra | trivy |
| security | semgrep |
| a11y | pa11y |

### 3. Show Missing Tools

Display a status table:

```markdown
## Tool Status

| Tool | Category | Status | Install Command |
|------|----------|--------|-----------------|
| curl | api | Installed | - |
| hurl | api | Missing | `brew install hurl` |
| ... | ... | ... | ... |
```

### 4. Get Install Commands

Run the install suggestion mode:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cli_discovery.py" --install
```

This returns grouped install commands by package manager (brew, npm, pip).

### 5. Offer Installation

Use AskUserQuestion to let the user choose:

**Question**: "{N} tools are missing. Which would you like to install?"
**Options**:
- **Install all missing** — Run all install commands
- **Install by category** — Choose which categories to install
- **Show commands only** — Print install commands without running them
- **Skip** — Do nothing

### 6. Execute Installation

If the user chooses to install, run the install commands via Bash in order:

1. **brew** commands first (merged into single `brew install` call)
2. **npm** commands next
3. **pip** commands last
4. **other** commands (platform-specific) individually

After each group, report success/failure.

### 7. Verify Installation

Re-run discovery to confirm:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cli_discovery.py" --summary
```

Display final status:

```markdown
## Setup Complete

**Before**: {old_count}/{total} tools available
**After**: {new_count}/{total} tools available

{If all installed: "All tools installed. Run `/wicked-garden:scenarios-list` to see available scenarios."}
{If some failed: "Some tools could not be installed. See errors above."}
```
