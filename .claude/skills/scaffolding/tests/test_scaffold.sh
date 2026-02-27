#!/bin/bash
#
# Test script for scaffold tool (unified wicked-garden plugin)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
SCAFFOLD_SCRIPT="$PROJECT_ROOT/.claude/skills/scaffolding/scripts/scaffold.py"

echo "=== Testing Scaffold Tool ==="
echo

# Test 1: Skill scaffold
echo "Test 1: Skill scaffold"
python3 "$SCAFFOLD_SCRIPT" skill \
  --name test-skill \
  --domain crew \
  --description "Test skill" \
  --use-when "testing"

if [ ! -f "$PROJECT_ROOT/skills/crew/test-skill/SKILL.md" ]; then
  echo "FAIL: Skill not created at skills/crew/test-skill/SKILL.md"
  exit 1
fi

echo "PASS: Skill scaffold"
echo

# Test 2: Agent scaffold
echo "Test 2: Agent scaffold"
python3 "$SCAFFOLD_SCRIPT" agent \
  --name test-agent \
  --domain platform \
  --description "Test agent" \
  --tools "Read,Write"

if [ ! -f "$PROJECT_ROOT/agents/platform/test-agent.md" ]; then
  echo "FAIL: Agent not created at agents/platform/test-agent.md"
  exit 1
fi

echo "PASS: Agent scaffold"
echo

# Test 3: Command scaffold
echo "Test 3: Command scaffold"
python3 "$SCAFFOLD_SCRIPT" command \
  --name test-command \
  --domain engineering \
  --description "Test command"

if [ ! -f "$PROJECT_ROOT/commands/engineering/test-command.md" ]; then
  echo "FAIL: Command not created at commands/engineering/test-command.md"
  exit 1
fi

echo "PASS: Command scaffold"
echo

# Test 4: Hook scaffold
echo "Test 4: Hook scaffold"
python3 "$SCAFFOLD_SCRIPT" hook \
  --event PostToolUse \
  --script test-hook \
  --description "Test hook" \
  --matcher "Read"

if [ ! -f "$PROJECT_ROOT/hooks/scripts/test-hook.py" ]; then
  echo "FAIL: Hook script not created at hooks/scripts/test-hook.py"
  exit 1
fi

# Check hooks.json was updated
if ! grep -q "PostToolUse" "$PROJECT_ROOT/hooks/hooks.json"; then
  echo "FAIL: hooks.json not updated with PostToolUse entry"
  exit 1
fi

echo "PASS: Hook scaffold"
echo

# Test 5: Invalid domain rejection
echo "Test 5: Invalid domain rejection"
if python3 "$SCAFFOLD_SCRIPT" skill --name bad-skill --domain invalid-domain --description "Should fail" 2>/dev/null; then
  echo "FAIL: Should have rejected invalid domain"
  exit 1
fi

echo "PASS: Invalid domain rejection"
echo

# Cleanup
echo "Cleaning up..."
rm -rf "$PROJECT_ROOT/skills/crew/test-skill"
rm -f "$PROJECT_ROOT/agents/platform/test-agent.md"
rm -f "$PROJECT_ROOT/commands/engineering/test-command.md"
rm -f "$PROJECT_ROOT/hooks/scripts/test-hook.py"
echo "PASS: Cleanup complete"
echo

echo "=== All Tests Passed ==="
