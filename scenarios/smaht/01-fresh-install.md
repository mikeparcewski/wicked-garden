---
name: fresh-install
title: Fresh Installation and First Session
description: Validates plugin installation, hook execution, MCP configuration, and skill availability
type: integration
difficulty: basic
estimated_minutes: 8
---

# Fresh Installation and First Session

Tests the complete installation flow: hooks run silently on session start, context7 MCP server is configured, and all skills are accessible. wicked-garden has a deliberately quiet startup — no nag messages, no setup wizard. Its value is in what it configures and provides, not in what it announces.

## Setup

```bash
# Verify plugin root is available
if [ -z "${CLAUDE_PLUGIN_ROOT}" ]; then
  # Fall back to finding it in the cache
  PLUGIN_DIR=$(find "${HOME}/.claude/plugins/cache" -name "plugin.json" -path "*/wicked-garden/*" 2>/dev/null | head -1 | xargs dirname 2>/dev/null | xargs dirname 2>/dev/null)
  if [ -z "$PLUGIN_DIR" ]; then
    PLUGIN_DIR="."
  fi
else
  PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"
fi
echo "PLUGIN_DIR=$PLUGIN_DIR"
echo "$PLUGIN_DIR" > "${TMPDIR:-/tmp}/wicked-scenario-plugin-dir"
```

## Steps

### Step 1: Verify plugin.json exists and is valid

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-plugin-dir")
PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"
[ -f "$PLUGIN_JSON" ] || { echo "FAIL: plugin.json not found at $PLUGIN_JSON"; exit 1; }
python3 -c "import json; d=json.load(open('$PLUGIN_JSON')); print(f\"Plugin: {d['name']} v{d['version']}\"); assert d.get('name'), 'missing name'; assert d.get('version'), 'missing version'"
echo "PASS: plugin.json is valid"
```

**Expect**: Exit code 0, plugin.json contains name and version

### Step 2: Verify hooks.json exists and has SessionStart

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-plugin-dir")
HOOKS_JSON="$PLUGIN_DIR/hooks/hooks.json"
[ -f "$HOOKS_JSON" ] || { echo "FAIL: hooks.json not found"; exit 1; }
python3 -c "
import json
hooks = json.load(open('$HOOKS_JSON'))
hooks_data = hooks.get('hooks', {})
events = set()
for event_name, handlers in hooks_data.items():
    events.add(event_name)
print('Hook events:', sorted(events))
assert 'SessionStart' in events, 'SessionStart hook not found'
"
echo "PASS: SessionStart hook configured in hooks.json"
```

**Expect**: Exit code 0, hooks.json contains SessionStart hook

### Step 3: Verify SessionStart hook script executes without error

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-plugin-dir")
BOOTSTRAP="$PLUGIN_DIR/hooks/scripts/bootstrap.py"
[ -f "$BOOTSTRAP" ] || { echo "FAIL: bootstrap.py not found"; exit 1; }
echo '{"session_id": "test-fresh-install"}' | python3 "$BOOTSTRAP" 2>/dev/null
EXIT_CODE=$?
[ $EXIT_CODE -eq 0 ] || { echo "FAIL: bootstrap.py exited with $EXIT_CODE"; exit 1; }
echo "PASS: SessionStart hook script runs without errors"
```

**Expect**: Exit code 0, bootstrap hook executes cleanly

### Step 4: Verify root-level skills exist on disk

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-plugin-dir")
MISSING=0
for SKILL in runtime-exec wickedizer multi-model integration-discovery; do
  if [ -d "$PLUGIN_DIR/skills/$SKILL" ] || [ -f "$PLUGIN_DIR/skills/$SKILL/SKILL.md" ]; then
    echo "  Found: $SKILL"
  else
    echo "  MISSING: $SKILL"
    MISSING=$((MISSING+1))
  fi
done
[ $MISSING -eq 0 ] || { echo "FAIL: $MISSING root-level skills missing"; exit 1; }
echo "PASS: root-level skills present on disk"
```

**Expect**: Exit code 0, all expected skills exist

### Step 5: Verify command files exist for key domains

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-plugin-dir")
DOMAINS=(crew search mem kanban engineering platform)
MISSING=0
for DOMAIN in "${DOMAINS[@]}"; do
  CMD_COUNT=$(find "$PLUGIN_DIR/commands/$DOMAIN" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$CMD_COUNT" -gt 0 ]; then
    echo "  $DOMAIN: $CMD_COUNT commands"
  else
    echo "  MISSING: $DOMAIN (no commands)"
    MISSING=$((MISSING+1))
  fi
done
[ $MISSING -eq 0 ] || { echo "FAIL: $MISSING domains have no commands"; exit 1; }
echo "PASS: key domains have command files"
```

**Expect**: Exit code 0, all key domains have at least one command

### Step 6: Verify specialist.json is valid

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-plugin-dir")
SPEC_JSON="$PLUGIN_DIR/.claude-plugin/specialist.json"
[ -f "$SPEC_JSON" ] || { echo "FAIL: specialist.json not found"; exit 1; }
python3 -c "
import json
d = json.load(open('$SPEC_JSON'))
specs = d.get('specialists', [])
print(f'Specialists: {len(specs)}')
for s in specs:
    print(f\"  {s.get('name', '?')}: {s.get('role', '?')} ({len(s.get('personas', []))} personas)\")
assert len(specs) >= 4, f'Expected at least 4 specialists, got {len(specs)}'
"
echo "PASS: specialist.json valid with multiple specialists"
```

**Expect**: Exit code 0, at least 4 specialists defined

## Expected Outcome

- Plugin installs without errors
- context7 MCP server is configured (bundled MCP server)
- SessionStart hook fires and completes silently within 2 seconds
- Root-level skills are discoverable and load correctly
- Hooks fire silently during session lifecycle
- Subsequent sessions behave identically — no first-run vs. repeat-run difference in startup behavior

## Success Criteria

- [ ] Plugin installation completes successfully
- [ ] context7 MCP server configured in mcp.json with `@upstash/context7-mcp@latest`
- [ ] SessionStart hook fires without errors (no failure notification in Claude Code)
- [ ] Hook completes within 2 seconds (no timeout)
- [ ] No setup message, nag, or prompt displayed on session start
- [ ] Root-level skills discoverable via `/wicked-garden:help`: multi-model, integration-discovery, runtime-exec, wickedizer
- [ ] Skills load correctly when queried (frontmatter and content accessible)
- [ ] Hooks fire silently on session start with no error notifications

## Value Demonstrated

wicked-garden provides a **low-friction installation experience**: install once, get context7 MCP server configured automatically, and have specialized skills available immediately. The deliberate silence of the SessionStart hook respects the user's workflow — no onboarding interruptions, no setup wizards, just capability that's there when you need it.
