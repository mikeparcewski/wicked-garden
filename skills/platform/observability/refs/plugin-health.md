# Plugin Health: Auth Retry Probe

Re-run the plugin readiness probes from bootstrap to check whether previously
unready plugins are now functional. Use after the user has authenticated a
CLI mid-session (the `--retry-auth` flow).

## 1. Run the bootstrap probe function directly

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

## 2. Report results

- If all ready: "All plugins authenticated and ready."
- If still unready: show each plugin, its error, and the fix command.
- Suggest: "Run the fix command in your terminal, then re-run this auth-retry
  probe (the observability skill's Health Probes pillar, `--retry-auth`)."
