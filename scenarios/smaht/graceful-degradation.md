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

```bash
# Create a test session for degradation testing
SCEN_SESSION="test-degradation-$$"
echo "Session ID: $SCEN_SESSION"
echo "$SCEN_SESSION" > "${TMPDIR:-/tmp}/wicked-scenario-degrade-session"

# Ensure smaht session directory exists
mkdir -p "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
```

## Steps

### Step 1: Router handles prompts without errors

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-degrade-session")
cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py route "Hello, I'm working on a new feature." --session "$SCEN_SESSION" --json 2>&1
EXIT_CODE=$?
[ $EXIT_CODE -eq 0 ] || { echo "FAIL: orchestrator route failed with exit $EXIT_CODE"; exit 1; }
echo "PASS: orchestrator routes without errors"
```

**Expect**: Exit code 0, router classifies prompt without crashing

### Step 2: Verify session directory created

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-degrade-session")
SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
[ -d "$SMAHT_DIR" ] || { echo "FAIL: session directory not created"; exit 1; }
echo "PASS: session directory exists at $SMAHT_DIR"
```

**Expect**: Exit code 0, session directory exists

### Step 3: HistoryCondenser works standalone

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-degrade-session")
cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/history_condenser.py "$SCEN_SESSION" "Let's use PostgreSQL for the database." 2>&1
EXIT_CODE=$?
[ $EXIT_CODE -eq 0 ] || { echo "FAIL: condenser failed with exit $EXIT_CODE"; exit 1; }
echo "PASS: HistoryCondenser works standalone without external plugins"
```

**Expect**: Exit code 0, condenser processes turn independently

### Step 4: Orchestrator gather handles missing adapters gracefully

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-degrade-session")
# Gather should complete even if some adapters can't reach their targets
OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py gather "Switch to planning the API design." --session "$SCEN_SESSION" --json 2>&1)
EXIT_CODE=$?
echo "$OUTPUT" | tail -5
# Should not contain Python tracebacks
echo "$OUTPUT" | grep -c "Traceback" | { read count; [ "$count" -eq 0 ] || { echo "FAIL: stack traces in output"; exit 1; }; }
echo "PASS: orchestrator gather completed (exit code: $EXIT_CODE)"
```

**Expect**: Exit code 0, no stack traces in output

### Step 5: No stack traces from adapter failures

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-degrade-session")
OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py gather "Tell me about the authentication setup." --session "$SCEN_SESSION" 2>&1)
# Check for clean output — no Python tracebacks
if echo "$OUTPUT" | grep -q "Traceback"; then
  echo "FAIL: Python traceback found in output"
  echo "$OUTPUT" | grep -A 3 "Traceback"
  exit 1
fi
echo "PASS: no stack traces — adapters degrade gracefully"
```

**Expect**: Exit code 0, clean output without tracebacks

## Cleanup

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-degrade-session" 2>/dev/null)
if [ -n "$SCEN_SESSION" ]; then
  rm -rf "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
fi
rm -f "${TMPDIR:-/tmp}/wicked-scenario-degrade-session"
```

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
