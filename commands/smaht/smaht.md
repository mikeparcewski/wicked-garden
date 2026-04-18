---
description: Gather intelligent context from wicked-brain + wicked-garden:search
argument-hint: "[query] [--deep]"
---

# /wicked-garden:smaht:smaht

Pull a context briefing from wicked-brain and wicked-garden:search. v6 replaced
the v5 push-model orchestrator (deleted in #428) — this command is now a thin
shim over brain + search.

## Usage

```
/smaht [query]           # Gather context (brain search)
/smaht --deep [query]    # Also query brain + search + active crew state
/smaht --sources         # Show available sources and their status
```

## Instructions

### 1. Parse Arguments

- `query` (optional): Focus query for context gathering
- `--deep`: Also pull active crew project state, recent events, and a codebase
  search slice — not just brain results
- `--sources`: Show source availability status instead of gathering

### 2. Gather Context

**Default (brain-only)**:

```
Skill(skill="wicked-brain:search", args={"query": "{query}", "limit": 10})
```

**Deep mode** — run these in parallel:

```
Skill(skill="wicked-brain:search", args={"query": "{query}", "limit": 20})
Skill(skill="wicked-garden:search:search", args={"query": "{query}", "limit": 10})
```

Then read active crew project state if one exists:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

### 3. Display Results

Show the context briefing in a clear format:

```markdown
## Wicked Smaht Context

**Mode**: default / deep
**Query**: {query}
**Sources**: brain{, search, crew}

### Brain Results
{bulleted list of top N brain hits with source_type, path, excerpt}

### Active Project (deep mode only)
{project name, phase, rigor_tier, last checkpoint}

### Search Hits (deep mode only)
{top code/doc symbols matching the query}
```

### 4. Sources Check

For `--sources`, don't gather — just report availability:

```bash
# Brain health
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import urllib.request, json, os
port = int(os.environ.get('WICKED_BRAIN_PORT', '4242'))
try:
    req = urllib.request.Request(f'http://localhost:{port}/api', data=json.dumps({'action':'ping'}).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=2) as r:
        print('brain: ok')
except Exception as e:
    print(f'brain: down ({e})')
"
```

## Examples

```
/smaht                     # Brain search on the current turn topic
/smaht authentication      # Brain search for "authentication"
/smaht --deep caching      # Brain + search + crew state for "caching"
/smaht --sources           # Check brain availability
```

## v5 → v6 Notes

The v5 HOT/FAST/SLOW/SYNTHESIZE router and its tiered adapter fan-out was
deleted in #428. Intent classification is no longer a thing — the caller asks
for what they need (brain, search, or both).
