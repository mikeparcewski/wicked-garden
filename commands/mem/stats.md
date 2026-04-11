---
description: Show memory statistics
argument-hint: ""
---

# /wicked-garden:mem:stats

Show memory statistics from the brain API.

## Execution

### Step 1: Get memory stats from brain

Invoke the brain stats skill:

```
Skill(skill="wicked-brain-stats", args="")
```

If `wicked-brain-stats` is unavailable, fall back to reading the port via Python and calling the API:

```python
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/_brain_port.py
```

Then call:
```
POST http://localhost:{port}/api
{"action":"memory_stats","params":{}}
```

### Step 2: Display

Show the memory breakdown:
- **By tier**: working / episodic / semantic counts
- **By type**: episodic / decision / procedural / preference / gotcha / discovery counts
- **By age**: recent (< 7d) / active (7-30d) / aging (30-90d) / stale (> 90d)
- **Total memories**

If brain API is unreachable, suggest starting the server with `npx wicked-brain-server`.
