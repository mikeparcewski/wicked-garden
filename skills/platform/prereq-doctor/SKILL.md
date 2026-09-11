---
name: wicked-garden-platform-prereq-doctor
description: |
  Diagnose missing tools and dependencies, offer to install them.

  Use when: "command not found", "ModuleNotFoundError", "missing tool",
  "install dependency", "prereq check", "setup validation"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# Prereq Doctor

Diagnoses missing CLI tools and Python dependencies, offers to install them.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.
Dispatch uses the Skill tool on Claude Code (a fresh forked context). On any other harness, open the named skill's `SKILL.md` from your skills catalog and carry out its instructions inline with the given args, then continue here.

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
wicked-garden run scripts/platform/prereq_doctor.py check <tool>

# Diagnose from an error message
wicked-garden run scripts/platform/prereq_doctor.py diagnose "<error_text>"

# Check all prerequisites for wicked-garden
wicked-garden run scripts/platform/prereq_doctor.py check-all
```

## Usage from Commands

Commands should NOT inline install logic. Instead:

```
Skill(skill="wicked-garden-platform-prereq-doctor", args="check gh")
```

Or let the PostToolUseFailure hook catch it automatically — just try to use the tool.

## Detailed Reference

- refs/tool-registry.md — Full tool→install mapping with platform variants
