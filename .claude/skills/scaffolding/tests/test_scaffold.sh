#!/bin/bash
#
# Test script for scaffold tool (unified wicked-garden plugin, skills-only)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
SCAFFOLD_SCRIPT="$PROJECT_ROOT/.claude/skills/scaffolding/scripts/scaffold.py"

echo "=== Testing Scaffold Tool (skills-only) ==="
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

# Test 2: Worker (context:fork) scaffold — the former "agent"
echo "Test 2: Worker scaffold (context:fork)"
python3 "$SCAFFOLD_SCRIPT" worker \
  --name test-worker \
  --domain platform \
  --description "Test worker" \
  --tools "Read,Write"

if [ ! -f "$PROJECT_ROOT/skills/platform-test-worker/SKILL.md" ]; then
  echo "FAIL: Worker skill not created at skills/platform-test-worker/SKILL.md"
  exit 1
fi

# It must declare context: fork and the dash-qualified name.
if ! grep -q "^context: fork$" "$PROJECT_ROOT/skills/platform-test-worker/SKILL.md"; then
  echo "FAIL: Worker skill missing 'context: fork' frontmatter"
  exit 1
fi
if ! grep -q "^name: wicked-garden-platform-test-worker$" "$PROJECT_ROOT/skills/platform-test-worker/SKILL.md"; then
  echo "FAIL: Worker skill missing dash-qualified 'name' frontmatter"
  exit 1
fi

echo "PASS: Worker scaffold"
echo

# Test 3: 'agent' back-compat alias still scaffolds a fork worker
echo "Test 3: Agent alias (back-compat) scaffolds a worker"
python3 "$SCAFFOLD_SCRIPT" agent \
  --name test-agent \
  --domain engineering \
  --description "Test agent alias" \
  --tools "Read"

if [ ! -f "$PROJECT_ROOT/skills/engineering-test-agent/SKILL.md" ]; then
  echo "FAIL: 'agent' alias did not create skills/engineering-test-agent/SKILL.md"
  exit 1
fi

echo "PASS: Agent alias"
echo

# Test 4: Command scaffold is RETIRED — must NOT create a commands/ file
echo "Test 4: Command scaffold is retired (no file written)"
python3 "$SCAFFOLD_SCRIPT" command \
  --name test-command \
  --domain engineering \
  --description "Test command"

if [ -e "$PROJECT_ROOT/commands" ]; then
  echo "FAIL: commands/ tree must not be re-created by the scaffolder"
  exit 1
fi

echo "PASS: Command retirement"
echo

# Test 5: Hook scaffold
echo "Test 5: Hook scaffold"
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

# Test 6: Invalid domain rejection
echo "Test 6: Invalid domain rejection"
if python3 "$SCAFFOLD_SCRIPT" skill --name bad-skill --domain invalid-domain --description "Should fail" 2>/dev/null; then
  echo "FAIL: Should have rejected invalid domain"
  exit 1
fi

echo "PASS: Invalid domain rejection"
echo

# Cleanup
echo "Cleaning up..."
rm -rf "$PROJECT_ROOT/skills/crew/test-skill"
rm -rf "$PROJECT_ROOT/skills/platform-test-worker"
rm -rf "$PROJECT_ROOT/skills/engineering-test-agent"
rm -f "$PROJECT_ROOT/hooks/scripts/test-hook.py"
echo "PASS: Cleanup complete"
echo

echo "=== All Tests Passed ==="
