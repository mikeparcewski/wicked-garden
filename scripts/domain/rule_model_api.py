#!/usr/bin/env python3
"""Direct-API drop-in for the rule-extraction model boundary.

The harness talks to its model via an argv that reads the prompt on stdin and
prints the response on stdout (`claude -p` shape). Each CLI invocation pays
full agent bootstrap for what is a single completion; this adapter makes the
same one-shot call straight against the Anthropic API — no bootstrap, explicit
prompt caching, stdlib-only (urllib, no SDK).

Usage:
    export ANTHROPIC_API_KEY=...              # required
    export WICKED_RULE_MODEL_BIN="python3 /path/to/rule_model_api.py"
    # optional: WICKED_RULE_MODEL_API_MODEL (default claude-haiku-4-5-20251001)

The prompt's static instruction header (everything before the first
"--- UNIT 1 ---") is sent as a system block with cache_control so every call
shares the cached prefix; only the framed units vary.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

_API_URL = "https://api.anthropic.com/v1/messages"
_UNIT_BOUNDARY = "\n--- UNIT 1 ---\n"


def main() -> int:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("rule_model_api: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 78  # EX_CONFIG
    model = os.environ.get("WICKED_RULE_MODEL_API_MODEL", "claude-haiku-4-5-20251001")
    prompt = sys.stdin.read()

    cut = prompt.find(_UNIT_BOUNDARY)
    if cut > 0:
        system_part, user_part = prompt[:cut], prompt[cut:]
    else:  # unexpected shape — send everything as the user turn, no cached prefix
        system_part, user_part = "", prompt

    body: dict = {
        "model": model,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": user_part}],
    }
    if system_part:
        body["system"] = [{"type": "text", "text": system_part,
                           "cache_control": {"type": "ephemeral"}}]

    req = urllib.request.Request(
        _API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=170) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        # Mirror the CLI failure shape the harness classifies on: rate/overloaded/
        # auth markers in the message route to the infra abort, not the floor.
        print(f"rule_model_api: HTTP {e.code} — {detail}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"rule_model_api: network failure — {e}", file=sys.stderr)
        return 1

    text = "".join(b.get("text", "") for b in payload.get("content", [])
                   if isinstance(b, dict) and b.get("type") == "text")
    if not text.strip():
        print(f"rule_model_api: empty completion (stop_reason={payload.get('stop_reason')!r})",
              file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
