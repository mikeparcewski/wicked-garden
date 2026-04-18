#!/usr/bin/env python3
"""
PostToolUse / PostToolUseFailure hook — wicked-garden unified post-tool dispatcher.

Consolidates: crew posttool_task, delivery metrics_refresh, mem task_checkpoint,
search mark_stale, qe change_tracker, agentic detect_framework,
observability trace_writer.

Dispatches by tool_name from hook payload:
  TaskCreate / TaskUpdate / TodoWrite  → mismatch detection on TaskUpdate
  Write / Edit                         → stale file marking + QE change tracking + MEMORY.md guard
  Task                                 → subagent activity tracking
  Read                                 → large-file-read warning + agentic framework detection
  Bash                                 → activity tracking + discovery hints
  Grep / Glob                          → discovery hints for search commands
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

def _resolve_brain_port():
    try:
        from _brain_port import resolve_port
        return resolve_port()
    except Exception:
        return int(os.environ.get("WICKED_BRAIN_PORT", "4242"))


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
# Discovery hints — "did you know?" suggestions (Issue #322)
#
# Each hint has an ID, a one-line suggestion, and fires at most once per session.
# Detects patterns in tool usage and suggests wicked-garden commands that could
# do the job better. Lightweight — single SessionState read/write.
# ---------------------------------------------------------------------------

_DISCOVERY_HINTS = {
    "grep_search": (
        "[Tip] wicked-garden has semantic code search: "
        "`/wicked-garden:search:code <query>` finds symbols with context, "
        "or `/wicked-garden:search:blast-radius <symbol>` for impact analysis."
    ),
    "manual_review": (
        "[Tip] For structured code review with senior-engineer perspective, "
        "try `/wicked-garden:engineering:review`."
    ),
    "debugging": (
        "[Tip] For systematic debugging with root cause analysis, "
        "try `/wicked-garden:engineering:debug`."
    ),
    "requirements": (
        "[Tip] For structured requirements elicitation, "
        "try `/wicked-garden:product:elicit`."
    ),
    "architecture": (
        "[Tip] For architecture analysis and design review, "
        "try `/wicked-garden:engineering:arch`."
    ),
    "data_analysis": (
        "[Tip] For interactive data analysis with DuckDB, "
        "try `/wicked-garden:data:numbers` or `/wicked-garden:data:analyze`."
    ),
}


def _try_discovery_hint(hint_id: str) -> str | None:
    """Emit a discovery hint if it hasn't been shown this session.

    Returns the hint message, or None if already shown or on any error.
    At most one hint is shown per session to avoid nagging.
    """
    try:
        from _session import SessionState
        state = SessionState.load()
        shown = state.hints_shown or []

        # Cap: at most 2 hints per session total to stay subtle
        if len(shown) >= 2:
            return None

        if hint_id in shown:
            return None

        hint_text = _DISCOVERY_HINTS.get(hint_id)
        if not hint_text:
            return None

        shown.append(hint_id)
        state.update(hints_shown=shown)
        return hint_text
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Handler: Grep / Glob (discovery hint for search commands)
# ---------------------------------------------------------------------------

def _handle_grep_glob(tool_name: str, tool_input: dict) -> dict:
    """On repeated Grep/Glob usage, suggest wicked-garden search commands."""
    hint = _try_discovery_hint("grep_search")
    if hint:
        return {"continue": True, "systemMessage": hint}
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

    # 1. Mark file stale + re-index in brain
    _mark_file_stale(file_path)
    _brain_reindex_file(file_path)

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


def _brain_reindex_file(file_path: str) -> None:
    """Re-index a changed file in the brain FTS5 index. Fails silently.

    Reads the file content and POSTs it to the brain index API so the brain
    stays current as files are edited during the session. Async-safe: uses
    stdlib urllib with a short timeout.
    """
    try:
        import urllib.request
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return
        # Only index text files the brain cares about
        text_ext = {".md", ".txt", ".py", ".js", ".ts", ".jsx", ".tsx", ".sh",
                    ".json", ".yaml", ".yml", ".toml", ".html", ".css", ".mjs"}
        if p.suffix.lower() not in text_ext:
            return
        # Read content (cap at 50KB to avoid slow indexing on huge files)
        content = p.read_text(encoding="utf-8", errors="replace")[:50000]
        if not content.strip():
            return
        # Build a safe chunk ID from the file path
        safe = file_path.lower().replace("/", "-").replace("\\", "-")
        safe = re.sub(r"[^a-z0-9.-]", "-", safe)
        safe = re.sub(r"-+", "-", safe).strip("-")
        chunk_id = f"chunks/extracted/{safe}/chunk-001.md"

        port = _resolve_brain_port()
        payload = json.dumps({
            "action": "index",
            "params": {
                "id": chunk_id,
                "path": chunk_id,
                "content": content,
                "brain_id": "wicked-brain",
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # brain re-index is best-effort, never blocks the hook


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

    Optimized (Issue #312): uses a single SessionState load/save for both
    large-file tracking and framework detection, avoiding redundant disk I/O
    on the highest-frequency tool.

    Always returns {"continue": True} — never blocks reads.
    """
    file_path = (tool_input.get("file_path") or "")
    messages = []

    # --- Quick path-based framework check (no I/O needed) ---
    file_path_lower = file_path.lower()
    detected_frameworks = []
    if file_path_lower:
        for framework, patterns in _FRAMEWORK_PATTERNS.items():
            if any(p in file_path_lower for p in patterns):
                detected_frameworks.append(framework)

    # --- Parse response text for size check ---
    response_text = ""
    try:
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
    except Exception:
        pass

    # --- Single SessionState load/save for both concerns ---
    needs_state = bool(response_text) or bool(detected_frameworks)
    if needs_state:
        try:
            from _session import SessionState
            state = SessionState.load()
            state_dirty = False

            # Large-file-read detection
            if response_text:
                char_count = len(response_text)
                line_count = response_text.count("\n") + 1

                cumulative = (state.read_bytes_total or 0) + char_count
                warn_count = state.read_large_warn_count or 0

                if line_count >= _READ_LINE_THRESHOLD or char_count >= _READ_CHAR_THRESHOLD:
                    warn_count += 1
                    short_path = Path(file_path).name if file_path else "unknown"

                    if cumulative >= _CUMULATIVE_WARN_THRESHOLD and warn_count > 2:
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

                state.read_bytes_total = cumulative
                state.read_large_warn_count = warn_count
                state_dirty = True

            # Framework detection (merged into same state load)
            if detected_frameworks:
                existing = state.detected_frameworks or []
                combined = list(set(existing + detected_frameworks))
                if combined != existing:
                    state.detected_frameworks = combined
                    state_dirty = True

            if state_dirty:
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
    """Handle Skill PostToolUse: mem:store compliance reset + pull-model tracking.

    1. Reset memory_compliance_escalations when a mem:store skill call succeeds.
    2. Track wicked-brain:query/search calls for pull-model calibration (Issue #416).
    """
    skill = (tool_input.get("skill") or "").lower()

    # Pull-model tracking (Issue #416): increment pull_count when the model
    # calls wicked-brain:query or wicked-brain:search. This feeds the
    # calibration stats shown in the next turn's pull directive.
    _PULL_SKILLS = ("wicked-brain:query", "wicked-brain:search")
    if any(s in skill for s in _PULL_SKILLS):
        try:
            from _session import SessionState
            state = SessionState.load()
            state.update(pull_count=(state.pull_count or 0) + 1)
        except Exception:
            pass  # fail open

    # Memory compliance reset
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
# Handler: Bash async — consensus gate (Issue #368, Tier 2)
# ---------------------------------------------------------------------------
# This handler is invoked from the ASYNC PostToolUse/Bash hook entry.
# It fires on every Bash call but fast-exits unless the command is a
# phase_manager.py approve invocation on a high-complexity project.
#
# When matched, it runs the full consensus evaluation synchronously within
# this process (which itself runs async/non-blocking to the agent).
# The result is written to phases/{phase}/reviewer-report.md for the
# PreToolUse Tier 1 hook to check on the NEXT phase's approve call.
# ---------------------------------------------------------------------------

