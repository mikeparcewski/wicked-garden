#!/usr/bin/env python3
"""
PostToolUse hook — writes a JSONL trace record for every tool call.

Classifies events as:
  - hook_invocation: Bash commands matching python3 .*/hooks/scripts/.*\\.py
  - tool_use: everything else

For hook invocations, detects silent failures where the hook claims
ok/continue but stderr is non-empty or exit_code != 0.

Safety guarantees:
  SG-1  Fail-open: all errors caught, always exits 0 with {"continue": true}
  SG-2  Anti-recursion: skips if WICKED_TRACE_ACTIVE=1
  SG-3  Correlation: session_id, seq counter per session, schema_version
  SG-4  Atomic append: single write per invocation, records capped at 4KB
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Constants ──────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1"
STORAGE_ROOT = Path.home() / ".something-wicked" / "wicked-observability" / "traces"
HOOK_CMD_PATTERN = re.compile(r"python3 .*/hooks/scripts/.*\.py")
HOOK_SCRIPT_PATTERN = re.compile(r".*/hooks/scripts/(.*\.py)")
PLUGIN_PATTERN = re.compile(r"plugins/(wicked-[^/]+)/hooks/scripts/")
MAX_COMMAND_CHARS = 120
MAX_STDERR_BYTES = 512

# Patterns to redact from command_summary (secrets, tokens, keys)
SECRET_PATTERNS = re.compile(
    r'(?i)'
    r'(?:'
    r'(?:api[_-]?key|token|secret|password|credential)\s*[=:]\s*\S+'  # KEY=value
    r'|Bearer\s+\S+'  # Authorization: Bearer <token>
    r'|(?:sk|ghp|gho|ghs|github_pat|xox[bpas])[_-]\S+'  # Known token prefixes
    r')',
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def sanitize_session_id(raw: str) -> str:
    """Strip path traversal characters from session ID."""
    # Remove anything that could escape the traces directory
    return re.sub(r'[/\\.\x00]', '_', raw)[:128]


def get_session_id() -> str:
    """Return SESSION_ID env var, falling back to a timestamp-based string."""
    session_id = os.environ.get("SESSION_ID", "").strip()
    if session_id:
        return sanitize_session_id(session_id)
    # Stable fallback: round to the nearest minute so repeated calls in the
    # same session share the same file even without the env var.
    now = datetime.now(timezone.utc)
    return f"session-{now.strftime('%Y%m%dT%H%M')}"


def get_seq(session_id: str) -> int:
    """Read and increment the per-session sequence counter.

    Not truly atomic (no file locking), but safe in practice because
    hooks.json sets "async": false, ensuring sequential invocation.
    """
    seq_path = STORAGE_ROOT / f"{session_id}.seq"
    try:
        seq = int(seq_path.read_text().strip()) + 1
    except (FileNotFoundError, ValueError):
        seq = 0
    try:
        seq_path.write_text(str(seq))
    except OSError:
        pass
    return seq


def parse_hook_response(tool_response: dict) -> tuple[bool, str, int | None]:
    """
    Extract (claimed_ok, stderr, exit_code) from a tool_response dict.

    tool_response for Bash typically has:
      stdout, stderr, exit_code (or returncode)
    """
    stdout = tool_response.get("stdout", "") or ""
    stderr = tool_response.get("stderr", "") or ""
    # Use sentinel to distinguish 0 from missing (0 is falsy)
    raw_exit = tool_response.get("exit_code")
    if raw_exit is None:
        raw_exit = tool_response.get("returncode")

    # Normalise exit_code to int or None
    try:
        exit_code = int(raw_exit) if raw_exit is not None else None
    except (TypeError, ValueError):
        exit_code = None

    # The hook claims success if its stdout contains "ok": true or
    # "continue": true (accounting for any reasonable JSON formatting).
    claimed_ok = bool(
        re.search(r'"ok"\s*:\s*true', stdout)
        or re.search(r'"continue"\s*:\s*true', stdout)
    )

    return claimed_ok, stderr, exit_code


def detect_silent_failure(claimed_ok: bool, stderr: str, exit_code: int | None) -> bool:
    """Return True when a hook claims success but evidence suggests otherwise."""
    if not claimed_ok:
        return False
    has_stderr = bool(stderr and stderr.strip())
    bad_exit = exit_code is not None and exit_code != 0
    return has_stderr or bad_exit


def classify_event(tool_name: str, tool_input: dict) -> str:
    """Return 'hook_invocation' or 'tool_use'."""
    if tool_name != "Bash":
        return "tool_use"
    command = tool_input.get("command", "") or ""
    if HOOK_CMD_PATTERN.search(command):
        return "hook_invocation"
    return "tool_use"


def extract_hook_fields(command: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse hook_plugin, hook_script, hook_event from a Bash command string.

    hook_event is not directly available in the command; return None unless
    the HOOK_EVENT env var is set in the command string itself.
    """
    plugin_match = PLUGIN_PATTERN.search(command)
    hook_plugin = plugin_match.group(1) if plugin_match else None

    script_match = HOOK_SCRIPT_PATTERN.search(command)
    hook_script = script_match.group(1) if script_match else None

    # hook_event may be injected as HOOK_EVENT=... in the command
    event_match = re.search(r'HOOK_EVENT=["\']?([A-Za-z:]+)["\']?', command)
    hook_event = event_match.group(1) if event_match else None

    return hook_plugin, hook_script, hook_event


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    # SG-2: Anti-recursion guard
    if os.environ.get("WICKED_TRACE_ACTIVE") == "1":
        print(json.dumps({"continue": True}))
        return

    os.environ["WICKED_TRACE_ACTIVE"] = "1"

    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}
        tool_response = input_data.get("tool_response") or {}

        session_id = get_session_id()
        seq = get_seq(session_id)
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        event_type = classify_event(tool_name, tool_input)

        # Defaults
        exit_code: int | None = None
        stderr: str = ""
        silent_failure: bool = False
        hook_plugin: str | None = None
        hook_script: str | None = None
        hook_event: str | None = None
        command_summary: str | None = None

        if tool_name == "Bash":
            command = tool_input.get("command", "") or ""
            # Redact potential secrets before persisting
            redacted = SECRET_PATTERNS.sub("[REDACTED]", command)
            command_summary = redacted[:MAX_COMMAND_CHARS]

            if event_type == "hook_invocation":
                hook_plugin, hook_script, hook_event = extract_hook_fields(command)
                claimed_ok, raw_stderr, exit_code = parse_hook_response(tool_response)
                stderr = (raw_stderr or "")[:MAX_STDERR_BYTES]
                silent_failure = detect_silent_failure(claimed_ok, raw_stderr or "", exit_code)
            else:
                # Regular Bash: capture exit code and stderr if present
                stderr_raw = tool_response.get("stderr", "") or ""
                stderr = stderr_raw[:MAX_STDERR_BYTES]
                try:
                    raw_exit = tool_response.get("exit_code")
                    if raw_exit is None:
                        raw_exit = tool_response.get("returncode")
                    exit_code = int(raw_exit) if raw_exit is not None else None
                except (TypeError, ValueError):
                    exit_code = None

        record = {
            "schema_version": SCHEMA_VERSION,
            "ts": ts,
            "session_id": session_id,
            "seq": seq,
            "event_type": event_type,
            "tool_name": tool_name,
            "duration_ms": None,
            "exit_code": exit_code,
            "stderr": stderr,
            "silent_failure": silent_failure,
            "hook_plugin": hook_plugin,
            "hook_script": hook_script,
            "hook_event": hook_event,
            "command_summary": command_summary,
        }

        # SG-4: Ensure the record stays under 4KB (byte count for UTF-8 safety)
        line = json.dumps(record, separators=(",", ":"))
        if len(line.encode("utf-8")) > 4096:
            # Truncate the two largest free-text fields further
            record["command_summary"] = (command_summary or "")[:60]
            record["stderr"] = (stderr or "")[:128]
            line = json.dumps(record, separators=(",", ":"))
        # Hard cap: if still over 4KB, emit a minimal valid-JSON sentinel
        if len(line.encode("utf-8")) > 4096:
            line = json.dumps({
                "schema_version": SCHEMA_VERSION,
                "ts": ts,
                "session_id": session_id,
                "seq": seq,
                "event_type": event_type,
                "tool_name": tool_name[:64],
                "truncated": True,
            }, separators=(",", ":"))

        # Write atomically via append
        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        trace_path = STORAGE_ROOT / f"{session_id}.jsonl"
        with trace_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    except Exception:
        pass  # SG-1: never raise

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
