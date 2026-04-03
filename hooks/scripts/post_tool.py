#!/usr/bin/env python3
"""
PostToolUse / PostToolUseFailure hook — wicked-garden unified post-tool dispatcher.

Consolidates: kanban todo_sync, crew posttool_task, delivery metrics_refresh,
mem task_checkpoint, search mark_stale, qe change_tracker,
agentic detect_framework, observability trace_writer.

Dispatches by tool_name from hook payload:
  TaskCreate / TaskUpdate / TodoWrite  → kanban sync + crew state + delivery metrics + mem checkpoint
  Write / Edit                         → stale file marking + QE change tracking + MEMORY.md guard
  Task                                 → subagent activity tracking
  Read                                 → large-file-read warning + agentic framework detection
  Bash                                 → activity tracking
  PostToolUseFailure (any tool_name)   → failure counting + auto issue detection

Traces are written to a session-scoped JSONL file in $TMPDIR (local only).

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
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
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_session_id(raw: str) -> str:
    """Strip path separators and traversal sequences from session ID."""
    sanitized = raw.replace("/", "_").replace("\\", "_").replace("..", "_")
    return sanitized if sanitized else "default"


def _get_session_id() -> str:
    return _sanitize_session_id(os.environ.get("CLAUDE_SESSION_ID", "default"))



# ---------------------------------------------------------------------------
# Handler: TaskCreate / TaskUpdate / TodoWrite
# (kanban sync, crew state update, delivery metrics, mem checkpoint)
# ---------------------------------------------------------------------------

def _infer_priority(content: str) -> str:
    lower = content.lower()
    if any(kw in lower for kw in ["critical", "urgent", "blocker", "hotfix", "security"]):
        return "P0"
    if any(kw in lower for kw in ["fix", "bug", "error", "broken", "failing", "important"]):
        return "P1"
    if any(kw in lower for kw in ["refactor", "cleanup", "minor", "polish"]):
        return "P3"
    return "P2"


def _parse_crew_initiative(subject: str):
    """Extract crew project name from task subject: 'Phase: project-name - description'."""
    match = re.match(r"^[A-Za-z-]+:\s+([a-zA-Z0-9][a-zA-Z0-9_-]*)\s+-\s+", subject)
    return match.group(1) if match else None


def _load_kanban_sync_state() -> dict:
    """Load kanban sync state from SessionState (ephemeral, per-session)."""
    try:
        from _session import SessionState
        state = SessionState.load()
        return state.kanban_sync or {"project_id": None, "task_map": {}, "initiative_id": None, "initiative_map": {}}
    except Exception:
        return {"project_id": None, "task_map": {}, "initiative_id": None, "initiative_map": {}}


def _save_kanban_sync_state(sync_data: dict) -> None:
    """Persist kanban sync state to SessionState."""
    try:
        from _session import SessionState
        state = SessionState.load()
        state.update(kanban_sync=sync_data)
    except Exception:
        pass


def _handle_task_tools(tool_name: str, tool_input: dict) -> dict:
    """Sync TaskCreate/TaskUpdate/TodoWrite to kanban via DomainStore."""
    try:
        from _domain_store import DomainStore
        sm = DomainStore("wicked-kanban", hook_mode=True)
        state = _load_kanban_sync_state()

        # Ensure project exists
        project_id = state.get("project_id")
        if not project_id:
            repo_path = os.environ.get("PWD", os.getcwd())
            repo_name = Path(repo_path).name or "Claude Tasks"
            project = sm.create("projects", {
                "name": f"{repo_name} Tasks",
                "description": f"Tasks for {repo_path}",
                "repo_path": repo_path,
            })
            if project:
                project_id = project.get("id") or project.get("data", {}).get("id")
                state["project_id"] = project_id

        if not project_id:
            return {"continue": True}

        messages = []

        if tool_name == "TaskCreate":
            subject = tool_input.get("subject", "")
            description = tool_input.get("description", "")
            metadata = tool_input.get("metadata") or {}
            initiative_name = metadata.get("initiative") or _parse_crew_initiative(subject) or "Issues"

            task = sm.create("tasks", {
                "project_id": project_id,
                "name": subject,
                "swimlane": "todo",
                "priority": metadata.get("priority") or _infer_priority(subject + " " + description),
                "description": description or tool_input.get("activeForm", ""),
                "initiative_name": initiative_name,
                "metadata": {
                    "source": "TaskCreate",
                    "session_id": _get_session_id(),
                },
            })
            if task:
                task_id = task.get("id") or task.get("data", {}).get("id")
                state.setdefault("task_map", {})[subject] = {
                    "kanban_id": task_id,
                    "initiative_name": initiative_name,
                }
                # Log activity for the new task
                if task_id:
                    sm.create("activity", {
                        "project_id": project_id,
                        "task_id": task_id,
                        "action": "created",
                        "details": {"from": None, "to": "todo"},
                        "source": "hook:post_tool",
                    })

            # Enrichment nudge
            hints = []
            if not description:
                hints.append("- Add a description: WHY does this task exist?")
            if not metadata.get("priority"):
                hints.append("- Set priority via metadata: {\"priority\": \"P0\"} through P3")
            if hints:
                messages.append(
                    "[Kanban] Task synced. Consider enriching it:\n"
                    + "\n".join(hints)
                )

        elif tool_name == "TaskUpdate":
            task_id_input = tool_input.get("taskId", "")
            status = tool_input.get("status")
            subject = tool_input.get("subject", "")

            # Resolve kanban task ID
            task_map = state.get("task_map", {})
            entry = task_map.get(task_id_input) or task_map.get(subject)
            kanban_id = None
            if isinstance(entry, dict):
                kanban_id = entry.get("kanban_id")
            elif isinstance(entry, str):
                kanban_id = entry

            if kanban_id and status:
                swimlane_map = {"pending": "todo", "in_progress": "in_progress", "completed": "done"}
                old_swimlane = None  # previous swimlane unknown from hook context
                swimlane = swimlane_map.get(status)
                updates = {}
                if swimlane:
                    updates["swimlane"] = swimlane
                if subject:
                    updates["name"] = subject
                if tool_input.get("description"):
                    updates["description"] = tool_input["description"]
                if updates:
                    sm.update("tasks", kanban_id, updates)
                    # Log activity for the status change
                    sm.create("activity", {
                        "project_id": project_id,
                        "task_id": kanban_id,
                        "action": "status_change",
                        "details": {"from": old_swimlane, "to": swimlane},
                        "source": "hook:post_tool",
                    })

        elif tool_name == "TodoWrite":
            todos = tool_input.get("todos", [])
            synced = 0
            swimlane_map = {"pending": "todo", "in_progress": "in_progress", "completed": "done"}
            for todo in todos:
                content = todo.get("content", "")
                if not content:
                    continue
                swimlane = swimlane_map.get(todo.get("status", "pending"), "todo")
                task_map = state.get("task_map", {})
                existing = task_map.get(content)
                existing_id = existing.get("kanban_id") if isinstance(existing, dict) else existing
                if existing_id:
                    sm.update("tasks", existing_id, {"swimlane": swimlane})
                    # Log activity for TodoWrite status change
                    sm.create("activity", {
                        "project_id": project_id,
                        "task_id": existing_id,
                        "action": "status_change",
                        "details": {"from": None, "to": swimlane},
                        "source": "hook:post_tool",
                    })
                else:
                    task = sm.create("tasks", {
                        "project_id": project_id,
                        "name": content,
                        "swimlane": swimlane,
                        "priority": _infer_priority(content),
                        "initiative_name": "Issues",
                        "metadata": {"source": "TodoWrite"},
                    })
                    if task:
                        tid = task.get("id") or task.get("data", {}).get("id")
                        state.setdefault("task_map", {})[content] = {
                            "kanban_id": tid,
                            "initiative_name": "Issues",
                        }
                        # Log activity for new TodoWrite task
                        if tid:
                            sm.create("activity", {
                                "project_id": project_id,
                                "task_id": tid,
                                "action": "created",
                                "details": {"from": None, "to": swimlane},
                                "source": "hook:post_tool",
                            })
                synced += 1

        _save_kanban_sync_state(state)

        result = {"continue": True}
        if messages:
            result["systemMessage"] = "\n".join(messages)
        return result

    except Exception as e:
        print(f"[wicked-garden] task_tools handler error: {e}", file=sys.stderr)
        return {"continue": True}


# ---------------------------------------------------------------------------
# Handler: Write / Edit
# (stale file marking, QE change tracking)
# ---------------------------------------------------------------------------

_QE_CHANGE_THRESHOLD = 3


def _handle_write_edit(tool_input: dict) -> dict:
    """Mark file as stale for search index + track change count for QE nudge + scenario staleness + CLAUDE.md/AGENTS.md sync."""
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return {"continue": True}

    messages = []

    # 0. CLAUDE.md ↔ AGENTS.md sync directive
    sync_msg = _check_instruction_file_sync(file_path)
    if sync_msg:
        messages.append(sync_msg)

    # 1. Mark file stale for wicked-search
    _mark_file_stale(file_path)

    # 2. QE change tracking
    qe_nudge = _track_qe_change(file_path)
    if qe_nudge:
        messages.append(qe_nudge)

    # 3. Scenario staleness: warn when commands change but scenarios may be stale
    scenario_nudge = _check_scenario_staleness(file_path)
    if scenario_nudge:
        messages.append(scenario_nudge)

    result = {"continue": True}
    if messages:
        result["systemMessage"] = "\n".join(messages)
    return result


def _check_instruction_file_sync(file_path: str) -> str | None:
    """When CLAUDE.md or AGENTS.md is edited, prompt to sync the counterpart.

    Both files serve as instruction files for different AI tools and must stay
    consistent. CLAUDE.md is the primary (loaded by Claude Code), AGENTS.md is
    the cross-tool counterpart (Codex, Cursor, Amp, etc.).

    Only fires once per session to avoid repeated nudges.
    """
    try:
        p = Path(file_path)
        name = p.name

        # Determine which file was edited and which needs syncing
        if name == "CLAUDE.md":
            counterpart_name = "AGENTS.md"
            counterpart = p.parent.parent / "AGENTS.md" if p.parent.name == ".claude" else p.parent / "AGENTS.md"
        elif name == "AGENTS.md":
            counterpart_name = "CLAUDE.md"
            # CLAUDE.md lives in .claude/ subdirectory
            counterpart = p.parent / ".claude" / "CLAUDE.md"
            if not counterpart.exists():
                counterpart = p.parent / "CLAUDE.md"
        else:
            return None

        # Only fire once per session
        from _session import SessionState
        state = SessionState.load()
        synced_flags = getattr(state, "instruction_sync_fired", None) or []
        if name in synced_flags:
            return None
        synced_flags.append(name)
        state.update(instruction_sync_fired=synced_flags)

        if not counterpart.exists():
            return (
                f"[Sync] {name} was updated but {counterpart_name} does not exist yet. "
                f"Create {counterpart_name} with the same user-facing instructions so "
                f"other AI tools (Codex, Cursor, Amp) follow the same rules."
            )

        return (
            f"[Sync] {name} was updated. Read {counterpart.name} and update it to "
            f"reflect the same user instructions and preferences. Both files must stay "
            f"consistent — {counterpart_name} is used by other AI coding tools."
        )
    except Exception:
        return None


def _mark_file_stale(file_path: str) -> None:
    """Accumulate stale file paths in SessionState for incremental re-index."""
    try:
        from _session import SessionState
        state = SessionState.load()
        stale = state.stale_files or []
        if file_path not in stale:
            stale.append(file_path)
            state.update(stale_files=stale)
    except Exception:
        pass


def _track_qe_change(file_path: str):
    """Track changed file via SessionState. Return nudge message if threshold crossed.

    When no active crew project exists, classifies accumulated file changes as
    UI/API/both and suggests specific QE tools (AC-6: one-off work coverage).
    """
    try:
        from _session import SessionState
        state = SessionState.load()
        # stale_files already includes this file (added by _mark_file_stale above)
        stale = state.stale_files or []
        unique_count = len(stale)

        if unique_count >= _QE_CHANGE_THRESHOLD and not state.qe_nudged:
            state.update(qe_nudged=True)

            # Check if a crew project is active — if so, crew handles QE via execute.md
            has_crew = bool(getattr(state, "crew_project", None))
            if has_crew:
                return (
                    f"[QE] {unique_count} files changed this session. "
                    "Crew project active — QE testing will run during the test phase."
                )

            # No crew project: classify files and suggest specific QE tools
            # Full testing pyramid: unit → integration → functional → E2E
            # See: skills/qe/qe-strategy/refs/test-type-taxonomy.md
            change_type = _classify_changed_files(stale)

            if change_type == "ui":
                return (
                    f"[QE] {unique_count} UI files changed this session. "
                    "Recommended testing (per test-type-taxonomy):\n"
                    "- **Unit**: `/wicked-garden:qe:automate` — generate unit tests for changed components\n"
                    "- **Visual**: `/wicked-garden:product:screenshot` — capture UI state + visual diff\n"
                    "- **Scenario**: `/wicked-garden:qe:scenarios` — generate user journey test scenarios\n"
                    "- **Regression**: run existing test suite to verify no breakage\n"
                    "- **Acceptance**: `/wicked-garden:qe:acceptance` — evidence-gated acceptance tests"
                )
            elif change_type == "api":
                return (
                    f"[QE] {unique_count} API files changed this session. "
                    "Recommended testing (per test-type-taxonomy):\n"
                    "- **Unit**: `/wicked-garden:qe:automate` — generate unit tests for changed logic\n"
                    "- **Integration**: test API contracts — request/response schema validation\n"
                    "- **Security**: `/wicked-garden:platform:security` — auth boundaries + input validation\n"
                    "- **Scenario**: `/wicked-garden:qe:scenarios` — generate endpoint test scenarios\n"
                    "- **Regression**: run existing test suite to verify no breakage\n"
                    "- **Acceptance**: `/wicked-garden:qe:acceptance` — evidence-gated acceptance tests"
                )
            elif change_type == "both":
                return (
                    f"[QE] {unique_count} files changed (UI + API) this session. "
                    "Recommended testing (per test-type-taxonomy):\n"
                    "- **Unit**: `/wicked-garden:qe:automate` — generate unit tests for changed code\n"
                    "- **Integration**: test API contracts + component integration\n"
                    "- **Visual**: `/wicked-garden:product:screenshot` — capture UI state + visual diff\n"
                    "- **Security**: `/wicked-garden:platform:security` — auth + input validation\n"
                    "- **Scenario**: `/wicked-garden:qe:scenarios` — generate E2E user journey scenarios\n"
                    "- **Regression**: run existing test suite to verify no breakage\n"
                    "- **Acceptance**: `/wicked-garden:qe:acceptance` — evidence-gated acceptance tests"
                )
            else:
                short_paths = [Path(f).name for f in sorted(stale)]
                return (
                    f"[QE] {unique_count} files changed this session "
                    f"({', '.join(short_paths[:5])}). "
                    "Recommended testing:\n"
                    "- **Unit**: `/wicked-garden:qe:automate` — generate unit tests\n"
                    "- **Regression**: run existing test suite\n"
                    "- **Scenario**: `/wicked-garden:qe:scenarios` — generate test scenarios"
                )
        return None
    except Exception:
        return None


def _classify_changed_files(file_paths: list) -> str:
    """Classify accumulated changed files using change_type_detector logic.

    Returns: "ui", "api", "both", or "unknown".
    Imports classify_file from scripts/crew/change_type_detector.py (stdlib-only).
    Falls back to "unknown" on any import or classification error.
    """
    try:
        scripts_crew = _PLUGIN_ROOT / "scripts" / "crew"
        if str(scripts_crew) not in sys.path:
            sys.path.insert(0, str(scripts_crew))
        from change_type_detector import classify_file

        ui_count = 0
        api_count = 0
        for fp in file_paths:
            classification, _ = classify_file(fp)
            if classification == "ui":
                ui_count += 1
            elif classification == "api":
                api_count += 1
            elif classification == "ambiguous":
                ui_count += 1
                api_count += 1

        if ui_count and api_count:
            return "both"
        if ui_count:
            return "ui"
        if api_count:
            return "api"
        return "unknown"
    except Exception:
        return "unknown"


def _check_scenario_staleness(file_path: str):
    """When a command or skill file changes, check if scenarios exist and may be stale.

    Detects edits to commands/{domain}/*.md or skills/{domain}/**.md and warns
    if scenarios/{domain}/ exists — those scenarios may need updating to match
    the changed command/skill behavior.

    Only fires once per domain per session (avoids repeated nudges).
    """
    try:
        p = Path(file_path)
        parts = p.parts

        # Detect if the file is in commands/ or skills/ under the plugin
        domain = None
        for i, part in enumerate(parts):
            if part in ("commands", "skills") and i + 1 < len(parts):
                # commands/{domain}/file.md or skills/{domain}/...
                candidate = parts[i + 1]
                # Skip if it looks like a filename (has extension)
                if "." not in candidate:
                    domain = candidate
                    break

        if not domain:
            return None

        # Check if scenarios exist for this domain
        plugin_root = _PLUGIN_ROOT
        scenario_dir = plugin_root / "scenarios" / domain
        if not scenario_dir.is_dir():
            return None

        scenario_count = len(list(scenario_dir.glob("*.md")))
        if scenario_count == 0:
            return None

        # Only nudge once per domain per session
        from _session import SessionState
        state = SessionState.load()
        warned_domains = getattr(state, "scenario_stale_warned", None) or []
        if domain in warned_domains:
            return None

        warned_domains.append(domain)
        state.update(scenario_stale_warned=warned_domains)

        return (
            f"[Scenarios] Command/skill in '{domain}' changed — "
            f"{scenario_count} scenario(s) in scenarios/{domain}/ may need updating. "
            f"Run `/wg-test {domain}` or `/wicked-garden:qe:acceptance scenarios/{domain}/ --all` to validate."
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Handler: Task (subagent dispatch tracking + permission failure detection)
# ---------------------------------------------------------------------------

# Patterns that indicate a subagent completed without doing work due to
# permission/access issues (Issue #318). Checked case-insensitively.
_PERMISSION_FAILURE_PATTERNS = [
    "i need bash access",
    "bash permission was denied",
    "permission denied",
    "tool was not available",
    "i don't have access to",
    "i do not have access to",
    "unable to execute bash",
    "bash tool is not available",
    "don't have permission",
    "do not have permission",
    "requires bash access",
    "couldn't run the command",
    "could not run the command",
    "bash tool was denied",
    "not permitted to run",
]


def _check_permission_failure(tool_response) -> str | None:
    """Inspect subagent result text for permission failure signals.

    Returns a short snippet of the matching text if a permission failure
    pattern is detected, or None if the result looks normal.
    """
    if not tool_response:
        return None

    # tool_response can be a string or a dict with a "result" or "text" field
    if isinstance(tool_response, dict):
        text = (
            tool_response.get("result", "")
            or tool_response.get("text", "")
            or tool_response.get("content", "")
            or tool_response.get("output", "")
        )
        # Also check stringified dict as fallback
        if not text:
            text = json.dumps(tool_response)
    elif isinstance(tool_response, str):
        text = tool_response
    else:
        text = str(tool_response)

    text_lower = text.lower()
    for pattern in _PERMISSION_FAILURE_PATTERNS:
        idx = text_lower.find(pattern)
        if idx != -1:
            # Extract a short snippet around the match for the system message
            start = max(0, idx - 20)
            end = min(len(text), idx + len(pattern) + 60)
            snippet = text[start:end].strip()
            # Truncate if still too long
            if len(snippet) > 120:
                snippet = snippet[:120] + "..."
            return snippet

    return None


def _handle_task_dispatch(tool_input: dict, tool_response=None) -> dict:
    """Record subagent activity in session state and detect permission failures."""
    messages = []

    try:
        subagent_type = tool_input.get("subagent_type", "")
        if not subagent_type:
            return {"continue": True}

        from _session import SessionState
        state = SessionState.load()
        dispatches = getattr(state, "subagent_dispatches", None) or []
        dispatches.append({
            "agent": subagent_type,
            "ts": _now_iso(),
        })
        # Keep last 20 dispatches only
        state.update(subagent_dispatches=dispatches[-20:])

        # --- Permission failure detection (Issue #318) ---
        snippet = _check_permission_failure(tool_response)
        if snippet:
            failures = (getattr(state, "subagent_permission_failures", None) or 0) + 1
            state.update(subagent_permission_failures=failures)

            _log(
                "crew", "warn", "subagent.permission_failure",
                ok=False,
                detail={"agent": subagent_type, "snippet": snippet, "count": failures},
            )

            messages.append(
                "[Crew] Subagent completed without work \u2014 permission issue detected. "
                "The subagent '{}' reported: '{}'. "
                "Consider running with broader permissions or executing the task inline.".format(
                    subagent_type, snippet
                )
            )

        state.save()
    except Exception:
        pass

    result = {"continue": True}
    if messages:
        result["systemMessage"] = "\n".join(messages)
    return result


# ---------------------------------------------------------------------------
# Handler: Read (agentic framework detection)
# ---------------------------------------------------------------------------

_FRAMEWORK_PATTERNS = {
    "langchain": ["langchain", "langsmith"],
    "langgraph": ["langgraph"],
    "autogen": ["autogen", "pyautogen"],
    "crewai": ["crewai", "crew_ai"],
    "dspy": ["dspy"],
    "llamaindex": ["llama_index", "llama-index"],
    "pydantic-ai": ["pydantic_ai", "pydantic-ai"],
    "anthropic-sdk": ["anthropic"],
    "openai-sdk": ["openai"],
}


_READ_LINE_THRESHOLD = 500
_READ_CHAR_THRESHOLD = 5000
_CUMULATIVE_WARN_THRESHOLD = 50000


def _handle_read(tool_input: dict, tool_response=None) -> dict:
    """Large-file-read warning + path-based agentic framework detection.

    Checks the Read tool output size and emits a systemMessage warning when
    a single read exceeds _READ_LINE_THRESHOLD lines or _READ_CHAR_THRESHOLD
    chars.  Tracks cumulative bytes read for escalating warnings.

    Always returns {"continue": True} — never blocks reads.
    """
    file_path = (tool_input.get("file_path") or "")
    messages = []

    # --- Large-file-read detection ---
    try:
        response_text = ""
        if isinstance(tool_response, str):
            response_text = tool_response
        elif isinstance(tool_response, dict):
            response_text = tool_response.get("content", "") or tool_response.get("output", "") or ""
        elif isinstance(tool_response, list):
            # Some hook payloads wrap content in a list of blocks
            parts = []
            for block in tool_response:
                if isinstance(block, dict):
                    parts.append(block.get("text", "") or block.get("content", "") or "")
                elif isinstance(block, str):
                    parts.append(block)
            response_text = "\n".join(parts)

        if response_text:
            char_count = len(response_text)
            line_count = response_text.count("\n") + 1

            from _session import SessionState
            state = SessionState.load()

            # Update cumulative read size
            cumulative = (state.read_bytes_total or 0) + char_count
            warn_count = state.read_large_warn_count or 0

            if line_count >= _READ_LINE_THRESHOLD or char_count >= _READ_CHAR_THRESHOLD:
                warn_count += 1
                short_path = Path(file_path).name if file_path else "unknown"

                if cumulative >= _CUMULATIVE_WARN_THRESHOLD and warn_count > 2:
                    # Escalated warning — heavy cumulative reads
                    messages.append(
                        f"[Context] Large file read: {short_path} ({line_count} lines, "
                        f"{char_count:,} chars). Session total: {cumulative:,} chars read inline. "
                        f"Context window pressure is high — delegate remaining reads to "
                        f"subagents via Task tool to preserve context."
                    )
                else:
                    messages.append(
                        f"[Context] Large file read detected ({line_count} lines, "
                        f"{char_count:,} chars). Consider delegating to a subagent to "
                        f"preserve context. Use Task tool with the file path instead of "
                        f"reading inline."
                    )

            state.update(
                read_bytes_total=cumulative,
                read_large_warn_count=warn_count,
            )
    except Exception:
        pass

    # --- Agentic framework detection (existing behavior) ---
    try:
        file_path_lower = file_path.lower()
        if file_path_lower:
            detected = []
            for framework, patterns in _FRAMEWORK_PATTERNS.items():
                if any(p in file_path_lower for p in patterns):
                    detected.append(framework)

            if detected:
                from _session import SessionState
                state = SessionState.load()
                existing = getattr(state, "detected_frameworks", None) or []
                combined = list(set(existing + detected))
                state.update(detected_frameworks=combined)
                state.save()
    except Exception:
        pass

    result = {"continue": True}
    if messages:
        result["systemMessage"] = "\n".join(messages)
    return result


# ---------------------------------------------------------------------------
# Handler: Skill (mem:store compliance counter reset)
# ---------------------------------------------------------------------------

def _handle_skill(tool_input: dict) -> dict:
    """Reset memory_compliance_escalations when a mem:store skill call succeeds.

    The TaskCompleted hook increments memory_compliance_escalations on every
    deliverable task completion. After 3 completions the [ESCALATION] prefix
    fires indefinitely. Resetting the counter here — triggered by any Skill
    invocation whose skill name matches *:mem:store — breaks the cycle.

    We reset on the Skill call regardless of whether the inner bash command
    succeeded: if the user invoked mem:store we treat that as intent to comply.
    """
    skill = (tool_input.get("skill") or "").lower()
    if ":mem:store" not in skill and skill != "mem:store":
        return {"continue": True}
    try:
        from _session import SessionState
        state = SessionState.load()
        if (state.memory_compliance_escalations or 0) > 0:
            state.update(memory_compliance_escalations=0)
    except Exception:
        pass
    return {"continue": True}


# ---------------------------------------------------------------------------
# Handler: Bash (general activity tracking)
# ---------------------------------------------------------------------------

def _handle_bash(tool_input: dict, tool_response) -> dict:
    """Track bash activity (lightweight — just increment counter in session state)."""
    try:
        from _session import SessionState
        state = SessionState.load()
        bash_count = (getattr(state, "bash_count", None) or 0) + 1
        state.update(bash_count=bash_count)
        state.save()
    except Exception:
        pass
    return {"continue": True}


# ---------------------------------------------------------------------------
# Handler: PostToolUseFailure
# (failure counting + threshold alerts)
# ---------------------------------------------------------------------------

_FAILURE_THRESHOLD_DEFAULT = 3
_MISMATCH_SIGNALS = [
    "failed", "not working", "broken", "error", "couldn't", "unable", "blocked"
]

# Patterns that indicate a missing CLI or Python module
_MISSING_TOOL_RE = [
    re.compile(r"command not found:\s*(\S+)"),
    re.compile(r"not found:\s*(\S+)"),
]
_MISSING_MODULE_RE = [
    re.compile(r"ModuleNotFoundError: No module named ['\"](\S+?)['\"]"),
    re.compile(r"ImportError: No module named ['\"](\S+?)['\"]"),
]


def _detect_missing_tool(error_text: str) -> str | None:
    """Check if error indicates a missing tool/module. Returns a prereq-doctor hint or None."""
    if not error_text:
        return None
    try:
        plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", ".")).resolve()
        doctor = plugin_root / "scripts" / "platform" / "prereq_doctor.py"
        if not doctor.exists():
            return None

        import subprocess as _sp
        proc = _sp.run(
            [sys.executable, str(doctor), "diagnose", error_text],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode != 0:
            return None
        diag = json.loads(proc.stdout)
        if diag.get("error_type") == "unknown":
            return None

        # Build a concise hint for the model
        if diag.get("fix") == "uv_sync":
            return (
                f"[Prereq Doctor] Missing Python module '{diag.get('module')}'. "
                f"Fix: run `uv sync` from the plugin root. "
                f"Or use: Skill(skill=\"wicked-garden:platform:prereq-doctor\", args=\"check uv\")"
            )
        if diag.get("status") == "missing":
            install_cmd = diag.get("install_cmd", "")
            return (
                f"[Prereq Doctor] CLI '{diag.get('cli', diag.get('tool'))}' not installed. "
                f"Install with: `{install_cmd}` — "
                f"Ask the user before installing. "
                f"Or use: Skill(skill=\"wicked-garden:platform:prereq-doctor\", args=\"check {diag.get('tool')}\")"
            )
        return None
    except Exception:
        return None


def _handle_failure(payload: dict) -> dict:
    """PostToolUseFailure: detect missing tools, count failures, queue issue at threshold."""
    tool_name = payload.get("tool_name", "unknown")
    tool_error = payload.get("tool_error", "") or payload.get("tool_use_error", "")

    # --- Missing tool detection (fires immediately, no threshold) ---
    prereq_hint = _detect_missing_tool(str(tool_error))
    if prereq_hint:
        return {"continue": True, "systemMessage": prereq_hint}

    # --- General failure counting (existing behavior) ---
    try:
        threshold = int(os.environ.get("WICKED_ISSUE_THRESHOLD", str(_FAILURE_THRESHOLD_DEFAULT)))
    except (ValueError, TypeError):
        threshold = _FAILURE_THRESHOLD_DEFAULT

    try:
        from _session import SessionState
        state = SessionState.load()
        counts = state.failure_counts or {}
        counts[tool_name] = counts.get(tool_name, 0) + 1
        current_count = counts[tool_name]
        state.update(failure_counts=counts)

        if current_count >= threshold:
            record = {
                "type": "tool_failure",
                "tool": tool_name,
                "count": current_count,
                "last_error": str(tool_error)[:500],
                "session_id": _get_session_id(),
                "ts": _now_iso(),
            }
            pending = state.pending_issues or []
            pending.append(record)
            counts[tool_name] = 0
            state.update(failure_counts=counts, pending_issues=pending)

            return {
                "continue": True,
                "systemMessage": (
                    f"[Issue Reporter] {current_count} {tool_name} failures — issue queued."
                ),
            }
    except Exception:
        pass

    return {"continue": True}


def _handle_task_update_mismatch(tool_input: dict) -> dict:
    """Detect task completion mismatch signals (task marked done but looks blocked)."""
    if tool_input.get("status") != "completed":
        return {"continue": True}

    subject = tool_input.get("subject", "") or ""
    description = tool_input.get("description", "") or ""
    task_id = tool_input.get("taskId", "") or ""

    combined = (subject + " " + description).lower()
    found_signal = next((s for s in _MISMATCH_SIGNALS if s in combined), None)

    if found_signal:
        record = {
            "type": "task_mismatch",
            "task_id": task_id,
            "subject": subject[:200],
            "signal": found_signal,
            "detail": description[:300],
            "ts": _now_iso(),
        }
        try:
            from _session import SessionState
            state = SessionState.load()
            pending = state.pending_issues or []
            pending.append(record)
            state.update(pending_issues=pending)
        except Exception:
            pass

    return {"continue": True}


# ---------------------------------------------------------------------------
# Observability trace writer
# ---------------------------------------------------------------------------

def _write_trace(payload: dict) -> None:
    """Write a trace entry to a session-scoped JSONL file in $TMPDIR."""
    if os.environ.get("WICKED_TRACE_ACTIVE"):
        return
    try:
        os.environ["WICKED_TRACE_ACTIVE"] = "1"
        session_id = _get_session_id()
        tool_name = payload.get("tool_name", "")
        event = payload.get("hook_event_name", "PostToolUse")
        ts = _now_iso()

        entry = {
            "ts": ts,
            "session_id": session_id,
            "tool": tool_name,
            "event": event,
        }

        tmpdir = os.environ.get("TMPDIR") or __import__("tempfile").gettempdir()
        trace_file = Path(tmpdir) / f"wicked-trace-{session_id}.jsonl"
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    finally:
        os.environ.pop("WICKED_TRACE_ACTIVE", None)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main():
    _t0 = time.monotonic()

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        print(json.dumps({"continue": True}))
        return

    try:
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {}) or {}
        has_error = "tool_error" in payload or "tool_use_error" in payload

        _log("posttool", "debug", "hook.start", detail={"tool": tool_name})

        # Write observability trace (low-priority, always runs)
        _write_trace(payload)

        # --- Route by event type and tool name ---

        # PostToolUseFailure path
        if has_error:
            result = _handle_failure(payload)
        # Task-management tools
        elif tool_name in ("TaskCreate", "TaskUpdate", "TodoWrite"):
            messages = []

            task_result = _handle_task_tools(tool_name, tool_input)
            if task_result.get("systemMessage"):
                messages.append(task_result["systemMessage"])

            # Mismatch detection only for TaskUpdate
            if tool_name == "TaskUpdate":
                _handle_task_update_mismatch(tool_input)

            result = {"continue": True}
            if messages:
                result["systemMessage"] = "\n".join(messages)
        # Write / Edit tools (async — quick operations only)
        elif tool_name in ("Write", "Edit"):
            result = _handle_write_edit(tool_input)
        # Task (subagent dispatch + permission failure detection)
        elif tool_name == "Task":
            tool_response = payload.get("tool_response", {})
            result = _handle_task_dispatch(tool_input, tool_response)
        # Read (large-file warning + framework detection)
        elif tool_name == "Read":
            tool_response = payload.get("tool_response", "")
            result = _handle_read(tool_input, tool_response)
        # Bash (activity tracking)
        elif tool_name == "Bash":
            tool_response = payload.get("tool_response", {})
            result = _handle_bash(tool_input, tool_response)
        # Skill (mem:store escalation counter reset)
        elif tool_name == "Skill":
            result = _handle_skill(tool_input)
        # All other tools — pass through
        else:
            result = {"continue": True}

        _log("posttool", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
        print(json.dumps(result))

    except Exception as e:
        print(f"[wicked-garden] post_tool error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
