#!/usr/bin/env python3
"""
SessionStart hook — wicked-garden unified bootstrap.

Consolidates: crew session_start, mem session_start,
search session_start, smaht session_start.

Flow:
1. Read config from ~/.something-wicked/wicked-garden/config.json
2. If missing or setup_complete=false: emit setup instructions, return
3. Load dynamic agents
4. Load active crew project
5. Run memory decay
6. Check onboarding status → imperative directive if needed
7. Assemble session briefing
8. Return {"continue": true, "systemMessage": "<briefing>"}

Always fails open — any unhandled exception returns {"continue": true}.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add shared scripts directory to path so hook can import shared modules
_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))

from _brain_port import resolve_port

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
# Shared module imports — each wrapped so missing modules degrade gracefully
# ---------------------------------------------------------------------------

def _load_session_state():
    try:
        from _session import SessionState
        return SessionState.load()
    except Exception:
        return None


def _save_session_state(state):
    try:
        state.save()
    except Exception:
        pass


def _check_prior_guard_findings():
    """Load the most recent guard-pipeline findings and render a briefing note.

    Reads ${TMPDIR}/wicked-guard/*/findings.json files written by stop.py's
    guard pipeline (Issue #448).  Returns a briefing string or None.

    Fail-open — never blocks bootstrap.
    """
    try:
        import tempfile
        guard_root = Path(tempfile.gettempdir()) / "wicked-guard"
        if not guard_root.is_dir():
            return None

        newest = None  # type: ignore
        newest_mtime = 0.0
        for session_dir in guard_root.iterdir():
            if not session_dir.is_dir():
                continue
            f = session_dir / "findings.json"
            if not f.is_file():
                continue
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            if mt > newest_mtime:
                newest_mtime = mt
                newest = f

        if newest is None:
            return None

        # Only surface if report is recent (<24h) — stale reports are noise.
        if (time.time() - newest_mtime) > 86400:
            return None

        with open(newest, "r", encoding="utf-8") as fh:
            report = json.load(fh)

        total = int(report.get("total_findings", 0) or 0)
        if total == 0:
            return None

        by_sev = report.get("findings_by_severity", {}) or {}
        profile = report.get("profile", "?")
        lines = [
            f"[Guard] Last session's {profile} guard pipeline surfaced {total} finding(s) "
            f"(block={by_sev.get('block', 0)} warn={by_sev.get('warn', 0)} info={by_sev.get('info', 0)}). "
            f"Report: {newest}"
        ]
        # Show up to 5 non-info findings for visibility
        shown = 0
        for check in report.get("checks", []) or []:
            for f in check.get("findings", []) or []:
                if shown >= 5:
                    break
                sev = f.get("severity", "info")
                if sev == "info":
                    continue
                msg = f.get("message", "")[:140]
                loc = ""
                if f.get("file"):
                    loc = f" @ {f['file']}"
                    if f.get("line"):
                        loc += f":{f['line']}"
                lines.append(f"  - [{sev}] {f.get('rule_id', '?')}: {msg}{loc}")
                shown += 1
            if shown >= 5:
                break
        return "\n".join(lines)
    except Exception:
        return None


def _probe_plugin_readiness():
    """Dynamically discover installed plugins and probe their hook readiness.

    Scans the plugin cache for installed plugins (excluding ourselves), finds
    their hooks.json, and runs a lightweight test of each hook command.
    Returns a list of dicts for plugins whose hooks fail, e.g.:
        [{"name": "semgrep", "hook": "PostToolUse", "error": "No SEMGREP_APP_TOKEN found"}]

    Runs with a tight timeout (2s per probe) and fails open — never blocks bootstrap.
    """
    unready = []
    try:
        # Discover plugin cache directories
        cache_dirs = [
            Path.home() / ".claude" / "plugins" / "cache",
            Path(os.environ.get("CLAUDE_CONFIG_DIR", "")) / "plugins" / "cache" if os.environ.get("CLAUDE_CONFIG_DIR") else None,
        ]
        # Also check alt-configs location
        alt_config = Path.home() / "alt-configs" / ".claude" / "plugins" / "cache"
        if alt_config.exists():
            cache_dirs.append(alt_config)

        our_name = "wicked-garden"
        seen_plugins = set()

        for cache_dir in cache_dirs:
            if cache_dir is None or not cache_dir.exists():
                continue
            # Walk plugin org/name directories
            for org_dir in cache_dir.iterdir():
                if not org_dir.is_dir():
                    continue
                for plugin_dir in org_dir.iterdir():
                    if not plugin_dir.is_dir():
                        continue
                    # Find the actual plugin root (may be versioned)
                    hooks_candidates = list(plugin_dir.rglob("hooks/hooks.json"))
                    for hooks_file in hooks_candidates:
                        plugin_root = hooks_file.parent.parent
                        # Read plugin.json to get name
                        pj = plugin_root / ".claude-plugin" / "plugin.json"
                        if not pj.exists():
                            pj = plugin_root / "plugin.json"
                        plugin_name = plugin_dir.name
                        if pj.exists():
                            try:
                                plugin_name = json.loads(pj.read_text()).get("name", plugin_dir.name)
                            except Exception:
                                pass

                        # Skip ourselves and already-checked plugins
                        if plugin_name == our_name or plugin_name in seen_plugins:
                            continue
                        seen_plugins.add(plugin_name)

                        # Read their hooks.json
                        try:
                            hooks_data = json.loads(hooks_file.read_text())
                        except Exception:
                            continue

                        # Probe each hook command with a dry-run (empty stdin, 2s timeout)
                        for event, entries in hooks_data.get("hooks", {}).items():
                            for entry in entries:
                                for hook in entry.get("hooks", []):
                                    cmd = hook.get("command", "")
                                    if not cmd or hook.get("type") != "command":
                                        continue
                                    # Extract the base binary name for the probe
                                    parts = cmd.split()
                                    if not parts:
                                        continue
                                    binary = parts[0]
                                    # Skip if binary references plugin root (needs env var)
                                    if "${CLAUDE_PLUGIN_ROOT}" in cmd:
                                        continue
                                    # Quick probe: just check if the binary is available and
                                    # runs without error when given empty input
                                    try:
                                        result = subprocess.run(
                                            parts + ["--help"] if len(parts) == 1 else parts[:2] + ["--version"],
                                            capture_output=True, text=True, timeout=2,
                                            input="",
                                        )
                                        # If the command itself isn't found, skip — that's a
                                        # different problem (missing install, not unready)
                                    except FileNotFoundError:
                                        continue  # Binary not installed — not our problem
                                    except subprocess.TimeoutExpired:
                                        continue  # Timed out — assume it works but is slow
                                    except Exception:
                                        continue

                                    # For env-var-gated tools, check common auth patterns
                                    # by looking at stderr for auth/token messages
                                    if result.returncode != 0:
                                        stderr = result.stderr.lower()
                                        auth_signals = ["token", "login", "auth", "credential", "api_key", "api key"]
                                        if any(sig in stderr for sig in auth_signals):
                                            # Extract a short error message
                                            err_lines = [l.strip() for l in result.stderr.strip().split("\n") if l.strip()]
                                            short_err = err_lines[-1][:120] if err_lines else "auth required"
                                            unready.append({
                                                "name": plugin_name,
                                                "hook": event,
                                                "command": cmd[:80],
                                                "error": short_err,
                                            })
                                            break  # One failure per plugin is enough
                                    break  # Only test first hook per event
                            if any(u["name"] == plugin_name for u in unready):
                                break  # Already flagged this plugin
    except Exception:
        pass  # Fail open — probe errors never block bootstrap
    return unready


def _suggest_auth_fix(probe_result):
    """Dynamically extract or infer an auth fix command from a probe failure.

    Looks for common patterns in the error message (e.g., "please login", "run X login",
    "set SOME_TOKEN") and returns the fix command. No hardcoded tool list — works by
    parsing the error text that the tool itself produced.

    Returns a fix command string, or None if no fix can be inferred.
    """
    error = probe_result.get("error", "")
    name = probe_result.get("name", "")
    cmd_base = probe_result.get("command", "").split()[0] if probe_result.get("command") else name

    # Pattern 1: error says "run '<tool> login'" or "please login"
    # e.g., "please login to Semgrep" → "semgrep login"
    import re
    login_match = re.search(r"(?:run|please)\s+['\"]?(\w[\w-]*\s+(?:login|auth\s+login))['\"]?", error, re.IGNORECASE)
    if login_match:
        return login_match.group(1)

    # Pattern 2: error mentions a specific env var
    # e.g., "No SEMGREP_APP_TOKEN found" → "export SEMGREP_APP_TOKEN=<your-token>"
    env_match = re.search(r"(?:no|missing|set|need)\s+(\w+_(?:TOKEN|KEY|SECRET|API_KEY))\b", error, re.IGNORECASE)
    if env_match:
        var = env_match.group(1)
        return f"export {var}=<your-token>  # or: {cmd_base} login"

    # Pattern 3: generic "login" or "auth" mention
    if "login" in error.lower() or "auth" in error.lower():
        return f"{cmd_base} login"

    return None


def _load_agents():
    """Load dynamic agents from disk. Returns (agent_count, agents_dict)."""
    try:
        from _agents import AgentLoader
        loader = AgentLoader()
        agents = loader.load_disk_agents(_PLUGIN_ROOT / "agents")
        return len(agents), agents
    except Exception as e:
        print(f"[wicked-garden] agent load error: {e}", file=sys.stderr)
        return 0, {}


def _resolve_capabilities(agents, config=None):
    """Run capability resolution for pre-loaded agents.

    Returns dict[agent_name, tool_list] or empty dict on any error.
    Fails open — never blocks bootstrap.
    """
    try:
        from _capability_resolver import resolve_all_agents, discover_mcp_servers

        mcp_servers = discover_mcp_servers()
        return resolve_all_agents(agents, config, mcp_servers)
    except Exception as e:
        print(f"[wicked-garden] capability resolution error: {e}", file=sys.stderr)
        return {}


def _find_active_crew_project(workspace: str = ""):
    """Return (project_data, project_name) for most recently updated active crew project
    scoped to the given workspace.

    Only returns projects whose ``workspace`` field matches the current folder.
    Projects without a workspace field (legacy) are never auto-selected.

    Uses DomainStore for consistent data access. Falls back to filesystem
    scan if DomainStore fails (legacy compat for one release).
    """
    try:
        from _domain_store import DomainStore
        ds = DomainStore("wicked-crew", hook_mode=True)
        projects = ds.list("projects") or []
        # Sort by updated_at descending, return first non-archived, non-complete
        # that matches the current workspace
        for p in sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True):
            if p.get("archived"):
                continue
            # Workspace scoping — skip projects from other workspaces
            if workspace and p.get("workspace", "") != workspace:
                continue
            phase = p.get("current_phase", "")
            if phase and phase != "complete":
                return p, p.get("name")
        return None, None
    except Exception:
        pass

    # Legacy fallback: direct filesystem scan (remove after one release)
    return _find_active_crew_project_legacy(workspace)


def _find_active_crew_project_legacy(workspace: str = ""):
    """Filesystem-based crew project scan. Legacy fallback."""
    projects_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects"
    if not projects_dir.exists():
        return None, None

    for pf in sorted(
        projects_dir.glob("*/project.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            data = json.loads(pf.read_text())
            if data.get("archived"):
                continue
            # Workspace scoping — skip projects from other workspaces
            if workspace and data.get("workspace", "") != workspace:
                continue
            phase = data.get("current_phase", "")
            if phase and phase != "complete":
                return data, data.get("name", pf.parent.name)
        except (json.JSONDecodeError, OSError):
            continue

    return None, None


