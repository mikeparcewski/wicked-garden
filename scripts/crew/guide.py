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
import re
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
# Phase + archetype-aware filtering (Issue #725 reframe)
# ---------------------------------------------------------------------------
#
# Each command may declare two relevance fields in its YAML frontmatter:
#
#     phase_relevance: ["build", "review"]      # crew phases this command fits
#     archetype_relevance: ["code-repo", ...]   # archetypes this command fits
#
# The wildcard ``["*"]`` matches every value. Missing frontmatter does not drop
# a command from the result — it's annotated with ``"missing-relevance"`` so
# the gap surfaces instead of silently filtering useful commands away. A
# wg-check lint warns on missing fields (warn-only this release; flips to deny
# after the bulk-pass PR — see ``scripts/wg/check_relevance_frontmatter.py``).
#
# The bootstrap entry-point set is the union of commands tagged with
# ``"bootstrap"`` in ``phase_relevance``. It's surfaced when no active crew
# project exists, replacing the hand-curated "starter list" the issue
# originally proposed.

WILDCARD: str = "*"
BOOTSTRAP_PHASE: str = "bootstrap"
MISSING_RELEVANCE_ANNOTATION: str = "missing-relevance"


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
# Frontmatter scanner + relevance filters (Issue #725)
# ---------------------------------------------------------------------------

# Match commands/{domain}/{name}.md or commands/{name}.md and emit a
# colon-namespaced id. Frontmatter parsing is intentionally tiny and stdlib —
# the canonical pattern lives in hooks/scripts/pre_tool.py::_parse_frontmatter
# but it doesn't decode list values, which we need here.

_FRONTMATTER_BLOCK = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_INLINE_LIST = re.compile(r"\[(.*?)\]")
_QUOTED_TOKEN = re.compile(r"""['"]([^'"]+)['"]|([^,\s'"]+)""")


def _parse_inline_list(raw: str) -> list[str]:
    """Parse a YAML inline list like ``["a", "b", c]`` to ``["a", "b", "c"]``.

    Returns ``[]`` if the value isn't an inline list. Multiline list syntax
    (`- item\n- item`) is intentionally not supported here — relevance fields
    are meant to be short and inline so they stay readable in frontmatter.
    """
    m = _INLINE_LIST.match(raw.strip())
    if not m:
        return []
    body = m.group(1)
    out: list[str] = []
    for tok in _QUOTED_TOKEN.finditer(body):
        value = tok.group(1) if tok.group(1) is not None else tok.group(2)
        if value:
            out.append(value.strip())
    return out


def _parse_frontmatter_with_lists(text: str) -> dict:
    """Frontmatter parser that understands inline-list values.

    Returns a dict where scalar fields stay as strings and inline-list fields
    become ``list[str]``. Missing frontmatter returns an empty dict.
    """
    out: dict = {}
    m = _FRONTMATTER_BLOCK.match(text)
    if not m:
        return out
    block = m.group(1)
    for line in block.splitlines():
        kv = re.match(r"^([\w][\w_-]*):\s*(.*)$", line)
        if not kv:
            continue
        key, raw = kv.group(1), kv.group(2).strip()
        if raw.startswith("["):
            out[key] = _parse_inline_list(raw)
        else:
            # Strip surrounding quotes for scalar string values.
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
                raw = raw[1:-1]
            out[key] = raw
    return out


def _command_id_from_path(path: Path, commands_root: Path) -> str:
    """Build the colon-namespaced id from a commands/**.md path.

    ``commands/setup.md`` → ``wicked-garden:setup``
    ``commands/crew/start.md`` → ``wicked-garden:crew:start``
    """
    rel = path.relative_to(commands_root).with_suffix("")
    return ":".join(("wicked-garden",) + rel.parts)


