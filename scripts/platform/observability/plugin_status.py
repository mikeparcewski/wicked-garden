#!/usr/bin/env python3
"""Plugin status reporter -- emits structural metadata about the installed plugin.

Reads plugin.json, counts domains/commands/agents/skills, and reports a summary
suitable for dashboards and contract assertions.

Usage:
    python3 plugin_status.py
    python3 plugin_status.py --health-check
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/observability/ -> scripts/ -> wicked-garden/


def _count_md_files(directory: Path) -> int:
    """Count .md files recursively under a directory."""
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.rglob("*.md"))


def _list_domains(base_dir: Path) -> list[str]:
    """List subdirectories (domains) under a base directory."""
    if not base_dir.is_dir():
        return []
    return sorted(
        d.name for d in base_dir.iterdir()
        if d.is_dir() and not d.name.startswith((".", "_"))
    )


def gather_status() -> dict:
    """Collect plugin metadata and structural counts."""
    # Read plugin.json
    plugin_json_path = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    plugin_meta = {}
    if plugin_json_path.exists():
        try:
            plugin_meta = json.loads(plugin_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass  # fail open: plugin.json unreadable

    commands_dir = PLUGIN_ROOT / "commands"
    agents_dir = PLUGIN_ROOT / "agents"
    skills_dir = PLUGIN_ROOT / "skills"
    hooks_dir = PLUGIN_ROOT / "hooks"

    domains = sorted(set(
        _list_domains(commands_dir)
        + _list_domains(agents_dir)
        + _list_domains(skills_dir)
    ))

    return {
        "plugin": plugin_meta.get("name", "unknown"),
        "version": plugin_meta.get("version", "0.0.0"),
        "status": "installed",
        "checked_at": datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
        "counts": {
            "domains": len(domains),
            "commands": _count_md_files(commands_dir),
            "agents": _count_md_files(agents_dir),
            "skills": sum(
                1 for d in skills_dir.rglob("SKILL.md")
            ) if skills_dir.is_dir() else 0,
            "hooks": len(list((hooks_dir / "scripts").glob("*.py")))
            if (hooks_dir / "scripts").is_dir() else 0,
        },
        "domains": domains,
    }


def main() -> None:
    # --health-check: emit a minimal status for contract testing
    if "--health-check" in sys.argv:
        print(json.dumps(gather_status(), indent=2))
        return

    print(json.dumps(gather_status(), indent=2))


if __name__ == "__main__":
    main()
