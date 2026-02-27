#!/usr/bin/env python3
"""Check availability of CLI tools for wicked-scenarios.

Usage:
    python3 cli_discovery.py              # Check all MVP tools
    python3 cli_discovery.py curl hurl    # Check specific tools
    python3 cli_discovery.py --summary    # One-line summary
    python3 cli_discovery.py --install    # Show grouped install commands for missing tools
"""
import json
import platform
import shutil
import sys

MVP_TOOLS = {
    "curl": {
        "install_brew": "pre-installed on most systems",
        "install_apt": "pre-installed on most systems",
        "install_npm": None,
        "category": "api",
    },
    "hurl": {
        "install_brew": "brew install hurl",
        "install_apt": "curl --location --remote-name https://github.com/Orange-OpenSource/hurl/releases/latest/download/hurl_amd64.deb && sudo dpkg -i hurl_amd64.deb && rm hurl_amd64.deb",
        "install_npm": None,
        "category": "api",
    },
    "playwright": {
        "install_brew": None,
        "install_apt": None,
        "install_npm": "npm i -D @playwright/test && npx playwright install",
        "category": "browser",
    },
    "agent-browser": {
        "install_brew": None,
        "install_apt": None,
        "install_npm": "npm i -g agent-browser",
        "category": "browser",
    },
    "k6": {
        "install_brew": "brew install k6",
        "install_apt": "sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D68 && echo 'deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main' | sudo tee /etc/apt/sources.list.d/k6.list && sudo apt-get update && sudo apt-get install k6",
        "install_npm": None,
        "category": "perf",
    },
    "hey": {
        "install_brew": "brew install hey",
        "install_apt": "sudo apt-get install -y hey",
        "install_npm": None,
        "category": "perf",
    },
    "trivy": {
        "install_brew": "brew install trivy",
        "install_apt": "sudo apt-get install -y wget apt-transport-https gnupg lsb-release && wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add - && echo deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main | sudo tee -a /etc/apt/sources.list.d/trivy.list && sudo apt-get update && sudo apt-get install -y trivy",
        "install_npm": None,
        "category": "infra",
    },
    "semgrep": {
        "install_brew": "brew install semgrep",
        "install_apt": None,
        "install_npm": None,
        "install_pip": "pip install semgrep",
        "category": "security",
    },
    "pa11y": {
        "install_brew": None,
        "install_apt": None,
        "install_npm": "npm i -g pa11y",
        "category": "a11y",
    },
}


def _detect_platform():
    """Detect package manager preference based on platform."""
    system = platform.system().lower()
    if system == "darwin":
        return "brew"
    if system == "linux":
        if shutil.which("apt-get"):
            return "apt"
        if shutil.which("brew"):
            return "brew"
        return "apt"
    return "brew"


def _best_install(tool_name, pkg_manager=None):
    """Return the best install command for a tool on this platform."""
    info = MVP_TOOLS.get(tool_name, {})
    pm = pkg_manager or _detect_platform()

    # Try platform-native first, then fallback chain
    candidates = [
        info.get(f"install_{pm}"),
        info.get("install_npm"),
        info.get("install_pip"),
        info.get("install_brew"),
        info.get("install_apt"),
    ]
    for cmd in candidates:
        if cmd and cmd != "pre-installed on most systems":
            return cmd
    return None


def check_tools(tools=None):
    """Check availability of specified tools (or all MVP tools)."""
    results = {}
    check = tools or list(MVP_TOOLS.keys())
    pm = _detect_platform()
    for tool in check:
        path = shutil.which(tool)
        install_cmd = _best_install(tool, pm)
        info = MVP_TOOLS.get(tool, {})
        results[tool] = {
            "available": path is not None,
            "path": path,
            "install": install_cmd or "see docs",
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


def install_commands(results):
    """Return grouped install commands for missing tools."""
    missing = {name: r for name, r in results.items() if not r["available"]}
    if not missing:
        return {"missing": 0, "tools": [], "groups": {}, "platform": _detect_platform()}

    # Group by package manager type
    brew_cmds = []
    npm_cmds = []
    pip_cmds = []
    other_cmds = []

    for name, r in missing.items():
        cmd = r.get("install", "")
        if not cmd or cmd == "see docs":
            continue
        if cmd.startswith("brew "):
            brew_cmds.append(cmd)
        elif cmd.startswith("npm "):
            npm_cmds.append(cmd)
        elif cmd.startswith("pip "):
            pip_cmds.append(cmd)
        else:
            other_cmds.append(cmd)

    # Merge brew installs into single command (deduplicated)
    brew_packages = []
    for cmd in brew_cmds:
        brew_packages.extend(cmd.replace("brew install ", "").split())
    brew_packages = list(dict.fromkeys(brew_packages))
    merged_brew = f"brew install {' '.join(brew_packages)}" if brew_packages else None

    # All groups use uniform list[str] type
    groups = {}
    if merged_brew:
        groups["brew"] = [merged_brew]
    if npm_cmds:
        groups["npm"] = npm_cmds
    if pip_cmds:
        groups["pip"] = pip_cmds
    if other_cmds:
        groups["other"] = other_cmds

    return {
        "missing": len(missing),
        "tools": list(missing.keys()),
        "groups": groups,
        "platform": _detect_platform(),
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    tools = args if args else None
    results = check_tools(tools)

    if "--summary" in flags:
        print(summary(results))
    elif "--install" in flags:
        print(json.dumps(install_commands(results), indent=2))
    else:
        print(json.dumps(results, indent=2))
