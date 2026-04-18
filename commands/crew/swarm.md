---
description: Check for quality crisis swarm trigger and recommend coalition response
---

# /wicked-garden:crew:swarm

Detect whether accumulated gate failures warrant a focused multi-specialist "Quality Coalition" response.

## Instructions

### 1. Find Active Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

If no active project found (`"project": null`), inform user and suggest `/wicked-garden:crew:start`.

### 2. Load Gate History

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_PLUGIN_ROOT}/scripts')))
from _domain_store import DomainStore
ds = DomainStore('wicked-crew')
project_name = '${project_name}'
gates = [g for g in ds.list('gates') if g.get('project') == project_name or g.get('project_id') == project_name]
print(json.dumps(gates, indent=2))
"
```

### 3. Run Swarm Detection

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_PLUGIN_ROOT}/scripts/crew')))
from swarm_trigger import detect_swarm_trigger
gate_results = json.loads(sys.stdin.read())
result = detect_swarm_trigger(gate_results)
if result:
    print(json.dumps(result, indent=2))
else:
    print(json.dumps({'triggered': False, 'message': 'No swarm trigger detected. Fewer than 3 BLOCK/REJECT findings in gate history.'}))
" <<< '${gate_results_json}'
```

### 4. Display Results

**If swarm NOT triggered:**

```markdown
## Swarm Status: No Crisis Detected

No quality coalition needed. Gate history shows fewer than 3 BLOCK/REJECT findings.

Current gate summary:
- Total gates: {count}
- Blocks/Rejects: {block_count}
- Passes: {pass_count}
```

**If swarm IS triggered:**

```markdown
## Quality Coalition Recommended

**Formation**: swarm
**Priority**: crisis
**Block count**: {block_count}

### Affected Phases
{list of phases with blocks}

### Recommended Coalition Specialists
{list of specialists with their focus areas}

### Reason
{human-readable explanation from detect_swarm_trigger}

### Next Steps
Confirm to concentrate these specialists on resolving the {block_count} blocking findings before other work proceeds.
```

Present the recommendation and ask the user to confirm before taking action. Do NOT automatically activate the coalition.
