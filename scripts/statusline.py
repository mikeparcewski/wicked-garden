#!/usr/bin/env python3
"""statusline.py — render wicked-garden's current work-mode as a Claude Code status line.

Claude Code runs a configured `statusLine` command every render and shows its
stdout at the bottom of the screen. This makes the *steering* visible: the
archetype the system detected for your work, the sticky session intent, the
active phase, and (when recorded) the latest gate verdict — so "what mode am I
in" and "did the gate re-derive clean" are always on screen instead of buried
in output that scrolls away.

It reads the per-session state wicked-garden already maintains
(`{TMPDIR}/wicked-garden-session-{CLAUDE_SESSION_ID}.json`, written by the
hooks) — it does NOT recompute anything. Output shape:

    🌱 wg │ build·migrate │ intent: feature │ phase: implement │ ⚖ PASS

**Contract:** this runs on every render, so it is fast (a single JSON read),
stdlib-only, cross-platform, and **fail-soft** — any error degrades to a
minimal `🌱 wg` line. It never raises, never blocks, never prints a traceback
into the status bar.

Enable it by pointing `statusLine` in settings.json at this script (see
docs/getting-started.md). Reads Claude Code's status JSON on stdin for the
session id; falls back to the `CLAUDE_SESSION_ID` env var.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

_PREFIX = "🌱 wg"
_SEP = " │ "
# Only surface archetypes the detector was reasonably sure about, so the line
# doesn't churn on every low-confidence near-match.
_MIN_SCORE = 0.40
_MAX_ARCHETYPES = 3


def _safe_session_id(raw: str | None) -> str | None:
    """Sanitize a session id the same way _session.py does (path-safe)."""
    if not raw:
        return None
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(raw))
    return safe or None


def _state_path(session_id: str) -> str:
    tmpdir = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return os.path.join(tmpdir, f"wicked-garden-session-{session_id}.json")


def _load_state(stdin_text: str) -> dict:
    """Locate and read the current session's state. Returns {} on any miss."""
    candidates = []
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
        # Claude Code status JSON carries the session id (key has varied across
        # versions — try the common spellings).
        for key in ("session_id", "sessionId", "session"):
            if isinstance(payload, dict) and payload.get(key):
                candidates.append(payload[key])
    except (json.JSONDecodeError, ValueError):
        pass
    candidates.append(os.environ.get("CLAUDE_SESSION_ID"))
    candidates.append("default")

    for raw in candidates:
        sid = _safe_session_id(raw)
        if not sid:
            continue
        path = _state_path(sid)
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return {}


def _archetype_segment(state: dict) -> str | None:
    items = state.get("archetypes_v11")
    if not isinstance(items, list) or not items:
        return None
    names = []
    for it in items[:_MAX_ARCHETYPES]:
        if not isinstance(it, dict):
            continue
        name = it.get("name")
        score = it.get("score")
        # Keep a name when it cleared the bar, or when score is absent (be
        # permissive rather than hide a detected shape).
        if name and (not isinstance(score, (int, float)) or score >= _MIN_SCORE):
            names.append(str(name))
    return "·".join(names) if names else None


def render(state: dict) -> str:
    """Pure: session-state dict -> status-line string. Always returns a line."""
    segments = [_PREFIX]

    arche = _archetype_segment(state)
    segments.append(arche if arche else "idle")

    intent = state.get("intent")
    if intent:
        segments.append(f"intent: {intent}")

    phase = state.get("last_approved_phase")
    if phase:
        segments.append(f"phase: {phase}")

    # Optional, forward-compatible: when a gate writes its latest verdict into
    # session state (`last_gate_verdict`), surface it. Absent today → omitted.
    verdict = state.get("last_gate_verdict")
    if verdict:
        mark = {"PASS": "⚖ PASS", "REJECT": "⚖ REJECT", "ERROR": "⚖ ERROR"}.get(
            str(verdict).upper(), f"⚖ {verdict}")
        segments.append(mark)

    return _SEP.join(segments)


def main() -> int:
    try:
        stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""
    except (OSError, ValueError):
        stdin_text = ""
    try:
        line = render(_load_state(stdin_text))
    except Exception:  # noqa: BLE001 — a status line must never crash the bar
        line = _PREFIX
    sys.stdout.write(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
