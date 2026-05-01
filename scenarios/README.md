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

### Frontmatter: `execution: manual`

Scenarios whose `## Steps` section consists entirely of `/wicked-garden:*` or `/wicked-testing:*` slash commands cannot be dispatched by a bash-only executor. These declare `execution: manual` in their frontmatter, which signals to `/wg-test` and `wicked-testing:execution` that the scenario needs a live Claude runtime to dispatch its slash commands. Such scenarios are reported as **MANUAL-ONLY** in summary tables — distinct from **SKIP** (tool missing) and **PASS/FAIL/PARTIAL** (actually executed). This keeps automation-coverage metrics honest.

If you are authoring a new scenario whose Steps are entirely slash commands, add `execution: manual` to the frontmatter so it doesn't inflate the SKIP count during automated sweeps.

## Data Access

All scenarios query plugin data via local storage (DomainStore + SQLite). Scripts are invoked through the cross-platform `_python.sh` shim and the `_run.py` wrapper:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/{domain}/{script}.py {args}
```

The shim resolves `python3`, `python`, or `py -3` based on what's available — bare `python3` is not present on Windows. See `skills/runtime-exec/SKILL.md` for the resolution chain.
