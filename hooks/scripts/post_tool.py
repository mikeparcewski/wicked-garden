#!/usr/bin/env python3
"""
PostToolUse / PostToolUseFailure hook — wicked-garden unified post-tool dispatcher.

Consolidates: kanban todo_sync, crew posttool_task, delivery metrics_refresh,
mem task_checkpoint, search mark_stale, qe change_tracker, startah auto_issue_reporter,
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
import tempfile
from datetime import datetime, timezone, timedelta
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


def _session_dir(subdir: str) -> Path:
    """Return (and create) a per-session state directory under TMPDIR."""
    tmpdir = os.environ.get("TMPDIR", "/tmp").rstrip("/")
    path = Path(tmpdir) / subdir / _get_session_id()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _append_jsonl(path: Path, record: dict) -> None:
    """Append a JSON record as a single line to a .jsonl file."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


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
    """Load kanban sync state from the legacy wicked-kanban location for compatibility."""
    sync_file = (
        Path.home() / ".something-wicked" / "wicked-kanban" / "sync_state.json"
    )
    if sync_file.exists():
        try:
            return json.loads(sync_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"project_id": None, "task_map": {}, "initiative_id": None, "initiative_map": {}}


def _save_kanban_sync_state(state: dict) -> None:
    data_dir = Path.home() / ".something-wicked" / "wicked-kanban"
    data_dir.mkdir(parents=True, exist_ok=True)
    sync_file = data_dir / "sync_state.json"
    tmp = sync_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, sync_file)


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
    """Mark file as stale for search index + track change count for QE nudge."""
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

    result = {"continue": True}
    if messages:
        result["systemMessage"] = "\n".join(messages)
    return result


def _mark_file_stale(file_path: str) -> None:
    """Append file path to per-project stale_files.json for incremental re-index."""
    try:
        project_name = Path.cwd().name
        stale_file = (
            Path.home()
            / ".something-wicked"
            / "wicked-search"
            / "projects"
            / project_name
            / "stale_files.json"
        )
        stale_set = set()
        if stale_file.exists():
            try:
                existing = json.loads(stale_file.read_text())
                if isinstance(existing, list):
                    stale_set.update(existing)
            except (json.JSONDecodeError, OSError):
                pass
        stale_set.add(file_path)
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = stale_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(stale_set), indent=2))
        os.replace(tmp, stale_file)
    except Exception:
        pass


def _get_qe_tracker_path() -> Path:
    session_id = _get_session_id()
    return Path(tempfile.gettempdir()) / f"wicked-qe-changes-{session_id}"


def _track_qe_change(file_path: str):
    """Track changed file. Return nudge message if threshold crossed, else None."""
    try:
        tracker = _get_qe_tracker_path()
        data = {}
        try:
            data = json.loads(tracker.read_text())
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            pass

        files = set(data.get("files", []))
        nudged = data.get("nudged", False)
        files.add(file_path)
        unique_count = len(files)

        if unique_count >= _QE_CHANGE_THRESHOLD and not nudged:
            short_paths = [Path(f).name for f in sorted(files)]
            # Write with nudged=True so we don't repeat
            tracker.write_text(json.dumps({"files": sorted(files), "nudged": True}))
            return (
                f"[QE] {unique_count} files changed this session "
                f"({', '.join(short_paths[:5])}). "
                "Consider running tests or verifying imports before continuing."
            )
        else:
            tracker.write_text(json.dumps({"files": sorted(files), "nudged": nudged}))
            return None
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
_SESSION_DIR_MAX_AGE_HOURS = 48


def _load_failure_counts(sdir: Path) -> dict:
    counts_file = sdir / "failure_counts.json"
    try:
        data = json.loads(counts_file.read_text())
        if "counts" not in data:
            data["counts"] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
        return {"counts": {}, "last_updated": _now_iso()}


def _save_failure_counts(sdir: Path, data: dict) -> None:
    data["last_updated"] = _now_iso()
    counts_file = sdir / "failure_counts.json"
    counts_file.write_text(json.dumps(data, indent=2))


