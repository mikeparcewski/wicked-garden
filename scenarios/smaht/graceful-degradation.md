---
name: graceful-degradation
title: Graceful Degradation
description: wicked-smaht works standalone without any wicked-garden dependencies
type: architecture
difficulty: basic
estimated_minutes: 4
---

# Graceful Degradation

Test that wicked-smaht works independently without requiring other wicked-garden plugins.

## Setup

Simulate a minimal installation where only wicked-smaht is available.

```bash
# Check which wicked-garden plugins are installed
ls "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json"
```

## Steps

1. **Start session with minimal plugins**

   Even without wicked-mem, wicked-jam, wicked-kanban, wicked-search, or wicked-crew:
   ```
   Hello, I'm working on a new feature.
   ```

   **Expected**: Session starts successfully. Adapters for missing plugins return empty results (not errors).

2. **Verify session creation**
   ```bash
   ls ~/.something-wicked/wicked-garden/local/wicked-smaht/sessions/
   ```
   Session directory should exist.

3. **Check adapter failures are silent**

   The hook output should NOT show errors for missing plugins:
   ```
   # Good: "wicked-mem: skipped (not found)"
   # Bad:  "Error: wicked-mem not installed"
   ```

4. **Test fact extraction (works standalone)**
   ```
   Let's use PostgreSQL for the database. I found that the connection pooling was misconfigured.
   ```

   Facts should be extracted even without wicked-mem:
   ```bash
   cat ~/.something-wicked/wicked-garden/local/wicked-smaht/sessions/*/facts.jsonl
   ```

5. **Test lane tracking (works standalone)**
   ```
   Switch to planning the API design.
   ```

   Lanes should be created:
   ```bash
   cat ~/.something-wicked/wicked-garden/local/wicked-smaht/sessions/*/lanes.jsonl
   ```

6. **Verify no stack traces**

   The Claude terminal should be clean - no Python tracebacks or error messages from missing dependencies.

## Expected Outcome

- Session management works without external plugins
- Fact extraction works locally (JSONL storage)
- Lane tracking works locally
- Missing adapters return empty results, not exceptions
- Hook execution completes successfully

## Adapter Behavior

| Plugin | If Installed | If Missing |
|--------|--------------|------------|
| wicked-mem | Query memories, promote facts | Skip, session-only facts |
| wicked-jam | Query brainstorm sessions | Skip |
| wicked-kanban | Query active tasks | Skip |
| wicked-search | Query code/docs index | Skip |
| wicked-crew | Query project phase | Skip |

## Code Patterns

Each adapter follows the same pattern:

```python
def query(prompt):
    script_path = find_plugin_script("wicked-mem")
    if not script_path:
        return []  # Graceful return, not exception

    try:
        result = subprocess.run(...)
    except subprocess.TimeoutExpired:
        return []  # Timeout handled gracefully
    except Exception as e:
        print(f"Warning: {e}", file=sys.stderr)
        return []  # Other errors handled gracefully
```

## Success Criteria

- [ ] Session starts without wicked-mem installed
- [ ] Session starts without wicked-kanban installed
- [ ] Facts extracted to local JSONL (no wicked-mem needed)
- [ ] Lanes tracked locally
- [ ] No error messages in Claude terminal
- [ ] Hook execution completes (exit code 0)

## Value Demonstrated

Plugin ecosystems often have dependency hell - "install A, which requires B, which requires C..."

wicked-smaht's graceful degradation:
1. **Works out of the box** - Just install wicked-smaht, get immediate value
2. **Progressive enhancement** - Each plugin you add provides more context
3. **No hard dependencies** - Missing plugins are skipped, not errors
4. **Stable operation** - Timeouts and failures don't crash the session
5. **Clear warnings** - Users know what's skipped (stderr), not confused

This makes wicked-smaht safe to install even in minimal environments.
