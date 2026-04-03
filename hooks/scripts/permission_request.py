#!/usr/bin/env python3
"""
PermissionRequest hook — wicked-garden intelligent auto-approval for known-safe operations.

Issue #336: Auto-approve known-safe operations to reduce permission prompt fatigue
during crew workflows and normal development.

Auto-approved operations (when in an active crew project or onboarded session):
  - Read: reading any file in the project directory
  - Grep/Glob: searching for files and patterns
  - Bash: running test commands (pytest, npm test, vitest, jest, cargo test, go test)
  - Bash: running lint/format commands (eslint, prettier, ruff, black, mypy)
  - Bash: running build commands (npm run build, cargo build, go build, make)
  - Bash: git status, git log, git diff (read-only git operations)

Never auto-approved (always require user confirmation):
  - Write/Edit to files outside the project
  - Bash commands that modify git state (push, reset, checkout, rebase)
  - Bash commands that install packages (npm install, pip install)
  - Any destructive operations (rm, delete, drop)

Always fails open — any unhandled exception returns {"decision": "ask"} (default behavior).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Add shared scripts directory to path
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Ops logger wrapper — fail-silent, never crashes the hook
# ---------------------------------------------------------------------------

def _log(domain, level, event, ok=True, ms=None, detail=None):
    """Ops logger — fail-silent, never crashes the hook."""
    try:
        from _logger import log
        log(domain, level, event, ok=ok, ms=ms, detail=detail)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Safe operation patterns
# ---------------------------------------------------------------------------

# Read-only git commands that are always safe
_SAFE_GIT_PATTERNS = [
    r"^git\s+status\b",
    r"^git\s+log\b",
    r"^git\s+diff\b",
    r"^git\s+show\b",
    r"^git\s+branch\b(?!.*-[dD])",  # branch without -d/-D
    r"^git\s+remote\s+-v\b",
    r"^git\s+tag\b(?!.*-d)",  # tag without -d
    r"^git\s+stash\s+list\b",
]

# Test runner commands
_SAFE_TEST_PATTERNS = [
    r"^(?:npx\s+)?(?:jest|vitest|mocha|playwright)\b",
    r"^(?:npm|yarn|pnpm)\s+(?:run\s+)?test\b",
    r"^pytest\b",
    r"^python3?\s+-m\s+pytest\b",
    r"^cargo\s+test\b",
    r"^go\s+test\b",
    r"^dotnet\s+test\b",
    r"^ruby\s+-Itest\b",
    r"^rspec\b",
    r"^make\s+test\b",
]

# Lint/format commands
_SAFE_LINT_PATTERNS = [
    r"^(?:npx\s+)?(?:eslint|prettier|biome)\b",
    r"^(?:npm|yarn|pnpm)\s+run\s+(?:lint|format|check)\b",
    r"^(?:ruff|black|isort|mypy|flake8|pylint)\b",
    r"^(?:python3?\s+-m\s+)?(?:ruff|black|isort|mypy|flake8|pylint)\b",
    r"^cargo\s+(?:clippy|fmt)\b",
    r"^go\s+vet\b",
    r"^golangci-lint\b",
    r"^rubocop\b",
    r"^make\s+(?:lint|check|format)\b",
]

# Build commands
_SAFE_BUILD_PATTERNS = [
    r"^(?:npm|yarn|pnpm)\s+run\s+build\b",
    r"^cargo\s+build\b",
    r"^go\s+build\b",
    r"^make(?:\s+(?!clean|install|deploy))?$",
    r"^dotnet\s+build\b",
    r"^tsc\b",
]

# Dangerous patterns that should NEVER be auto-approved
_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf?\b",
    r"\bgit\s+(?:push|reset|checkout|rebase|merge|cherry-pick)\b",
    r"\bgit\s+branch\s+-[dD]\b",
    r"\b(?:npm|yarn|pnpm|pip|pip3)\s+install\b",
    r"\bcurl\b.*\|\s*(?:sh|bash)\b",
    r"\bsudo\b",
    r"\bdrop\s+(?:table|database)\b",
    r"\bdelete\s+from\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bmkfs\b",
    r"\bformat\b",
]

# Compile all patterns
_SAFE_GIT_RE = [re.compile(p, re.IGNORECASE) for p in _SAFE_GIT_PATTERNS]
_SAFE_TEST_RE = [re.compile(p, re.IGNORECASE) for p in _SAFE_TEST_PATTERNS]
_SAFE_LINT_RE = [re.compile(p, re.IGNORECASE) for p in _SAFE_LINT_PATTERNS]
_SAFE_BUILD_RE = [re.compile(p, re.IGNORECASE) for p in _SAFE_BUILD_PATTERNS]
_DANGEROUS_RE = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS_PATTERNS]


def _is_safe_bash_command(command: str) -> bool:
    """Check if a bash command is known-safe for auto-approval."""
    cmd = command.strip()

    # First check: dangerous commands are never safe
    for pattern in _DANGEROUS_RE:
        if pattern.search(cmd):
            return False

    # Check safe patterns
    all_safe = _SAFE_GIT_RE + _SAFE_TEST_RE + _SAFE_LINT_RE + _SAFE_BUILD_RE
    for pattern in all_safe:
        if pattern.search(cmd):
            return True

    return False


def _is_project_file(file_path: str) -> bool:
    """Check if a file path is within the current project directory."""
    try:
        cwd = str(Path.cwd().resolve())
        resolved = str(Path(file_path).resolve())
        return resolved.startswith(cwd)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

def _evaluate_permission(payload: dict) -> str:
    """Evaluate a permission request and return 'allow', 'deny', or 'ask'.

    Returns 'ask' (defer to user) for anything uncertain.
    Returns 'allow' only for known-safe operations.
    Never returns 'deny' — that is too aggressive for auto-approval.
    """
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    # Read, Grep, Glob within the project are always safe
    if tool_name in ("Read", "Grep", "Glob"):
        # Check that target is within project
        target = tool_input.get("file_path", "") or tool_input.get("path", "")
        if not target or _is_project_file(target):
            return "allow"

    # Bash commands: check against safe patterns
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if command and _is_safe_bash_command(command):
            return "allow"

    # All other tools: defer to user
    return "ask"


def main():
    _t0 = time.monotonic()

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    try:
        tool_name = payload.get("tool_name", "")
        decision = _evaluate_permission(payload)

        _log("permission", "debug", "permission.evaluate",
             detail={"tool": tool_name, "decision": decision})

        if decision == "allow":
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "autoApprove": True,
                }
            }))
        else:
            # Return empty/default to defer to normal permission flow
            print(json.dumps({}))

    except Exception as e:
        print(f"[wicked-garden] permission_request error: {e}", file=sys.stderr)
        # Always fail open — defer to user on any error
        print(json.dumps({}))

    _log("permission", "debug", "hook.end",
         ms=int((time.monotonic() - _t0) * 1000))


if __name__ == "__main__":
    main()