_REVIEWER_REPORT_HEADER = """\
---
verdict: {verdict}
evidence_items_checked: {evidence_items_checked}
reviewer: consensus-gate
reviewed_at: {reviewed_at}
agreement_ratio: {agreement_ratio}
findings: {findings}
conditions: {conditions}
---
"""

_REVIEWER_REPORT_PENDING = """\
---
verdict: pending
evidence_items_checked: 0
reviewer: consensus-gate
reviewed_at: {reviewed_at}
agreement_ratio: 0.0
findings: []
conditions: []
note: "consensus evaluation failed or was skipped — will be re-evaluated on next approve"
---
"""


def _parse_project_phase_from_command(command: str):
    """Extract project name and optional --phase from a phase_manager.py approve command.

    Returns (project_name, phase) tuple. phase may be None if --phase not given.
    Example command:
      sh ...phase_manager.py my-project approve --phase design
    """
    import shlex
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    project_name = None
    phase = None

    # Find index of phase_manager.py in tokens
    pm_idx = next(
        (i for i, t in enumerate(tokens) if "phase_manager.py" in t),
        None,
    )
    if pm_idx is None:
        return None, None

    # Tokens after phase_manager.py: project action [--phase name] [--other flags]
    after = tokens[pm_idx + 1:]

    # after[0] = project name (positional arg comes before action in phase_manager CLI)
    # Format is: phase_manager.py <project> <action> [flags]
    if len(after) >= 2:
        project_name = after[0]
        # after[1] should be "approve"
        # Look for --phase flag
        for i, tok in enumerate(after[2:], start=2):
            if tok == "--phase" and i + 1 < len(after):
                phase = after[i + 1]
                break

    # Safety: validate project name
    if project_name:
        import re as _re
        if not _re.match(r'^[a-zA-Z0-9_-]{1,64}$', project_name):
            project_name = None

    return project_name, phase