def _prune_stale_sessions(parent_dir: Path, flag_file: Path) -> None:
    """Delete session dirs whose failure_counts.json is older than 48h."""
    if flag_file.exists():
        return
    try:
        flag_file.write_text(_now_iso())
    except OSError:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_SESSION_DIR_MAX_AGE_HOURS)
    try:
        for entry in parent_dir.iterdir():
            if not entry.is_dir():
                continue
            counts_file = entry / "failure_counts.json"
            try:
                data = json.loads(counts_file.read_text())
                last_str = data.get("last_updated", "")
                last = datetime.fromisoformat(last_str)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if last < cutoff:
                    for child in entry.iterdir():
                        try:
                            child.unlink()
                        except OSError:
                            pass
                    try:
                        entry.rmdir()
                    except OSError:
                        pass
            except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
                continue
    except OSError:
        pass


def _handle_failure(payload: dict) -> dict:
    """PostToolUseFailure: count failures, queue issue at threshold."""
    tool_name = payload.get("tool_name", "unknown")
    tool_error = payload.get("tool_error", "") or payload.get("tool_use_error", "")

    sdir = _session_dir("wicked-issue-reporter")
    parent = sdir.parent

    # Prune stale sessions once per session
    try:
        _prune_stale_sessions(parent, sdir / ".pruned")
    except Exception:
        pass

    try:
        threshold = int(os.environ.get("WICKED_ISSUE_THRESHOLD", str(_FAILURE_THRESHOLD_DEFAULT)))
    except (ValueError, TypeError):
        threshold = _FAILURE_THRESHOLD_DEFAULT

    counts_data = _load_failure_counts(sdir)
    counts = counts_data["counts"]
    counts[tool_name] = counts.get(tool_name, 0) + 1
    current_count = counts[tool_name]

    try:
        _save_failure_counts(sdir, counts_data)
    except OSError:
        pass

    if current_count >= threshold:
        record = {
            "type": "tool_failure",
            "tool": tool_name,
            "count": current_count,
            "last_error": str(tool_error)[:500],
            "session_id": _get_session_id(),
            "ts": _now_iso(),
        }
        try:
            _append_jsonl(sdir / "pending_issues.jsonl", record)
        except OSError:
            pass

        # Reset so next cycle starts fresh
        counts[tool_name] = 0
        try:
            _save_failure_counts(sdir, counts_data)
        except OSError:
            pass

        return {
            "continue": True,
            "systemMessage": (
                f"[Issue Reporter] {current_count} {tool_name} failures — issue queued."
            ),
        }

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
            sdir = _session_dir("wicked-issue-reporter")
            _append_jsonl(sdir / "mismatches.jsonl", record)
        except OSError:
            pass

    return {"continue": True}


# ---------------------------------------------------------------------------
# Observability trace writer
# ---------------------------------------------------------------------------

def _write_trace(payload: dict) -> None:
    """Write a JSONL trace entry for observability. Anti-recursion guarded."""
    if os.environ.get("WICKED_TRACE_ACTIVE"):
        return
    try:
        traces_dir = Path.home() / ".something-wicked" / "wicked-garden" / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        session_id = _get_session_id()
        trace_file = traces_dir / f"session-{session_id}.jsonl"

        tool_name = payload.get("tool_name", "")
        record = {
            "ts": _now_iso(),
            "session_id": session_id,
            "tool": tool_name,
            "event": payload.get("hook_event_name", "PostToolUse"),
        }
        _append_jsonl(trace_file, record)
    except Exception:
        pass


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
            print(json.dumps(result))
            return

        # Task-management tools
        if tool_name in ("TaskCreate", "TaskUpdate", "TodoWrite"):
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
            print(json.dumps(result))
            return

        # Write / Edit tools (async — quick operations only)
        if tool_name in ("Write", "Edit"):
            result = _handle_write_edit(tool_input)
            print(json.dumps(result))
            return

        # Task (subagent dispatch)
        if tool_name == "Task":
            result = _handle_task_dispatch(tool_input)
            print(json.dumps(result))
            return

        # Read (framework detection)
        if tool_name == "Read":
            result = _handle_read(tool_input)
            print(json.dumps(result))
            return

        # Bash (activity tracking)
        if tool_name == "Bash":
            tool_response = payload.get("tool_response", {})
            result = _handle_bash(tool_input, tool_response)
            print(json.dumps(result))
            return

        # All other tools — pass through
        print(json.dumps({"continue": True}))

    except Exception as e:
        print(f"[wicked-garden] post_tool error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
