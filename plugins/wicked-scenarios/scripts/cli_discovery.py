#!/usr/bin/env python3
"""Check availability of CLI tools for wicked-scenarios.

Usage:
    python3 cli_discovery.py              # Check all MVP tools
    python3 cli_discovery.py curl hurl    # Check specific tools
    python3 cli_discovery.py --summary    # One-line summary
"""
import json
import shutil
import sys

MVP_TOOLS = {
    "curl": {"install": "pre-installed on most systems", "category": "api"},
    "hurl": {"install": "brew install hurl", "category": "api"},
    "playwright": {
        "install": "npm i -D @playwright/test && npx playwright install",
        "category": "browser",
    },
    "agent-browser": {"install": "npm i -g agent-browser", "category": "browser"},
    "k6": {"install": "brew install k6", "category": "perf"},
    "hey": {"install": "brew install hey", "category": "perf"},
    "trivy": {"install": "brew install trivy", "category": "infra"},
    "semgrep": {"install": "brew install semgrep", "category": "security"},
    "pa11y": {"install": "npm i -g pa11y", "category": "a11y"},
}


def check_tools(tools=None):
    """Check availability of specified tools (or all MVP tools)."""
    results = {}
    check = tools or list(MVP_TOOLS.keys())
    for tool in check:
        path = shutil.which(tool)
        info = MVP_TOOLS.get(tool, {})
        results[tool] = {
            "available": path is not None,
            "path": path,
            "install": info.get("install", "unknown"),
            "category": info.get("category", "unknown"),
        }
    return results


def summary(results):
    """Return one-line summary of tool availability."""
    available = sum(1 for r in results.values() if r["available"])
    total = len(results)
    missing = [name for name, r in results.items() if not r["available"]]
    msg = f"{available}/{total} tools available"
    if missing:
        msg += f". Missing: {', '.join(missing)}"
    return msg


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    tools = args if args else None
    results = check_tools(tools)

    if "--summary" in flags:
        print(summary(results))
    else:
        print(json.dumps(results, indent=2))