def _load_project_for_consensus(project_name: str):
    """Load project state dict for consensus evaluation.

    Returns (project_state_dict, project_dir_path) or (None, None) on failure.
    project_state_dict contains at minimum 'complexity_score'.
    """
    try:
        scripts_crew = _PLUGIN_ROOT / "scripts" / "crew"
        if str(scripts_crew) not in sys.path:
            sys.path.insert(0, str(scripts_crew))

        from phase_manager import load_project_state, get_project_dir
        state = load_project_state(project_name)
        if state is None:
            return None, None

        project_dir = get_project_dir(project_name)

        # Convert dataclass to dict (handles both dataclass and plain dict)
        try:
            import dataclasses
            if dataclasses.is_dataclass(state):
                state_dict = dataclasses.asdict(state)
            else:
                state_dict = dict(state)
        except Exception:
            state_dict = {"complexity_score": getattr(state, "complexity_score", 0)}

        return state_dict, project_dir
    except Exception:
        return None, None


def _resolve_phase_for_consensus(project_state_dict: dict, explicit_phase) -> str:
    """Resolve which phase was just approved.

    Uses explicit_phase if provided, else current_phase from project state.
    """
    if explicit_phase:
        return str(explicit_phase)

    # project_state_dict may have current_phase directly or nested
    phase = project_state_dict.get("current_phase")
    if phase:
        return str(phase)

    return "unknown"


