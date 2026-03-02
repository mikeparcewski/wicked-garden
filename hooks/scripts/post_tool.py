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
  Read                                 → agentic framework detection (path-based heuristic)
  Bash                                 → activity tracking
  PostToolUseFailure (any tool_name)   → failure counting + auto issue detection

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add shared scripts directory to path
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))


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
    """Sync TaskCreate/TaskUpdate/TodoWrite to kanban via StorageManager."""
    try:
        from _storage import StorageManager
        sm = StorageManager("wicked-kanban")
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
    """Mark file as stale for search index + track change count for QE nudge + scenario staleness."""
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return {"continue": True}

    messages = []

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
    """Track changed file via SessionState. Return nudge message if threshold crossed."""
    try:
        from _session import SessionState
        state = SessionState.load()
        # stale_files already includes this file (added by _mark_file_stale above)
        stale = state.stale_files or []
        unique_count = len(stale)

        if unique_count >= _QE_CHANGE_THRESHOLD and not state.qe_nudged:
            short_paths = [Path(f).name for f in sorted(stale)]
            state.update(qe_nudged=True)
            return (
                f"[QE] {unique_count} files changed this session "
                f"({', '.join(short_paths[:5])}). "
                "Consider running tests or verifying imports before continuing."
            )
        return None
    except Exception:
        return None


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
# Handler: Task (subagent dispatch tracking)
# ---------------------------------------------------------------------------

def _handle_task_dispatch(tool_input: dict) -> dict:
    """Record subagent activity in session state."""
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
        state.save()
    except Exception:
        pass
    return {"continue": True}


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


def _handle_read(tool_input: dict) -> dict:
    """Quick path-based agentic framework detection."""
    file_path = (tool_input.get("file_path") or "").lower()
    if not file_path:
        return {"continue": True}

    try:
        detected = []
        for framework, patterns in _FRAMEWORK_PATTERNS.items():
            if any(p in file_path for p in patterns):
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


def _handle_failure(payload: dict) -> dict:
    """PostToolUseFailure: count failures via SessionState, queue issue at threshold."""
    tool_name = payload.get("tool_name", "unknown")
    tool_error = payload.get("tool_error", "") or payload.get("tool_use_error", "")

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
    """Append a trace entry to a session-scoped JSONL file (batched, not per-call SM create).

    Avoids creating individual JSON files + queue entries on every hook invocation
    in offline/local-fallback mode. The session trace file is flushed to SM at
    session end by stop.py.
    """
    if os.environ.get("WICKED_TRACE_ACTIVE"):
        return
    try:
        os.environ["WICKED_TRACE_ACTIVE"] = "1"
        session_id = _get_session_id()
        tool_name = payload.get("tool_name", "")
        entry = json.dumps({
            "ts": _now_iso(),
            "session_id": session_id,
            "tool": tool_name,
            "event": payload.get("hook_event_name", "PostToolUse"),
        })
        tmpdir = os.environ.get("TMPDIR", "/tmp")
        trace_file = Path(tmpdir) / f"wicked-trace-{session_id}.jsonl"
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass
    finally:
        os.environ.pop("WICKED_TRACE_ACTIVE", None)


# ---------------------------------------------------------------------------
# CP error surfacing (checks SessionState for errors recorded by _control_plane.py)
# ---------------------------------------------------------------------------

def _check_cp_errors() -> str | None:
    """Check for new CP errors and return a systemMessage if any."""
    try:
        from _session import SessionState
        state = SessionState.load()
        errors = state.cp_errors or []
        if not errors:
            return None

        # Consume errors (clear after reading)
        state.update(cp_errors=[])

        # Group by domain/source (extract from URL)
        grouped = {}
        for err in errors:
            parts = err["url"].split("/data/")[-1].split("/") if "/data/" in err["url"] else []
            key = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else err["url"]
            grouped.setdefault(key, []).append(err)

        lines = [f"[CP Error] {len(errors)} control plane error(s) detected:"]
        for key, errs in grouped.items():
            codes = set(e["code"] for e in errs)
            lines.append(f"  - {key}: HTTP {'/'.join(str(c) for c in sorted(codes))} ({len(errs)}x)")
        lines.append("Read .claude/skills/cp-error-detector/SKILL.md for diagnosis steps.")

        return "\n".join(lines)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main():
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
        # Task (subagent dispatch)
        elif tool_name == "Task":
            result = _handle_task_dispatch(tool_input)
        # Read (framework detection)
        elif tool_name == "Read":
            result = _handle_read(tool_input)
        # Bash (activity tracking)
        elif tool_name == "Bash":
            tool_response = payload.get("tool_response", {})
            result = _handle_bash(tool_input, tool_response)
        # All other tools — pass through
        else:
            result = {"continue": True}

        # --- CP error surfacing (runs after every handler) ---
        cp_msg = _check_cp_errors()
        if cp_msg:
            existing = result.get("systemMessage", "")
            result["systemMessage"] = f"{existing}\n\n{cp_msg}" if existing else cp_msg

        print(json.dumps(result))

    except Exception as e:
        print(f"[wicked-garden] post_tool error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
