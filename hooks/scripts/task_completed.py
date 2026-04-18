#!/usr/bin/env python3
"""
TaskCompleted hook — wicked-garden memory capture on task completion.

Fires when Claude Code marks a task as completed (TaskCompleted event).
This hook does NOT use matchers — it fires for all task completions.

Responsibilities:
1. Increment memory_compliance_tasks_completed in session state.
2. For any deliverable-producing task, emit a systemMessage directive
   asking Claude to evaluate the completed task for storable learnings.
   Uses stronger language when memory_compliance_required (crew project).

Always returns {"ok": true} — task completion is never blocked.
Wraps all logic in try/except and fails open.

Input schema (from Claude Code):
    {"task_id": "...", "subject": "...", "status": "completed"}
"""

import json
import os
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

# Keywords that suggest a deliverable-producing task
_DELIVERABLE_PATTERNS = (
    "phase:",
    "implement",
    "write",
    "design",
    "build",
    "create",
    "develop",
    "refactor",
    "migrate",
    "fix",
    "resolve",
    "deploy",
    "integrate",
    "add",
    "update",
    "test",
    "review",
    "document",
    "configure",
    "setup",
    "scaffold",
    "generate",
    "analyze",
)


def _is_deliverable_task(subject: str) -> bool:
    """Return True if the task subject suggests it produced a deliverable."""
    subject_lower = subject.lower()
    return any(kw in subject_lower for kw in _DELIVERABLE_PATTERNS)


def _infer_mem_type(subject: str) -> str:
    """Infer the most appropriate mem:store type from task subject."""
    s = subject.lower()
    if any(kw in s for kw in ("fix", "resolve", "bug", "defect")):
        return "decision"
    if any(kw in s for kw in ("phase:", "design", "architect", "strategy")):
        return "episodic"
    return "procedural"


def _read_task_chain_id(session_id: str, task_id: str) -> "str | None":
    """Read ``metadata.chain_id`` from the native task JSON file.

    File path: ``${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/{task_id}.json``.

    Fail-open: returns None on any error (missing file, bad JSON, absent metadata,
    absent chain_id). This is deliberately permissive so task completion is never
    blocked by a facilitator-re-eval signal error.
    """
    if not session_id or not task_id:
        return None
    try:
        config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
        base = Path(config_dir) if config_dir else Path.home() / ".claude"
        task_file = base / "tasks" / session_id / f"{task_id}.json"
        if not task_file.is_file():
            return None
        data = json.loads(task_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            return None
        chain_id = metadata.get("chain_id")
        if isinstance(chain_id, str) and chain_id.strip():
            return chain_id
        return None
    except Exception:
        return None


def main():
    _t0 = time.monotonic()

    # Read task data from stdin
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {}
    except Exception:
        input_data = {}

    try:
        subject = input_data.get("subject", "")
        task_id = input_data.get("task_id", "")
        session_id = input_data.get("session_id", os.environ.get("CLAUDE_SESSION_ID", ""))

        _log("task", "debug", "hook.start")

        # Look up metadata.chain_id from the native task file (fail-open).
        # Gate 3 (v6): surface re-eval signal so prompt_submit.py can tell Claude
        # to invoke propose-process in re-evaluation mode on the next turn.
        chain_id = _read_task_chain_id(session_id, task_id)

        # Load session state, increment counters, and read escalation level
        escalations = 0
        try:
            from _session import SessionState
            state = SessionState.load()
            state.memory_compliance_tasks_completed = (
                (state.memory_compliance_tasks_completed or 0) + 1
            )
            compliance_required = bool(state.memory_compliance_required)
            # Increment escalation counter (reset by post_tool.py on mem:store)
            state.memory_compliance_escalations = (
                (state.memory_compliance_escalations or 0) + 1
            )
            escalations = state.memory_compliance_escalations

            # v6 facilitator re-evaluation signal (Gate 3, epic #428).
            # Set flag when the completed task carries a chain_id. prompt_submit.py
            # consumes this on the next UserPromptSubmit, emits a systemMessage
            # directive, and clears the flag. Fail-open: a missing chain_id is
            # a no-op (most native tasks don't have metadata).
            if chain_id:
                state.facilitator_reeval_due = True
                state.facilitator_reeval_chain = chain_id

            # Phase-start gate signal: set when the completed task is a
            # phase-transition event so prompt_submit.py can dispatch
            # phase_start_gate.check() before the next phase's specialists engage.
            # Fires ONLY for phase-transition event_type to avoid OQ-5 noise.
            # Fail-open: missing metadata is a no-op; never blocks completion.
            try:
                event_type = None
                if session_id and task_id:
                    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
                    base = Path(config_dir) if config_dir else Path.home() / ".claude"
                    task_file = base / "tasks" / session_id / f"{task_id}.json"
                    if task_file.is_file():
                        task_data = json.loads(task_file.read_text(encoding="utf-8"))
                        event_type = (
                            task_data.get("metadata", {}).get("event_type")
                            if isinstance(task_data, dict)
                            else None
                        )
                if event_type == "phase-transition":
                    state.phase_start_gate_due = True
            except Exception:
                pass  # fail-open: gate-due flag is best-effort

            state.save()
        except Exception as e:
            print(f"[wicked-garden] task_completed session state error: {e}", file=sys.stderr)
            compliance_required = False

        # Emit a memory directive for any deliverable-producing task.
        # Crew projects get stronger "REQUIRED" language; normal sessions
        # get a lighter nudge so memories still get captured.
        system_message = ""
        if subject and _is_deliverable_task(subject):
            mem_type = _infer_mem_type(subject)
            task_label = f'"{subject}"' if subject else f"task {task_id}"
            if compliance_required:
                escalation_prefix = "[ESCALATION] " if escalations >= 3 else ""
                system_message = (
                    f"{escalation_prefix}[Memory] Task {task_label} completed. "
                    f"REQUIRED: Call /wicked-garden:mem:store with type={mem_type} "
                    "to capture any decision, gotcha, or pattern from this work. "
                    "If genuinely nothing is worth storing, respond with 'No memory stored: <reason>'."
                )
            else:
                system_message = (
                    f"[Memory] Task {task_label} completed. "
                    "If this produced a decision, gotcha, or reusable pattern, "
                    f"store it with /wicked-garden:mem:store (type={mem_type})."
                )

        # Evidence nudge for crew tasks (Issue #253).
        # Remind agents to include structured evidence in TaskUpdate descriptions.
        if compliance_required and subject and _is_deliverable_task(subject):
            evidence_nudge = (
                " [Evidence] Ensure your TaskUpdate description includes structured evidence: "
                "test results (PASS/FAIL), files modified/created, and verification steps. "
                "Phase approval validates evidence at complexity >= 3."
            )
            system_message = (system_message or "") + evidence_nudge

        output: dict = {"ok": True}
        if system_message:
            output["systemMessage"] = system_message

        _log("task", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
        print(json.dumps(output))

    except Exception as e:
        print(f"[wicked-garden] task_completed hook error: {e}", file=sys.stderr)
        print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
