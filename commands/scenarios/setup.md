---
description: Install required CLI tools for running E2E test scenarios
---

# /wicked-garden:scenarios:setup

Install required CLI tools for running E2E test scenarios.

## Usage

```
/wicked-garden:scenarios:setup [--category api|browser|perf|infra|security|a11y]
```

## Instructions

### 1. Discover Tool Status

Use the prereq-doctor to check scenario tools by category:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/prereq_doctor.py check-category testing
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/prereq_doctor.py check-category security
```

Also check scenario-specific tools not in the prereq-doctor registry (playwright, agent-browser, curl) via the legacy discovery script:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/scenarios/cli_discovery.py curl playwright agent-browser
```

Merge results. Separate tools into **available** and **missing**.

If all tools are available, report success and exit:

```markdown
All scenario tools are installed. You're ready to run any scenario.
```

### 2. Filter by Category (optional)

If `--category` is specified, filter to only tools used by that category. Category-to-tool mapping:

| Category | Prereq-Doctor Tools | Legacy Tools |
|----------|-------------------|--------------|
| api | hurl | curl |
| browser | — | playwright, agent-browser |
| perf | hey, k6 | — |
| infra | trivy | — |
| security | semgrep | — |
| a11y | pa11y | — |

### 3. Show Missing Tools

Display a status table from the merged results:

```markdown
## Tool Status

| Tool | Category | Status | Install Command |
|------|----------|--------|-----------------|
| curl | api | Installed | - |
| hurl | api | Missing | `brew install hurl` |
| ... | ... | ... | ... |
```

### 4. Offer Installation

Use AskUserQuestion to let the user choose:

**Question**: "{N} tools are missing. Which would you like to install?"
**Options**:
- **Install all missing** — Run all install commands
- **Install by category** — Choose which categories to install
- **Show commands only** — Print install commands without running them
- **Skip** — Do nothing

### 5. Execute Installation

If the user chooses to install, run the install commands via Bash in order:

1. **brew** commands first (merged into single `brew install` call)
2. **npm** commands next
3. **pip** commands last
4. **other** commands (platform-specific) individually

After each group, report success/failure.

### 6. Verify Installation

Re-run prereq-doctor to confirm:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/prereq_doctor.py check-category testing
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/prereq_doctor.py check-category security
```

Display final status:

```markdown
## Setup Complete

**Before**: {old_count}/{total} tools available
**After**: {new_count}/{total} tools available

{If all installed: "All tools installed. Run `/wicked-garden:scenarios:list` to see available scenarios."}
{If some failed: "Some tools could not be installed. See errors above."}
```
