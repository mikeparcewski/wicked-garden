---
description: Run contract assertions against plugin subprocess outputs
---

# /wicked-garden:observability-assert

Run contract assertions to validate that plugin scripts return data matching their declared schemas.

Instructions:
- Parse arguments: `--plugin {name}` for single plugin, `--json` for machine-readable
- Run the assertion script inline:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/assert_contracts.py" {args}
  ```
- Display results: pass/fail per script, violation details for failures
- Note: schemas must exist in `schemas/{plugin}/{script}.json` before assertions can run
