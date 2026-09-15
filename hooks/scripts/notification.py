#!/usr/bin/env python3
"""
Notification hook — wicked-garden context limit adaptation.

Issue #343: Detect context limit warnings and warn Claude.

When Claude Code emits notifications about approaching context limits,
this hook returns a systemMessage nudging Claude to:
  - Minimize context — keep only what the current step needs
  - Encourage delegation over inline execution
  - Log the context pressure event for observability

Also handles other notification types for general observability.

Always fails open — returns {"continue": true} on any error.
Runs async so it does not block the user.
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
# Context limit detection patterns
# ---------------------------------------------------------------------------

_CONTEXT_LIMIT_PATTERNS = [
    re.compile(r"context\s+(?:limit|window|length)", re.IGNORECASE),
    re.compile(r"(?:approaching|near(?:ing)?|reaching|exceed)\s+(?:the\s+)?(?:context|token)\s+(?:limit|maximum)", re.IGNORECASE),
    re.compile(r"token\s+(?:limit|budget|count)", re.IGNORECASE),
    re.compile(r"(?:running\s+)?(?:low|out)\s+(?:of\s+)?(?:context|tokens)", re.IGNORECASE),
    re.compile(r"compact(?:ion|ing)", re.IGNORECASE),
    re.compile(r"conversation\s+(?:too\s+)?long", re.IGNORECASE),
    re.compile(r"context_limit", re.IGNORECASE),
    re.compile(r"max_tokens", re.IGNORECASE),
]


def _is_context_limit_notification(payload: dict) -> bool:
    """Check if a notification is about context limits."""
    message = payload.get("message", "") or payload.get("text", "") or ""
    notification_type = payload.get("type", "") or ""

    # Direct type match
    if notification_type in ("context_limit", "compaction", "token_limit"):
        return True

    # Pattern match on message content
    for pattern in _CONTEXT_LIMIT_PATTERNS:
        if pattern.search(message):
            return True

    return False


# ---------------------------------------------------------------------------
# Handler: context limit adaptation
# ---------------------------------------------------------------------------

def _handle_context_limit(payload: dict) -> str:
    """Warn Claude when context limits are approaching.

    Returns a systemMessage with guidance for Claude (prefer delegation,
    keep responses concise, save critical context before compaction).
    """
    _log("notification", "warn", "context.limit_approaching",
         detail={"payload_type": payload.get("type", ""), "message": (payload.get("message", "") or "")[:100]})

    # Name the memory surface (estate memory.capture). Fail-open to the
    # same wording.
    try:
        from _context_backend import memory_directive_target
        _mem_target = memory_directive_target()
    except Exception:
        _mem_target = "the wicked-garden-mem skill (store action)"

    return json.dumps({
        "systemMessage": (
            "[Context Pressure] Context limit is approaching. Adapting behavior:\n"
            "1. Minimize context — keep only what the current step needs\n"
            "2. Prefer delegation to subagents over inline execution\n"
            "3. Keep responses concise — avoid large code dumps\n"
            "4. If in a crew project, consider completing the current phase before starting new work\n"
            f"5. Use {_mem_target} to save critical context before compaction"
        ),
        "continue": True,
    })


# ---------------------------------------------------------------------------
# Handler: general notification logging
# ---------------------------------------------------------------------------

def _handle_general_notification(payload: dict) -> str:
    """Log general notifications for observability."""
    notification_type = payload.get("type", "unknown")
    message = (payload.get("message", "") or payload.get("text", "") or "")[:200]

    _log("notification", "debug", f"notification.{notification_type}",
         detail={"message": message})

    return json.dumps({"continue": True})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _t0 = time.monotonic()

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    try:
        if _is_context_limit_notification(payload):
            result = _handle_context_limit(payload)
        else:
            result = _handle_general_notification(payload)

        _log("notification", "debug", "hook.end",
             ms=int((time.monotonic() - _t0) * 1000))
        print(result)

    except Exception as e:
        print(f"[wicked-garden] notification error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
