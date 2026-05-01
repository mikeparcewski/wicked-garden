# Acceptance Test Scenarios

This directory contains acceptance test scenarios for the wicked-garden plugin ecosystem. Each scenario is a markdown file with setup steps, executable commands, and success criteria.

## Running Scenarios

```bash
# Run scenarios via wicked-testing or wg-test dev tool
/wg-test scenarios/crew

# Specific scenario
/wg-test scenarios/crew/01-end-to-end-feature

# All scenarios
/wg-test --all
```

## Scenario Format

Each scenario follows a standard structure with YAML frontmatter, setup steps, numbered executable steps, expected outcomes, and success criteria checkboxes. See any scenario file for the template.

## Data Access

All scenarios query plugin data via local storage (DomainStore + SQLite). Scripts are invoked through the cross-platform `_python.sh` shim and the `_run.py` wrapper:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/{domain}/{script}.py {args}
```

The shim resolves `python3`, `python`, or `py -3` based on what's available — bare `python3` is not present on Windows. See `skills/runtime-exec/SKILL.md` for the resolution chain.