def _brain_api(action, params=None, timeout=3):
    """Call brain API. Returns parsed JSON or None."""
    try:
        import urllib.request
        port = resolve_port()
        payload = json.dumps({"action": action, "params": params or {}}).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _run_memory_decay():
    """Run memory decay maintenance via brain lint. Returns a summary string or None."""
    try:
        result = _brain_api("lint", {}, timeout=5)
        if result and (result.get("archived", 0) > 0 or result.get("deleted", 0) > 0):
            return f"Memory: {result.get('archived', 0)} archived, {result.get('deleted', 0)} cleaned"
        return None
    except Exception:
        return None


def _check_search_staleness():
    """Check brain index health. Returns a briefing note or None.

    Brain is the unified knowledge layer — no legacy SQLite fallback.
    Fails open — any exception returns None so the session always continues.
    """
    try:
        import urllib.request
        port = resolve_port()
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=json.dumps({"action": "stats", "params": {}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
            total = stats.get("total", 0)
            if total == 0:
                return "Brain index is empty — run `wicked-brain:ingest` to index your codebase"
            return None  # Brain is healthy

    except Exception:
        return "Brain server is not reachable — start wicked-brain to enable context assembly"


def _check_onboarding_status():
    """Check if the current project has been onboarded (search index + memories).

    Returns (has_index, has_memories, directive_or_none).
    Both checks fail open — if we can't determine status, assume onboarded.
    """
    project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
    cwd = str(Path.cwd())

    has_index = False
    has_memories = False  # default: assume not onboarded (fail-closed for new projects)

    # Check search index — brain is the knowledge layer
    try:
        import urllib.request
        import urllib.error
        port = resolve_port()
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=json.dumps({"action": "stats", "params": {}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
            if stats.get("total", 0) > 0:
                has_index = True
    except Exception:
        pass  # brain unavailable — covered by _check_brain_dependency directive

    # Check for any stored memories (broad: any brain result, not just /mem- paths).
    # If brain has an index with content (has_index=True), that alone is sufficient
    # evidence that the project has been set up — skip the memory search.
    if has_index:
        has_memories = True  # indexed brain content ≡ project was onboarded
    else:
        try:
            result = _brain_api("search", {"query": "project memory onboarding", "limit": 5}, timeout=3)
            if result and isinstance(result, list) and result:
                has_memories = True  # any search result = memories exist
            elif result and isinstance(result, dict) and result.get("results"):
                has_memories = True
            else:
                has_memories = False  # empty result from healthy brain → not onboarded
        except Exception:
            has_memories = True  # fail open on exception — assume onboarded
            print("[wicked-garden] onboarding check: brain API error, assuming onboarded", file=sys.stderr)

    directive = None
    if not has_index and not has_memories:
        # Neither index nor memories → first-time setup required
        directive = (
            f"[Action Required] Project '{project}' has not been onboarded.\n"
            "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
            "to launch the interactive onboarding wizard.\n"
            "Do NOT ask the user for confirmation — invoke the skill now.\n"
            "Do NOT respond with text first — invoke the skill as your first action."
        )
    elif not has_index and has_memories:
        # Memories exist but brain index is gone → rebuild only
        directive = (
            f"[Onboarding] IMPORTANT: Project '{project}' has memories but no search index. "
            "You MUST run /wicked-garden:search:index now to build the search index."
        )

    return has_index, has_memories, directive


def _read_config():
    """Read config from ~/.something-wicked/wicked-garden/config.json."""
    config_path = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
    if not config_path.exists():
        return None
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Memory behavior instructions (injected every session)
# ---------------------------------------------------------------------------

_MEMORY_INSTRUCTIONS = (
    "[Memory] This project uses wicked-garden memory for persistence. "
    "Never write to MEMORY.md directly — use /wicked-garden:mem:store. "
    "MEMORY.md is auto-generated and read-only. "
    "When editing CLAUDE.md or AGENTS.md, keep both files in sync — "
    "a PostToolUse hook will remind you. "
    "Memory uses 3 tiers: semantic (durable project knowledge, prioritized in recall), "
    "episodic (sprint-level patterns), working (transient session context, auto-consolidated). "
    "Use --tier semantic for decisions and permanent knowledge."
)

_DANGEROUS_MODE_WARNING = (
    "[Question Mode] Dangerous mode is active (skipDangerousModePermissionPrompt). "
    "AskUserQuestion is BROKEN in this mode — it auto-completes with empty answers. "
    "You MUST use plain text questions instead: present numbered options, "
    "then STOP and wait for the user to reply before proceeding."
)


# ---------------------------------------------------------------------------
# Dangerous mode detection
# ---------------------------------------------------------------------------

def _detect_dangerous_mode():
    """Check if Claude Code is running in dangerous mode.

    Dangerous mode (skipDangerousModePermissionPrompt=true) breaks
    AskUserQuestion by auto-completing it with empty answers.
    """
    try:
        settings_path = Path.home() / ".claude" / "settings.json"
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            return bool(settings.get("skipDangerousModePermissionPrompt"))
    except Exception:
        pass
    return False



# ---------------------------------------------------------------------------
# wicked-brain dependency check
# ---------------------------------------------------------------------------

def _check_brain_dependency():
    """Check whether the wicked-brain plugin is installed.

    Scans ~/.claude/settings.json and .claude/settings.json (project-level)
    for 'wicked-brain' in their enabledPlugins keys.

    If found:
        - Returns (True, None) — no briefing note needed.
        - Also attempts a lightweight server health probe on the default port
          and returns (True, note) where note describes the offline state if
          the server is not reachable.

    If NOT found:
        - Returns (False, note) — note contains the install instruction.

    Always fails open — any exception returns (None, None) so the session
    is never blocked.
    """
    try:
        # Settings file locations to check (global first, then project-local)
        settings_candidates = [
            Path.home() / ".claude" / "settings.json",
            Path(".claude") / "settings.json",
        ]

        # Also honour CLAUDE_CONFIG_DIR if set
        config_dir_env = os.environ.get("CLAUDE_CONFIG_DIR")
        if config_dir_env:
            settings_candidates.append(Path(config_dir_env) / "settings.json")

        brain_installed = False

        # Check 1: enabledPlugins in settings.json (plugin-style install)
        for settings_path in settings_candidates:
            try:
                if not settings_path.exists():
                    continue
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                enabled = settings.get("enabledPlugins", {})
                if isinstance(enabled, dict) and "wicked-brain" in enabled:
                    brain_installed = True
                    break
                if isinstance(enabled, list) and "wicked-brain" in enabled:
                    brain_installed = True
                    break
            except (json.JSONDecodeError, OSError):
                continue

        # Check 2: loose skill installs at ~/.claude/skills/wicked-brain-*
        # Users can install wicked-brain skills directly without the plugin wrapper.
        if not brain_installed:
            try:
                skills_dir = Path.home() / ".claude" / "skills"
                if skills_dir.exists():
                    for entry in skills_dir.iterdir():
                        if entry.is_dir() and entry.name.startswith("wicked-brain"):
                            brain_installed = True
                            break
            except OSError:
                pass  # fail open

        # Check 3: CLAUDE_CONFIG_DIR skills directory
        if not brain_installed and config_dir_env:
            try:
                alt_skills_dir = Path(config_dir_env) / "skills"
                if alt_skills_dir.exists():
                    for entry in alt_skills_dir.iterdir():
                        if entry.is_dir() and entry.name.startswith("wicked-brain"):
                            brain_installed = True
                            break
            except OSError:
                pass  # fail open

        if not brain_installed:
            note = (
                "[wicked-brain] REQUIRED but not installed.\n"
                "Install now: claude plugin install wicked-brain --scope project\n"
                "wicked-brain provides the memory, search, and context assembly that "
                "wicked-garden depends on — it cannot function without it."
            )
            return False, note

        # wicked-brain is installed — optionally probe server health
        # Use a short timeout so we never block the hook budget
        server_note = None
        try:
            import urllib.request
            import urllib.error

            # Resolve brain port: env var → project brain config → root config → 4242
            port = resolve_port()
            url = f"http://localhost:{port}/api"
            req = urllib.request.Request(
                url,
                data=json.dumps({"action": "health"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1) as resp:
                pass  # Server responded — healthy
        except Exception:
            # Server not running, connection refused, or timeout — informational only
            server_note = (
                "[wicked-brain] Plugin installed but server is not running. "
                "Start it to enable enhanced code intelligence."
            )

        return True, server_note

    except Exception:
        return None, None  # Fail open — never block session start


# ---------------------------------------------------------------------------
# Discovery: contextual command suggestions based on project type (Issue #322)
# ---------------------------------------------------------------------------

def _check_facilitator_context(project_name: str | None) -> str | None:
    """Return a briefing line for unresolved action items aged >= 2 sessions.

    Lazily imports ``scripts.delivery.process_memory`` so environments that
    do not ship that module (pre-#447 plugin installs) continue to boot.
    Returns a short ``[ProcessMemory]`` line when the project has any
    aging AIs, or ``None`` when:

    - No active project was detected (nothing to surface for).
    - ``delivery.process_memory`` is not importable (fail-open).
    - The project has no unresolved action items at the aging threshold.
    - Any exception is raised while reading the memory file.

    Matches the fail-open pattern used by ``_run_quality_telemetry`` and
    the guard pipeline in ``stop.py``.
    """
    if not project_name:
        return None
    try:
        # Lazy import — absence must NOT break bootstrap on legacy installs.
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "delivery"))
        try:
            import process_memory as _pm  # type: ignore
        except ImportError as exc:
            print(
                f"[wicked-garden] process_memory not importable ({exc!r}); "
                "skipping facilitator context",
                file=sys.stderr,
            )
            return None

        ctx = _pm.facilitator_context(project_name)
        aging = ctx.get("aging_action_items", []) if isinstance(ctx, dict) else []
        if not aging:
            return None

        # Show up to 3 AIs inline so the line stays readable; rest are
        # countable via the summary prefix and fully visible via
        # process-memory.md on disk.
        shown = aging[:3]
        preview = ", ".join(
            f"{ai.get('id', '?')} \"{(ai.get('title') or '')[:60]}\""
            for ai in shown
        )
        more = f" (+{len(aging) - len(shown)} more)" if len(aging) > len(shown) else ""
        return (
            f"[ProcessMemory] {len(aging)} unresolved action item(s) "
            f">=2 sessions old: {preview}{more}"
        )
    except Exception as exc:
        # Fail-open: never block session start on process-memory errors.
        print(
            f"[wicked-garden] facilitator_context error: {exc!r}",
            file=sys.stderr,
        )
        return None


def _probe_onedrive_path() -> str | None:
    """Detect if cwd is under a OneDrive or CloudStorage path with spaces.

    On macOS, OneDrive-synced directories live under paths like:
        ~/Library/CloudStorage/OneDrive - CompanyName/...
    The spaces cause failures when paths are not properly quoted.

    Returns the resolved canonical base path (via Path.resolve()), or None
    if cwd is not under a OneDrive/CloudStorage directory.
    Fails open — any error returns None.
    """
    try:
        cwd = Path.cwd()
        cwd_str = str(cwd)
        if "OneDrive" in cwd_str or "CloudStorage" in cwd_str:
            resolved = cwd.resolve()
            return str(resolved)
    except Exception:
        pass
    return None


# Critical v6 skills — if these files exist on disk under the plugin root
# but a Skill() call fails with "Unknown skill", the plugin cache is stale
# and needs `/reload-plugins`. Issue #434.
_CRITICAL_V6_SKILLS = (
    "skills/propose-process/SKILL.md",
)


def _check_critical_skills() -> str | None:
    """Verify critical v6 skill files are present in the plugin root.

    Claude Code's skill registry is cached at plugin-install time. When the
    plugin ships a new skill mid-version, the cache lags until the user runs
    `/reload-plugins`. We can't query the live registry from a hook — but we
    can check the files exist on disk and emit a diagnostic directive so an
    "Unknown skill" error surfaces a fix path instead of being cryptic.

    Returns a directive string (shown in the briefing) when any critical skill
    is missing from disk, OR a 1-liner when all files are present that tells
    Claude how to handle a cache-stale Skill() failure. Fails open on errors.
    """
    try:
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if not plugin_root:
            return None
        root = Path(plugin_root)
        missing = [s for s in _CRITICAL_V6_SKILLS if not (root / s).exists()]
        if missing:
            return (
                "[Skills] Critical v6 skill files are missing from the plugin root:\n"
                + "\n".join(f"  - {s}" for s in missing)
                + "\nThe plugin install is incomplete. Reinstall with "
                "`claude plugin install wicked-garden --scope project`."
            )
        return (
            "[Skills] Critical v6 skills are present on disk. "
            "If Skill() returns 'Unknown skill: wicked-garden:crew:*', the plugin "
            "cache is stale — run `/reload-plugins` once, then retry."
        )
    except Exception:
        return None  # fail open — never block bootstrap


def _suggest_commands_for_project() -> str | None:
    """Detect project type from files in cwd and suggest 2-3 relevant commands.

    Lightweight: checks only for a few marker files (no directory walks).
    Returns a formatted suggestion string, or None if no suggestions apply.
    """
    try:
        cwd = Path.cwd()
        suggestions = []

        # Detect project signals from marker files
        has_package_json = (cwd / "package.json").exists()
        has_pyproject = (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists()
        has_dockerfile = (cwd / "Dockerfile").exists() or (cwd / "docker-compose.yml").exists()
        has_terraform = (cwd / "main.tf").exists() or (cwd / "terraform").is_dir()
        has_tests = (
            (cwd / "tests").is_dir() or (cwd / "test").is_dir()
            or (cwd / "__tests__").is_dir() or (cwd / "spec").is_dir()
        )
        has_csv_data = any(cwd.glob("*.csv")) or (cwd / "data").is_dir()
        has_ci = (cwd / ".github" / "workflows").is_dir()

        # Always useful
        suggestions.append("`/wicked-garden:search:code` — semantic code search")
        suggestions.append("`/wicked-garden:engineering:review` — structured code review")

        # Project-type-specific
        if has_tests:
            suggestions.append("`/wicked-garden:qe:scenarios` — generate test scenarios")
        if has_dockerfile or has_terraform:
            suggestions.append("`/wicked-garden:platform:security` — security review")
        if has_csv_data:
            suggestions.append("`/wicked-garden:data:numbers` — interactive data analysis")
        if has_ci:
            suggestions.append("`/wicked-garden:platform:actions` — GitHub Actions optimization")

        # Cap at 3 suggestions
        suggestions = suggestions[:3]

        if not suggestions:
            return None

        return (
            "[Quick Start] Available commands for this project:\n"
            + "\n".join(f"  - {s}" for s in suggestions)
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# #506 — WG_GATE_RESULT_STRICT_AFTER pre-flip monitoring
#
# Surfaces a visible warning as the strict-mode cutover approaches so
# operators aren't surprised when orphan gate-results start rejecting.
# Thresholds (T = days until flip, computed in UTC):
#   T > 7       silent
#   7 >= T >= 1 stderr WARN, every SessionStart
#   T == 0      stderr INFO, one-time per session (latched via
#               SessionState.strict_mode_active_announced)
#   T < 0       stderr INFO, same one-time latch (post-flip banner)
#
# Fail-open: malformed dates fall back to the module default and the
# signal is skipped silently rather than blocking bootstrap.
# ---------------------------------------------------------------------------


def _check_pre_flip_notice(state, today=None) -> None:
    """Emit pre-flip / post-flip monitoring signals on stderr.

    Arguments:
        state: The loaded SessionState (or None). When None, the
            post-flip banner still fires but won't latch — next
            SessionStart in the same session may re-fire, which is
            the expected degrade.
        today: ``datetime.date`` override for deterministic tests.
            Production callers pass ``None`` and the helper uses
            today's UTC date.
    """
    try:
        # Lazy import — keeps hook cheap; dispatch_log is in the crew
        # scripts dir which is already on sys.path via the hook bootstrap.
        sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "crew"))
        from dispatch_log import (  # type: ignore
            DEFAULT_STRICT_AFTER,
            _get_strict_after_date,
        )
    except Exception:
        return  # fail-open: module unavailable, skip the signal

    try:
        from datetime import datetime, timezone

        flip_date = _get_strict_after_date()
        if today is None:
            today = datetime.now(timezone.utc).date()
        delta_days = (flip_date - today).days
        raw_env_val = os.environ.get("WG_GATE_RESULT_STRICT_AFTER", "").strip()
        # Display the user-supplied value when it parsed; otherwise show
        # the effective default. A malformed env-var produces the fallback
        # WARN in ``_get_strict_after_date`` already — we don't duplicate.
        if raw_env_val and flip_date.isoformat() == raw_env_val:
            raw_env = raw_env_val
        else:
            raw_env = flip_date.isoformat()

        if delta_days > 7:
            return  # silent

        if 1 <= delta_days <= 7:
            sys.stderr.write(
                f"[PreFlipNotice] Strict-mode activation in {delta_days} "
                f"days (WG_GATE_RESULT_STRICT_AFTER={raw_env}). "
                "Orphan gate-result files will start rejecting.\n"
            )
            return

        # delta_days <= 0 → post-flip; emit one-time-per-session INFO.
        already = bool(getattr(state, "strict_mode_active_announced", False)) \
            if state is not None else False
        if already:
            return
        sys.stderr.write(
            f"[StrictMode] Strict-mode active (flipped on "
            f"{flip_date.isoformat()}). Any orphan gate-result now rejects.\n"
        )
        if state is not None:
            try:
                state.update(strict_mode_active_announced=True)
            except Exception:  # pragma: no cover — defensive
                pass  # session-state write failure: banner may re-fire, acceptable
    except Exception:
        # Signal computation errors must never block bootstrap.
        return


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _t0 = time.monotonic()
    _log("bootstrap", "debug", "hook.start")

    try:
        sys.stdin.read()  # consume hook payload (not needed for SessionStart)
    except Exception:
        pass

    # Export CLAUDE_PLUGIN_ROOT to CLAUDE_ENV_FILE so Bash tool calls can access it.
    # Hooks receive CLAUDE_PLUGIN_ROOT from the plugin runtime, but Bash tool calls
    # do not inherit it.  Writing to CLAUDE_ENV_FILE bridges the gap.
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_file and plugin_root:
        try:
            with open(env_file, "a") as f:
                f.write(f'export CLAUDE_PLUGIN_ROOT="{plugin_root}"\n')
        except OSError:
            pass

    try:
        # 1. Read config
        config = _read_config()

        if config is None or not config.get("setup_complete", False):
            # Clear stale session state before early return.  Without this,
            # setup_in_progress=True from a crashed/killed previous session
            # survives and lets prompt_submit bypass the setup gate.
            _stale = _load_session_state()
            if _stale is not None:
                if _stale.session_ended:
                    _stale.delete()
                    _stale = _load_session_state()
                if _stale is not None:
                    _stale.update(
                        setup_in_progress=False,
                        setup_complete=False,
                        setup_confirmed=False,
                    )

            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": (
                        "[Action Required] wicked-garden is not configured for this project.\n"
                        "You MUST immediately invoke the Skill tool with skill='wicked-garden:setup' "
                        "to launch the interactive setup wizard.\n"
                        "Do NOT ask the user for confirmation — invoke the skill now.\n"
                        "Do NOT respond with text first — invoke the skill as your first action."
                    ),
                },
            }))
            return

        # Clear one-time task suggestion flag from crew
        flag = Path.home() / ".something-wicked" / "wicked-crew" / ".task_suggest_shown"
        flag.unlink(missing_ok=True)

        # 2. Load session state — if stale from a previous session, start fresh.
        state = _load_session_state()
        if state is not None and state.session_ended:
            state.delete()
            state = _load_session_state()  # fresh defaults
        if state is not None:
            state.update(
                setup_complete=True,
                turn_count=0,
                session_ended=False,
            )

        # 2a. Probe OneDrive / spaces-in-paths (Issue #321)
        onedrive_path = _probe_onedrive_path()
        if onedrive_path and state is not None:
            state.update(onedrive_base_path=onedrive_path)

        _log("bootstrap", "normal", "storage.local", ok=True)

        # 2b. Initialize event store schema (fire-and-forget)
        try:
            from _event_store import EventStore
            EventStore.ensure_schema()
            _log("bootstrap", "debug", "event_store.schema", ok=True)
        except Exception:
            pass  # event store is optional — never block session start

        # 2c. #506 — pre-flip monitoring signal for WG_GATE_RESULT_STRICT_AFTER.
        # Fail-open: never blocks bootstrap. Emits stderr WARN at T-7..T-1,
        # stderr INFO once per session post-flip.
        _check_pre_flip_notice(state)

        # 3. Load dynamic agents
        agents_loaded, agents_dict = _load_agents()
        if state is not None:
            state.update(agents_loaded=agents_loaded)

        # 3b. Resolve tool-capabilities for agents that declare them
        resolutions = _resolve_capabilities(agents_dict, config)
        if resolutions and state is not None:
            state.update(resolved_capabilities=resolutions)

        # 4. Load last crew project for this workspace
        workspace = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        project_data, project_name = _find_active_crew_project(workspace)

        # 6. Run memory decay
        decay_summary = _run_memory_decay()

        # 6b. Check search index staleness and auto-reindex if needed
        search_staleness_note = _check_search_staleness()
        mode_notes = []
        if onedrive_path:
            mode_notes.append(
                f"[Path] OneDrive directory detected. Resolved base: {onedrive_path}. "
                "Always quote paths with spaces."
            )
        if search_staleness_note:
            mode_notes.append(f"[Search] {search_staleness_note}")

        # 6c. Surface prior session's guard-pipeline findings (Issue #448)
        guard_note = _check_prior_guard_findings()
        if guard_note:
            mode_notes.append(guard_note)

        # 7. Check onboarding status (search index + memories)
        has_index, has_memories, onboarding_directive = _check_onboarding_status()
        _log("bootstrap", "normal", "onboarding.status",
             ok=(has_memories and has_index),
             detail={"has_memories": has_memories, "has_index": has_index})

        # Persist onboarding gate flags so prompt_submit can enforce them
        if state is not None:
            if not has_memories:
                state.update(
                    needs_onboarding=True,
                    onboarding_complete=False,
                )
            else:
                state.update(
                    needs_onboarding=False,
                    onboarding_complete=True,
                )

        # 7b. Probe installed plugin hooks for readiness
        unready_plugins = _probe_plugin_readiness()
        if unready_plugins and state is not None:
            state.update(unready_plugins=[p["name"] for p in unready_plugins])
        if unready_plugins:
            plugin_lines = []
            for p in unready_plugins:
                fix_cmd = _suggest_auth_fix(p)
                plugin_lines.append(f"  - **{p['name']}**: {p['error']}")
                if fix_cmd:
                    plugin_lines.append(f"    Fix: `{fix_cmd}`")
            mode_notes.append(
                f"[Plugins] {len(unready_plugins)} plugin(s) installed but not ready:\n"
                + "\n".join(plugin_lines)
                + "\n  After authenticating, run `/wicked-garden:platform:health` to re-probe."
            )

        # 7c. Detect dangerous mode (AskUserQuestion broken)
        dangerous_mode = _detect_dangerous_mode()
        if state is not None:
            state.update(dangerous_mode=dangerous_mode)

        # 7c.1. Critical v6 skill smoke-test (issue #434)
        skills_note = _check_critical_skills()
        if skills_note:
            mode_notes.append(skills_note)

        # 7d. Check wicked-brain dependency (required, not optional)
        brain_available, brain_note = _check_brain_dependency()
        if state is not None and brain_available is not None:
            state.update(brain_available=brain_available)
        if brain_note:
            if brain_available is False:
                # Not installed — escalate to imperative directive
                mode_notes.insert(0, (
                    "[Action Required] wicked-brain is not installed.\n"
                    "You MUST tell the user to install it immediately:\n"
                    "  claude plugin install wicked-brain --scope project\n"
                    "wicked-garden cannot function without wicked-brain. "
                    "Do NOT proceed with other tasks until brain is installed."
                ))
            else:
                mode_notes.append(brain_note)

        # 7e. Brain auto-init and auto-ingest
        #     If brain is installed but has no content for this project, emit
        #     a directive so the agent auto-runs init + ingest on first use.
        if brain_available:
            try:
                import urllib.request
                port = resolve_port()
                req = urllib.request.Request(
                    f"http://localhost:{port}/api",
                    data=json.dumps({"action": "stats", "params": {}}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    stats = json.loads(resp.read().decode("utf-8"))
                    if stats.get("total", 0) == 0:
                        mode_notes.append(
                            "[wicked-brain] Brain is empty for this project. "
                            "You MUST run the full brain pipeline now as background agents:\n"
                            "  1. `wicked-brain:init` — initialize the brain if needed\n"
                            "  2. `wicked-brain:ingest` with the current working directory\n"
                            "  3. `wicked-brain:retag` — expand keywords into semantic tags\n"
                            "  4. `wicked-brain:compile` — synthesize wiki articles from chunks\n"
                            "Run these sequentially in a background agent. "
                            "Do NOT wait for completion before responding to the user."
                        )
            except Exception:
                # Brain server not running — emit start directive
                if brain_available:
                    mode_notes.append(
                        "[wicked-brain] Plugin installed but server is not running. "
                        "You MUST invoke `wicked-brain-server` to start the brain server, "
                        "then run the brain pipeline: ingest → retag → compile."
                    )

        # 8. Assemble session briefing
        # --- Status block (user-facing) ---
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name

        onboarding_parts = []
        if has_index:
            onboarding_parts.append("search index")
        if has_memories:
            onboarding_parts.append("memories")
        if onboarding_parts:
            onboarding_status = "Complete (" + " + ".join(onboarding_parts) + ")"
        else:
            onboarding_status = "Not started"

        status_lines = [
            f"wicked-garden | {project}",
            "  Storage:     local",
            f"  Onboarding:  {onboarding_status}",
        ]

        # Show last crew project for this workspace as informational only.
        # Do NOT auto-activate — the user must explicitly start/resume a project.
        if project_data:
            name = project_data.get("name", project_name or "unknown")
            phase = project_data.get("current_phase", "unknown")
            status_lines.append(f"  Last crew:   {name} ({phase})")

            # Store as reference info only — NOT as active_project
            if state is not None:
                # active_project_id: only set when project is in a non-complete, non-skipped phase
                active_phase = project_data.get("current_phase", "")
                is_active = active_phase not in ("", "complete", "done", "archived")
                state.update(active_project_id=project_name if is_active else None)

                # #459 telemetry producer: anchor complexity_at_session_open
                # from the active project's complexity_score so session-close
                # drift capture has a delta baseline.  Only set when not
                # already populated this session (first SessionStart wins).
                try:
                    raw_complexity = project_data.get("complexity_score", 0)
                    complexity_val = int(raw_complexity) if raw_complexity is not None else 0
                    updates = {"complexity_score": complexity_val}
                    if getattr(state, "complexity_at_session_open", None) is None:
                        updates["complexity_at_session_open"] = complexity_val
                    state.update(**updates)
                except (TypeError, ValueError):
                    # Malformed complexity_score — fail-open, don't block bootstrap.
                    pass

            # Enable memory compliance directives for crew sessions.
            # task_completed.py reads this flag to decide whether to emit
            # per-task memory prompts; stop.py reads it for session summary.
            if state is not None:
                state.update(memory_compliance_required=True)

        briefing_parts = ["\n".join(status_lines)]

        # --- Mode-specific warnings/notes ---
        for note in mode_notes:
            briefing_parts.append(note)

        if decay_summary:
            briefing_parts.append(f"[Memory] {decay_summary}")

        # --- Internal instructions for Claude ---
        briefing_parts.append(_MEMORY_INSTRUCTIONS)

        if dangerous_mode:
            briefing_parts.append(_DANGEROUS_MODE_WARNING)

        if not onboarding_directive:
            briefing_parts.append(
                "[Setup] Run `/wicked-garden:setup --reconfigure` to change connection or re-onboard."
            )

        # Discovery: show 2-3 contextual command suggestions based on project files
        if not onboarding_directive and has_memories:
            discovery_lines = _suggest_commands_for_project()
            if discovery_lines:
                briefing_parts.append(discovery_lines)

        # Facilitator context: surface aging action items from process_memory.
        # Additive briefing line (issue #461) — runs last of the informational
        # notes and is independent of onboarding or setup state.
        fc_note = _check_facilitator_context(project_name)
        if fc_note:
            briefing_parts.append(fc_note)

        # Onboarding directive goes LAST for highest priority
        if onboarding_directive:
            briefing_parts.append(onboarding_directive)

        # 9. Persist final session state
        if state is not None:
            _save_session_state(state)

        _log("bootstrap", "debug", "hook.end", ms=int((time.monotonic() - _t0) * 1000))
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join(briefing_parts),
            },
        }))

    except Exception as e:
        print(f"[wicked-garden] bootstrap error: {e}", file=sys.stderr)
        print(json.dumps({}))


if __name__ == "__main__":
    main()
