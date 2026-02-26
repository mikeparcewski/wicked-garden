---
description: Run health probes against all installed plugins
---

# /wicked-observability:health

Run health probes to validate ecosystem integrity.

Instructions:
- Parse arguments: `--plugin {name}` for single plugin, `--json` for machine-readable output
- Run the health probe script inline (no agent delegation needed):
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/health_probe.py" {args}
  ```
- Display the results: show violations grouped by plugin, with severity icons
- Report the exit code meaning: 0=healthy, 1=warnings, 2=failures
- Show path to latest.json for programmatic consumption
