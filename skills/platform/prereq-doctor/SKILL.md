---
name: prereq-doctor
description: |
  Diagnose missing tools and dependencies, offer to install them.

  Use when: "command not found", "ModuleNotFoundError", "missing tool",
  "install dependency", "prereq check", "setup validation"
---

# Prereq Doctor

Diagnoses missing CLI tools and Python dependencies, offers to install them.

## When to Use

- PostToolUseFailure hook detects a missing-tool error pattern
- Setup needs to validate a selected integration (issue tracker, CLI tool)
- Any command fails with "command not found" or "ModuleNotFoundError"
- User asks to check or install prerequisites

## How It Works

1. **Diagnose**: Parse the error or tool name to identify what's missing
2. **Lookup**: Match against the known tool registry (see refs/tool-registry.md)
3. **Detect platform**: macOS (brew) vs Linux (apt/dnf) vs generic (pip/npm/cargo)
4. **Ask**: Present the install command and ask the user for permission
5. **Install**: Run the install command if approved
6. **Verify**: Confirm the tool is now available

## Quick Reference

```bash
# Diagnose a specific tool
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/platform/prereq_doctor.py" check <tool>

# Diagnose from an error message
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/platform/prereq_doctor.py" diagnose "<error_text>"

# Check all prerequisites for wicked-garden
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/platform/prereq_doctor.py" check-all
```

## Usage from Commands

Commands should NOT inline install logic. Instead:

```
Skill(skill="wicked-garden:platform:prereq-doctor", args="check gh")
```

Or let the PostToolUseFailure hook catch it automatically — just try to use the tool.

## Detailed Reference

- refs/tool-registry.md — Full tool→install mapping with platform variants
