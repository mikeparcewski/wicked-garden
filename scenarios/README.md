# Acceptance Test Scenarios

This directory contains acceptance test scenarios for the wicked-garden plugin ecosystem. Each scenario is a markdown file with setup steps, executable commands, and success criteria.

## Running Scenarios

```bash
# Interactive selection
/wicked-garden:scenarios:run

# Specific scenario
/wicked-garden:scenarios:run 01-fresh-install

# List all scenarios
/wicked-garden:scenarios:list
```

## Scenario Format

Each scenario follows a standard structure with YAML frontmatter, setup steps, numbered executable steps, expected outcomes, and success criteria checkboxes. See any scenario file for the template.

## Data Access

All scenarios that query plugin data use the Control Plane (CP) at `http://localhost:18889`:

```bash
python3 scripts/cp.py {domain} {source} {verb} [id] [--param value]
```

See `scripts/cp.py` for usage details and `scripts/_control_plane.py` for the client library.
