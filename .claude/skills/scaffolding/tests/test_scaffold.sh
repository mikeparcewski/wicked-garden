#!/bin/bash
#
# Test script for scaffold tool
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SCAFFOLD_SCRIPT="$PROJECT_ROOT/tools/scaffold/scripts/scaffold.py"

echo "=== Testing Scaffold Tool ==="
echo

# Test 1: Plugin scaffold
echo "Test 1: Plugin scaffold with all components"
python3 "$SCAFFOLD_SCRIPT" plugin \
  --name wicked-test-plugin \
  --description "Test plugin for validation" \
  --with-commands \
  --with-skills \
  --with-agents \
  --with-hooks

if [ ! -d "$PROJECT_ROOT/plugins/wicked-test-plugin" ]; then
  echo "❌ Plugin directory not created"
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/.claude-plugin/plugin.json" ]; then
  echo "❌ plugin.json not created"
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/README.md" ]; then
  echo "❌ README.md not created"
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/.gitignore" ]; then
  echo "❌ .gitignore not created"
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/commands/example.md" ]; then
  echo "❌ Command not created"
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/skills/example-skill/SKILL.md" ]; then
  echo "❌ Skill not created"
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/agents/example-agent.md" ]; then
  echo "❌ Agent not created"
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/hooks/hooks.json" ]; then
  echo "❌ Hook not created"
  exit 1
fi

echo "✓ Plugin scaffold passed"
echo

# Test 2: Skill scaffold
echo "Test 2: Skill scaffold"
python3 "$SCAFFOLD_SCRIPT" skill \
  --name test-skill \
  --plugin wicked-test-plugin \
  --description "Test skill" \
  --use-when "testing"

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/skills/test-skill/SKILL.md" ]; then
  echo "❌ Skill not created"
  exit 1
fi

echo "✓ Skill scaffold passed"
echo

# Test 3: Agent scaffold
echo "Test 3: Agent scaffold"
python3 "$SCAFFOLD_SCRIPT" agent \
  --name test-agent \
  --plugin wicked-test-plugin \
  --description "Test agent" \
  --domain "testing" \
  --tools "Read,Write"

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/agents/test-agent.md" ]; then
  echo "❌ Agent not created"
  exit 1
fi

echo "✓ Agent scaffold passed"
echo

# Test 4: Hook scaffold
echo "Test 4: Hook scaffold"
python3 "$SCAFFOLD_SCRIPT" hook \
  --event PostToolUse \
  --plugin wicked-test-plugin \
  --script test-hook \
  --description "Test hook" \
  --matcher "Read"

if [ ! -f "$PROJECT_ROOT/plugins/wicked-test-plugin/hooks/scripts/test-hook.py" ]; then
  echo "❌ Hook script not created"
  exit 1
fi

# Check hooks.json was updated
if ! grep -q "PostToolUse" "$PROJECT_ROOT/plugins/wicked-test-plugin/hooks/hooks.json"; then
  echo "❌ hooks.json not updated"
  exit 1
fi

echo "✓ Hook scaffold passed"
echo

# Cleanup
echo "Cleaning up..."
rm -rf "$PROJECT_ROOT/plugins/wicked-test-plugin"
echo "✓ Cleanup complete"
echo

echo "=== All Tests Passed ==="
