---
description: Show memory statistics
argument-hint: ""
---

# /wicked-garden:mem:stats

Show memory statistics from the brain API.

## Execution

### Step 1: Get memory stats from brain

```bash
curl -s -X POST http://localhost:{port}/api \
  -H "Content-Type: application/json" \
  -d '{"action":"memory_stats","params":{}}'
```

Read the port from `~/.wicked-brain/_meta/config.json` (`server_port` field).

### Step 2: Display

Show the memory breakdown:
- **By tier**: working / episodic / semantic counts
- **By type**: episodic / decision / procedural / preference / gotcha / discovery counts
- **By age**: recent (< 7d) / active (7-30d) / aging (30-90d) / stale (> 90d)
- **Total memories**

If brain API is unreachable, suggest starting the server.
