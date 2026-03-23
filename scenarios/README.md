# Acceptance Test Scenarios

This directory contains acceptance test scenarios for the wicked-garden plugin ecosystem. Each scenario is a markdown file with setup steps, executable commands, and success criteria.

## Running Scenarios

```bash
# Interactive selection
/wicked-garden:qe:run

# Specific scenario
/wicked-garden:qe:run 01-fresh-install

# List all scenarios
/wicked-garden:qe:list
```

## Scenario Format

Each scenario follows a standard structure with YAML frontmatter, setup steps, numbered executable steps, expected outcomes, and success criteria checkboxes. See any scenario file for the template.

## Data Access

All scenarios query plugin data via local storage (DomainStore + SQLite). Scripts are invoked through the `_run.py` wrapper:

```bash
python3 scripts/_run.py scripts/{domain}/{script}.py {args}
```