def _load_phases_config() -> dict:
    """Load phases.json from .claude-plugin/. Returns {} on failure."""
    try:
        phases_file = _PLUGIN_ROOT / ".claude-plugin" / "phases.json"
        if phases_file.exists():
            return json.loads(phases_file.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _build_reviewer_report_yaml(verdict: str, consensus_result: dict) -> str:
    """Build the YAML frontmatter block for reviewer-report.md from consensus result."""
    agreement_ratio = consensus_result.get("agreement_ratio", 0.0)
    try:
        agreement_ratio = round(float(agreement_ratio), 4)
    except (TypeError, ValueError):
        agreement_ratio = 0.0

    # Collect findings from consensus_points
    findings_raw = consensus_result.get("consensus_points", [])
    findings_list = []
    for fp in findings_raw[:10]:  # cap at 10
        if isinstance(fp, dict):
            text = fp.get("point", fp.get("description", str(fp)))
        else:
            text = str(fp)
        # YAML-safe single-line entry
        findings_list.append(
            '  - "' + text[:200].replace('"', "'") + '"'
        )

    # Collect conditions from consensus result
    conditions_raw = consensus_result.get("conditions", []) or []
    conditions_list = []
    for cond in conditions_raw[:10]:
        if isinstance(cond, dict):
            text = cond.get("description", str(cond))
        else:
            text = str(cond)
        conditions_list.append(
            '  - "' + text[:200].replace('"', "'") + '"'
        )

    evidence_count = len(findings_raw) + len(
        consensus_result.get("dissenting_views", []) or []
    )

    findings_yaml = "[\n" + "\n".join(findings_list) + "\n]" if findings_list else "[]"
    conditions_yaml = "[\n" + "\n".join(conditions_list) + "\n]" if conditions_list else "[]"

    return _REVIEWER_REPORT_HEADER.format(
        verdict=verdict.lower(),
        evidence_items_checked=evidence_count,
        reviewed_at=_now_iso(),
        agreement_ratio=agreement_ratio,
        findings=findings_yaml,
        conditions=conditions_yaml,
    )


def _write_reviewer_report(phase_dir: "Path", verdict: str, consensus_result: dict) -> None:
    """Write or append consensus findings to reviewer-report.md.

    If the file already exists (written by the independent-reviewer agent from #367),
    append the consensus section rather than overwriting it.
    """
    report_path = phase_dir / "reviewer-report.md"
    yaml_block = _build_reviewer_report_yaml(verdict, consensus_result)

    if report_path.exists():
        # Append consensus section to existing report
        existing = report_path.read_text(encoding="utf-8")
        separator = "\n\n---\n## Consensus Gate Evaluation\n\n"
        report_path.write_text(
            existing + separator + yaml_block,
            encoding="utf-8",
        )
    else:
        # Create new report with full frontmatter
        phase_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(yaml_block, encoding="utf-8")


def _write_pending_reviewer_report(phase_dir: "Path") -> None:
    """Write a pending reviewer-report.md when consensus evaluation fails.

    Only writes if no report exists yet — never overwrites a real result.
    """
    report_path = phase_dir / "reviewer-report.md"
    if report_path.exists():
        return  # Don't clobber an existing report

    try:
        phase_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            _REVIEWER_REPORT_PENDING.format(reviewed_at=_now_iso()),
            encoding="utf-8",
        )
    except Exception:
        pass


def _handle_bash_consensus(tool_input: dict, tool_response) -> dict:
    """Async consensus gate — fires after phase_manager.py approve on high-complexity projects.

    FAST EARLY-EXIT: Returns immediately if the Bash command is not a
    phase_manager.py approve call (the vast majority of Bash invocations).

    On match:
    1. Parse project name and phase from the command.
    2. Load project state. If complexity < 5, skip.
    3. Invoke consensus_gate.evaluate_consensus_gate() directly (this process is async).
    4. Write result to phases/{phase}/reviewer-report.md.
    5. If evaluation fails, write a pending report. Never block.

    """
    # --- Fast early-exit: only act on phase_manager.py approve ---
    command = (tool_input.get("command") or "")
    if "phase_manager.py" not in command or "approve" not in command:
        return {"continue": True}

    # Verify the command contains both keywords in the right order
    # (avoid false matches on e.g. "grep approve phase_manager.py")
    pm_pos = command.find("phase_manager.py")
    approve_pos = command.find("approve", pm_pos)
    if pm_pos < 0 or approve_pos < 0:
        return {"continue": True}

    # --- Parse project name and phase from command ---
    project_name, explicit_phase = _parse_project_phase_from_command(command)
    if not project_name:
        return {"continue": True}

    # --- Load project state ---
    project_state_dict, project_dir = _load_project_for_consensus(project_name)
    if project_state_dict is None or project_dir is None:
        return {"continue": True}

    # --- Complexity gate: skip if complexity < 5 ---
    try:
        complexity = int(project_state_dict.get("complexity_score") or 0)
    except (TypeError, ValueError):
        complexity = 0

    if complexity < 5:
        return {"continue": True}

    # --- Determine which phase was just approved ---
    phase = _resolve_phase_for_consensus(project_state_dict, explicit_phase)
    phase_dir = project_dir / "phases" / phase

    # --- Load phases config and check if consensus is configured for this phase ---
    phases_config = _load_phases_config()
    phase_config = phases_config.get(phase, {})
    proposers = phase_config.get("consensus_proposers", [])
    consensus_threshold = phase_config.get("consensus_threshold")

    # If phase has no consensus config, check for a generic threshold of 5
    if not proposers:
        # Default proposers for unconfigured phases at high complexity
        proposers = ["engineering", "quality-engineering", "product"]
    if consensus_threshold is None:
        consensus_threshold = 5

    # Final consensus threshold check
    try:
        if complexity < int(consensus_threshold):
            return {"continue": True}
    except (TypeError, ValueError):
        pass

    # --- Run consensus evaluation ---
    try:
        scripts_crew = _PLUGIN_ROOT / "scripts" / "crew"
        if str(scripts_crew) not in sys.path:
            sys.path.insert(0, str(scripts_crew))

        import consensus_gate as _cg

        # Inject proposers into phases_config if not present (default fallback)
        if phase not in phases_config:
            phases_config[phase] = {
                "consensus_threshold": consensus_threshold,
                "consensus_proposers": proposers,
                "strong_dissent_blocks": True,
                "confidence_threshold": 0.7,
            }

        consensus_result = _cg.evaluate_consensus_gate(
            project_dir=str(project_dir),
            phase=phase,
            project_state=project_state_dict,
            phases_config=phases_config,
        )

        if consensus_result is None:
            # No gate-result.json to evaluate — not an error, just nothing to do
            return {"continue": True}

        verdict = consensus_result.get("result", "pending").lower()
        if verdict not in ("approved", "conditional", "rejected"):
            # Map gate result codes to reviewer-report verdicts
            verdict_map = {"approve": "approved", "reject": "rejected",
                           "conditional": "conditional"}
            verdict = verdict_map.get(verdict, "pending")

        _write_reviewer_report(phase_dir, verdict, consensus_result)
        _log("crew", "info", "consensus_gate.complete",
             detail={"project": project_name, "phase": phase, "verdict": verdict,
                     "complexity": complexity})

    except Exception as exc:
        # Fail-open: write pending report, log error, never crash
        try:
            _write_pending_reviewer_report(phase_dir)
            _log("crew", "warn", "consensus_gate.error",
                 ok=False, detail={"project": project_name, "phase": phase,
                                   "error": str(exc)[:200]})
        except Exception:
            pass

    return {"continue": True}


