#!/usr/bin/env python3
"""
crew:guide — context-aware command discovery inspector.

Inspects the current workspace state and returns a ranked list of
"what to do next" suggestions, each with the exact slash command and a
one-line rationale.

Signals inspected (priority order):
  1. Open CONDITIONAL gate (unresolved conditions-manifest.json)
  2. Active project on stalled phase (no advancement > STALE_HOURS hours)
  3. Uncommitted work in git (staged or unstaged changes)
  4. No active crew project
  5. Brain context nudge (wicked-brain reachable — surface relevant context)

Output: JSON list of up to MAX_SUGGESTIONS suggestion dicts.

This module is read-only — it never writes state.

R1: no dead code.
R3: all constants named.
R4: no swallowed errors — each probe is isolated and returns empty list on failure.
R5: subprocess calls have explicit timeouts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Resolve scripts/ root so we can import sibling modules regardless of cwd.
_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from _brain_port import resolve_port as _resolve_brain_port  # noqa: E402

# ---------------------------------------------------------------------------
# Constants  (R3)
# ---------------------------------------------------------------------------

MAX_SUGGESTIONS: int = 5
STALE_HOURS: float = 4.0
_CREW_PY = Path(__file__).resolve().parent / "crew.py"
_PYTHON_SH = Path(__file__).resolve().parents[1] / "_python.sh"

_PHASE_ADVANCE_CMD = "/wicked-garden:crew:execute"
_GATE_CMD = "/wicked-garden:crew:gate"
_START_CMD = "/wicked-garden:crew:start <description>"


# ---------------------------------------------------------------------------
# Python / subprocess helper
# ---------------------------------------------------------------------------

def _python_exe() -> str:
    """Return the best Python executable to use — shim first, fallback to current."""
    shim = str(_PYTHON_SH)
    if os.path.exists(shim):
        return shim
    return sys.executable


def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a subprocess, returning (returncode, stdout, stderr).

    Never raises — returns (-1, "", str(exc)) on unexpected errors.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except (OSError, FileNotFoundError) as exc:
        return -1, "", str(exc)


# ---------------------------------------------------------------------------
# Signal probes  (each returns a list[dict], empty if no signal found)
# ---------------------------------------------------------------------------

def _probe_open_conditions(project: dict, project_dir: str | None) -> list[dict]:
    """Signal 1: open CONDITIONAL gate with unresolved conditions.

    Scans all phase directories under the project dir for a
    conditions-manifest.json that still has unverified conditions.
    """
    if not project_dir:
        return []
    base = Path(project_dir) / "phases"
    if not base.is_dir():
        return []
    blocking_phases: list[str] = []
    try:
        for phase_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            manifest = phase_dir / "conditions-manifest.json"
            if not manifest.is_file():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            conditions = data.get("conditions", [])
            unresolved = [c for c in conditions if not c.get("verified", False)]
            if unresolved:
                blocking_phases.append(phase_dir.name)
    except OSError:
        return []

    if not blocking_phases:
        return []

    phases_str = ", ".join(blocking_phases)
    return [
        {
            "rank": 1,
            "command": f"{_GATE_CMD}",
            "rationale": (
                f"Open CONDITIONAL gate with unresolved conditions in phase(s): "
                f"{phases_str} — review and clear before advancing."
            ),
        }
    ]


def _probe_stale_phase(project: dict, project_dir: str | None) -> list[dict]:
    """Signal 2: active project whose current phase hasn't advanced in STALE_HOURS.

    Uses `updated_at` from the project record.  If the field is missing or
    cannot be parsed, the probe returns empty (fail-open, not noisy).
    """
    updated_at_raw = project.get("updated_at") or project.get("created_at")
    if not updated_at_raw:
        return []

    try:
        # Accept ISO-8601 with or without timezone info.
        # `Z` → `+00:00` so fromisoformat handles UTC suffix on Python 3.7+.
        # Any explicit offset (`+05:30`, `-04:00`) is preserved by fromisoformat
        # — do NOT strip it. Naive timestamps (no offset, no Z) fail open by
        # being labelled UTC, matching the pre-fix assumption for legacy data.
        raw = updated_at_raw.replace("Z", "+00:00")
        updated = datetime.fromisoformat(raw)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_hours = (now - updated).total_seconds() / 3600.0
    except (ValueError, AttributeError):
        return []

    if age_hours < STALE_HOURS:
        return []

    phase = project.get("current_phase", "unknown")
    age_display = f"{age_hours:.0f}h"
    return [
        {
            "rank": 2,
            "command": _PHASE_ADVANCE_CMD,
            "rationale": (
                f"Project '{project.get('name', '?')}' has been on phase '{phase}' "
                f"for {age_display} — run execute to advance."
            ),
        }
    ]


def _probe_uncommitted_work(cwd: str | None = None) -> list[dict]:
    """Signal 3: uncommitted changes in the git working tree.

    Runs `git status --porcelain` — fast, read-only.  Returns empty if
    not in a git repo or no changes found.
    """
    if cwd is None:
        cwd = os.getcwd()
    rc, stdout, _ = _run(["git", "-C", cwd, "status", "--porcelain"], timeout=5)
    if rc != 0 or not stdout:
        return []
    line_count = len([l for l in stdout.splitlines() if l.strip()])
    if line_count == 0:
        return []
    return [
        {
            "rank": 3,
            "command": "git add -p && git commit",
            "rationale": (
                f"{line_count} file(s) with uncommitted changes — commit or stash "
                "before advancing the crew phase."
            ),
        }
    ]


def _probe_no_active_project() -> list[dict]:
    """Signal 4 (fallback): no active crew project exists.

    This fires only when the active-project probe returned nothing.
    """
    return [
        {
            "rank": 4,
            "command": _START_CMD,
            "rationale": (
                "No active crew project found — start one with a description of "
                "the work you want to kick off."
            ),
        }
    ]


def _probe_brain_context() -> list[dict]:
    """Signal 5 (supplemental): suggest brain context grounding if brain server reachable.

    This is a lightweight, low-priority nudge.  We only emit it when the
    other high-priority signals didn't already fill the MAX_SUGGESTIONS budget.
    """
    try:
        import urllib.request
        # Note: _resolve_brain_port() returns the project-config port (4243 for
        # wicked-garden via ~/.wicked-brain/projects/wicked-garden/_meta/config.json).
        # Falls back to 4242 only when no env override AND no project/root config
        # match — an edge case for users invoking guide outside any wicked-brain
        # project. Old hardcoded 4243 was wrong for cross-project usage.
        port = _resolve_brain_port()
        url = f"http://localhost:{port}/api"
        body = json.dumps({"action": "health", "params": {}}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1) as resp:
            health = json.loads(resp.read())
        if not health.get("ok"):
            return []
    except Exception:
        return []

    return [
        {
            "rank": 5,
            # Use /wicked-brain:search — a real slash command. The previous
            # /wicked-brain:agent context form is not a dispatchable command
            # (wicked-brain:agent is invoked as a Skill, not a slash command).
            "command": "/wicked-brain:search \"<your current task>\"",
            "rationale": (
                "wicked-brain is running — surface relevant project context "
                "before starting a new task."
            ),
        }
    ]


# ---------------------------------------------------------------------------
# Active project fetch
# ---------------------------------------------------------------------------

def _find_active_project(workspace: str = "") -> dict:
    """Call crew.py find-active and return its parsed JSON output.

    Returns {"project": None, "project_dir": None} on any failure.
    """
    exe = _python_exe()
    cmd = [exe, str(_CREW_PY), "find-active", "--json"]
    if workspace:
        cmd += ["--workspace", workspace]
    rc, stdout, _ = _run(cmd, timeout=10)
    if rc != 0 or not stdout:
        return {"project": None, "project_dir": None}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"project": None, "project_dir": None}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_suggestions(workspace: str = "", cwd: str | None = None) -> list[dict]:
    """Assemble a ranked list of up to MAX_SUGGESTIONS suggestions.

    Probes run in priority order:
      1. Open CONDITIONAL gate (urgent — blocks phase advancement)
      2. Stale phase (active project stuck for STALE_HOURS hours)
      3. Uncommitted work (lose-work risk before phase advance)
      4. Brain context nudge (low-priority quality-of-life)
      5. No project fallback (only when nothing else applies)

    Returns list[dict] with keys: rank (int), command (str), rationale (str).
    """
    active = _find_active_project(workspace=workspace)
    project = active.get("project")
    project_dir = active.get("project_dir")

    suggestions: list[dict] = []

    if project:
        suggestions.extend(_probe_open_conditions(project, project_dir))
        suggestions.extend(_probe_stale_phase(project, project_dir))
        suggestions.extend(_probe_uncommitted_work(cwd=cwd))
        if len(suggestions) < MAX_SUGGESTIONS:
            suggestions.extend(_probe_brain_context())
    else:
        suggestions.extend(_probe_uncommitted_work(cwd=cwd))
        suggestions.extend(_probe_no_active_project())
        if len(suggestions) < MAX_SUGGESTIONS:
            suggestions.extend(_probe_brain_context())

    # Deduplicate by command (keep first occurrence), cap at MAX_SUGGESTIONS.
    seen: set[str] = set()
    deduped: list[dict] = []
    for s in suggestions:
        cmd = s.get("command", "")
        if cmd not in seen:
            seen.add(cmd)
            deduped.append(s)
        if len(deduped) >= MAX_SUGGESTIONS:
            break

    # Re-number ranks sequentially for clean output.
    for i, s in enumerate(deduped, start=1):
        s["rank"] = i

    return deduped


def format_output(suggestions: list[dict]) -> str:
    """Format suggestions as a numbered list for display."""
    if not suggestions:
        return "No suggestions — context is clear."
    lines = ["## What to do next\n"]
    for s in suggestions:
        lines.append(f"{s['rank']}. `{s['command']}`")
        lines.append(f"   {s['rationale']}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# CLI entry point (stdlib-only, no argparse required for simple use)
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    workspace_arg = ""
    if len(sys.argv) > 1 and sys.argv[1] not in ("--json",):
        workspace_arg = sys.argv[1]

    emit_json = "--json" in sys.argv

    data = build_suggestions(workspace=workspace_arg)

    if emit_json:
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        sys.stdout.write(format_output(data) + "\n")
