---
description: Run contract assertions against plugin subprocess outputs
---

# /wicked-garden:platform:assert

Run contract assertions to validate that plugin scripts return data matching their declared schemas.

Instructions:
- Parse arguments: `--plugin {name}` for single plugin, `--json` for machine-readable
- Run the assertion script inline:
  ```bash
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/assert_contracts.py {args}
  ```
- Display results: pass/fail per script, violation details for failures
- Note: schemas must exist in `schemas/{plugin}/{script}.json` before assertions can run
