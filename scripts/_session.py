#!/usr/bin/env python3
"""
_session.py — Session state shared across hook script invocations.

Hook scripts run as separate processes, so they cannot share in-memory state.
This module persists a lightweight JSON state file keyed by CLAUDE_SESSION_ID
so all hooks within a session read/write a consistent view.

State file location:
    {tempfile.gettempdir()}/wicked-garden-session-{SESSION_ID}.json

Atomic writes: write to .tmp, then os.replace — prevents partial reads.

Usage (hook scripts):
    from _session import SessionState

    state = SessionState.load()
    state.turn_count += 1
    state.save()

    # Or update multiple fields at once:
    state.update(setup_complete=True)
"""

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Session ID resolution
# ---------------------------------------------------------------------------

_SESSION_ID_ENV = "CLAUDE_SESSION_ID"
_FALLBACK_SESSION_ID = "default"

# Characters that could be used for path traversal — strip them from session IDs
_SAFE_ID_RE = None  # initialized lazily


def _get_session_id() -> str:
    """Read and sanitize the Claude session ID from the environment.

    Returns a safe string usable as a filename component.
    """
    import re

    raw = os.environ.get(_SESSION_ID_ENV, _FALLBACK_SESSION_ID)
    # Strip any path traversal or shell-special characters — keep only
    # alphanumerics, hyphens, and underscores.
    safe = re.sub(r"[^a-zA-Z0-9\-_]", "_", raw)
    return safe or _FALLBACK_SESSION_ID


def _state_file_path() -> Path:
    """Return the path to the session state JSON file for the current session."""
    tmpdir = os.environ.get("TMPDIR") or tempfile.gettempdir()
    session_id = _get_session_id()
    filename = f"wicked-garden-session-{session_id}.json"
    return Path(tmpdir) / filename


# ---------------------------------------------------------------------------
# SessionState dataclass
# ---------------------------------------------------------------------------


