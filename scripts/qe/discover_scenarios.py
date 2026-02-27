#!/usr/bin/env python3
"""Discover wicked-scenarios plugin and list available E2E scenarios.

Cross-plugin discovery utility that finds wicked-scenarios if installed,
parses scenario metadata, and returns structured JSON.

Usage:
    python3 discover_scenarios.py                    # All scenarios
    python3 discover_scenarios.py --category api     # Filter by category
    python3 discover_scenarios.py --available-only   # Only runnable scenarios
    python3 discover_scenarios.py --check-tools      # Include tool availability
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def _parse_version(v: str) -> tuple:
    """Parse semver string to comparable tuple."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def discover_plugin(plugin_name: str) -> "Path | None":
    """Find a plugin's root directory via cache or local repo.

    Discovery order:
    1. Cache path (~/.claude/plugins/cache/wicked-garden/{plugin}/{version}/)
       - Selects highest semver version
    2. Local repo sibling path (../../../{plugin}/)
    """
    # 1. Cache path (highest semver)
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / plugin_name
    if cache_base.exists():
        versions = []
        for d in cache_base.iterdir():
            if d.is_dir():
                versions.append((_parse_version(d.name), d))
        if versions:
            versions.sort(key=lambda x: x[0], reverse=True)
            return versions[0][1]

    # 2. Local repo sibling path
    local = Path(__file__).parent.parent.parent / plugin_name
    if local.exists() and (local / ".claude-plugin" / "plugin.json").exists():
        return local

    return None


def parse_frontmatter(filepath: Path) -> dict:
    """Parse YAML frontmatter from a scenario markdown file.

    Returns dict with name, description, category, tools, difficulty, timeout.
    Uses simple regex parsing to avoid PyYAML dependency.
    """
    try:
        text = filepath.read_text()
    except (OSError, UnicodeDecodeError):
        return {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    fm = match.group(1)
    result = {}

    # Simple key: value parsing for flat keys
    for line in fm.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        kv = re.match(r"^(\w+):\s*(.+)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip().strip('"').strip("'")
            if key in ("name", "description", "category", "difficulty"):
                result[key] = val
            elif key == "timeout":
                try:
                    result["timeout"] = int(val)
                except ValueError:
                    pass

    # Parse tools block (required/optional arrays)
    # Supports both inline [curl, hurl] and list (- curl) syntax
    tools_match = re.search(
        r"^tools:\s*\n((?:[ \t]+.*\n?)*)", fm, re.MULTILINE
    )
    if tools_match:
        tools_block = tools_match.group(1)
        result["tools"] = {"required": [], "optional": []}

        current_key = None
        for line in tools_block.split("\n"):
            stripped = line.strip()
            for key in ("required", "optional"):
                if stripped.startswith(f"{key}:"):
                    current_key = key
                    # Check for inline array: required: [curl, hurl]
                    inline = re.search(r"\[([^\]]*)\]", stripped)
                    if inline:
                        items = [i.strip() for i in inline.group(1).split(",") if i.strip()]
                        result["tools"][current_key] = items
                    break
            else:
                if stripped.startswith("- ") and current_key:
                    result["tools"][current_key].append(stripped[2:].strip())

    return result


def discover_scenarios(
    plugin_root: Path,
    category: "str | None" = None,
    check_tools: bool = False,
) -> dict:
    """Discover scenarios from a wicked-scenarios plugin root.

    Returns:
        {
            "available": true,
            "plugin_root": "/path/to/wicked-scenarios",
            "scenarios": [
                {
                    "name": "api-health-check",
                    "file": "scenarios/api-health-check.md",
                    "category": "api",
                    "description": "...",
                    "tools": {"required": [...], "optional": [...]},
                    "difficulty": "basic",
                    "runnable": true  # only if check_tools=True
                }
            ],
            "tool_status": {...}  # only if check_tools=True
        }
    """
    scenarios_dir = plugin_root / "scenarios"
    if not scenarios_dir.exists():
        return {"available": True, "plugin_root": str(plugin_root), "scenarios": []}

    scenarios = []
    for md_file in sorted(scenarios_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue
        fm = parse_frontmatter(md_file)
        if not fm.get("name"):
            continue
        if category and fm.get("category") != category:
            continue

        scenario = {
            "name": fm.get("name", md_file.stem),
            "file": str(md_file),
            "category": fm.get("category", "unknown"),
            "description": fm.get("description", ""),
            "tools": fm.get("tools", {"required": [], "optional": []}),
            "difficulty": fm.get("difficulty", "basic"),
        }
        scenarios.append(scenario)

    result = {
        "available": True,
        "plugin_root": str(plugin_root),
        "scenarios": scenarios,
    }

    # Optionally check tool availability via cli_discovery.py
    if check_tools:
        cli_discovery = plugin_root / "scripts" / "cli_discovery.py"
        if cli_discovery.exists():
            try:
                proc = subprocess.run(
                    [sys.executable, str(cli_discovery)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if proc.returncode == 0:
                    tool_status = json.loads(proc.stdout)
                    result["tool_status"] = tool_status

                    # Mark each scenario as runnable or not
                    for s in scenarios:
                        required = s["tools"].get("required", [])
                        s["runnable"] = all(
                            tool_status.get(t, {}).get("available", False)
                            for t in required
                        )
            except (subprocess.TimeoutExpired, json.JSONDecodeError):
                pass

    return result


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    category = None
    available_only = "--available-only" in flags
    do_check_tools = "--check-tools" in flags or available_only

    # Parse --category value
    for i, f in enumerate(flags):
        if f == "--category" and i + 1 < len(sys.argv[1:]):
            # Find the value after --category
            idx = sys.argv.index("--category")
            if idx + 1 < len(sys.argv):
                category = sys.argv[idx + 1]

    # Discover wicked-scenarios plugin
    plugin_root = discover_plugin("wicked-scenarios")
    if plugin_root is None:
        print(json.dumps({"available": False, "scenarios": []}, indent=2))
        return

    result = discover_scenarios(
        plugin_root, category=category, check_tools=do_check_tools
    )

    # Filter to runnable only
    if available_only:
        if "tool_status" in result:
            result["scenarios"] = [s for s in result["scenarios"] if s.get("runnable", False)]
        else:
            # Can't verify runnability without tool status — return empty
            result["scenarios"] = []

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