# ---------------------------------------------------------------------------
# Handler: Bash (general activity tracking)
# ---------------------------------------------------------------------------

def _handle_bash(tool_input: dict, tool_response) -> dict:
    """Track bash activity + detect usage patterns for discovery hints."""
    messages = []
    try:
        from _session import SessionState
        state = SessionState.load()
        bash_count = (getattr(state, "bash_count", None) or 0) + 1
        state.update(bash_count=bash_count)
        state.save()
    except Exception:
        pass

    # --- Discovery hints from bash command patterns ---
    command = (tool_input.get("command") or "").lower()
    if command:
        # Manual grep/rg usage → suggest wicked-garden search
        if any(kw in command for kw in ["grep ", "rg ", "ripgrep", "ag "]):
            hint = _try_discovery_hint("grep_search")
            if hint:
                messages.append(hint)

    result = {"continue": True}
    if messages:
        result["systemMessage"] = "\n".join(messages)
    return result


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
# Turn progress visibility (Issue #323)
# ---------------------------------------------------------------------------

_TURN_STATUS_THRESHOLD_SECS = 120  # 2 minutes


def _check_turn_progress(tool_name: str) -> str | None:
    """Increment turn tool count and return a status note if the turn is long-running.

    Returns a status string when elapsed time exceeds _TURN_STATUS_THRESHOLD_SECS,
    or None if the turn is still short or state is unavailable.
    """
    try:
        from _session import SessionState
        state = SessionState.load()

        # Increment tool count
        new_count = (state.turn_tool_count or 0) + 1
        state.update(turn_tool_count=new_count)

        # Check elapsed time
        turn_start = state.turn_start_ts
        if not turn_start:
            return None

        start_dt = datetime.fromisoformat(turn_start.replace("Z", "+00:00"))
        now_dt = datetime.now(timezone.utc)
        elapsed_secs = (now_dt - start_dt).total_seconds()

        if elapsed_secs < _TURN_STATUS_THRESHOLD_SECS:
            return None

        elapsed_mins = int(elapsed_secs / 60)

        # Build status note
        parts = [
            f"[Status] This turn has been running for {elapsed_mins} "
            f"minute{'s' if elapsed_mins != 1 else ''}. "
            f"{new_count} tool call{'s' if new_count != 1 else ''} so far."
        ]

        # Include active crew phase/specialist if available
        active_project = state.active_project
        if active_project and isinstance(active_project, dict):
            phase = active_project.get("current_phase", "")
            specialist = active_project.get("current_specialist", "")
            if phase:
                detail = f"Active crew phase: {phase}"
                if specialist:
                    detail += f" ({specialist})"
                parts.append(detail)

        return " ".join(parts)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Latency profiling (Issue #312) — cumulative PostToolUse timing in SessionState
# ---------------------------------------------------------------------------

def _record_latency(handler_label: str, handler_ms: int, total_ms: int) -> None:
    """Accumulate PostToolUse latency in SessionState for profiling.

    Updates three fields:
      - post_tool_total_ms:    cumulative wall-clock time across all invocations
      - post_tool_call_count:  total invocation count
      - post_tool_handler_ms:  per-handler cumulative ms (keyed by handler_label)

    Fails silently — never crashes the hook.
    """
    try:
        from _session import SessionState
        state = SessionState.load()
        state.post_tool_total_ms = (state.post_tool_total_ms or 0) + total_ms
        state.post_tool_call_count = (state.post_tool_call_count or 0) + 1
        handler_breakdown = state.post_tool_handler_ms or {}
        handler_breakdown[handler_label] = handler_breakdown.get(handler_label, 0) + handler_ms
        state.post_tool_handler_ms = handler_breakdown
        state.save()
    except Exception:
        pass


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
        _t_trace = time.monotonic()
        _write_trace(payload)
        _trace_ms = int((time.monotonic() - _t_trace) * 1000)

        # --- Route by event type and tool name ---
        handler_label = tool_name or "unknown"
        _t_handler = time.monotonic()

        # PostToolUseFailure path
        if has_error:
            handler_label = "failure"
            result = _handle_failure(payload)
        # Task-management tools — native task store is the source of truth.
        # PreToolUse validates metadata; PostToolUse only runs the mismatch
        # detector for TaskUpdate (status/subject/metadata consistency).
        elif tool_name in ("TaskCreate", "TaskUpdate", "TodoWrite"):
            handler_label = "TaskCreate|TaskUpdate|TodoWrite"
            if tool_name == "TaskUpdate":
                _handle_task_update_mismatch(tool_input)
            result = {"continue": True}
        # Write / Edit tools (async — quick operations only)
        elif tool_name in ("Write", "Edit"):
            handler_label = "Write|Edit"
            result = _handle_write_edit(tool_input)
        # Task (subagent dispatch + permission failure detection)
        elif tool_name == "Task":
            tool_response = payload.get("tool_response", {})
            result = _handle_task_dispatch(tool_input, tool_response)
        # Read (large-file warning + framework detection)
        elif tool_name == "Read":
            tool_response = payload.get("tool_response", "")
            result = _handle_read(tool_input, tool_response)
        # Bash (activity tracking + discovery hints + async consensus gate)
        elif tool_name == "Bash":
            tool_response = payload.get("tool_response", {})
            result = _handle_bash(tool_input, tool_response)
            # Tier 2 consensus gate (Issue #368) — fast-exits unless phase_manager approve
            _handle_bash_consensus(tool_input, tool_response)
        # Skill (mem:store escalation counter reset)
        elif tool_name == "Skill":
            result = _handle_skill(tool_input)
        # Grep / Glob (discovery hints for search commands)
        elif tool_name in ("Grep", "Glob"):
            handler_label = "Grep|Glob"
            result = _handle_grep_glob(tool_name, tool_input)
        # All other tools — pass through
        else:
            handler_label = "passthrough"
            result = {"continue": True}

        _handler_ms = int((time.monotonic() - _t_handler) * 1000)

        # Turn progress visibility (Issue #323): append status note on long turns
        _t_turn = time.monotonic()
        turn_status = _check_turn_progress(tool_name)
        _turn_ms = int((time.monotonic() - _t_turn) * 1000)
        if turn_status:
            existing_msg = result.get("systemMessage", "")
            if existing_msg:
                result["systemMessage"] = existing_msg + "\n" + turn_status
            else:
                result["systemMessage"] = turn_status

        # --- Latency profiling (Issue #312) ---
        _total_ms = int((time.monotonic() - _t0) * 1000)
        _record_latency(handler_label, _handler_ms, _total_ms)

        _log("posttool", "verbose", "hook.latency", ms=_total_ms, detail={
            "tool": tool_name,
            "handler": handler_label,
            "handler_ms": _handler_ms,
            "trace_ms": _trace_ms,
            "turn_progress_ms": _turn_ms,
            "total_ms": _total_ms,
        })

        _log("posttool", "debug", "hook.end", ms=_total_ms)
        print(json.dumps(result))

    except Exception as e:
        print(f"[wicked-garden] post_tool error: {e}", file=sys.stderr)
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