@dataclass
class SessionState:
    """Lightweight session state persisted across hook script invocations.

    All fields have safe defaults so a missing or partial state file never
    causes a hook to crash.

    Fields:
        setup_complete: True when config.json has setup_complete == true.
        active_project: Dict summary of the active crew project, or None.
        agents_loaded:  Number of agents loaded at bootstrap.
        turn_count:     Number of user prompts in this session (incremented by
                        prompt_submit.py on each UserPromptSubmit hook).
    """

    setup_complete: bool = False
    active_project: dict | None = None
    agents_loaded: int = 0
    turn_count: int = 0
    session_ended: bool = False

    # One-time nudge flags (reset per session)
    task_suggest_shown: bool = False

    # Stale files accumulated this session (flushed to SM on demand)
    stale_files: list | None = None

    # QE change tracking nudge flag
    qe_nudged: bool = False

    # Set by bootstrap.py when onboarding is incomplete; checked by prompt_submit gate
    needs_onboarding: bool = False

    # Set by prompt_submit gate when /wicked-garden:setup passes through;
    # allows subsequent user answers (AskUserQuestion responses) through the gate
    setup_in_progress: bool = False

    # True when Claude Code is running in dangerous mode (skipDangerousModePermissionPrompt).
    # AskUserQuestion is broken in this mode — commands must use plain text questions instead.
    dangerous_mode: bool = False

    # Failure counts per tool (for issue reporter threshold)
    failure_counts: dict | None = None

    # Queued issue records (pending_issues + mismatches)
    pending_issues: list | None = None

    # Subagent dispatch log (post_tool.py Task handler)
    subagent_dispatches: list | None = None

    # Detected agentic frameworks (post_tool.py Read handler)
    detected_frameworks: list | None = None

    # Bash command counter (post_tool.py Bash handler)
    bash_count: int = 0

    # Memory compliance tracking (set by bootstrap + incremented by task_completed.py)
    # memory_compliance_required: True when a crew project is active (enables directives)
    # memory_compliance_tasks_completed: count of TaskCompleted events this session
    memory_compliance_required: bool = False
    memory_compliance_tasks_completed: int = 0

    # Crew recommendation heuristic — shown at most once per session on SLOW path
    # when complexity >= 2 and no active crew project exists.
    crew_hint_shown: bool = False

    # Context dedup hash — tracks the last session state hash to skip redundant
    # re-injection on HOT path when state hasn't changed between turns.
    context_hash: str = ""

    # Escalation counter: incremented by task_completed.py on each deliverable completion.
    # Reset by post_tool.py when a mem:store Write/Edit is detected.
    memory_compliance_escalations: int = 0

    # Written by bootstrap.py when onboarding is confirmed complete (both memories and index).
    # prompt_submit.py reads this as the primary signal, bypassing per-turn re-check.
    onboarding_complete: bool = False

    # Separate from cp_project_id (which is a CP UUID reference).
    # active_project_id is the LOCAL project name (slug) for a project that is currently
    # in an active (non-complete) phase in this workspace. None when no active project.
    active_project_id: str | None = None

    # One-per-session gate for jam suggestion (reset each session).
    jam_hint_shown: bool = False

    # Operational log verbosity level for this session.
    # "" means "not set" — the logger defaults to "normal".
    # Valid values: "normal", "verbose", "debug"
    # Written by /wicked-garden:platform:debug; read by _logger._resolve_level().
    log_level: str = ""

    # Cached integration-discovery results for this session.
    # Maps domain name to selected tool name ("linear", "jira", "notion") or "local".
    # None means discovery has not run yet this session.
    integration_tools: dict | None = None

    # Resolved tool lists from capability-based routing.
    # Maps agent_name -> list of resolved tool names.
    # None means resolution has not run yet this session.
    resolved_capabilities: dict | None = None

    # wicked-brain dependency check (set by bootstrap.py at SessionStart).
    # True  — wicked-brain plugin is installed (found in enabledPlugins).
    # False — not installed; bootstrap emits an install hint to the briefing.
    # None  — check has not run yet this session (e.g., early-exit before setup).
    brain_available: bool | None = None

    # Fast-path sentinel: set by bootstrap.py when config.json setup_complete=True.
    # Allows prompt_submit.py guard to skip config.json file read on every turn.
    # Once True for a session, it never goes back to False.
    setup_confirmed: bool = False

    # Onboarding mode selected during this session's wizard run.
    # Written by setup.md Step 5. Values: None | "full" | "quick" | "skip"
    onboarding_mode: str | None = None

    # Dedup guard for PreCompact hook — ISO timestamp of last compaction.
    # If compaction happened <60s ago, skip redundant WIP save.
    last_compact_ts: str = ""

    # Cumulative bytes read via the Read tool this session (post_tool.py).
    # Used for escalating context-window warnings.
    read_bytes_total: int = 0

    # Number of large-file-read warnings emitted this session.
    # Escalation tiers: first warning is informational, repeated warnings
    # become more urgent.
    read_large_warn_count: int = 0

    # Subagent permission failure counter (post_tool.py Task handler).
    # Incremented when a subagent completes without doing work due to
    # Bash permission issues or tool-access failures (Issue #318).
    subagent_permission_failures: int = 0

    # Discovery hints shown this session — tracks which "did you know?" hints
    # have been emitted so each is shown at most once (Issue #322).
    # List of hint IDs like ["grep_search", "manual_review", "debugging"].
    hints_shown: list | None = None

    # OneDrive / spaces-in-paths resolution (Issue #321).
    # Stores the resolved canonical base path when cwd is under a OneDrive
    # or CloudStorage directory (macOS ~/Library/CloudStorage/OneDrive - .../...).
    # Empty string means not applicable (cwd is not under OneDrive).
    onedrive_base_path: str = ""

    # Turn progress visibility (Issue #323).
    # turn_start_ts: ISO timestamp when the current turn began (set by prompt_submit).
    # turn_tool_count: number of tool calls in the current turn (incremented by post_tool).
    turn_start_ts: str = ""
    turn_tool_count: int = 0

    # Pull-model context assembly (Issue #416).
    # Phase: bootstrap (turns 1-2, mandatory pull), calibrating (turns 3-8),
    # cruising (turns 9+, minimal directive). Transition driven by turn count.
    pull_phase: str = "bootstrap"  # bootstrap | calibrating | cruising
    # Count of brain:query/search pulls the model made this session.
    pull_count: int = 0
    # Turns where the model answered without pulling and was NOT corrected.
    unpulled_ok: int = 0
    # Turns where the model was corrected after not pulling.
    corrections: int = 0
    # Turn number when phase was regressed to mandatory pull due to corrections.
    # 0 means no regression active. When set, mandatory pull lasts for 3 turns
    # from this turn number, then resumes normal phase progression.
    pull_regress_at: int = 0

    # PostToolUse hook latency profiling (Issue #312).
    # Cumulative milliseconds spent in the post_tool.py main() function.
    post_tool_total_ms: int = 0
    # Total number of PostToolUse hook invocations this session.
    post_tool_call_count: int = 0
    # Per-handler cumulative milliseconds: {"Read": 42, "Write|Edit": 15, ...}
    post_tool_handler_ms: dict | None = None

    # v6 facilitator re-evaluation (Gate 3, epic #428).
    # task_completed.py sets these when a task with metadata.chain_id completes.
    # prompt_submit.py reads on the next turn, emits a re-eval directive, then clears.
    facilitator_reeval_due: bool = False
    facilitator_reeval_chain: str | None = None  # chain_id needing re-eval

    # v6 phase-start heuristic gate (AC-11). task_completed.py sets this when
    # a completed task is the last in a phase; prompt_submit.py dispatches
    # phase_start_gate.py::check() on next turn and emits the directive.
    # MUST be a declared dataclass field — asdict() only serializes declared
    # attributes, so setting it as a transient attr won't persist. (Caught by
    # senior-engineer review of this very project — meta bug fix.)
    phase_start_gate_due: bool = False

    # Name of the last phase the user approved this session (#462).
    # Written by scripts/crew/phase_manager.py::approve_phase() after a
    # successful approval. Read by stop.py to decide whether to promote
    # the guard pipeline profile (scalpel → standard) when build just closed.
    # None when no approval has happened yet this session.
    last_phase_approved: str | None = None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "SessionState":
        """Load state from the session file.

        Returns a fresh default-valued SessionState if the file does not exist
        or contains invalid JSON — ensures hooks never crash on missing state.
        """
        path = _state_file_path()

        if not path.exists():
            return cls()

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            # Corrupted or unreadable state — return clean defaults
            return cls()

        # Build from dict; unknown keys are silently ignored so older state
        # files remain compatible with newer code that adds fields.
        return cls._from_dict(data)

    def save(self) -> None:
        """Atomically persist the current state to the session file."""
        path = _state_file_path()
        tmp_path = path.with_suffix(".tmp")

        data = asdict(self)

        try:
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp_path, path)
        except OSError as exc:
            print(
                f"[wicked-garden] Failed to save session state: {exc}",
                file=sys.stderr,
            )

    def update(self, **kwargs: Any) -> None:
        """Update one or more fields and immediately save to disk.

        Only recognised field names are applied; unknown keys are silently
        dropped so callers cannot accidentally corrupt the state schema.

        Args:
            **kwargs: Field name -> new value pairs.
        """
        valid_fields = {f for f in self.__dataclass_fields__}
        for key, value in kwargs.items():
            if key in valid_fields:
                object.__setattr__(self, key, value)
            else:
                print(
                    f"[wicked-garden] SessionState.update: unknown field {key!r} ignored",
                    file=sys.stderr,
                )
        self.save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _from_dict(cls, data: dict) -> "SessionState":
        """Construct a SessionState from a dict, ignoring unknown keys."""
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Return a plain dict representation (JSON-safe)."""
        return asdict(self)

    def increment_turn(self) -> int:
        """Increment turn_count, persist, and return the new value."""
        self.turn_count += 1
        self.save()
        return self.turn_count

    # ------------------------------------------------------------------
    # Session file cleanup (called by stop.py)
    # ------------------------------------------------------------------

    def delete(self) -> None:
        """Remove the session state file at session end.

        Silently succeeds if the file does not exist.
        """
        path = _state_file_path()
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            print(
                f"[wicked-garden] Failed to delete session state file: {exc}",
                file=sys.stderr,
            )