def read_command_metadata(commands_dir: Path) -> list[dict]:
    """Walk ``commands/**/*.md`` and return per-command metadata dicts.

    Each entry has:
        id: ``wicked-garden:domain:name`` (or ``wicked-garden:name`` at root)
        path: absolute path to the .md file
        description: scalar description string (empty if missing)
        phase_relevance: list[str] | None (None when the field is absent)
        archetype_relevance: list[str] | None (None when the field is absent)

    The function never raises on individual file errors — bad frontmatter or
    unreadable files are skipped, which matches the read-only inspector
    contract of guide.py.
    """
    commands_dir = Path(commands_dir)
    if not commands_dir.is_dir():
        return []

    out: list[dict] = []
    for md in sorted(commands_dir.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter_with_lists(text)
        out.append(
            {
                "id": _command_id_from_path(md, commands_dir),
                "path": str(md),
                "description": fm.get("description", "") or "",
                "phase_relevance": (
                    fm["phase_relevance"]
                    if isinstance(fm.get("phase_relevance"), list)
                    else None
                ),
                "archetype_relevance": (
                    fm["archetype_relevance"]
                    if isinstance(fm.get("archetype_relevance"), list)
                    else None
                ),
            }
        )
    return out


def _matches_value(declared: list[str] | None, target: str) -> tuple[bool, bool]:
    """Return (included, missing) for a single command.

    ``included``: True if the declared list matches ``target`` OR is wildcard.
                  Also True when declared is None (so missing frontmatter
                  doesn't silently drop the command — see annotation contract).
    ``missing``:  True when the field is absent (declared is None). Lets
                  callers attach a ``missing-relevance`` annotation instead of
                  silently letting the command through unflagged.
    """
    if declared is None:
        return True, True
    if not declared:
        return False, False
    if WILDCARD in declared:
        return True, False
    return target in declared, False


def filter_by_phase(commands: list[dict], phase: str) -> list[dict]:
    """Return commands relevant to ``phase`` (wildcard + missing both pass).

    Each returned dict is a shallow copy — callers may add an
    ``annotations`` field (list[str]) without mutating the original record.
    """
    out: list[dict] = []
    for cmd in commands:
        included, missing = _matches_value(cmd.get("phase_relevance"), phase)
        if not included:
            continue
        record = dict(cmd)
        if missing:
            existing = list(record.get("annotations") or [])
            if MISSING_RELEVANCE_ANNOTATION not in existing:
                existing.append(MISSING_RELEVANCE_ANNOTATION)
            record["annotations"] = existing
        out.append(record)
    return out


def filter_by_archetype(commands: list[dict], archetype: str) -> list[dict]:
    """Return commands relevant to ``archetype`` (wildcard + missing both pass)."""
    out: list[dict] = []
    for cmd in commands:
        included, missing = _matches_value(cmd.get("archetype_relevance"), archetype)
        if not included:
            continue
        record = dict(cmd)
        if missing:
            existing = list(record.get("annotations") or [])
            if MISSING_RELEVANCE_ANNOTATION not in existing:
                existing.append(MISSING_RELEVANCE_ANNOTATION)
            record["annotations"] = existing
        out.append(record)
    return out


def filter_for_context(
    commands: list[dict],
    *,
    phase: str | None,
    archetype: str | None,
) -> list[dict]:
    """Combined phase × archetype filter.

    Either filter is skipped when the corresponding argument is None — this is
    the bootstrap path where archetype hasn't been picked yet. ``annotations``
    accumulates across both filters when a command is missing both fields.
    """
    if phase is None and archetype is None:
        return [dict(c) for c in commands]
    result = list(commands)
    if phase is not None:
        result = filter_by_phase(result, phase)
    if archetype is not None:
        result = filter_by_archetype(result, archetype)
    return result


def bootstrap_entry_points(commands: list[dict]) -> list[dict]:
    """Return the entry-point set: commands whose phase_relevance includes
    ``"bootstrap"``.

    This replaces the hand-curated starter list the original issue proposed.
    The set is derived from frontmatter, not a separate JSON manifest, so the
    catalog stays the single source of truth.
    """
    out: list[dict] = []
    for cmd in commands:
        phases = cmd.get("phase_relevance")
        if isinstance(phases, list) and BOOTSTRAP_PHASE in phases:
            out.append(dict(cmd))
    return out


# ---------------------------------------------------------------------------
# Active project context (DomainStore-backed, hook-mode safe)
# ---------------------------------------------------------------------------

def read_active_project_context() -> dict | None:
    """Return ``{"archetype": ..., "current_phase": ...}`` for the active
    crew project, or ``None`` when no project is active in this workspace.

    Mirrors the workspace-scoped lookup used by
    ``hooks/scripts/pre_tool.py::_find_active_crew_project`` so guide and
    pre_tool agree on which project counts as "active". DomainStore is opened
    in ``hook_mode=True`` so this can be called from hot paths without
    triggering integration discovery side-effects.
    """
    workspace = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
    try:
        from _domain_store import DomainStore  # noqa: WPS433 — local import keeps cold start cheap
        ds = DomainStore("wicked-crew", hook_mode=True)
        projects = ds.list("projects") or []
    except Exception:
        return None

    for project in sorted(
        projects,
        key=lambda x: x.get("updated_at", x.get("created_at", "")),
        reverse=True,
    ):
        if project.get("archived"):
            continue
        if workspace and project.get("workspace", "") != workspace:
            continue
        phase = project.get("current_phase", "")
        if phase and phase not in ("complete", "done", ""):
            archetype = project.get("archetype")
            if not archetype:
                metadata = project.get("metadata") or {}
                archetype = metadata.get("archetype")
            return {
                "archetype": archetype,
                "current_phase": phase,
                "project_name": project.get("name", ""),
            }
    return None


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
