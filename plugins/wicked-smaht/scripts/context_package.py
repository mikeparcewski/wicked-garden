#!/usr/bin/env python3
"""
Context Package Builder for subagent dispatches.

Builds structured context packages for subagents instead of prose dumps.
Called by other plugins (wicked-crew, etc.) via discover_script().

Usage:
    context_package.py build --task "Review auth implementation" [--project myproject] [--files src/auth/]
    context_package.py build --task "..." --json

Output: A structured JSON context package with typed fields:
{
    "task": "Review auth implementation",
    "constraints": ["Must use JWT", "No session storage"],
    "decisions": ["Chose JWT for stateless auth"],
    "files": ["src/auth/handler.py", "src/auth/middleware.py"],
    "tools": ["Read", "Grep", "Glob"],
    "project_state": {"phase": "build", "complexity": 4},
    "memories": [{"title": "...", "summary": "..."}]
}
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


async def build_package(task: str, project: str = None, files: list = None) -> dict:
    """Build a structured context package for a subagent.

    This is the core function — assembles task-scoped context from
    wicked-mem (decisions, constraints) and wicked-search (code context),
    plus session state from the history condenser.
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

    return {
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
            lines.append(f"### Project State")
            lines.append(f"- Phase: {ps['phase']}")
            if ps.get("complexity"):
                lines.append(f"- Complexity: {ps['complexity']}/7")
            if ps.get("signals"):
                lines.append(f"- Signals: {', '.join(ps['signals'])}")
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

    args = parser.parse_args()

    package = asyncio.run(build_package(args.task, args.project, args.files))

    if args.command == "format" or args.prompt:
        print(format_as_prompt(package))
    elif args.json:
        print(json.dumps(package, indent=2))
    else:
        # Default: formatted prompt
        print(format_as_prompt(package))


if __name__ == "__main__":
    main()
