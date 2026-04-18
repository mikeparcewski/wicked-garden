#!/usr/bin/env python3
"""
PreToolUse hook — wicked-garden unified pre-tool dispatcher.

Consolidates: crew pretool_taskcreate, crew pretool_planmode, mem block_memory_md,
              crew gate preflight (Bash approve calls).

Dispatches by tool_name from hook payload:
  TaskCreate    → validate event metadata envelope + crew initiative injection
  TaskUpdate    → validate event metadata envelope on updates
  EnterPlanMode → deny and redirect to crew workflow
  Write / Edit  → MEMORY.md write guard (AGENTS.md writes allowed, synced via PostToolUse)
  Bash          → crew gate preflight for phase_manager.py approve calls

Always fails open — any unhandled exception returns permissionDecision: "allow".
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
# Response helpers
# ---------------------------------------------------------------------------

def _allow(updated_input=None, system_message=None) -> str:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    if updated_input is not None:
        output["hookSpecificOutput"]["updatedInput"] = updated_input
    if system_message:
        output["systemMessage"] = system_message
    return json.dumps(output)


def _deny(reason: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })


# ---------------------------------------------------------------------------
# Handler: TaskCreate
# (inject crew initiative metadata, one-time crew suggestion)
# ---------------------------------------------------------------------------

def _find_active_crew_project():
    """Return (project_data_dict, project_name, initiative_name).

    Scoped to the current workspace (CLAUDE_PROJECT_NAME or cwd basename).
    Only returns projects whose ``workspace`` field matches.
    Uses DomainStore exclusively — operates local-only in hook mode.

    ``initiative_name`` is the project name (used to tag task metadata
    with a coarse grouping). Custom display names can be set via the
    optional ``initiative`` field on project.json.
    """
    workspace = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
    try:
        from _domain_store import DomainStore
        ds = DomainStore("wicked-crew", hook_mode=True)
        projects = ds.list("projects") or []
        for p in sorted(projects, key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True):
            if p.get("archived"):
                continue
            # Workspace scoping — skip projects from other workspaces
            if workspace and p.get("workspace", "") != workspace:
                continue
            phase = p.get("current_phase", "")
            if phase and phase not in ("complete", "done", ""):
                name = p.get("name", "")
                initiative = p.get("initiative") or name
                return p, name, initiative
    except Exception:
        pass

    return None, None, None


def _validate_event_metadata(tool_input: dict) -> "str | None":
    """Validate the metadata envelope on TaskCreate / TaskUpdate.

    Returns an error string on failure, or None on pass. Loads phases.json
    for phase enum validation. Fail-silent on import errors — an
    un-importable schema module must never break task creation.
    """
    try:
        from _event_schema import validate_metadata
    except Exception:
        return None  # schema module unavailable; fail open

    metadata = tool_input.get("metadata") or {}
    phases = set(_load_phases_config_hook().keys())
    return validate_metadata(metadata, valid_phases=phases or None)


def _task_metadata_mode() -> str:
    """``off`` | ``warn`` | ``strict`` — mirrors CREW_GATE_ENFORCEMENT convention."""
    mode = (os.environ.get("WG_TASK_METADATA") or "warn").strip().lower()
    return mode if mode in ("off", "warn", "strict") else "warn"


def _handle_task_create(tool_input: dict) -> str:
    """Inject crew initiative metadata and validate the event envelope."""
    mode = _task_metadata_mode()
    err = None if mode == "off" else _validate_event_metadata(tool_input)

    if err and mode == "strict":
        _log("pretool", "info", "task.metadata.blocked", detail={"reason": err})
        return _deny(f"[wicked-garden] task metadata invalid: {err}")

    _data, project_name, initiative_name = _find_active_crew_project()

    if project_name:
        metadata = tool_input.get("metadata") or {}
        if not metadata.get("initiative"):
            metadata["initiative"] = initiative_name
            tool_input["metadata"] = metadata
        system_message = None
        if err and mode == "warn":
            _log("pretool", "warn", "task.metadata.deprecated", detail={"reason": err})
            system_message = f"[wicked-garden] DEPRECATION: task metadata: {err}"
        return _allow(updated_input=tool_input, system_message=system_message)

    # No active project — show one-time suggestion via SessionState
    system_message = None
    if err and mode == "warn":
        _log("pretool", "warn", "task.metadata.deprecated", detail={"reason": err})
        system_message = f"[wicked-garden] DEPRECATION: task metadata: {err}"
    try:
        from _session import SessionState
        state = SessionState.load()
        if not state.task_suggest_shown:
            state.update(task_suggest_shown=True)
            suggest = "Creating tasks? Consider `/wicked-garden:crew:start` for quality gates."
            return _allow(
                system_message=(system_message + "\n" + suggest) if system_message else suggest
            )
    except Exception:
        pass

    return _allow(system_message=system_message)


def _handle_task_update(tool_input: dict) -> str:
    """Validate the event envelope on TaskUpdate (metadata merges).

    TaskUpdate metadata is a merge patch — an empty/absent metadata is valid
    (the caller is updating status or subject only). Validation only fires
    when metadata is present and contains an event_type claim.
    """
    mode = _task_metadata_mode()
    if mode == "off":
        return _allow()

    metadata = tool_input.get("metadata") or {}
    if not metadata.get("event_type"):
        return _allow()  # pure status/subject update

    err = _validate_event_metadata(tool_input)
    if err and mode == "strict":
        _log("pretool", "info", "task.metadata.blocked", detail={"reason": err})
        return _deny(f"[wicked-garden] task metadata invalid: {err}")
    if err and mode == "warn":
        _log("pretool", "warn", "task.metadata.deprecated", detail={"reason": err})
        return _allow(
            system_message=f"[wicked-garden] DEPRECATION: task metadata: {err}"
        )
    return _allow()


# ---------------------------------------------------------------------------
# Handler: EnterPlanMode
# (deny native plan mode, redirect to crew workflow)
# ---------------------------------------------------------------------------

def _handle_enter_plan_mode(tool_input: dict) -> str:
    """Block native plan mode — redirect to crew workflow instead.

    wicked-garden uses crew projects for planning, not Claude's built-in
    plan mode. Always deny and point to /wicked-garden:crew:start.
    """
    try:
        data, project_name, _ = _find_active_crew_project()
        if project_name and data:
            current_phase = data.get("current_phase", "")
            return _deny(
                f"Do not use native plan mode. A crew project '{project_name}' is already active "
                f"(phase: {current_phase}). Continue working within the crew workflow. "
                f"Use `/wicked-garden:crew:execute` to proceed or `/wicked-garden:crew:status` to check progress."
            )
    except Exception:
        pass

    return _deny(
        "Do not use native plan mode. This project uses wicked-garden crew workflows for planning. "
        "Use `/wicked-garden:crew:start` to create a new crew project with outcome clarification, "
        "phased execution, and quality gates."
    )


# ---------------------------------------------------------------------------
# Handler: Write / Edit
# (MEMORY.md and AGENTS.md write guard)
# ---------------------------------------------------------------------------

# Claude Code auto-memory directory pattern
_AUTO_MEMORY_MARKER = ".claude/projects/"


def _handle_write_guard(tool_input: dict) -> str:
    """Block direct writes to MEMORY.md, auto-memory directory, and AGENTS.md.

    Also warns when an active crew project is in build or review phase and the
    file path is not on the orchestrator allowlist. This enforces the
    orchestrator-only principle (Issue #251): orchestrators should write only
    to project state files, not directly produce implementation artifacts.

    TODO (Issue #329): When Claude Code supports updatedInput for PreToolUse hooks
    to redirect tool calls, change the MEMORY.md deny into an updatedInput redirect
    that rewrites the Write/Edit call into a mem:store invocation instead. This
    would be less disruptive than a hard deny — the intent to persist data would
    still succeed, just through the correct channel.
    """
    file_path = tool_input.get("file_path", "")

    # AGENTS.md is a cross-tool instruction file shared with Codex, Cursor, Amp, etc.
    # Writes are allowed — a PostToolUse hook keeps CLAUDE.md and AGENTS.md in sync.

    # Block writes to MEMORY.md or Claude's auto-memory directory
    is_memory_md = file_path.endswith("MEMORY.md")
    is_auto_memory = _AUTO_MEMORY_MARKER in file_path and "/memory/" in file_path

    if is_memory_md or is_auto_memory:
        return _deny(
            "Do not write to MEMORY.md or the auto memory directory. "
            "This project uses wicked-garden memory for persistence. "
            "Use /wicked-garden:mem:store to save decisions, patterns, and gotchas instead."
        )

    # Orchestrator-only warning (Issue #251): warn when writing outside allowlist
    # during build or review phases. Fail open — always allow, but emit systemMessage.
    warning = _check_orchestrator_write(file_path)
    if warning:
        return _allow(system_message=warning)

    return _allow()


# ---------------------------------------------------------------------------
# Orchestrator allowlist (Issue #251)
# ---------------------------------------------------------------------------

# Paths that the orchestrator is permitted to write directly.
# .something-wicked/ contains project state, status.md files are orchestrator output.
_ORCHESTRATOR_ALLOWLIST = [
    ".something-wicked/",
]

_ORCHESTRATOR_ALLOWLIST_SUFFIXES = [
    "status.md",
]

_ORCHESTRATOR_PHASES = {"build", "review"}


def _is_allowlisted(file_path: str) -> bool:
    """Return True if file_path is on the orchestrator write allowlist."""
    for fragment in _ORCHESTRATOR_ALLOWLIST:
        if fragment in file_path:
            return True
    for suffix in _ORCHESTRATOR_ALLOWLIST_SUFFIXES:
        if file_path.endswith(suffix):
            return True
    return False


def _check_orchestrator_write(file_path: str) -> str:
    """Return a warning message if the write appears to be orchestrator inline work.

    Only warns — never denies. Returns empty string if no warning needed.
    """
    if _is_allowlisted(file_path):
        return ""

    # Check if there is an active crew project in build or review phase
    try:
        data, project_name, _ = _find_active_crew_project()
        if not project_name or not data:
            return ""

        current_phase = data.get("current_phase", "")
        if current_phase.lower() not in _ORCHESTRATOR_PHASES:
            return ""

        return (
            f"[wicked-garden] Orchestrator principle: The active crew project "
            f"'{project_name}' is in '{current_phase}' phase. "
            f"Orchestrators should not write implementation files directly. "
            f"Delegate to implementer, researcher, or specialist subagents via Task(). "
            f"Allowed direct writes: .something-wicked/ paths and status.md files."
        )
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Handler: Bash
# (crew gate preflight — intercepts phase_manager.py approve calls)
# ---------------------------------------------------------------------------

# Regex to extract project and phase from phase_manager.py approve invocations.
# Matches forms like:
#   phase_manager.py myproject approve --phase build
#   phase_manager.py myproject approve --phase build --override-gate
_APPROVE_RE = re.compile(
    r"phase_manager\.py\s+(\S+)\s+approve(?:\s+.*?)?(?:--phase\s+(\S+))?",
    re.DOTALL,
)


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter fields using simple regex — no YAML library.

    Parses only the first ``---`` block. Returns a dict of key → raw string
    values. Multi-line values and lists are NOT parsed; only flat scalar
    ``key: value`` pairs are extracted.
    """
    fm: dict = {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return fm
    block = match.group(1)
    for line in block.splitlines():
        kv = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip()
    return fm


def _safe_read_text(path: Path) -> str:
    """Read file text; return '' on any error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _safe_read_json(path: Path):
    """Read and parse JSON; return None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _load_phases_config_hook() -> dict:
    """Load phases.json from .claude-plugin/ relative to plugin root.

    Returns the ``phases`` sub-dict, or an empty dict on any error.
    This is a local copy of the logic in phase_manager.py so the hook
    stays stdlib-only and avoids importing phase_manager (which has
    side-effects at import time like reading env vars at module level).
    """
    try:
        config_path = _PLUGIN_ROOT / ".claude-plugin" / "phases.json"
        if config_path.exists():
            data = _safe_read_json(config_path)
            if isinstance(data, dict):
                return data.get("phases", {})
    except Exception:
        pass
    return {}


def _get_project_id_for(project_arg: str) -> str:
    """Resolve project ID from a project name / slug argument.

    The phase_manager CLI accepts a project name or ID.  We look inside the
    wicked-crew projects directory for a project.json whose ``name`` or ``id``
    matches ``project_arg``.  Falls back to using ``project_arg`` verbatim as
    the directory name (which works when the CLI was given the raw ID).
    """
    try:
        from _paths import get_local_path
        base = get_local_path("wicked-crew", "projects")
        # Validate before using as a path component
        if re.match(r'^[a-zA-Z0-9_-]{1,64}$', project_arg):
            direct = base / project_arg
            if direct.is_dir():
                return project_arg

        # Scan all project directories for a name match
        if base.exists():
            for p in base.iterdir():
                if not p.is_dir():
                    continue
                pjson = _safe_read_json(p / "project.json")
                if pjson and (pjson.get("name") == project_arg or pjson.get("id") == project_arg):
                    return p.name
    except Exception:
        pass
    return project_arg


def _get_phase_plan(project_dir: Path) -> list:
    """Return the phase_plan list from project.json, or [] on failure."""
    pjson = _safe_read_json(project_dir / "project.json")
    if isinstance(pjson, dict):
        return [str(p) for p in pjson.get("phase_plan", [])]
    return []


def _get_project_complexity(project_dir: Path) -> int:
    """Return complexity_score from project.json, or 0 on failure."""
    pjson = _safe_read_json(project_dir / "project.json")
    if isinstance(pjson, dict):
        return int(pjson.get("complexity_score", 0))
    return 0


def _check_skipped_phases(phase_dir_base: Path, phase_plan: list, current_phase: str) -> str:
    """Return error message if any planned phase before current_phase has no directory.

    A missing phase directory means the phase was silently skipped without
    going through the proper skip flow (which records a skip reason).
    """
    try:
        idx = phase_plan.index(current_phase)
    except ValueError:
        return ""  # current phase not in plan — can't assess

    for prev in phase_plan[:idx]:
        if not (phase_dir_base / prev).is_dir():
            return (
                f"phase '{prev}' has no execution directory — it appears to have been "
                f"silently skipped without a recorded skip reason. "
                f"Use /wicked-garden:crew:approve on '{prev}' first, or record a valid "
                f"skip reason via phase_manager.py {prev} skip."
            )
    return ""


def _check_deliverables(phase_dir: Path, phase_name: str, phases_config: dict) -> str:
    """Return error message if any required deliverable is missing or too small."""
    phase = phases_config.get(phase_name, {})
    raw_deliverables = phase.get("required_deliverables", [])

    for entry in raw_deliverables:
        if isinstance(entry, str):
            entry = {"file": entry, "min_bytes": 100, "frontmatter": []}
        elif not isinstance(entry, dict):
            continue

        fname = entry.get("file", "")
        min_bytes = int(entry.get("min_bytes", 100))
        required_fm = entry.get("frontmatter", [])

        if not fname:
            continue

        fpath = phase_dir / fname
        if not fpath.exists():
            return (
                f"required deliverable '{fname}' is missing from phases/{phase_name}/. "
                f"Complete the phase work before approving."
            )

        size = fpath.stat().st_size
        if size < min_bytes:
            return (
                f"required deliverable '{fname}' is too small ({size} bytes, "
                f"minimum {min_bytes} bytes). The file may be a stub or incomplete."
            )

        # Check frontmatter fields
        if required_fm:
            text = _safe_read_text(fpath)
            fm = _parse_frontmatter(text)
            for field in required_fm:
                if field not in fm or not fm[field]:
                    return (
                        f"required deliverable '{fname}' is missing frontmatter field "
                        f"'{field}'. Add the field to the YAML frontmatter block."
                    )

    return ""


def _check_test_coverage(phase_dir_base: Path, phase_name: str, phases_config: dict) -> str:
    """Return error message if test coverage ratio is below threshold."""
    phase = phases_config.get(phase_name, {})
    min_coverage = phase.get("min_test_coverage")

    # Only enforce for phases that declare a coverage requirement
    if min_coverage is None:
        return ""

    # --- Find the planned count from test-strategy ---
    planned = 0
    for strategy_fname in ("test-plan.md", "test-strategy.md"):
        strategy_path = phase_dir_base / "test-strategy" / strategy_fname
        if strategy_path.exists():
            fm = _parse_frontmatter(_safe_read_text(strategy_path))
            raw = fm.get("case_count", "")
            if raw:
                try:
                    planned = int(re.sub(r"[^\d]", "", raw))
                except ValueError:
                    pass
            if planned:
                break

    if not planned:
        return ""  # Can't assess without a planned count

    # --- Find the executed count from test-results ---
    executed = 0
    results_path = phase_dir_base / phase_name / "test-results.md"
    if results_path.exists():
        text = _safe_read_text(results_path)
        fm = _parse_frontmatter(text)

        # Try frontmatter fields first
        for key in ("executed", "pass_count", "total_count", "test_count"):
            if key in fm:
                try:
                    executed = int(re.sub(r"[^\d]", "", fm[key]))
                    break
                except ValueError:
                    pass

        # Fallback: count test entries in markdown body (lines starting with - [ ] or - [x])
        if not executed:
            executed = len(re.findall(r"- \[[ xX]\]", text))

    if not executed:
        return ""  # Can't assess without an executed count

    ratio = executed / planned
    if ratio < min_coverage:
        pct_actual = int(ratio * 100)
        pct_required = int(min_coverage * 100)
        return (
            f"test coverage is {pct_actual}% ({executed}/{planned} tests executed), "
            f"but {pct_required}% is required for phase '{phase_name}'. "
            f"Run the missing tests and update test-results.md before approving."
        )

    return ""


def _check_conditions_resolved(phase_dir_base: Path, phase_plan: list, current_phase: str,
                                phases_config: dict) -> str:
    """Return error message if any prior phase has unresolved conditions."""
    try:
        idx = phase_plan.index(current_phase)
    except ValueError:
        return ""

    for prev in phase_plan[:idx]:
        prev_cfg = phases_config.get(prev, {})
        if not prev_cfg.get("conditions_manifest_required", False):
            continue

        manifest_path = phase_dir_base / prev / "conditions-manifest.json"
        if not manifest_path.exists():
            continue  # No manifest = no conditional gate was issued

        manifest = _safe_read_json(manifest_path)
        if not isinstance(manifest, (list, dict)):
            continue

        conditions = manifest if isinstance(manifest, list) else manifest.get("conditions", [])
        unresolved = [c for c in conditions if isinstance(c, dict) and not c.get("resolved_at")]
        if unresolved:
            labels = [c.get("id") or c.get("description", "unknown") for c in unresolved[:3]]
            extra = f" (and {len(unresolved) - 3} more)" if len(unresolved) > 3 else ""
            return (
                f"phase '{prev}' has {len(unresolved)} unresolved condition(s): "
                f"{', '.join(labels)}{extra}. "
                f"Resolve all conditions in phases/{prev}/conditions-manifest.json "
                f"before approving '{current_phase}'."
            )

    return ""


def _check_specialist_engagement(phase_dir: Path, phase_name: str, phases_config: dict,
                                  complexity: int) -> str:
    """Return error message if required specialists are missing and complexity >= 5."""
    phase = phases_config.get(phase_name, {})
    required = phase.get("required_specialists", [])

    if not required or complexity < 5:
        return ""

    engagement_path = phase_dir / "specialist-engagement.json"
    if not engagement_path.exists():
        engaged_domains: set = set()
    else:
        entries = _safe_read_json(engagement_path)
        if isinstance(entries, list):
            engaged_domains = {e.get("domain", "") for e in entries if isinstance(e, dict)}
        else:
            engaged_domains = set()

    missing = [s for s in required if s not in engaged_domains]
    if missing:
        return (
            f"required specialist(s) did not engage for phase '{phase_name}': "
            f"{', '.join(missing)}. "
            f"This project has complexity {complexity} (>= 5), so specialist engagement "
            f"is mandatory. Invoke the missing specialists via Task() before approving."
        )

    return ""


def _warn_reviewer_report(phase_dir: Path, phase_name: str, complexity: int) -> str:
    """Return a warning (non-blocking) if reviewer-report.md is missing for high-complexity phases."""
    if complexity < 5:
        return ""
    report_path = phase_dir / "reviewer-report.md"
    if not report_path.exists():
        return (
            f"[wicked-garden] Warning: phases/{phase_name}/reviewer-report.md is missing "
            f"for a complexity-{complexity} project. The async reviewer (Tier 2) should "
            f"have written this. Proceeding with approve, but consider running "
            f"/wicked-garden:crew:gate to generate a reviewer report."
        )
    return ""


def _crew_gate_preflight(command: str) -> dict:
    """Run deterministic file-based gate checks before phase_manager.py approve executes.

    Returns {"ok": True} to allow, or {"ok": False, "reason": "..."} to block.
    All checks complete in <100ms (file stat + small reads only).
    Fails open on any unexpected error.
    """
    # ------------------------------------------------------------------ #
    # FAST EARLY-EXIT: skip if not an approve call                        #
    # ------------------------------------------------------------------ #
    if "phase_manager.py" not in command or "approve" not in command:
        return {"ok": True}

    # ------------------------------------------------------------------ #
    # Respect legacy mode                                                  #
    # ------------------------------------------------------------------ #
    if os.environ.get("CREW_GATE_ENFORCEMENT", "strict") == "legacy":
        return {"ok": True}

    # ------------------------------------------------------------------ #
    # Parse project and phase from command                                 #
    # ------------------------------------------------------------------ #
    m = _APPROVE_RE.search(command)
    if not m:
        return {"ok": True}  # Unrecognised form — fail open

    project_arg = m.group(1)
    phase_name = m.group(2)

    if not project_arg:
        return {"ok": True}

    # If --phase was not explicit, try to derive from session state
    if not phase_name:
        try:
            from _session import SessionState
            state = SessionState.load()
            if state.active_project and isinstance(state.active_project, dict):
                phase_name = state.active_project.get("current_phase")
        except Exception:
            pass

    if not phase_name:
        return {"ok": True}  # Can't validate without knowing the phase

    # ------------------------------------------------------------------ #
    # Resolve paths                                                        #
    # ------------------------------------------------------------------ #
    try:
        project_id = _get_project_id_for(project_arg)
        from _paths import get_local_path
        base = get_local_path("wicked-crew", "projects")
        project_dir = base / project_id
        phase_dir = project_dir / "phases" / phase_name
        phase_dir_base = project_dir / "phases"
    except Exception:
        return {"ok": True}  # Path resolution failure — fail open

    # If project.json doesn't exist, we have no ground truth — fail open.
    # This handles the case where phase_manager.py is invoked on a project
    # that doesn't yet have local state (e.g. first run, or different workspace).
    if not (project_dir / "project.json").exists():
        return {"ok": True}

    phases_config = _load_phases_config_hook()
    phase_plan = _get_phase_plan(project_dir)
    complexity = _get_project_complexity(project_dir)

    # ------------------------------------------------------------------ #
    # Check a: Skipped phase detection                                     #
    # ------------------------------------------------------------------ #
    if phase_plan:
        msg = _check_skipped_phases(phase_dir_base, phase_plan, phase_name)
        if msg:
            return {"ok": False, "reason": f"Cannot approve {phase_name}: {msg}"}

    # ------------------------------------------------------------------ #
    # Check b: Phase directory exists                                      #
    # ------------------------------------------------------------------ #
    if not phase_dir.is_dir():
        return {
            "ok": False,
            "reason": (
                f"Cannot approve {phase_name}: phases/{phase_name}/ directory does not exist. "
                f"The phase has not produced any output. Execute the phase before approving."
            ),
        }

    # ------------------------------------------------------------------ #
    # Check c: Required deliverables present + frontmatter valid          #
    # ------------------------------------------------------------------ #
    msg = _check_deliverables(phase_dir, phase_name, phases_config)
    if msg:
        return {"ok": False, "reason": f"Cannot approve {phase_name}: {msg}"}

    # ------------------------------------------------------------------ #
    # Check d: Test coverage ratio                                         #
    # ------------------------------------------------------------------ #
    msg = _check_test_coverage(phase_dir_base, phase_name, phases_config)
    if msg:
        return {"ok": False, "reason": f"Cannot approve {phase_name}: {msg}"}

    # ------------------------------------------------------------------ #
    # Check e: Conditions resolved in prior phases                        #
    # ------------------------------------------------------------------ #
    if phase_plan:
        msg = _check_conditions_resolved(phase_dir_base, phase_plan, phase_name, phases_config)
        if msg:
            return {"ok": False, "reason": f"Cannot approve {phase_name}: {msg}"}

    # ------------------------------------------------------------------ #
    # Check f: Specialist engagement (blocks if complexity >= 5)          #
    # ------------------------------------------------------------------ #
    msg = _check_specialist_engagement(phase_dir, phase_name, phases_config, complexity)
    if msg:
        return {"ok": False, "reason": f"Cannot approve {phase_name}: {msg}"}

    # ------------------------------------------------------------------ #
    # Check g: Reviewer report (warn only)                                #
    # ------------------------------------------------------------------ #
    warning = _warn_reviewer_report(phase_dir, phase_name, complexity)

    return {"ok": True, "_warning": warning}


def _handle_bash(tool_input: dict) -> str:
    """Run crew gate preflight on Bash calls that invoke phase_manager.py approve."""
    command = tool_input.get("command", "") or ""

    # Fast path — non-approve Bash commands take <1ms
    result = _crew_gate_preflight(command)

    if not result.get("ok"):
        reason = result.get("reason", "Gate preflight check failed.")
        return _deny(reason)

    warning = result.get("_warning", "")
    if warning:
        return _allow(system_message=warning)

    return _allow()


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main():
    _t0 = time.monotonic()

    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        print(_allow())
        return

    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}

        _log("pretool", "debug", "hook.start", detail={"tool": tool_name})

        if tool_name == "TaskCreate":
            result = _handle_task_create(tool_input)
            _log("pretool", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
            print(result)
            return

        if tool_name == "TaskUpdate":
            result = _handle_task_update(tool_input)
            _log("pretool", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
            print(result)
            return

        if tool_name == "EnterPlanMode":
            result = _handle_enter_plan_mode(tool_input)
            _log("pretool", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
            print(result)
            return

        if tool_name in ("Write", "Edit"):
            result = _handle_write_guard(tool_input)
            _log("pretool", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
            print(result)
            return

        if tool_name == "Bash":
            result = _handle_bash(tool_input)
            _log("pretool", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
            print(result)
            return

        # All other tools — allow
        _log("pretool", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
        print(_allow())

    except Exception as e:
        print(f"[wicked-garden] pre_tool error: {e}", file=sys.stderr)
        # Always fail open on error
        print(_allow())


if __name__ == "__main__":
    main()
