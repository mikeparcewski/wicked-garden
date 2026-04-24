---
description: |
  Use when diagnosing wicked-garden plugin health — runs readiness probes, views operational logs,
  queries hook traces, or adjusts log verbosity. Single entry point for all plugin-level diagnostics.
  NOT for distributed tracing (use platform:traces) or system-wide health (use platform:health).
argument-hint: "[--plugin name] [--retry-auth] [--json]"
---

# /wicked-garden:platform:health

Run health probes to validate ecosystem integrity.

## Arguments

- `--plugin {name}` — probe a single plugin
- `--retry-auth` — re-probe plugins that were flagged as unready at session start (use after authenticating a CLI mid-session)
- `--json` — machine-readable output

## Instructions

### Standard Health Probe

Run the health probe script inline (no agent delegation needed):
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/platform/observability/health_probe.py $ARGUMENTS
```
- Display results grouped by plugin, with severity icons
- Exit code: 0=healthy, 1=warnings, 2=failures
- Show path to latest.json for programmatic consumption

### Plugin Auth Retry (`--retry-auth`)

When the user passes `--retry-auth`, re-run the plugin readiness probes from bootstrap to check if previously unready plugins are now functional.

1. Run the bootstrap probe function directly:
   ```bash
   python3 -c "
   import sys, json, os
   sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'hooks', 'scripts'))
   from bootstrap import _probe_plugin_readiness, _suggest_auth_fix
   results = _probe_plugin_readiness()
   if not results:
       print(json.dumps({'status': 'all_ready', 'message': 'All installed plugins are ready.'}))
   else:
       out = []
       for r in results:
           fix = _suggest_auth_fix(r)
           out.append({**r, 'fix': fix})
       print(json.dumps({'status': 'unready', 'plugins': out}))
   "
   ```

2. Report results:
   - If all ready: "All plugins authenticated and ready."
   - If still unready: show each plugin, its error, and the fix command.
   - Suggest: "Run the fix command in your terminal, then retry with `/wicked-garden:platform:health --retry-auth`"
