#!/usr/bin/env python3
"""
Context Package Builder for subagent dispatches.

Builds structured context packages for subagents instead of prose dumps.
Called by other plugins (wicked-crew, etc.) via discover_script().

Usage:
    context_package.py build --task "Review auth implementation" [--project myproject] [--files src/auth/]
    context_package.py build --task "..." --json
    context_package.py build --task "..." --dispatch   # includes ecosystem orientation for subagents

Output: A structured JSON context package with typed fields:
{
    "task": "Review auth implementation",
    "constraints": ["Must use JWT", "No session storage"],
    "decisions": ["Chose JWT for stateless auth"],
    "files": ["src/auth/handler.py", "src/auth/middleware.py"],
    "tools": ["Read", "Grep", "Glob"],
    "project_state": {"phase": "build", "complexity": 4},
    "memories": [{"title": "...", "summary": "..."}],
    "ecosystem": {"installed_plugins": [...], "key_skills": [...]}
}

The --dispatch flag adds ecosystem orientation: which plugins are installed,
what skills/tools are available, and conciseness guidance. This replaces the
SubagentStart hook that was removed (hooks caused subagent exits).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add paths for adapter imports
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))
sys.path.insert(0, str(scripts_dir / "v2"))


def discover_script(plugin_name: str, script_name: str):
    """Find a plugin script in cache or local repo."""
    # Check cache first (highest semver)
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / plugin_name
    if cache_base.exists():
        versions = sorted(cache_base.iterdir(), key=lambda p: p.name, reverse=True)
        for v in versions:
            candidate = v / "scripts" / script_name
            if candidate.exists():
                return candidate

    # Check local repo
    local = Path(__file__).parent.parent.parent.parent / plugin_name / "scripts" / script_name
    if local.exists():
        return local

    return None


# Maps installed plugins → their most useful skills/tools for subagents.
# This is the static reference that replaces SubagentStart hook's pointer injection.
PLUGIN_SKILL_MAP = {
    "wicked-mem": [
        "/wicked-mem:recall — retrieve past decisions, constraints, patterns",
        "/wicked-mem:store — persist a decision or learning for future sessions",
    ],
    "wicked-search": [
        "/wicked-search:code — find code symbols (functions, classes, methods)",
        "/wicked-search:refs — find where a symbol is referenced",
        "/wicked-search:blast-radius — analyze what changing a symbol affects",
        "/wicked-search:docs — search documents (PDF, markdown, Office)",
    ],
    "wicked-kanban": [
        "TaskCreate/TaskUpdate/TaskList/TaskGet — native task tools (kanban syncs automatically)",
    ],
    "wicked-qe": [
        "/wicked-qe:scenarios — generate test scenarios with edge cases",
        "/wicked-qe:qe-plan — generate comprehensive test plan",
    ],
    "wicked-engineering": [
        "/wicked-engineering:review — code review with senior engineering perspective",
    ],
    "wicked-platform": [
        "/wicked-platform:security — security review and vulnerability assessment",
    ],
    "wicked-startah": [
        "context7 MCP tools — query up-to-date library documentation",
    ],
}


def discover_installed_plugins() -> list:
    """Discover which wicked-garden plugins are installed."""
    installed = []

    # Check plugin cache
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden"
    if cache_base.exists():
        for entry in cache_base.iterdir():
            if entry.is_dir() and entry.name.startswith("wicked-"):
                installed.append(entry.name)

    # Also check local repo (for dev mode)
    if not installed:
        local_plugins = Path(__file__).parent.parent.parent.parent
        if local_plugins.exists():
            for entry in local_plugins.iterdir():
                if entry.is_dir() and entry.name.startswith("wicked-"):
                    installed.append(entry.name)

    return sorted(set(installed))


def build_ecosystem_orientation(installed_plugins: list = None) -> dict:
    """Build ecosystem orientation metadata for subagent prompts.

    Returns dict with:
    - installed_plugins: list of installed wicked-garden plugins
    - key_skills: list of skill references relevant to subagents
    - built_in_tools: list of Claude's built-in tools
    """
    if installed_plugins is None:
        installed_plugins = discover_installed_plugins()

    # Collect skill references for installed plugins
    key_skills = []
    for plugin in installed_plugins:
        if plugin in PLUGIN_SKILL_MAP:
            key_skills.extend(PLUGIN_SKILL_MAP[plugin])

    return {
        "installed_plugins": installed_plugins,
        "key_skills": key_skills,
        "built_in_tools": [
            "Read, Grep, Glob — file reading and search",
            "Edit, Write — file modification",
            "Bash — shell commands",
            "TaskCreate/TaskUpdate/TaskList/TaskGet — task management",
            "WebSearch, WebFetch — web research",
        ],
    }


async def gather_memories(task: str, limit: int = 3) -> list:
    """Query wicked-mem for task-relevant memories."""
    try:
        from adapters import mem_adapter
        items = await mem_adapter.query(task)
        results = []
        for item in items[:limit]:
            results.append({
                "title": getattr(item, "title", ""),
                "summary": getattr(item, "summary", "")[:200],
                "type": getattr(item, "metadata", {}).get("type", "unknown"),
            })
        return results
    except Exception:
        return []


async def gather_code_context(task: str, files: list = None, limit: int = 5) -> list:
    """Query wicked-search for relevant code symbols."""
    try:
        from adapters import search_adapter
        items = await search_adapter.query(task)
        results = []
        for item in items[:limit]:
            results.append({
                "title": getattr(item, "title", ""),
                "file": getattr(item, "metadata", {}).get("file", ""),
                "summary": getattr(item, "summary", "")[:200],
            })
        return results
    except Exception:
        return []


def get_session_state() -> dict:
    """Get current session state from history condenser."""
    try:
        from history_condenser import HistoryCondenser
        session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
        condenser = HistoryCondenser(session_id)
        return condenser.get_session_state()
    except Exception:
        return {}


async def build_package(task: str, project: str = None, files: list = None,
                        include_ecosystem: bool = False) -> dict:
    """Build a structured context package for a subagent.

    This is the core function — assembles task-scoped context from
    wicked-mem (decisions, constraints) and wicked-search (code context),
    plus session state from the history condenser.

    Args:
        task: Task description for the subagent
        project: Crew project name (optional)
        files: Explicit file scope (optional)
        include_ecosystem: Include ecosystem orientation (tools, skills, plugins)
    """
    # Gather from multiple sources in parallel
    mem_task = gather_memories(task)
    code_task = gather_code_context(task, files)

    memories, code_context = await asyncio.gather(mem_task, code_task)

    # Get session state (sync)
    session = get_session_state()

    # Extract typed fields from session state
    constraints = session.get("active_constraints", [])
    decisions = session.get("decisions", [])
    file_scope = files or session.get("file_scope", [])
    current_task = session.get("current_task", "")

    # Get project state if available
    project_state = {}
    if project:
        try:
            project_dir = Path.home() / ".something-wicked" / "wicked-crew" / "projects" / project
            project_json = project_dir / "project.json"
            if project_json.exists():
                data = json.loads(project_json.read_text())
                project_state = {
                    "phase": data.get("current_phase", ""),
                    "complexity": data.get("complexity_score", 0),
                    "signals": data.get("signals_detected", []),
                }
        except Exception:
            pass

    package = {
        "task": task,
        "current_task": current_task,
        "constraints": constraints,
        "decisions": decisions,
        "files": file_scope,
        "code_context": code_context,
        "memories": memories,
        "project_state": project_state,
        "session_topics": session.get("topics", []),
    }

    # Add ecosystem orientation for dispatch mode
    if include_ecosystem:
        package["ecosystem"] = build_ecosystem_orientation()

    return package


def format_as_prompt(package: dict) -> str:
    """Format a context package as a prompt section for subagent injection.

    This converts the structured JSON into a readable prompt block that
    can be included in Task() dispatches.
    """
    lines = ["## Context Package", ""]

    if package.get("task"):
        lines.append(f"**Task**: {package['task']}")
    if package.get("current_task"):
        lines.append(f"**Session task**: {package['current_task']}")
    lines.append("")

    # Ecosystem orientation (dispatch mode) — goes first so subagent
    # knows what tools are available before reading the task context
    eco = package.get("ecosystem")
    if eco:
        lines.append("### Available Tools & Skills")
        if eco.get("built_in_tools"):
            for tool in eco["built_in_tools"]:
                lines.append(f"- {tool}")
        if eco.get("key_skills"):
            lines.append("")
            lines.append("**Ecosystem skills** (from installed plugins):")
            for skill in eco["key_skills"]:
                lines.append(f"- {skill}")
        lines.append("")

    if package.get("decisions"):
        lines.append("### Decisions Made")
        for d in package["decisions"]:
            lines.append(f"- {d}")
        lines.append("")

    if package.get("constraints"):
        lines.append("### Active Constraints")
        for c in package["constraints"]:
            lines.append(f"- {c}")
        lines.append("")

    if package.get("files"):
        lines.append("### File Scope")
        for f in package["files"][:10]:
            lines.append(f"- `{f}`")
        lines.append("")

    if package.get("code_context"):
        lines.append("### Relevant Code")
        for c in package["code_context"]:
            title = c.get("title", "")
            file = c.get("file", "")
            summary = c.get("summary", "")
            lines.append(f"- **{title}** (`{file}`): {summary}")
        lines.append("")

    if package.get("memories"):
        lines.append("### Relevant Memories")
        for m in package["memories"]:
            lines.append(f"- [{m.get('type', '')}] **{m.get('title', '')}**: {m.get('summary', '')}")
        lines.append("")

    if package.get("project_state"):
        ps = package["project_state"]
        if ps.get("phase"):
            lines.append("### Project State")
            lines.append(f"- Phase: {ps['phase']}")
            if ps.get("complexity"):
                lines.append(f"- Complexity: {ps['complexity']}/7")
            if ps.get("signals"):
                lines.append(f"- Signals: {', '.join(ps['signals'])}")
            lines.append("")

    # Conciseness guidance for subagents (replaces PreToolUse pressure gate)
    if eco:
        lines.append("### Output Guidance")
        lines.append("Keep responses focused and concise. Return structured data (JSON) "
                      "when possible. For CLI outputs or evidence artifacts, summarize "
                      "rather than including verbatim. The parent orchestrator manages "
                      "context pressure — help by keeping your output lean.")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Build structured context packages for subagents")
    parser.add_argument("command", choices=["build", "format"], help="Command to run")
    parser.add_argument("--task", required=True, help="Task description for the subagent")
    parser.add_argument("--project", help="Crew project name (optional)")
    parser.add_argument("--files", nargs="*", help="Explicit file scope (optional)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--prompt", action="store_true", help="Output as formatted prompt section")
    parser.add_argument("--dispatch", action="store_true",
                        help="Include ecosystem orientation (tools, skills, plugins) for subagent dispatch")

    args = parser.parse_args()

    include_ecosystem = args.dispatch
    package = asyncio.run(build_package(args.task, args.project, args.files,
                                        include_ecosystem=include_ecosystem))

    if args.command == "format" or args.prompt:
        print(format_as_prompt(package))
    elif args.json:
        print(json.dumps(package, indent=2))
    else:
        # Default: formatted prompt
        print(format_as_prompt(package))


if __name__ == "__main__":
    main()
